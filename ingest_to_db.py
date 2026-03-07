"""
Script to ingest the existing CSV data (processed indicators, raw OHLCV, and trade signals)
into the SQLite database. This can be run as a standalone script to perform an initial data load,
or called at the end of the AI pipeline to update the database with the latest day's data.
"""
import sqlite3
import pandas as pd
import os
import glob
import json

BASE_DIR          = os.path.dirname(__file__)
DATA_DIR          = os.path.join(BASE_DIR, "TrainingData", "indicators_data", "processed", "stocksData")
RAW_DIR           = os.path.join(BASE_DIR, "TrainingData", "indicators_data", "raw", "stocksData")
TRADE_SUMMARY     = os.path.join(BASE_DIR, "trade_summary_prob_strategy.csv")
DB_PATH           = os.path.join(BASE_DIR, "stock_data.db")
NAMES_FILE        = os.path.join(BASE_DIR, "stockvision-deploy", "company_names.json")

def get_db_connection():
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        # Handle Railway's potentially different connection string formats
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(db_url)
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def is_pg(conn):
    return not isinstance(conn, sqlite3.Connection)

def ingest_company_names(conn):
    """Load cached company names from JSON into the tickers table."""
    print("--- Ingesting Company Names ---")
    if not os.path.exists(NAMES_FILE):
        print(f"Company names file not found at {NAMES_FILE}")
        return

    try:
        with open(NAMES_FILE, 'r') as f:
            names_dict = json.load(f)
            
        cursor = conn.cursor()
        
        for ticker, name in names_dict.items():
            if is_pg(conn):
                cursor.execute(
                    "INSERT INTO tickers (ticker, company_name) VALUES (%s, %s) ON CONFLICT (ticker) DO UPDATE SET company_name = EXCLUDED.company_name",
                    (ticker, name)
                )
            else:
                cursor.execute(
                    "INSERT OR REPLACE INTO tickers (ticker, company_name) VALUES (?, ?)",
                    (ticker, name)
                )
            
        conn.commit()
        print(f"[OK] Ingested {len(names_dict)} company names.")
        
    except Exception as e:
        print(f"Error ingesting company names: {e}")

def ingest_stock_data(conn):
    """Read processed and raw CSVs, merge, and insert into daily_stock_data table."""
    print("\n--- Ingesting Daily Stock Data ---")
    processed_files = glob.glob(os.path.join(DATA_DIR, "*_daily_processed.csv"))
    print(f"Found {len(processed_files)} processed files to ingest.")
    
    total_rows = 0
    
    for filepath in processed_files:
        basename = os.path.basename(filepath)
        ticker = basename.replace("_daily_processed.csv", "")
        
        try:
            # Read processed data (indicators, close price)
            df = pd.read_csv(filepath)
            if df.empty or "date" not in df.columns or "close" not in df.columns:
                continue
                
            # Need to merge raw data to get Open, High, Low, Volume
            raw_ticker = ticker.replace("/", "-")
            raw_path = os.path.join(RAW_DIR, f"{raw_ticker}_daily.csv")
            
            if os.path.exists(raw_path):
                raw = pd.read_csv(raw_path)
                # Ensure column names map correctly
                raw = raw.rename(columns={c: c.lower() for c in raw.columns})
                ohi_cols = [c for c in ["open", "high", "low", "volume"] if c in raw.columns]
                
                if ohi_cols and "date" in raw.columns:
                    raw = raw[["date"] + ohi_cols].drop_duplicates("date")
                    df = df.merge(raw, on="date", how="left")
            else:
                # If raw doesn't exist, fill with None/NaN which becomes NULL in DB
                for col in ["open", "high", "low", "volume"]:
                     if col not in df.columns:
                         df[col] = None

            # Select only the columns we want for the database
            cols_to_keep = [
                "date", "close", "open", "high", "low", "volume",
                "MA10", "MA20", "MA30", "RSI", "MACD", "MACD_Signal",
                "BollingerUpper", "BollingerLower", "EMA10", "EMA30",
                "OBV", "ZScore", "Volatility_10", "Volatility_20"
            ]
            
            # Ensure all columns exist, fill missing with None
            for col in cols_to_keep:
                if col not in df.columns:
                    df[col] = None
                    
            db_df = df[cols_to_keep].copy()
            
            # Format date as string YYYY-MM-DD for SQLite
            db_df["date"] = pd.to_datetime(db_df["date"]).dt.strftime("%Y-%m-%d")
            db_df["ticker"] = ticker
            
            # Rename for DataFrame.to_sql
            # Write to database
            if is_pg(conn):
                # Use psycopg2 batch insert or efficient multi-row INSERT
                # For simplicity and consistency with migrate script:
                from psycopg2.extras import execute_values
                cursor = conn.cursor()
                cursor.execute("DELETE FROM daily_stock_data WHERE ticker = %s", (ticker,))
                
                # Convert DataFrame to list of tuples
                args = [tuple(x) for x in db_df.to_numpy()]
                cols = ",".join(db_df.columns)
                execute_values(cursor, f"INSERT INTO daily_stock_data ({cols}) VALUES %s ON CONFLICT (ticker, date) DO NOTHING", args)
            else:
                # SQLite logic
                conn.execute("DELETE FROM daily_stock_data WHERE ticker = ?", (ticker,))
                db_df.to_sql("daily_stock_data", conn, if_exists="append", index=False)
            
            # Also ensure ticker exists in tickers table if it wasn't caught by the names JSON
            conn.execute(
                "INSERT OR IGNORE INTO tickers (ticker, company_name) VALUES (?, ?)", 
                (ticker, ticker)
            )
            
            total_rows += len(db_df)
            
        except Exception as e:
            print(f"Error ingesting {ticker}: {e}")

    conn.commit()
    print(f"[OK] Ingested {total_rows} total rows of daily stock data.")


