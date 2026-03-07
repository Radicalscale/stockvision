
import os
import pandas as pd
from run_forecast_v4 import process_stock_for_inference, horizons, make_forecast, MCDropout, Attention
from pathlib import Path
from tensorflow.keras.models import load_model

def test_single():
    import run_forecast_v4
    
    # Simulate the setup in main()
    all_csvs = ["TrainingData/indicators_data/processed/stocksData/AAPL_daily_processed.csv"]
    csv_path = Path(all_csvs[0])
    
    # 1. Fit scaler and find feature_cols
    df = pd.read_csv(csv_path, parse_dates=["date"]).sort_values("date").dropna()
    df = run_forecast_v4.add_features(df, drop_nans=True)
    run_forecast_v4.feature_cols = [c for c in df.columns if c not in run_forecast_v4.CONFIG["EXCLUDED_COLS"]]
    run_forecast_v4.scaler.fit(df[run_forecast_v4.feature_cols].values)
    
    print(f"Features found: {len(run_forecast_v4.feature_cols)}")
    
    print("Loading model...")
    model = load_model("lstm_model.h5", custom_objects={'MCDropout': MCDropout, 'Attention': Attention})
    
    print("Processing AAPL for inference...")
    X_all, closes, pred_dates, df = process_stock_for_inference(csv_path)
    
    print(f"Number of samples for inference: {len(X_all)}")
    if len(X_all) > 0:
        print(f"Latest prediction date: {pred_dates[-1]}")
    
    forecast_df = make_forecast(model, X_all, pred_dates, closes, horizons)
    print("Final Forecast tail:")
    print(forecast_df.tail())

if __name__ == "__main__":
    test_single()
