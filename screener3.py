import os
import pandas as pd
import yfinance as yf
import numpy as np
from scipy.stats import norm
import time

# --- CUSTOM RSI FUNCTION (REPLACES PANDAS_TA) ---
def calculate_rsi(data, window=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_pop(S, K, IV, T=30/365, r=0.045):
    if IV <= 0 or T <= 0: return 50.0
    d2 = (np.log(S / K) + (r - 0.5 * IV**2) * T) / (IV * np.sqrt(T))
    return round(norm.cdf(d2) * 100, 2)

def get_whale_support(df):
    price_bins = pd.cut(df['Close'], bins=20)
    volume_at_price = df.groupby(price_bins, observed=True)['Volume'].sum()
    return round(volume_at_price.idxmax().left, 2)

def run_screener():
    tickers = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "AMZN", "META"]
    final_candidates = []
    
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y")
            if len(hist) < 200: continue

            price = hist['Close'].iloc[-1]
            sma200 = hist['Close'].rolling(200).mean().iloc[-1]
            
            # Use our custom RSI instead of the library
            rsi_series = calculate_rsi(hist['Close'])
            rsi = rsi_series.iloc[-1]
            
            if price > sma200 and rsi < 50:
                poc_support = get_whale_support(hist.tail(90))
                iv = stock.info.get('impliedVolatility', 0.25)
                target_strike = poc_support if poc_support < price else round(price * 0.95, 2)
                pop = calculate_pop(price, target_strike, iv)

                final_candidates.append({
                    'Ticker': ticker, 'Price': round(price, 2), 'RSI': round(rsi, 2),
                    'Whale_Support': poc_support, 'Target_Strike': target_strike,
                    'PoP_%': pop, 'Status': 'PRIME' if (pop > 80 and rsi < 40) else 'Watch'
                })
            time.sleep(1)
        except Exception as e:
            print(f"Error on {ticker}: {e}")

    df_output = pd.DataFrame(final_candidates)
    df_output.to_csv("Options_Whale_Screen_2026.csv", index=False)
    print("Success! File Created.")

if __name__ == "__main__":
    run_screener()

