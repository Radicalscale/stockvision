"""
Stock Dashboard Flask API
Serves stock data from the local SQLite database as a REST API.
"""
import os
import sqlite3
import psycopg2
import psycopg2.extras
from flask import Flask, jsonify, request, send_from_directory, make_response, session, redirect, url_for
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import datetime

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = "super-secret-key-change-this-in-production" # Secure session key
app.permanent_session_lifetime = datetime.timedelta(hours=8)  # Sessions expire after 8 hours
CORS(app)

BASE_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(BASE_DIR, "..", "stock_data.db")

import functools

def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function

class PgConnWrapper:
    """Compatibility wrapper to make PostgreSQL connection behave like SQLite connection for simple execute calls."""
    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        # Convert ? to %s for PostgreSQL
        sql = sql.replace('?', '%s')
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute(sql, params)
        return cur

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

def is_pg(conn):
    """Check if the connection is a PostgreSQL connection."""
    return isinstance(conn, PgConnWrapper) or not isinstance(conn, sqlite3.Connection)

def get_db_connection():
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        # Handle Railway's potentially different connection string formats
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        conn = psycopg2.connect(db_url)
        return PgConnWrapper(conn)
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def init_auth_db():
    """Create users table if it doesn't exist. Designed to be portable to PostgreSQL."""
    conn = get_db_connection()
    if is_pg(conn):
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    else:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    conn.commit()
    conn.close()

# Initialize DB on start
init_auth_db()

# ── ROUTES ───────────────────────────────────────────────────────────────────

