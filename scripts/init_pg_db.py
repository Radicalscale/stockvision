
import os
import psycopg2

DATABASE_URL = "postgresql://postgres:YrbvdRNdBHXOXWCqnakpxLXqbvsnBAZF@shortline.proxy.rlwy.net:20771/railway"

def init_pg():
    print("Initializing PostgreSQL database on Railway...")
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # 1. Tickers Table
        print("Creating 'tickers' table...")
        cur.execute('''
        CREATE TABLE IF NOT EXISTS tickers (
            ticker TEXT PRIMARY KEY,
            company_name TEXT
        )
        ''')

        # 2. Daily Stock Data Table
        print("Creating 'daily_stock_data' table...")
        cur.execute('''
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

        # 3. Trade Signals / Predictions Table
        print("Creating 'trade_signals' table...")
        cur.execute('''
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

        # 4. Users Table
        print("Creating 'users' table...")
        cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Create indexes
        print("Creating indexes...")
        cur.execute('CREATE INDEX IF NOT EXISTS idx_stock_data_ticker_date ON daily_stock_data(ticker, date DESC);')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_trade_signals_ticker_date ON trade_signals(ticker, buy_date DESC);')

        conn.commit()
        cur.close()
        conn.close()
        print("PostgreSQL initialization complete.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    init_pg()
