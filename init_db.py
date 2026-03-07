import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "stock_data.db")

def create_database():
    print(f"Initializing database at: {DB_PATH}")
    
    # Connect to the database (creates it if it doesn't exist)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Tickers Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tickers (
        ticker TEXT PRIMARY KEY,
        company_name TEXT
    )
    ''')
    print("[OK] Created 'tickers' table")

    # 2. Daily Stock Data Table
    # (Storing OHLCV and main indicators to power the charts)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS daily_stock_data (
        ticker TEXT,
        date DATE,
        close REAL,
        open REAL,
        high REAL,
        low REAL,
        volume REAL,
        MA10 REAL,
        MA20 REAL,
        MA30 REAL,
        RSI REAL,
        MACD REAL,
        MACD_Signal REAL,
        BollingerUpper REAL,
        BollingerLower REAL,
        EMA10 REAL,
        EMA30 REAL,
        OBV REAL,
        ZScore REAL,
        Volatility_10 REAL,
        Volatility_20 REAL,
        PRIMARY KEY (ticker, date),
        FOREIGN KEY (ticker) REFERENCES tickers(ticker)
    )
    ''')
    print("[OK] Created 'daily_stock_data' table")

    # 3. Trade Signals / Predictions Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS trade_signals (
        ticker TEXT,
        buy_date DATE,
        sell_date DATE,
        horizon TEXT,
        days_held INTEGER,
        pred_prob REAL,
        adj_prob REAL,
        actual_return REAL,
        PRIMARY KEY (ticker, buy_date, horizon),
        FOREIGN KEY (ticker) REFERENCES tickers(ticker)
    )
    ''')
    print("[OK] Created 'trade_signals' table")

    # Create indexes for faster querying
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_stock_data_ticker_date ON daily_stock_data(ticker, date DESC);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_trade_signals_ticker_date ON trade_signals(ticker, buy_date DESC);')
    print("[OK] Created performance indexes")

    # Commit changes and close
    conn.commit()
    conn.close()
    print("Database initialization complete.")

if __name__ == "__main__":
    create_database()
