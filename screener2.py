import os
import pandas as pd
import yfinance as yf
import numpy as np
from scipy.stats import norm
import time

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

def get_sp500_tickers():
    """Scrapes the current S&P 500 list from Wikipedia."""
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    table = pd.read_html(url)
    df = table[0]
    # Convert 'BRK.B' format to 'BRK-B' for Yahoo Finance compatibility
    tickers = df['Symbol'].str.replace('.', '-').tolist()
    return tickers

def run_screener():
    print("Fetching live S&P 500 list from Wikipedia...")
    tickers = get_sp500_tickers()
    all_data = []
    
    print(f"Scanning {len(tickers)} stocks. This will take ~10-15 minutes...")

    for i, ticker in enumerate(tickers):
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y")
            if len(hist) < 200: continue

            price = hist['Close'].iloc[-1]
            sma200 = hist['Close'].rolling(200).mean().iloc[-1]
            rsi = calculate_rsi(hist['Close']).iloc[-1]
            poc_support = get_whale_support(hist.tail(90))
            iv = stock.info.get('impliedVolatility', 0.25)
            target_strike = poc_support if poc_support < price else round(price * 0.95, 2)
            pop = calculate_pop(price, target_strike, iv)

            # Scoring: RSI (Lower=Better) + PoP (Higher=Better)
            match_score = (100 - rsi) + pop

            all_data.append({
                'Ticker': ticker,
                'Price': round(price, 2),
                'RSI': round(rsi, 2),
                'Whale_Support': poc_support,
                'PoP_%': pop,
                'Match_Score': round(match_score, 2),
                'Trend': 'BULL' if price > sma200 else 'BEAR'
            })
            
            # Print progress every 50 tickers
            if i % 50 == 0: print(f"Progress: {i}/{len(tickers)}...")
            time.sleep(1.2) # Throttling to stay under Yahoo's radar
            
        except Exception:
            continue

    df = pd.DataFrame(all_data)
    df = df.sort_values(by='Match_Score', ascending=False).head(20)
    
    # Labeling Matches vs Non-Matches
    df['Status'] = 'WATCH'
    df.loc[(df['PoP_%'] >= 80) & (df['RSI'] <= 45) & (df['Trend'] == 'BULL'), 'Status'] = 'PRIME'
    df.loc[(df['Trend'] == 'BEAR'), 'Status'] = 'RISKY (Downtrend)'

    df.to_csv("Options_Whale_Screen_2026.csv", index=False)
    print("Scan Complete! Top 20 ranking saved.")

if __name__ == "__main__":
    run_screener()


