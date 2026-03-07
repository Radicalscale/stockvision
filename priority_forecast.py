import numpy as np
import os
import pandas as pd
import run_forecast_v4
from run_forecast_v4 import process_stock_for_inference, horizons, make_forecast, MCDropout, Attention, CONFIG
from pathlib import Path
from tensorflow.keras.models import load_model
import tensorflow as tf

def priority_run():
    # 1. Tickers to prioritize
    priority = ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMD", "META", "AMZN"]
    
    # 2. First 50 from stockList
    try:
        with open('TrainingData/stockList.csv', 'r') as f:
            stock_list = [line.strip() for line in f if line.strip()][:50]
    except:
        stock_list = []
        
    all_to_run = list(set(priority + stock_list))
    
    # 3. Setup global feature_cols and scaler by sampling first 100 as in main()
    import run_forecast_v4
    all_csvs = sorted(list(CONFIG["DATA_DIR"].glob("*.csv")))
    scaler_inputs = []
    print("Fitting Scaler...")
    for csv_path in all_csvs[:100]:
        df = pd.read_csv(csv_path, parse_dates=["date"]).sort_values("date").dropna()
        df = run_forecast_v4.add_features(df, drop_nans=True)
        if df.empty: continue
        feat_cols = [c for c in df.columns if c not in CONFIG["EXCLUDED_COLS"]]
        if run_forecast_v4.feature_cols is None: run_forecast_v4.feature_cols = feat_cols
        scaler_inputs.append(df[run_forecast_v4.feature_cols].values)
    run_forecast_v4.scaler.fit(np.vstack(scaler_inputs))

    # 4. Load model
    print("Loading model...")
    model = load_model("lstm_model.h5", custom_objects={'MCDropout': MCDropout, 'Attention': Attention})
    
    # 5. Run Forecast
    print(f"Running forecast for {len(all_to_run)} priority stocks...")
    for ticker in all_to_run:
        csv_path = CONFIG["DATA_DIR"] / f"{ticker}_daily_processed.csv"
        if not csv_path.exists():
            print(f"Skipping {ticker}, file not found")
            continue
            
        try:
            X_all, closes, pred_dates, df = process_stock_for_inference(csv_path)
            if X_all.size == 0: continue
            
            forecast_df = make_forecast(model, X_all, pred_dates, closes, horizons)
            forecast_df.to_csv(CONFIG["FORECAST_DIR"] / f"{ticker}_daily_processed_forecast.csv", index=False)
            print(f"Updated: {ticker}")
        except Exception as e:
            print(f"Error on {ticker}: {e}")

if __name__ == "__main__":
    priority_run()