@app.route("/api/tickers")
@login_required
def list_tickers():
    try:
        conn = get_db_connection()
        tickers_rows = conn.execute("SELECT ticker, company_name FROM tickers ORDER BY ticker ASC").fetchall()
        conn.close()
        
        result = [{"ticker": row["ticker"], "name": row["company_name"]} for row in tickers_rows]
        return jsonify({"tickers": result, "count": len(result)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/stock/<ticker>")
@login_required
def get_stock_data(ticker):
    ticker = ticker.upper().replace("-", "/")
    
    period = request.args.get("period", "2y")
    period_map = {"1m": 30, "3m": 90, "6m": 180, "1y": 252, "2y": 504, "5y": 1260}
    limit = period_map.get(period, 504)

    try:
        conn = get_db_connection()
        
        # Get company name
        name_row = conn.execute("SELECT company_name FROM tickers WHERE ticker = ?", (ticker,)).fetchone()
        company_name = name_row["company_name"] if name_row else ticker
        
        # Get historical data (ordered desc to get latest, but we need asc for charts, so we subquery)
        data_query = f"""
            SELECT * FROM (
                SELECT * FROM daily_stock_data 
                WHERE ticker = ? 
                ORDER BY date DESC 
                LIMIT ?
            ) ORDER BY date ASC
        """
        rows = conn.execute(data_query, (ticker, limit)).fetchall()
        
        if not rows:
            conn.close()
            return jsonify({"error": f"Ticker {ticker} not found or has no data"}), 404

        # Calculate stats from the whole year (last 252 days)
        stats_query = """
            SELECT 
                MAX(close) as week52_high,
                MIN(close) as week52_low,
                AVG(volume) as avg_volume
            FROM (
                SELECT close, volume FROM daily_stock_data 
                WHERE ticker = ? 
                ORDER BY date DESC 
                LIMIT 252
            )
        """
        stats_row = conn.execute(stats_query, (ticker,)).fetchone()
        conn.close()
        
        # Format the response to match the old API
        candles = []
        indicators_data = {
            "MA10": [], "MA20": [], "MA30": [], "RSI": [], "MACD": [], "MACD_Signal": [],
            "BollingerUpper": [], "BollingerLower": [], "EMA10": [], "EMA30": [],
            "OBV": [], "ZScore": [], "Volatility_10": [], "Volatility_20": []
        }
        dates = []
        
        for row in rows:
            dates.append(row["date"])
            candles.append({
                "date": row["date"],
                "open": round(float(row["open"]), 4) if row["open"] is not None else None,
                "high": round(float(row["high"]), 4) if row["high"] is not None else None,
                "low": round(float(row["low"]), 4) if row["low"] is not None else None,
                "close": round(float(row["close"]), 4) if row["close"] is not None else None,
                "volume": round(float(row["volume"]), 4) if row["volume"] is not None else None
            })
            
            for ind in indicators_data.keys():
                val = row[ind]
                indicators_data[ind].append(round(float(val), 4) if val is not None else None)

        latest = rows[-1]
        prev = rows[-2] if len(rows) > 1 else latest
        latest_close = float(latest["close"]) if latest["close"] else 0
        prev_close = float(prev["close"]) if prev["close"] else 0
        change = latest_close - prev_close
        change_pct = (change / prev_close * 100) if prev_close != 0 else 0

        return jsonify({
            "ticker": ticker,
            "name": company_name,
            "latest_close": round(latest_close, 4),
            "change": round(change, 4),
            "change_pct": round(change_pct, 4),
            "week52_high": round(float(stats_row["week52_high"] or 0), 4),
            "week52_low": round(float(stats_row["week52_low"] or 0), 4),
            "avg_volume": round(float(stats_row["avg_volume"] or 0), 0),
            "data_points": len(rows),
            "dates": dates,
            "candles": candles,
            "indicators": indicators_data,
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/search")
@login_required
def search_tickers():
    """Search by ticker symbol OR company name."""
    q = request.args.get("q", "").strip().upper()
    
    try:
        conn = get_db_connection()
        
        if not q:
            rows = conn.execute("SELECT ticker, company_name FROM tickers LIMIT 50").fetchall()
        else:
            # Match exact first, then starts with, then contains
            query = """
                SELECT ticker, company_name,
                    CASE 
                        WHEN ticker = ? THEN 1
                        WHEN ticker LIKE ? THEN 2
                        WHEN company_name LIKE ? THEN 3
                        ELSE 4
                    END as match_score
                FROM tickers
                WHERE ticker LIKE ? OR company_name LIKE ?
                ORDER BY match_score ASC, ticker ASC
                LIMIT 60
            """
            search_starts = f"{q}%"
            search_contains = f"%{q}%"
            rows = conn.execute(query, (q, search_starts, search_contains, search_contains, search_contains)).fetchall()
            
        conn.close()
        
        results = [{"ticker": row["ticker"], "name": row["company_name"]} for row in rows]
        return jsonify({"results": results})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/predictions/<ticker>")
@login_required
def get_predictions(ticker):
    try:
        conn = get_db_connection()
        
        # Get past 50 signals
        query = """
            SELECT * FROM trade_signals 
            WHERE ticker = ? 
            ORDER BY buy_date ASC
        """
        rows = conn.execute(query, (ticker,)).fetchall()
        
        if not rows:
            conn.close()
            return jsonify({"signals": [], "summary": {}})
            
        signals = []
        for r in rows:
            # Need to get buy price from the stock table for this date
            price_row = conn.execute(
                "SELECT close FROM daily_stock_data WHERE ticker = ? AND date = ?", 
                (ticker, r["buy_date"])
            ).fetchone()
            
            buy_price = round(float(price_row["close"]), 2) if price_row and price_row["close"] else "N/A"
            
            signals.append({
                "buy_date": r["buy_date"],
                "sell_date": r["sell_date"],
                "horizon": r["horizon"],
                "days_held": r["days_held"],
                "confidence": round(float(r["pred_prob"] or 0) * 100, 1),
                "adj_confidence": round(float(r["adj_prob"] or 0) * 100, 1),
                "actual_return": round(float(r["actual_return"]), 2) if r["actual_return"] is not None else None,
                "buy_price": buy_price
            })
            
        conn.close()

        total = len(signals)
        wins = sum(1 for s in signals if s["actual_return"] is not None and s["actual_return"] > 0)
        avg_conf = round(sum(s["confidence"] for s in signals) / total, 1) if total else 0
        
        rets = [s["actual_return"] for s in signals if s["actual_return"] is not None]
        avg_ret = round(sum(rets) / len(rets), 2) if rets else None

        # --- AI EXPERT ADVISOR (Advanced Future Forecast) ---
        summary_text = ""
        win_rate = round(wins / total * 100, 1) if total > 0 else 0
        
        if total > 0:
            # 1. Group the LATEST signals (same latest buy_date, different horizons)
            latest_date = signals[-1]['buy_date']
            latest_group = [s for s in signals if s['buy_date'] == latest_date]
            
            # Find the best horizon among the latest bunch
            best_signal = max(latest_group, key=lambda x: x['confidence'])
            prob_pct = best_signal['confidence']
            horizon = best_signal['horizon']
            
            # 2. Map horizon to a future human date/month
            from datetime import datetime, timedelta
            base_date = datetime.strptime(latest_date, "%Y-%m-%d")
            h_map = {"1d": 1, "1w": 7, "1m": 30, "6m": 180}
            future_date = base_date + timedelta(days=h_map.get(horizon, 1))
            best_month = future_date.strftime("%B %Y")
            
            # 3. Determine "Reading" and "Future Advice"
            if prob_pct >= 70:
                reading = f"🔥 STRONG BUY FOR {best_month.upper()}"
                advice = f"The AI is highly confident in an entry for **{best_month}**. Technical cycles indicate this is the prime accumulation zone."
            elif prob_pct >= 50:
                reading = f"✅ BUY OPPORTUNITY: {best_month}"
                advice = f"The AI sees a solid setup for **{best_month}**. This horizon offers the best risk/reward ratio currently."
            elif prob_pct >= 30:
                reading = "⚠️ WEAK / SPECULATIVE"
                advice = f"While **{best_month}** shows the most promise, the confidence is still low. High-risk territory."
            else:
                reading = "🛑 WAIT / NO IDEAL ENTRY"
                advice = f"None of the horizons (1d, 1w, 1m, 6m) show strong entry signals. The AI suggests staying on the sidelines through **{best_month}**."

            summary_text = (
                f"### AI Expert Analysis for {ticker}<br>"
                f"**Current Status:** {reading}<br>"
                f"**Expert Recommendation:** {advice}<br><br>"
                f"**Optimal Entry Details:** ${best_signal['buy_price']} (target: **{best_month}**)<br>"
                f"**Confidence Level:** {prob_pct}% (Horizon: {horizon})<br>"
                f"**Model Reliability:** Historical strategy accuracy is {win_rate}%."
            )

        return jsonify({
            "signals": signals[-50:],
            "summary": {
                "total_trades": total,
                "win_rate": win_rate,
                "avg_confidence": avg_conf,
                "avg_return": avg_ret,
                "summary_text": summary_text
            }
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/chat", methods=["POST"])
@login_required
def ai_chat():
    """
    Real AI Database Oracle using Gemini Pro.
    Consults local SQLite and then asks a real LLM to analyze.
    """
    try:
        import google.generativeai as genai
        # Configure with the user's provided key
        genai.configure(api_key="AIzaSyAZDGWFrNzA23FoSgjGuRrzwNPSY_uCGbs")
        
        # --- Dynamic Model Selection ---
        # Instead of hardcoding (which can cause 404s), we find a working model.
        # We prioritize 'flash' for speed, then 'pro'.
        try:
            available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            prioritized = [m for m in available_models if 'flash' in m] + [m for m in available_models if 'pro' in m]
            
            model = None
            selected_model_name = "gemini-pro" # Default fallback
            for m_name in prioritized:
                # Skip models that previously hit quota in our tests
                if "gemini-2.0-flash" in m_name: continue
                
                try:
                    test_model = genai.GenerativeModel(m_name)
                    # Simple test
                    test_model.generate_content("ok", generation_config={"max_output_tokens": 1})
                    model = test_model
                    selected_model_name = m_name
                    break
                except Exception:
                    continue
            
            if not model:
                model = genai.GenerativeModel('gemini-pro')
        except Exception as e:
            print(f"[Model Selection Error] {e}")
            model = genai.GenerativeModel('gemini-pro')
        
        data = request.json
        ticker = data.get("ticker", "").upper()
        user_query = data.get("query", "")
        
        if not ticker:
            return jsonify({"response": "Please select a stock first so I can access its data."})

        conn = get_db_connection()
        
        # 1. Fetch Latest Technical Context
        tech_row = conn.execute("""
            SELECT close, RSI, MACD, MACD_Signal, MA20, ZScore, Volatility_10, date, open, high, low, volume
            FROM daily_stock_data 
            WHERE ticker = ? 
            ORDER BY date DESC LIMIT 1
        """, (ticker,)).fetchone()
        
        # 2. Fetch Latest Prediction Context (Last 5 signals)
        pred_rows = conn.execute("""
            SELECT horizon, pred_prob, buy_date
            FROM trade_signals 
            WHERE ticker = ? 
            ORDER BY buy_date DESC, pred_prob DESC LIMIT 5
        """, (ticker,)).fetchall()
        
        conn.close()

        if not tech_row:
            return jsonify({"response": f"I don't have enough data in my local database to analyze {ticker} right now."})

        # 3. Construct the RAG Prompt
        context_str = f"""
        STOCK: {ticker}
        DATE: {tech_row['date']}
        LATEST PRICE: ${round(float(tech_row['close']), 2)}
        OPEN: ${round(float(tech_row['open']), 2)} | HIGH: ${round(float(tech_row['high']), 2)} | LOW: ${round(float(tech_row['low']), 2)}
        VOLUME: {tech_row['volume']}
        TECHNICALS:
        - RSI: {round(float(tech_row['RSI']), 2) if tech_row['RSI'] else 'N/A'}
        - MACD: {round(float(tech_row['MACD']), 2) if tech_row['MACD'] else 'N/A'}
        - MA20: ${round(float(tech_row['MA20']), 2) if tech_row['MA20'] else 'N/A'}
        - Z-Score: {round(float(tech_row['ZScore']), 2) if tech_row['ZScore'] else 'N/A'}
        - Volatility: {round(float(tech_row['Volatility_10']), 2) if tech_row['Volatility_10'] else 'N/A'}
        
        AI PREDICTIONS (High probability entries):
        """
        for r in pred_rows:
            context_str += f"- {r['horizon']} forecast with {round(float(r['pred_prob'])*100, 1)}% confidence (dated {r['buy_date']})\n"

        prompt = f"""
        You are the 'Database Oracle', a professional stock market analyst. 
        Analyze the following real-time data from our internal database for {ticker} and answer the user's question.
        
        STRICT RULES:
        1. Use ONLY the data provided below. 
        2. If the user asks for something not in the data, tell them clearly you don't have that in your local database.
        3. Be professional, concise, and definitive.
        4. Use markdown for emphasis.
        
        DATA CONTEXT:
        {context_str}
        
        USER QUESTION:
        {user_query}
        """

        # 4. Get Real LLM Response
        gen_response = model.generate_content(prompt)
        ai_response = gen_response.text

        return jsonify({
            "response": ai_response,
            "ticker": ticker
        })

    except Exception as e:
        print(f"[Chat Error] {e}")
        return jsonify({"error": str(e)}), 500


# ── AUTHENTICATION ROUTES ───────────────────────────────────────────────────

@app.route("/api/auth/signup", methods=["POST"])
def signup():
    data = request.json
    email = data.get("email", "").lower().strip()
    password = data.get("password", "")
    
    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400
    
    try:
        conn = get_db_connection()
        user = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if user:
            conn.close()
            return jsonify({"error": "User already exists"}), 400
        
        hashed_password = generate_password_hash(password)
        conn.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email, hashed_password))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "User created successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email", "").lower().strip()
    password = data.get("password", "")
    
    try:
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["email"] = user["email"]
            return jsonify({"success": True, "user": {"email": user["email"]}})
        
        return jsonify({"error": "Invalid email or password"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/api/auth/status")
def auth_status():
    print(f"[DEBUG] Auth Status Check - Session: {dict(session)}")
    if "user_id" in session:
        return jsonify({"logged_in": True, "user": {"email": session.get("email")}})
    return jsonify({"logged_in": False})

# ── LOGIC PROTECTIONS ───────────────────────────────────────────────────────

@app.route("/")
def index():
    print(f"[DEBUG] Root Access - Session: {dict(session)}")
    if "user_id" not in session:
        print("[DEBUG] No user_id in session, redirecting to login")
        return redirect(url_for("login_page"))
        
    print("[DEBUG] Serving Dashboard index.html")
    static_dir = os.path.join(BASE_DIR, "static")
    resp = make_response(send_from_directory(static_dir, "index.html"))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

# ── NEWS & RECOMMENDATIONS ────────────────────────────────────────────────────

@app.route("/api/news")
@login_required
def get_news():
    """Proxy Yahoo Finance RSS feed for general market news. No API key required."""
    import urllib.request
    import xml.etree.ElementTree as ET

    ticker = request.args.get("ticker", "").upper().strip()

    # Build RSS URL — ticker-specific if provided, otherwise general market news
    if ticker:
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
    else:
        url = "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC,^DJI,^IXIC&region=US&lang=en-US"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read()

        root = ET.fromstring(raw)
        ns = {"media": "http://search.yahoo.com/mrss/"}

        articles = []
        for item in root.findall(".//item")[:15]:
            title   = item.findtext("title", "").strip()
            link    = item.findtext("link", "").strip()
            pub     = item.findtext("pubDate", "").strip()
            source  = item.findtext("source", "Yahoo Finance").strip()
            desc    = item.findtext("description", "").strip()

            # Parse pub date to ISO
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(pub)
                pub_iso = dt.strftime("%Y-%m-%dT%H:%M:%S")
            except Exception:
                pub_iso = pub

            articles.append({
                "title":       title,
                "link":        link,
                "published":   pub_iso,
                "source":      source or "Yahoo Finance",
                "description": desc[:200] if desc else ""
            })

        return jsonify({"articles": articles, "ticker": ticker or "MARKET"})

    except Exception as e:
        print(f"[News Error] {e}")
        return jsonify({"error": str(e), "articles": []}), 500


@app.route("/api/recommendations")
@login_required
def get_recommendations():
    """
    Return top-5 stock picks from the AI model.
    Picks the highest adj_prob signal per ticker from the most recent date
    across the whole trade_signals table, then returns the top 5.
    """
    try:
        conn = get_db_connection()

        # Get the latest signal date available
        latest_row = conn.execute(
            "SELECT MAX(buy_date) as d FROM trade_signals"
        ).fetchone()
        latest_date = latest_row["d"] if latest_row else None

        if not latest_date:
            conn.close()
            return jsonify({"recommendations": []})

        # Best signal per ticker on that date (highest adj_prob)
        rows = conn.execute("""
            SELECT
                ts.ticker,
                t.company_name,
                ts.horizon,
                ts.pred_prob,
                ts.adj_prob,
                ts.buy_date,
                ts.sell_date,
                d.close as latest_close
            FROM trade_signals ts
            LEFT JOIN tickers t ON ts.ticker = t.ticker
            LEFT JOIN (
                SELECT ticker, close FROM daily_stock_data
                WHERE date = (SELECT MAX(date) FROM daily_stock_data)
            ) d ON d.ticker = ts.ticker
            WHERE ts.buy_date = ?
            ORDER BY ts.adj_prob DESC
            LIMIT 10
        """, (latest_date,)).fetchall()

        conn.close()

        seen = set()
        recs = []
        for r in rows:
            if r["ticker"] in seen:
                continue
            seen.add(r["ticker"])
            conf = round(float(r["adj_prob"] or 0) * 100, 1)
            if conf < 20:
                continue  # skip very low confidence

            if conf >= 70:
                rating, rating_cls = "Strong Buy", "strong-buy"
            elif conf >= 50:
                rating, rating_cls = "Buy", "buy"
            elif conf >= 35:
                rating, rating_cls = "Watch", "watch"
            else:
                rating, rating_cls = "Speculative", "spec"

            recs.append({
                "ticker":       r["ticker"],
                "name":         r["company_name"] or r["ticker"],
                "horizon":      r["horizon"],
                "confidence":   conf,
                "rating":       rating,
                "rating_cls":   rating_cls,
                "latest_close": round(float(r["latest_close"]), 2) if r["latest_close"] else None,
                "buy_date":     r["buy_date"]
            })
            if len(recs) >= 5:
                break

        return jsonify({"recommendations": recs, "as_of": latest_date})

    except Exception as e:
        print(f"[Recommendations Error] {e}")
        return jsonify({"error": str(e)}), 500


# ── LOGIC PROTECTIONS ───────────────────────────────────────────────────────

@app.route("/login")
def login_page():
    if "user_id" in session:
        return redirect(url_for("index"))
    static_dir = os.path.join(BASE_DIR, "static")
    return send_from_directory(static_dir, "auth.html")

# ── STARTUP ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print("WARNING: Database not found. Please run init_db.py and ingest_to_db.py first.")
        
    print("=" * 60)
    print("  Stock Dashboard (SQLite backend) ->  http://localhost:5050")
    print("=" * 60)
    app.run(debug=False, port=5050, host="0.0.0.0")
