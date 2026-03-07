
import psycopg2
PG_URL = "postgresql://postgres:YrbvdRNdBHXOXWCqnakpxLXqbvsnBAZF@shortline.proxy.rlwy.net:20771/railway"
try:
    conn = psycopg2.connect(PG_URL)
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM tickers")
    print(f"Connection OK. Tickers in PG: {cur.fetchone()[0]}")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
