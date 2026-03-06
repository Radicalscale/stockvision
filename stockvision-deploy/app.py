"""
Stock Dashboard Flask API
Serves processed stock data CSV files as a REST API.
Includes company-name search via yfinance (cached to disk).
Railway-ready deployment version.
"""
import os
import json
import glob
import threading
from flask import Flask, jsonify, request, send_from_directory, make_response
import pandas as pd
from flask_cors import CORS

app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app)

# ─── FLAT PATHS (relative to this file) ─────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
DATA_DIR      = os.path.join(BASE_DIR, "data", "processed")
RAW_DIR       = os.path.join(BASE_DIR, "data", "raw")
NAMES_FILE    = os.path.join(BASE_DIR, "company_names.json")
TRADE_SUMMARY = os.path.join(BASE_DIR, "trade_summary_prob_strategy.csv")

# ── Cache trade signals in memory ────────────────────────────────────────────
_trade_df = None

def _load_trade_df():
    global _trade_df
    if _trade_df is not None:
        return _trade_df
    if not os.path.exists(TRADE_SUMMARY):
        _trade_df = pd.DataFrame()
        return _trade_df
    df = pd.read_csv(TRADE_SUMMARY)
    df["Ticker"] = df["Ticker"].str.replace(r"_daily_processed$", "", regex=True)
    _trade_df = df
    return _trade_df

# ── In-memory company-name map  { "AAPL": "Apple Inc." }
_company_names: dict = {}
_names_lock = threading.Lock()


def _load_names_from_disk():
    global _company_names
    if os.path.exists(NAMES_FILE):
        try:
            with open(NAMES_FILE, "r") as f:
                with _names_lock:
                    _company_names = json.load(f)
            print(f"[names] Loaded {len(_company_names)} company names from cache.")
        except Exception as e:
            print(f"[names] Failed to load cache: {e}")