def ingest_trade_signals(conn):
    """Read the trade summary CSV and insert into the trade_signals table."""
    print("\n--- Ingesting Trade Signals ---")
    if not os.path.exists(TRADE_SUMMARY):
        print(f"Trade summary file not found at {TRADE_SUMMARY}")
        return
        
    try:
        # 1. Load historical backtest signals
        df = pd.read_csv(TRADE_SUMMARY)
        if df.empty:
            print("Trade summary file is empty.")
            df = pd.DataFrame()
        else:
            # Clean up column names to match DB
            df = df.rename(columns={
                "Ticker": "ticker",
                "BuyDate": "buy_date",
                "SellDate": "sell_date",
                "Horizon": "horizon",
                "DaysHeld": "days_held",
                "Pred_Prob": "pred_prob",
                "Adj_Prob": "adj_prob",
                "Actual_Return%": "actual_return"
            })
            df["ticker"] = df["ticker"].str.replace(r"_daily_processed$", "", regex=True)

        # 2. Extract LIVE predictions from forecasts/ directory
        # These are predictions that have no realized return yet
        print("Scanning forecasts for live signals...")
        forecast_files = glob.glob(os.path.join(BASE_DIR, "forecasts", "*_forecast.csv"))
        live_signals = []
        
        # We only want the LATEST prediction for each ticker if it's strong enough
        PROB_THRESHOLD = 0.5 
        
        for fpath in forecast_files:
            try:
                fdf = pd.read_csv(fpath)
                if fdf.empty: continue
                
                ticker = os.path.basename(fpath).replace("_daily_processed_forecast.csv", "")
                latest_row = fdf.iloc[-1]
                buy_date = latest_row["Date"]
                
                # AI EXPERT ADVICE LOGIC:
                # We always want the LATEST prediction to provide advice (e.g., "Wait" or "Not the right time")
                # Even if it's below the PROB_THRESHOLD for a "Buy" signal.
                
                # Check all horizons
                for h in ["1d", "1w", "1m", "6m"]:
                    prob = latest_row.get(f"Pred_Prob_{h}", 0)
                    
                    # We store it if it's either high confidence (Buy) 
                    # OR if it's the latest prediction (to provide advice)
                    if prob >= PROB_THRESHOLD or True: # Always True now to ensure we have data for advice
                        live_signals.append({
                            "ticker": ticker,
                            "buy_date": buy_date,
                            "sell_date": None,
                            "horizon": h,
                            "days_held": None,
                            "pred_prob": prob,
                            "adj_prob": prob, 
                            "actual_return": None
                        })
            except Exception as e:
                print(f"Error reading forecast {fpath}: {e}")

        if live_signals:
            live_df = pd.DataFrame(live_signals)
            if df.empty:
                df = live_df
            else:
                # Merge and Drop Duplicates (preferring backtest data if overlap exists)
                df = pd.concat([df, live_df], ignore_index=True)
                df = df.drop_duplicates(subset=["ticker", "buy_date", "horizon"], keep='first')

        if df.empty:
            print("No signals found (historical or live).")
            return

        # Format dates
        df["buy_date"] = pd.to_datetime(df["buy_date"], errors='coerce').dt.strftime("%Y-%m-%d")
        df["sell_date"] = pd.to_datetime(df["sell_date"], errors='coerce').dt.strftime("%Y-%m-%d")
        
        # Filter rows where buy_date or horizon is null as they make up the primary key
        df = df.dropna(subset=["ticker", "buy_date", "horizon"])
        
        # Convert types safely
        df["days_held"] = pd.to_numeric(df["days_held"], errors='coerce').fillna(1).astype(int)
        df["pred_prob"] = pd.to_numeric(df["pred_prob"], errors='coerce')
        df["adj_prob"] = pd.to_numeric(df["adj_prob"], errors='coerce')
        df["actual_return"] = pd.to_numeric(df["actual_return"], errors='coerce')

        cols_to_keep = [
            "ticker", "buy_date", "sell_date", "horizon", 
            "days_held", "pred_prob", "adj_prob", "actual_return"
        ]
        db_df = df[cols_to_keep]
        
        if is_pg(conn):
            from psycopg2.extras import execute_values
            cursor = conn.cursor()
            cursor.execute("DELETE FROM trade_signals")
            cols = ",".join(db_df.columns)
            args = [tuple(x) for x in db_df.to_numpy()]
            execute_values(cursor, f"INSERT INTO trade_signals ({cols}) VALUES %s ON CONFLICT (ticker, buy_date, horizon) DO NOTHING", args)
        else:
            # Delete existing to prevent PK violations on re-run
            conn.execute("DELETE FROM trade_signals")
            # Insert
            db_df.to_sql("trade_signals", conn, if_exists="append", index=False)
        conn.commit()
        
        print(f"[OK] Ingested {len(db_df)} total trade signals (Historical + Live).")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error ingesting trade signals: {e}")

def run_full_ingestion():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}. Please run init_db.py first.")
        return
        
    conn = get_db_connection()
    try:
        ingest_company_names(conn)
        ingest_stock_data(conn)
        ingest_trade_signals(conn)
        print("\n--- Ingestion Complete ---")
    finally:
        conn.close()

if __name__ == "__main__":
    run_full_ingestion()
