
import sqlite3
import psycopg2
import psycopg2.extras
import os
import time

SQLITE_DB = os.path.join(os.path.dirname(__file__), "..", "stock_data.db")
PG_URL = "postgresql://postgres:YrbvdRNdBHXOXWCqnakpxLXqbvsnBAZF@shortline.proxy.rlwy.net:20771/railway"

def get_pg_conn():
    while True:
        try:
            conn = psycopg2.connect(PG_URL)
            return conn
        except Exception as e:
            print(f"\n  PostgreSQL Connection failed: {e}. Retrying in 5s...", flush=True)
            time.sleep(5)

def migrate():
    print(f"Connecting to local SQLite: {SQLITE_DB}", flush=True)
    if not os.path.exists(SQLITE_DB):
        print("SQLite database not found. Skipping migration.", flush=True)
        return

    lite_conn = sqlite3.connect(SQLITE_DB)
    lite_conn.row_factory = sqlite3.Row
    lite_cur = lite_conn.cursor()

    print("Connecting to remote PostgreSQL...", flush=True)
    pg_conn = get_pg_conn()
    pg_cur = pg_conn.cursor()

    # 1. Migrate Tickers
    print("Migrating 'tickers' table...", flush=True)
    lite_cur.execute("SELECT * FROM tickers")
    rows = lite_cur.fetchall()
    for row in rows:
        while True:
            try:
                pg_cur.execute(
                    "INSERT INTO tickers (ticker, company_name) VALUES (%s, %s) ON CONFLICT (ticker) DO NOTHING",
                    (row['ticker'], row['company_name'])
                )
                break
            except (psycopg2.OperationalError, psycopg2.InterfaceError):
                pg_conn = get_pg_conn()
                pg_cur = pg_conn.cursor()
    pg_conn.commit()
    print(f"  Done: {len(rows)} tickers", flush=True)

    # 2. Migrate Users
    print("Migrating 'users' table...", flush=True)
    try:
        lite_cur.execute("SELECT * FROM users")
        rows = lite_cur.fetchall()
        for row in rows:
            while True:
                try:
                    pg_cur.execute(
                        "INSERT INTO users (email, password_hash, created_at) VALUES (%s, %s, %s) ON CONFLICT (email) DO NOTHING",
                        (row['email'], row['password_hash'], row['created_at'])
                    )
                    break
                except (psycopg2.OperationalError, psycopg2.InterfaceError):
                    pg_conn = get_pg_conn()
                    pg_cur = pg_conn.cursor()
        pg_conn.commit()
        print(f"  Done: {len(rows)} users", flush=True)
    except sqlite3.OperationalError:
        print("  Table 'users' not found in SQLite (fresh install). Skipping.", flush=True)

    # 3. Migrate Trade Signals
    print("Migrating 'trade_signals' table...", flush=True)
    lite_cur.execute("SELECT count(*) FROM trade_signals")
    total_signals = lite_cur.fetchone()[0]
    
    lite_cur.execute("SELECT * FROM trade_signals")
    count = 0
    while True:
        chunk = lite_cur.fetchmany(1000)
        if not chunk: break
        while True:
            try:
                for r in chunk:
                    pg_cur.execute("""
                        INSERT INTO trade_signals (ticker, buy_date, sell_date, horizon, days_held, pred_prob, adj_prob, actual_return)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (ticker, buy_date, horizon) DO NOTHING
                    """, (r['ticker'], r['buy_date'], r['sell_date'], r['horizon'], r['days_held'], r['pred_prob'], r['adj_prob'], r['actual_return']))
                pg_conn.commit()
                break
            except (psycopg2.OperationalError, psycopg2.InterfaceError):
                pg_conn = get_pg_conn()
                pg_cur = pg_conn.cursor()
        count += len(chunk)
        print(f"  Progress: {count}/{total_signals} signals...", end="\r", flush=True)
    print(f"\n  Done: {count} signals", flush=True)

    # 4. Migrate Daily Stock Data (Large)
    print("Migrating 'daily_stock_data' (1.9GB) ... This may take a while.", flush=True)
    lite_cur.execute("SELECT count(*) FROM daily_stock_data")
    total_rows = lite_cur.fetchone()[0]
    print(f"  Total records to migrate: {total_rows}", flush=True)

    lite_cur.execute("SELECT * FROM daily_stock_data")
    count = 0
    start_time = time.time()
    batch_size = 2000
    
    while True:
        chunk = lite_cur.fetchmany(batch_size)
        if not chunk: break
        
        # Prepare batch insert
        args = []
        for r in chunk:
            args.append((
                r['ticker'], r['date'], r['close'], r['open'], r['high'], r['low'], r['volume'],
                r['MA10'], r['MA20'], r['MA30'], r['RSI'], r['MACD'], r['MACD_Signal'],
                r['BollingerUpper'], r['BollingerLower'], r['EMA10'], r['EMA30'], r['OBV'],
                r['ZScore'], r['Volatility_10'], r['Volatility_20']
            ))
        
        while True:
            try:
                psycopg2.extras.execute_values(pg_cur, """
                    INSERT INTO daily_stock_data (
                        ticker, date, close, open, high, low, volume, 
                        MA10, MA20, MA30, RSI, MACD, MACD_Signal, 
                        BollingerUpper, BollingerLower, EMA10, EMA30, OBV, 
                        ZScore, Volatility_10, Volatility_20
                    ) VALUES %s ON CONFLICT (ticker, date) DO NOTHING
                """, args)
                pg_conn.commit()
                break
            except (psycopg2.OperationalError, psycopg2.InterfaceError):
                pg_conn = get_pg_conn()
                pg_cur = pg_conn.cursor()
        
        count += len(chunk)
        
        if count % 10000 == 0 or count == total_rows:
            elapsed = time.time() - start_time
            rate = count / elapsed if elapsed > 0 else 0
            eta = (total_rows - count) / rate if rate > 0 else 0
            print(f"  Progress: {count}/{total_rows} ({ (count/total_rows)*100:.1f}%) | Rate: {rate:.1f} r/s | ETA: {eta/60:.1f}m    ", end="\r", flush=True)

    print(f"\n  Done: {count} daily records", flush=True)

    lite_conn.close()
    pg_conn.close()
    print("\nMigration successful!", flush=True)

if __name__ == "__main__":
    migrate()