def _save_names_to_disk():
    try:
        with _names_lock:
            data = dict(_company_names)
        with open(NAMES_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[names] Failed to save cache: {e}")


def _fetch_names_background(tickers: list):
    """Fetch company names via yfinance in batches — runs in background thread."""
    try:
        import yfinance as yf
    except ImportError:
        print("[names] yfinance not installed — company name search unavailable.")
        return

    print(f"[names] Starting background fetch for {len(tickers)} tickers…")
    batch_size = 50
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        try:
            data = yf.Tickers(" ".join(batch))
            for t in batch:
                if t in _company_names:
                    continue
                try:
                    name = data.tickers[t].info.get("shortName") or data.tickers[t].info.get("longName") or t
                    with _names_lock:
                        _company_names[t] = name
                except Exception:
                    with _names_lock:
                        _company_names[t] = t
        except Exception as e:
            print(f"[names] Batch error: {e}")
        _save_names_to_disk()
    print("[names] Background fetch complete.")


def get_all_tickers():
    """Return sorted list of all available tickers (non-empty files only)."""
    pattern = os.path.join(DATA_DIR, "*_daily_processed.csv")
    files   = glob.glob(pattern)
    tickers = []
    for f in files:
        basename = os.path.basename(f)
        ticker   = basename.replace("_daily_processed.csv", "")
        if os.path.getsize(f) > 500:
            tickers.append(ticker)
    return sorted(tickers)


# ── ROUTES ───────────────────────────────────────────────────────────────────

@app.route("/api/debug")
def debug_info():
    try:
        if not os.path.exists(DATA_DIR):
            return jsonify({"error": f"DATA_DIR not found: {DATA_DIR}"})
        files = os.listdir(DATA_DIR)
        first_few = files[:5]
        sizes = [os.path.getsize(os.path.join(DATA_DIR, f)) for f in first_few]
        return jsonify({
            "data_dir": DATA_DIR,
            "exists": os.path.exists(DATA_DIR),
            "file_count": len(files),
            "first_few": first_few,
            "sizes": sizes,
            "pattern_matched": len(glob.glob(os.path.join(DATA_DIR, "*_daily_processed.csv")))
        })
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route("/api/tickers")

def list_tickers():
    tickers = get_all_tickers()
    result = []
    for t in tickers:
        with _names_lock:
            name = _company_names.get(t, t)
        result.append({"ticker": t, "name": name})
    return jsonify({"tickers": result, "count": len(result)})


@app.route("/api/stock/<ticker>")
def get_stock_data(ticker):
    ticker   = ticker.upper().replace("-", "/")
    filepath = os.path.join(DATA_DIR, f"{ticker}_daily_processed.csv")

    if not os.path.exists(filepath):
        return jsonify({"error": f"Ticker {ticker} not found"}), 404

    try:
        df = pd.read_csv(filepath, parse_dates=["date"])
        df = df.sort_values("date").dropna(subset=["close"])

        raw_ticker = ticker.replace("/", "-")
        raw_path = os.path.join(RAW_DIR, f"{raw_ticker}_daily.csv")
        if os.path.exists(raw_path):
            try:
                raw = pd.read_csv(raw_path, parse_dates=["date"])
                raw = raw.rename(columns={c: c.lower() for c in raw.columns})
                ohlcv_cols = [c for c in ["open", "high", "low", "volume"] if c in raw.columns]
                if ohlcv_cols:
                    raw = raw[["date"] + ohlcv_cols].drop_duplicates("date")
                    df = df.merge(raw, on="date", how="left")
            except Exception as e:
                print(f"[raw merge] {ticker}: {e}")

        period = request.args.get("period", "2y")
        period_map = {"1m": 30, "3m": 90, "6m": 180, "1y": 252, "2y": 504, "5y": 1260}
        if period in period_map:
            df = df.tail(period_map[period])

        df["date"] = df["date"].dt.strftime("%Y-%m-%d")

        latest     = df.iloc[-1]
        prev       = df.iloc[-2] if len(df) > 1 else latest
        latest_close = float(latest["close"])
        prev_close   = float(prev["close"])
        change       = latest_close - prev_close
        change_pct   = (change / prev_close * 100) if prev_close != 0 else 0

        yr_df        = df.tail(252)
        week52_high  = float(yr_df["close"].max())
        week52_low   = float(yr_df["close"].min())
        avg_volume   = float(yr_df["volume"].mean()) if "volume" in yr_df.columns else None

        candles = []
        for _, row in df.iterrows():
            entry = {"date": row["date"], "close": round(float(row.get("close", 0)), 4)}
            for c in ["open", "high", "low", "volume"]:
                if c in df.columns:
                    entry[c] = round(float(row[c]), 4)
            candles.append(entry)

        selected_indicators = [
            "MA10", "MA20", "MA30", "RSI", "MACD", "MACD_Signal",
            "BollingerUpper", "BollingerLower", "EMA10", "EMA30",
            "OBV", "ZScore", "Volatility_10", "Volatility_20",
        ]
        indicators_data = {}
        for ind in selected_indicators:
            if ind in df.columns:
                indicators_data[ind] = [
                    round(float(v), 4) if pd.notna(v) else None for v in df[ind]
                ]

        with _names_lock:
            company_name = _company_names.get(ticker, ticker)

        return jsonify({
            "ticker":       ticker,
            "name":         company_name,
            "latest_close": round(latest_close, 4),
            "change":       round(change, 4),
            "change_pct":   round(change_pct, 4),
            "week52_high":  round(week52_high, 4),
            "week52_low":   round(week52_low, 4),
            "avg_volume":   round(avg_volume, 0) if avg_volume else None,
            "data_points":  len(df),
            "dates":        [c["date"] for c in candles],
            "candles":      candles,
            "indicators":   indicators_data,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/search")
def search_tickers():
    q       = request.args.get("q", "").strip().upper()
    tickers = get_all_tickers()

    if not q:
        results = [{"ticker": t, "name": _company_names.get(t, t)} for t in tickers[:50]]
        return jsonify({"results": results})

    exact, starts, contains, name_hits = [], [], [], []
    for t in tickers:
        with _names_lock:
            name = _company_names.get(t, t).upper()
        if t == q:           exact.append(t)
        elif t.startswith(q): starts.append(t)
        elif q in t:          contains.append(t)
        elif q in name:       name_hits.append(t)

    ordered = exact + starts + contains + name_hits
    seen, deduped = set(), []
    for t in ordered:
        if t not in seen:
            seen.add(t)
            deduped.append(t)

    results = [{"ticker": t, "name": _company_names.get(t, t)} for t in deduped[:60]]
    return jsonify({"results": results})


@app.route("/api/predictions/<ticker>")
def get_predictions(ticker):
    df = _load_trade_df()
    if df.empty:
        return jsonify({"signals": [], "summary": {}})

    mask = (df["Ticker"].str.upper() == ticker.upper()) | \
           (df["Ticker"].str.upper() == f"{ticker.upper()}_DAILY_PROCESSED")
    rows = df[mask].copy()

    if rows.empty:
        return jsonify({"signals": [], "summary": {}})

    rows = rows.sort_values("BuyDate")
    signals = []
    for _, r in rows.iterrows():
        actual_return = r.get("Actual_Return%", None)
        try:
            actual_return = float(actual_return) if actual_return == actual_return else None
        except (ValueError, TypeError):
            actual_return = None

        signals.append({
            "buy_date"      : str(r["BuyDate"])[:10],
            "sell_date"     : str(r["SellDate"])[:10],
            "horizon"       : str(r.get("Horizon", "1d")),
            "days_held"     : int(r.get("DaysHeld", 1)),
            "confidence"    : round(float(r.get("Pred_Prob", 0)) * 100, 1),
            "adj_confidence": round(float(r.get("Adj_Prob", 0)) * 100, 1),
            "actual_return" : round(actual_return, 2) if actual_return is not None else None,
        })

    total    = len(signals)
    wins     = sum(1 for s in signals if s["actual_return"] is not None and s["actual_return"] > 0)
    avg_conf = round(sum(s["confidence"] for s in signals) / total, 1) if total else 0
    rets     = [s["actual_return"] for s in signals if s["actual_return"] is not None]
    avg_ret  = round(sum(rets) / len(rets), 2) if rets else None
    win_rate = round(wins / total * 100, 1) if total else 0

    buy_price = "N/A"
    try:
        data_path = os.path.join(DATA_DIR, f"{ticker}_daily_processed.csv")
        if os.path.exists(data_path):
            stock_df = pd.read_csv(data_path)
            for s in signals:
                row = stock_df[stock_df['date'] == s['buy_date']]
                if not row.empty:
                    s['buy_price'] = round(float(row.iloc[0]['close']), 2)
                else:
                    s['buy_price'] = "N/A"
            latest = signals[-1]
            buy_price = latest.get('buy_price', "N/A")
    except Exception as e:
        print(f"[error] Error getting buy price: {e}")

    summary_text = ""
    if total > 0:
        latest = signals[-1]
        summary_text = (
            f"**AI Prediction Analysis for {ticker}:**<br>"
            f"**Entry Price:** ${buy_price} (on {latest['buy_date']})<br>"
            f"**Target Period:** {latest['horizon']} holding period.<br>"
            f"**Historical Reliable:** This model has a {win_rate}% accuracy for this specific strategy on {ticker}."
        )

    return jsonify({
        "signals": signals[-50:],
        "summary": {
            "total_trades"   : total,
            "win_rate"       : win_rate,
            "avg_confidence" : avg_conf,
            "avg_return"     : avg_ret,
            "summary_text"   : summary_text
        }
    })


@app.route("/")
def index():
    resp = make_response(send_from_directory("static", "index.html"))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


# ── STARTUP ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    _load_names_from_disk()
    all_tickers = get_all_tickers()
    missing = [t for t in all_tickers if t not in _company_names]
    if missing:
        print(f"[names] {len(missing)} tickers need company-name lookup. Starting background fetch…")
        t = threading.Thread(target=_fetch_names_background, args=(missing,), daemon=True)
        t.start()
    else:
        print("[names] All company names already cached.")

    print("=" * 60)
    print(f"  Stock Dashboard →  http://localhost:{port}")
    print("=" * 60)
    app.run(debug=False, port=port, host="0.0.0.0")
