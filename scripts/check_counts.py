
import sqlite3
import os

db = "stock_data.db"
if os.path.exists(db):
    conn = sqlite3.connect(db)
    print(f"Tickers: {conn.execute('SELECT count(*) FROM tickers').fetchone()[0]}")
    print(f"Signals: {conn.execute('SELECT count(*) FROM trade_signals').fetchone()[0]}")
    print(f"Daily:   {conn.execute('SELECT count(*) FROM daily_stock_data').fetchone()[0]}")
    conn.close()
else:
    print("DB not found")
