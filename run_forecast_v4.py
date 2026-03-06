import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import Conv1D, LSTM, Dense, Dropout, BatchNormalization, Layer
from tensorflow.keras.callbacks import EarlyStopping
from sklearn.preprocessing import StandardScaler
from pathlib import Path
import glob
import os
import time

# Config
CONFIG = {
    "DATA_DIR": Path("TrainingData/indicators_data/processed/stocksData"),
    "FORECAST_DIR": Path("forecasts"),
    "CACHE_DIR": Path("cache"),
    "WINDOW_SIZE": 90,
    "TRAIN_VAL_FRAC": 0.8,
    "VAL_FRAC_WITHIN_TRAIN": 0.2,
    "MC_DROPOUT_SAMPLES": 25,
    "EXCLUDED_COLS": ["date", "Target_1d", "Target_1w", "Target_1m", "Target_6m"],
    "PROB_THRESHOLD": 0.7,
}

horizons = ["1d", "1w", "1m", "6m"]
horizon_days = [1, 5, 21, 126]

# Ensure dirs exist
CONFIG["FORECAST_DIR"].mkdir(exist_ok=True)
CONFIG["CACHE_DIR"].mkdir(exist_ok=True)

# Globals
scaler = StandardScaler()
feature_cols = None

class Attention(Layer):
    def __init__(self, **kwargs):
        super(Attention, self).__init__(**kwargs)

    def build(self, input_shape):
        self.W = self.add_weight(name="att_weight", shape=(input_shape[-1], 1),
                                 initializer="normal")
        self.b = self.add_weight(name="att_bias", shape=(input_shape[1], 1),
                                 initializer="zeros")        
        super().build(input_shape)

    def call(self, x):
        e = tf.keras.backend.tanh(tf.keras.backend.dot(x, self.W) + self.b)
        a = tf.keras.backend.softmax(e, axis=1)
        output = x * a
        return tf.keras.backend.sum(output, axis=1)

class MCDropout(Dropout):
    def call(self, inputs, training=None):
        return super().call(inputs, training=True)

def mc_dropout_predict(model, X, n_samples=50):
    # Process in smaller batches if X is very large to avoid memory issues
    batch_size = 128
    all_means = []
    all_stds = []
    
    for i in range(0, len(X), batch_size):
        X_batch = X[i:i+batch_size]
        preds = np.array([model(X_batch, training=True).numpy() for _ in range(n_samples)])
        all_means.append(preds.mean(axis=0))
        all_stds.append(preds.std(axis=0))
        
    return np.vstack(all_means), np.vstack(all_stds), None

def compute_horizon_thresholds(df):
    thresholds = {}
    for h in horizons:
        mu = df[f"Target_{h}"].mean()
        sig = df[f"Target_{h}"].std()
        thresholds[h] = mu + 2 * sig
    return thresholds

def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df["Target_1d"] = np.log(df["close"].shift(-1) / df["close"])
    df["Target_1w"] = np.log(df["close"].shift(-5) / df["close"])
    df["Target_1m"] = np.log(df["close"].shift(-21) / df["close"])
    df["Target_6m"] = np.log(df["close"].shift(-126) / df["close"])
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df.dropna(inplace=True)
    return df

