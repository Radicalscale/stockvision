# 🚀 Setup Guide — AI Stock Predictor + Dashboard

This guide walks you through setting up the automated local LSTM AI stock predictor and the corresponding Railway Deployment Dashboard.

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

If you don't have it yet, download or clone this project from your GitHub.

Open **PowerShell** and navigate to the project folder:
```powershell
cd "C:\path\to\LSTM_AI_Stock_Predictor-main"
```

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
.\.venv\Scripts\pip install -r stockvision-deploy/requirements.txt
```

This installs all required Machine Learning bindings (TensorFlow, Keras) and Web Framework dependencies (Flask, Pandas, yfinance). It may take **5–15 minutes**.

---

## ✅ Step 5 — Configure Your Data Provider

By default, the AI pipeline uses **yfinance** for high-speed, free stock data fetching across your entire `stockList.csv`.

If you wish to switch to Alpha Vantage:
1. Get a free key at: 👉 https://www.alphavantage.co/support/#api-key
2. Copy the file `config.example.json` and rename it to `config.json`
3. Open `config.json` and paste your key:
   ```json
   {
       "ALPHA_VANTAGE_KEY": "YOUR_KEY_HERE",
       "DATA_PROVIDER": "alpha_vantage"
   }
   ```
4. If you leave `DATA_PROVIDER` as `"yfinance"`, it will use Yahoo Finance for free.

---

## 🤖 Step 6 — Run the Automated AI Pipeline

To start generating predictions on autopilot every 30 minutes, simply run the master script:

```bash
.\.venv\Scripts\python local_pipeline.py
```

This single command orchestrates everything:
1. **Fetching**: Downloads historical price action for all 2000+ stocks.
2. **Feature Engineering**: Auto-calculates Volatility, RSI, MACD, Moving Averages.
3. **AI Inference**: Standardizes the math, loads `lstm_model.h5`, and outputs predictions to `forecasts/`.
4. **Rescheduling**: Sleeps and auto-repeats the whole process every 30 minutes.

---

## 🖥️ Step 7 — Launch the Local Stock Dashboard

You can view the results of the pipeline directly on your laptop. Open a new terminal tab and run:

```powershell
.\.venv\Scripts\python stockvision-deploy\app.py
```

Then open your browser and go to:
👉 **http://localhost:5050**

---

## ☁️ Step 8 — Push Predictions to Live Railway App

Your live application on Railway automatically hosts from your GitHub repository. 

Whenever your `local_pipeline.py` finishes generating fresh data arrays and predictions on your laptop, you can immediately send those new numbers up to your live Railway website by running this command:

```bash
.\.venv\Scripts\python stockvision-deploy\railway_sync.py
```

*Note: You must have the Railway CLI installed (`npm install -g @railway/cli`) and be logged in to your account (`railway login`) for the live sync bridge to work.*

---

## 🗂️ Project Structure

```text
LSTM_AI_Stock_Predictor-main/
├── stockvision-deploy/         ← Railway Deployment Environment (Backend + UI)
│   ├── app.py                  ← Backend API server
│   ├── railway_sync.py         ← Pushes fresh local data to Railway cloud
│   ├── static/index.html       ← Frontend UI Dashboard
│   └── data/                   ← Where the local AI generated CSVs are stored
├── TrainingData/
│   ├── downloader.py           ← Legacy raw downloader scripts
│   ├── processor.py            ← Mathematical Indicator features script
│   └── stockList.csv           ← List of all 2000+ active tickers
├── local_pipeline.py           ← ★ Master AI Pipeline & Task Scheduler
├── forecasts/                  ← Directory storing 1d, 1w, 1m, 6m predictions
└── lstm_model.h5               ← The trained Neural Network Weights
```

---

## ⚡ Quick Reference — Daily Use Commands

| Task | Command |
|---|---|
| **Start AI Autopilot** | `.\.venv\Scripts\python local_pipeline.py` |
| View Local Dashboard | `.\.venv\Scripts\python stockvision-deploy\app.py` |
| **Sync Live Website** | `.\.venv\Scripts\python stockvision-deploy\railway_sync.py` |
| Train New Model | `.\.venv\Scripts\jupyter notebook run_forecast_v4.ipynb` |
