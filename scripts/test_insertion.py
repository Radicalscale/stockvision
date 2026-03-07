
import psycopg2
PG_URL = "postgresql://postgres:YrbvdRNdBHXOXWCqnakpxLXqbvsnBAZF@shortline.proxy.rlwy.net:20771/railway"
try:
    print("Connecting...")
    conn = psycopg2.connect(PG_URL)
    cur = conn.cursor()
    print("Inserting one ticker...")
    cur.execute("INSERT INTO tickers (ticker, company_name) VALUES ('TEST', 'Test Company') ON CONFLICT DO NOTHING")
    conn.commit()
    print("Commit successful.")
    cur.execute("SELECT ticker FROM tickers WHERE ticker='TEST'")
    print(f"Retrieved: {cur.fetchone()}")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
