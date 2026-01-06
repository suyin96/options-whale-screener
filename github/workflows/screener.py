import os
import pandas as pd
import yfinance as yf
import pandas_ta as ta
import numpy as np
from scipy.stats import norm
import time
import requests

# --- CLOUD SECURITY CONFIG ---
# GitHub Actions or Colab will inject this key into the environment
FINNHUB_KEY = os.getenv('FINNHUB_KEY')

def calculate_pop(S, K, IV, T=30/365, r=0.045):
    """Calculates Probability of Profit using Black-Scholes d2."""
    if IV <= 0 or T <= 0: return 50.0
    try:
        d2 = (np.log(S / K) + (r - 0.5 * IV**2) * T) / (IV * np.sqrt(T))
        return round(norm.cdf(d2) * 100, 2)
    except:
        return 50.0

def get_whale_support(df):
    """Identifies the Point of Control (POC) as institutional support."""
    price_bins = pd.cut(df['Close'], bins=20)
    # observed=True prevents errors in newer pandas versions
    volume_at_price = df.groupby(price_bins, observed=True)['Volume'].sum()
    return round(volume_at_price.idxmax().left, 2)

def run_screener():
    # TEST LIST: Start with these to ensure the script works. 
    # You can expand this to the full S&P 500 later.
    tickers = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "AMZN", "META", "BRK-B", "UNH", "JNJ"]
    
    final_candidates = []
    print(f"Cloud Scan Started: Processing {len(tickers)} Whale Targets...")

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            # Fetch 1 year of data for technicals
            hist = stock.history(period="1y")
            if len(hist) < 200: continue

            # 1. Technical Indicators
            price = hist['Close'].iloc[-1]
            sma200 = hist['Close'].rolling(200).mean().iloc[-1]
            rsi = ta.rsi(hist['Close'], length=14).iloc[-1]
            
            # 2. Logic: Trend must be UP, but currently in a PULLBACK (RSI < 50)
            if price > sma200 and rsi < 50:
                # Calculate Institutional Support (Whale Floor)
                poc_support = get_whale_support(hist.tail(90))
                
                # Fetch Options Data for PoP
                iv = stock.info.get('impliedVolatility', 0.25)
                # Strike Idea: Set it at the Whale Floor or 5% below current price
                target_strike = poc_support if poc_support < price else round(price * 0.95, 2)
                
                pop = calculate_pop(price, target_strike, iv)

                # 3. UOA Check: Volume > Open Interest on nearest OTM Put
                uoa = "No"
                try:
                    exp = stock.options[0]
                    puts = stock.option_chain(exp).puts
                    otm_puts = puts[puts['strike'] < price]
                    if not otm_puts.empty:
                        if any(otm_puts['volume'] > otm_puts['openInterest']):
                            uoa = "YES"
                except:
                    uoa = "N/A"

                final_candidates.append({
                    'Ticker': ticker,
                    'Price': round(price, 2),
                    'RSI': round(rsi, 2),
                    'Whale_Support': poc_support,
                    'Target_Strike': target_strike,
                    'PoP_%': pop,
                    'IV_%': round(iv * 100, 2),
                    'UOA': uoa,
                    'Status': 'PRIME' if (pop > 80 and rsi < 40) else 'Watch'
                })
            
            # Throttle to avoid API rate limits
            time.sleep(0.5) 
            
        except Exception as e:
            print(f"Skipping {ticker}: {e}")
            continue

    # 4. Export to CSV
    df_output = pd.DataFrame(final_candidates)
    filename = "Options_Whale_Screen_2026.csv"
    df_output.to_csv(filename, index=False)
    print(f"Success! {len(df_output)} candidates saved to {filename}")

if __name__ == "__main__":
    run_screener()
