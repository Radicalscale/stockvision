import os
import sys
import time
import json
import subprocess
import schedule
import pandas as pd
from datetime import datetime

# --- CONFIGURATION ---
try:
    with open("config.json", "r") as f:
        config = json.load(f)
except FileNotFoundError:
    config = {}

# Default to yfinance, allow switching to alpha_vantage
DATA_PROVIDER = config.get("DATA_PROVIDER", "yfinance").lower()
ALPHA_VANTAGE_KEY = config.get("ALPHA_VANTAGE_KEY", "")

RAW_DIR = "TrainingData/indicators_data/raw/stocksData"
PROCESSED_DIR = "TrainingData/indicators_data/processed/stocksData"
FORECAST_DIR = "forecasts"

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)
os.makedirs(FORECAST_DIR, exist_ok=True)

def load_tickers():
    with open('TrainingData/stockList.csv', 'r') as file:
        tickers = [line.strip() for line in file if line.strip()]
    return tickers

def fetch_data_yfinance(tickers):
    import yfinance as yf
    print(f"[yfinance] Fetching data for {len(tickers)} tickers...")
    
    # Download 1 year of data for all tickers efficiently
    # group_by='ticker' ensures we can iterate through the top level columns easily
    df = yf.download(tickers, period="2y", group_by="ticker", auto_adjust=False, threads=True)
    
    for ticker in tickers:
        try:
            # yfinance uses '-' instead of '/' for tickers like BRK/B -> BRK-B
            yf_ticker = ticker.replace('/', '-')
            
            if len(tickers) == 1:
                ticker_df = df.copy()
            else:
                if yf_ticker not in df.columns.levels[0]:
                    print(f"[yfinance] Skipping {ticker} (no data found or delisted)")
                    continue
                ticker_df = df[yf_ticker].copy()
                
            ticker_df = ticker_df.dropna(how='all')
            if ticker_df.empty:
                print(f"[yfinance] Skipping {ticker} (empty dataframe returned)")
                continue
                
            # yfinance returns capitalized columns: Open, High, Low, Close, Volume
            ticker_df = ticker_df[['Open', 'High', 'Low', 'Close', 'Volume']]
            ticker_df.columns = ['open', 'high', 'low', 'close', 'volume']
            ticker_df.index.name = 'date'
            
            # Reset index to make 'date' a column
            ticker_df = ticker_df.reset_index()
            # yfinance date might be tz-aware, make it tz-naive for consistency
            if ticker_df['date'].dt.tz is not None:
                ticker_df['date'] = ticker_df['date'].dt.tz_localize(None)
                
            filepath = os.path.join(RAW_DIR, f"{ticker}_daily.csv")
            ticker_df.to_csv(filepath, index=False)
            
        except Exception as e:
            print(f"[yfinance] Error saving {ticker}: {e}")
            
    print("[yfinance] Data fetching complete.")

def fetch_data_alpha_vantage(tickers):
    print("[Alpha Vantage] Using existing stockScrapper.py for Alpha Vantage data...")
    # The existing script handles loading from config and fetching for all tickers
    subprocess.run([sys.executable, "TrainingData/featuresPy/stockScrapper.py"])

def run_feature_processing():
    print("\n--- Running Feature Processing ---")
    subprocess.run([sys.executable, "TrainingData/processor.py"])
    print("--- Feature Processing Complete ---\n")

def run_predictions():
    print("\n--- Running AI Predictions ---")
    subprocess.run([sys.executable, "run_forecast_v4.py"])
    print("--- AI Predictions Complete ---\n")

def pipeline_job():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting Pipeline Run...")
    tickers = load_tickers()
    
    if DATA_PROVIDER == "yfinance":
        fetch_data_yfinance(tickers)
    elif DATA_PROVIDER == "alpha_vantage":
        fetch_data_alpha_vantage(tickers)
    else:
        print(f"Unknown data provider: {DATA_PROVIDER}. Check config.json.")
        return
        
    run_feature_processing()
    run_predictions()
    
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Pipeline Run Finished.")

def main():
    print("===========================================")
    print("      LSTM AI Local Stock Pipeline         ")
    print(f"      Data Provider: {DATA_PROVIDER}     ")
    print("===========================================")
    
    # Run once immediately on startup
    pipeline_job()
    
    # Schedule to run every 30 minutes
    print("\nScheduling next job in 30 minutes...")
    schedule.every(30).minutes.do(pipeline_job)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    main()
