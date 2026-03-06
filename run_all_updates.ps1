# ─────────────────────────────────────────────────────────────────────────────
# AI Stock Predictor - Full Pipeline + Auto Railway Sync
# Run this script to process data, generate predictions, and push to Railway.
# ─────────────────────────────────────────────────────────────────────────────

$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$DEPLOY = "$ROOT\stockvision-deploy"

Write-Host "`n🚀 Starting AI Data Update Pipeline..." -ForegroundColor Cyan

# ─── 1. Download Fresh Data ──────────────────────────────────────────────────
Write-Host "`n[1/5] Downloading fresh stock & market data..." -ForegroundColor Yellow
& ".\.venv\Scripts\python" "TrainingData/downloader.py"
if ($LASTEXITCODE -ne 0) { Write-Error "Downloader failed!"; exit 1 }

# ─── 2. Process Indicators ───────────────────────────────────────────────────
Write-Host "`n[2/5] Calculating technical indicators..." -ForegroundColor Yellow
& ".\.venv\Scripts\python" "TrainingData/processor.py"
if ($LASTEXITCODE -ne 0) { Write-Error "Processor failed!"; exit 1 }

# ─── 3. AI LSTM Forecasting ──────────────────────────────────────────────────
Write-Host "`n[3/5] Running AI LSTM Forecasting..." -ForegroundColor Yellow
& ".\.venv\Scripts\python" "run_forecast_v4.py"
if ($LASTEXITCODE -ne 0) { Write-Error "Forecasting failed!"; exit 1 }

# ─── 4. Backtest & Summary ───────────────────────────────────────────────────
Write-Host "`n[4/5] Running backtest and updating dashboard summary..." -ForegroundColor Yellow
& ".\.venv\Scripts\python" "run_backtest_v4.py"
if ($LASTEXITCODE -ne 0) { Write-Error "Backtest failed!"; exit 1 }

Write-Host "`n✅ Pipeline complete!" -ForegroundColor Green

# ─── 5. Sync to Railway ──────────────────────────────────────────────────────
Write-Host "`n[5/5] Syncing updated data to Railway..." -ForegroundColor Cyan

# 5a. Copy updated processed CSVs → deploy folder
Write-Host "  Copying processed CSVs..."
Copy-Item "$ROOT\TrainingData\indicators_data\processed\stocksData\*" `
    "$DEPLOY\data\processed\" -Force

# 5b. Copy updated raw CSVs → deploy folder
Write-Host "  Copying raw CSVs..."
Copy-Item "$ROOT\TrainingData\indicators_data\raw\stocksData\*" `
    "$DEPLOY\data\raw\" -Force

# 5c. Copy updated trade summary (AI predictions)
Write-Host "  Copying AI predictions..."
Copy-Item "$ROOT\trade_summary_prob_strategy.csv" `
    "$DEPLOY\trade_summary_prob_strategy.csv" -Force

# 5d. Copy updated company names cache
if (Test-Path "$ROOT\dashboard\company_names.json") {
    Copy-Item "$ROOT\dashboard\company_names.json" "$DEPLOY\company_names.json" -Force
}

# 5e. Copy updated index.html (in case dashboard was modified)
Copy-Item "$ROOT\dashboard\static\index.html" "$DEPLOY\static\index.html" -Force

Write-Host "  Files synced to deploy folder." -ForegroundColor Green

# 5f. Git commit and push → triggers Railway auto-deploy
Write-Host "  Pushing to GitHub..."
Push-Location $DEPLOY
try {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
    git add -A
    $changes = git status --short
    if ($changes) {
        git commit -m "Auto-sync: pipeline run $timestamp"
        git push origin main
        Write-Host "  ✅ Pushed to GitHub! Railway will auto-deploy in ~60 seconds." -ForegroundColor Green
        Write-Host "  🌐 Check your Railway dashboard for deploy status." -ForegroundColor Cyan
    }
    else {
        Write-Host "  No changes detected — Railway is already up to date." -ForegroundColor Yellow
    }
}
catch {
    Write-Host "  ⚠️  Git push failed: $_" -ForegroundColor Red
    Write-Host "  You can manually push from: $DEPLOY" -ForegroundColor Yellow
}
finally {
    Pop-Location
}

Write-Host "`n🎉 All done! Your Railway dashboard will reflect new predictions shortly.`n" -ForegroundColor Green