def process_stock(csv_path: Path, for_training=True):
    df = pd.read_csv(csv_path, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    df = add_features(df)
    if df.empty:
        return np.array([]), np.array([]), df, np.array([])
        
    thresholds = compute_horizon_thresholds(df)
    for h in horizons:
        df[f"Class_{h}"] = (df[f"Target_{h}"] > thresholds[h]).astype(int)

    global feature_cols
    for col in feature_cols:
        if col not in df.columns:
            df[col] = 0.0

    features_scaled = scaler.transform(df[feature_cols].values).astype(np.float32)
    dates = df["date"].values
    target = df[["Class_1d", "Class_1w", "Class_1m", "Class_6m"]].values if for_training else None

    X, y, y_dates = [], [], []
    window = CONFIG["WINDOW_SIZE"]
    max_horizon = max(horizon_days)

    for i in range(window, len(features_scaled), max_horizon):
        X.append(features_scaled[i - window:i + 1])
        if for_training:
            y.append(target[i])
        y_dates.append(dates[i])

    return (
        np.array(X),
        np.array(y) if for_training else None,
        df,
        np.array(y_dates, dtype="datetime64[ns]"),
    )

def process_stock_for_inference(csv_path: Path):
    df = pd.read_csv(csv_path, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    df = add_features(df)
    if df.empty:
        return np.array([]), np.array([]), np.array([]), df

    global feature_cols
    for col in feature_cols:
        if col not in df.columns:
            df[col] = 0.0

    features_scaled = scaler.transform(df[feature_cols].values).astype(np.float32)
    dates = df["date"].values
    
    window = CONFIG["WINDOW_SIZE"]
    n_samples = len(features_scaled) - window
    
    if n_samples <= 0:
        return np.array([]), np.array([]), np.array([]), df

    # Memory-efficient sliding window creation
    X = np.zeros((n_samples, window + 1, len(feature_cols)), dtype=np.float32)
    for i in range(n_samples):
        X[i] = features_scaled[i : i + window + 1]
    
    x_dates = dates[window:]
    closes = df.loc[window:, "close"].values[:n_samples]

    return X, closes, np.array(x_dates, dtype="datetime64[ns]"), df

class StockDataGenerator(tf.keras.utils.Sequence):
    def __init__(self, csv_paths, batch_size=128, split="train", shuffle=True, use_time_weights=False, decay_factor=0.002):
        self.csv_paths = csv_paths
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.split = split
        self.use_time_weights = use_time_weights
        self.decay_factor = decay_factor
        self.windows = []
        self.stock_names = [Path(p).stem for p in csv_paths]
        self._prepare_indices()
        self.on_epoch_end()

    def _prepare_indices(self):
        self.windows = []
        for stock_name in self.stock_names:
            X_path = CONFIG["CACHE_DIR"] / f"{stock_name}_X_{self.split}.npy"
            if X_path.exists():
                X = np.load(X_path, mmap_mode="r")
                for i in range(len(X)):
                    self.windows.append((stock_name, i))
        self.indices = np.arange(len(self.windows))

    def __len__(self):
        return int(np.ceil(len(self.windows) / self.batch_size))

    def __getitem__(self, idx):
        batch_indices = self.indices[idx * self.batch_size:(idx + 1) * self.batch_size]
        X_batch, y_batch, weights_batch = [], [], []
        cache = {}
        for bi in batch_indices:
            stock_name, win_idx = self.windows[bi]
            if stock_name not in cache:
                X = np.load(CONFIG["CACHE_DIR"] / f"{stock_name}_X_{self.split}.npy", mmap_mode="r")
                y = np.load(CONFIG["CACHE_DIR"] / f"{stock_name}_y_{self.split}.npy", mmap_mode="r")
                cache[stock_name] = (X, y)
            X_arr, y_arr = cache[stock_name]
            X_batch.append(X_arr[win_idx])
            y_batch.append(y_arr[win_idx])
            weights_batch.append(1.0)
        return np.array(X_batch, dtype=np.float32), np.array(y_batch, dtype=np.float32), np.array(weights_batch, dtype=np.float32)

    def on_epoch_end(self):
        if self.shuffle:
            np.random.shuffle(self.indices)

def cache_preprocessed_stock(csv_path: Path, train_cutoff, train_val_cutoff):
    stock_name = csv_path.stem
    X, y, _, y_dates = process_stock(csv_path, for_training=True)
    if X.size == 0:
        return

    y_dates = pd.to_datetime(y_dates)
    splits = {
        "train": y_dates < np.datetime64(train_cutoff),
        "val": (y_dates >= np.datetime64(train_cutoff)) & (y_dates < np.datetime64(train_val_cutoff)),
    }
    for split, mask in splits.items():
        if np.any(mask):
            np.save(CONFIG["CACHE_DIR"] / f"{stock_name}_X_{split}.npy", X[mask].astype(np.float32))
            np.save(CONFIG["CACHE_DIR"] / f"{stock_name}_y_{split}.npy", y[mask].astype(np.float32))

def make_forecast(model, X, dates, closes, horizons):
    y_pred_mean, y_pred_std, _ = mc_dropout_predict(model, X, n_samples=CONFIG["MC_DROPOUT_SAMPLES"])
    df_dict = {"Date": dates, "Close": closes}
    for i, h in enumerate(horizons):
        df_dict[f"Pred_Prob_{h}"] = y_pred_mean[:, i]
        df_dict[f"Pred_Prob_Std_{h}"] = y_pred_std[:, i]
    return pd.DataFrame(df_dict)

def main():
    all_csvs = sorted(glob.glob(str(CONFIG["DATA_DIR"] / "*.csv")))
    print(f"Found {len(all_csvs)} stocks")

    # Fit scaler
    global_min_date, global_max_date = None, None
    scaler_inputs = []
    global feature_cols

    print("Determining global date range...")
    for csv_path in all_csvs:
        try:
            df_tmp = pd.read_csv(csv_path, parse_dates=["date"])
            if df_tmp.empty or "date" not in df_tmp.columns:
                continue
            
            # Fix for TypeError: handle potential NaN or non-datetime objects
            valid_dates = pd.to_datetime(df_tmp["date"], errors="coerce").dropna()
            if valid_dates.empty:
                continue
                
            current_min = valid_dates.min()
            current_max = valid_dates.max()
            
            if global_min_date is None or current_min < global_min_date:
                global_min_date = current_min
            if global_max_date is None or current_max > global_max_date:
                global_max_date = current_max
        except Exception as e:
            print(f"Error processing {csv_path}: {e}")
            continue

    if global_min_date is None:
        print("No valid data found.")
        return

    train_val_cutoff = global_min_date + (global_max_date - global_min_date) * CONFIG["TRAIN_VAL_FRAC"]
    train_cutoff = global_min_date + (train_val_cutoff - global_min_date) * (1 - CONFIG["VAL_FRAC_WITHIN_TRAIN"])

    print("Fitting scaler...")
    for csv_path in all_csvs[:100]: # Sample 100 for speed if needed, or all
        df = pd.read_csv(csv_path, parse_dates=["date"]).sort_values("date").dropna()
        df = add_features(df)
        if df.empty: continue
        feat_cols = [c for c in df.columns if c not in CONFIG["EXCLUDED_COLS"]]
        if feature_cols is None: feature_cols = feat_cols
        train_rows = df[df["date"] < train_cutoff]
        if len(train_rows) > 0:
            scaler_inputs.append(train_rows[feat_cols].values)
    
    if not scaler_inputs:
        print("Not enough training data to fit scaler.")
        return
        
    scaler.fit(np.vstack(scaler_inputs))

    # Cache
    print("Caching preprocessed data...")
    for csv_path in all_csvs:
        cache_preprocessed_stock(Path(csv_path), train_cutoff, train_val_cutoff)

    # Generators
    train_gen = StockDataGenerator(all_csvs, split="train", shuffle=True)
    val_gen = StockDataGenerator(all_csvs, split="val", shuffle=False)

    # Model
    model_path = "lstm_model.h5"
    if os.path.exists(model_path):
        print("Loading existing model...")
        model = load_model(model_path, custom_objects={'MCDropout': MCDropout, 'Attention': Attention})
    else:
        print("Training model...")
        n_features = len(feature_cols)
        model = Sequential([
            Conv1D(32, kernel_size=3, activation="relu", input_shape=(CONFIG["WINDOW_SIZE"] + 1, n_features)),
            BatchNormalization(),
            MCDropout(0.3),
            LSTM(64, return_sequences=False), 
            MCDropout(0.3),
            Dense(32, activation="relu"),
            Dense(4, activation="sigmoid")
        ])
        model.compile(optimizer="adam", loss="binary_crossentropy", metrics=[tf.keras.metrics.AUC(name="auc")])
        early_stop = EarlyStopping(patience=25, monitor="val_loss", restore_best_weights=True, mode="min")
        model.fit(train_gen, validation_data=val_gen, callbacks=[early_stop], epochs=50)
        model.save(model_path)

    # Forecast
    print("Generating forecasts...")
    for csv_path in all_csvs:
        stock_name = Path(csv_path).stem
        X_all, closes, pred_dates, df = process_stock_for_inference(Path(csv_path))
        if X_all.size == 0: continue
        
        forecast_df = make_forecast(model, X_all, pred_dates, closes, horizons)
        forecast_df.to_csv(CONFIG["FORECAST_DIR"] / f"{stock_name}_forecast.csv", index=False)
        print("Saved:", stock_name)

    print("Success!")

if __name__ == "__main__":
    main()
