"""
The purpose of this script is to download the stock and market data
for training the model.
"""

import subprocess
import sys

#Run the stockScrapper.py script to download stock data for:
#Close, Open, High, Low, Volume
subprocess.run([sys.executable, "TrainingData/featuresPy/stockScrapper.py"])


#Run the markets.py script to download market data for SPY and VIX
subprocess.run([sys.executable, "TrainingData/featuresPy/markets.py"])

#Run the insiderbuying.py script to download insider buying data
subprocess.run([sys.executable, "TrainingData/featuresPy/insiderbuying.py"])

#Run the sentiment.py script to download sentiment data
subprocess.run([sys.executable, "TrainingData/featuresPy/sentiment.py"])