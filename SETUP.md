# 🚀 Setup Guide — AI Stock Predictor + Dashboard

This guide walks you through setting up the project from scratch on a new Windows computer, even if you've never used Python before.

---

## ✅ Step 1 — Install Python 3.10

> ⚠️ **You must use Python 3.10 exactly.** Newer versions (3.11+) are not compatible with TensorFlow 2.10.

1. Download **Python 3.10** from the official website:
   👉 https://www.python.org/downloads/release/python-31011/
   - Scroll down and click **"Windows installer (64-bit)"**

2. Run the installer.  
   ☑️ **Check "Add Python to PATH"** at the bottom before clicking Install.

3. Verify installation — open **PowerShell** and run:
   ```powershell
   py -3.10 --version
   ```
   You should see: `Python 3.10.x`

---

## ✅ Step 2 — Download the Project

If you don't have it yet, download or clone this project folder to your computer.

Open **PowerShell** and navigate to the project folder:
```powershell
cd "C:\path\to\LSTM_AI_Stock_Predictor-main"
```
> Replace the path above with wherever you saved the project.

---

## ✅ Step 3 — Create a Virtual Environment

This keeps the project's packages isolated from the rest of your system.

```powershell
py -3.10 -m venv .venv
```

You should see a new `.venv` folder appear in the project directory.

---

## ✅ Step 4 — Install Dependencies

```powershell
.\.venv\Scripts\pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\pip install flask flask-cors alpha_vantage
```

This may take **5–15 minutes** depending on your internet speed.

---

## ✅ Step 5 — Configure Your API Key

The downloader needs a free **AlphaVantage** API key to fetch stock data.

1. Get a free key at: 👉 https://www.alphavantage.co/support/#api-key
2. Copy the file `config.example.json` and rename it to `config.json`
3. Open `config.json` and paste your key:
   ```json
   {
       "ALPHA_VANTAGE_KEY": "YOUR_KEY_HERE"
   }
   ```

---

## ✅ Step 6 — Download & Process Stock Data

> Only needed if you want to generate fresh data. The project already includes sample data.

**Step 6a — Download raw data:**
```powershell
.\.venv\Scripts\python TrainingData/downloader.py
```
> This can take a long time (hours) depending on how many stocks are in `TrainingData/stockList.csv`.

**Step 6b — Process into indicator CSVs:**
```powershell
.\.venv\Scripts\python TrainingData/processor.py
```
> Output goes to `TrainingData/indicators_data/processed/stocksData/`

---

## 🖥️ Step 7 — Launch the Stock Dashboard

```powershell
.\.venv\Scripts\python dashboard\app.py
```

Then open your browser and go to:
👉 **http://localhost:5050**

You should see the full exchange-style chart dashboard!

---

## 📓 Step 8 — Run the Forecasting Notebook (Optional)

Open **`run_forecast_v4.ipynb`** in VS Code or Jupyter:

```powershell
.\.venv\Scripts\jupyter notebook run_forecast_v4.ipynb
```

This trains the LSTM model and outputs predictions to `/forecasts/`.

---

## 🗂️ Project Structure

```
LSTM_AI_Stock_Predictor-main/
├── dashboard/                  ← Web dashboard (Flask + HTML)
│   ├── app.py                  ← Backend API server
│   └── static/index.html       ← Frontend UI
├── TrainingData/
│   ├── downloader.py           ← Downloads raw stock data
│   ├── processor.py            ← Generates technical indicators
│   ├── stockList.csv           ← List of tickers to download
│   └── indicators_data/
│       └── processed/stocksData/  ← Processed CSV files (one per ticker)
├── forecasts/                  ← Model predictions output here
├── run_forecast_v4.ipynb       ← Jupyter notebook for training & forecasting
├── run_backtest_v4.py          ← Backtest script
├── config.json                 ← Your AlphaVantage API key (create this)
├── config.example.json         ← API key template
└── requirements.txt            ← Python package list
```

---

## ⚡ Quick Reference — Daily Use Commands

| Task | Command |
|---|---|
| Start dashboard | `.\.venv\Scripts\python dashboard\app.py` |
| Download new data | `.\.venv\Scripts\python TrainingData/downloader.py` |
| Process raw data | `.\.venv\Scripts\python TrainingData/processor.py` |
| Run backtest | `.\.venv\Scripts\python run_backtest_v4.py` |

---

## 🛠️ Troubleshooting

| Problem | Solution |
|---|---|
| `'py' is not recognized` | Reinstall Python 3.10 and check "Add to PATH" |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` again |
| Dashboard not loading | Make sure `app.py` is running and visit `http://localhost:5050` |
| API rate limit errors | AlphaVantage free tier allows 25 requests/day. Wait or upgrade plan |
| Port 5050 already in use | Change `port=5050` in `dashboard/app.py` to another port like `5051` |
