
import pandas as pd
import glob
import os

def check_signals():
    forecast_files = glob.glob(os.path.join(os.getcwd(), 'forecasts', '*_forecast.csv'))
    print(f"Scanning {len(forecast_files)} files...")
    
    all_max = []
    for f in forecast_files:
        try:
            df = pd.read_csv(f)
            if df.empty: continue
            last = df.iloc[-1]
            date = last['Date']
            probs = {h: last.get(f'Pred_Prob_{h}', 0) for h in ['1d', '1w', '1m', '6m']}
            
            max_p = max(probs.values())
            all_max.append((os.path.basename(f), date, max_p))
        except:
            continue
            
    all_max.sort(key=lambda x: x[2], reverse=True)
    print(f"Top 20 absolute highest signals found:")
    for f, d, p in all_max[:20]:
        print(f"{f}: {d} (Max Prob: {p:.4f})")

if __name__ == "__main__":
    check_signals()
