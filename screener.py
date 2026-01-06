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

import requests

def get_sp500_tickers():
    """Scrapes the S&P 500 list using a User-Agent to avoid 403 Forbidden errors."""
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    
    # This header makes the script look like a real browser
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    response = requests.get(url, headers=headers)
    
    # Now we pass the response text to pandas
    table = pd.read_html(response.text, flavor='bs4')
    df = table[0]
    tickers = df['Symbol'].str.replace('.', '-').tolist()
    return tickers



def run_screener():
    print("Starting S&P 500 Whale Scan...")
    tickers = get_sp500_tickers()
    all_results = []
    
    # Scanning a subset for speed, or all 500
    for i, ticker in enumerate(tickers):
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y")
            if len(hist) < 200: continue

            price = hist['Close'].iloc[-1]
            sma200 = hist['Close'].rolling(200).mean().iloc[-1]
            rsi = calculate_rsi(hist['Close']).iloc[-1]
            poc_support = get_whale_support(hist.tail(90))
            
            # Options math
            iv = stock.info.get('impliedVolatility', 0.25)
            target_strike = poc_support if poc_support < price else round(price * 0.95, 2)
            pop = calculate_pop(price, target_strike, iv)

            # Score: Low RSI + High PoP
            match_score = (100 - rsi) + pop

            all_results.append({
                'Ticker': ticker,
                'Price': round(price, 2),
                'RSI': round(rsi, 2),
                'PoP_%': pop,
                'Match_Score': round(match_score, 2),
                'Trend': 'BULL' if price > sma200 else 'BEAR'
            })
            
            if i % 20 == 0: print(f"Scanned {i}/{len(tickers)}...")
            time.sleep(1.1) # Throttling to prevent Yahoo blocking
            
        except Exception:
            continue

    # Create and sort report
    df = pd.DataFrame(all_results)
    df = df.sort_values(by='Match_Score', ascending=False).head(20)
    
    # Categorize
    df['Status'] = 'WATCH'
    df.loc[(df['PoP_%'] >= 80) & (df['RSI'] <= 45) & (df['Trend'] == 'BULL'), 'Status'] = 'PRIME MATCH'
    df.loc[(df['Trend'] == 'BEAR'), 'Status'] = 'RISKY (Downtrend)'

    df.to_csv("Options_Whale_Screen_2026.csv", index=False)
    print("Report generated successfully!")

if __name__ == "__main__":
    run_screener()



