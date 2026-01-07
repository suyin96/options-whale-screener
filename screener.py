import os
import pandas as pd
import yfinance as yf
import numpy as np
from scipy.stats import norm
import requests
import time
from twilio.rest import Client

# --- HELPER FUNCTIONS ---
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
    """Fetches tickers from Wikipedia with a User-Agent to prevent 403 errors."""
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    table = pd.read_html(response.text, flavor='bs4')
    df = table[0]
    return df['Symbol'].str.replace('.', '-').tolist()

def send_whatsapp_alert(top_tickers):
    """Sends the top 5 'Prime' picks to your phone via Twilio."""
    try:
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        my_number = os.getenv('MY_PHONE_NUMBER')
        
        if not account_sid or not auth_token:
            print("Twilio credentials missing. Skipping WhatsApp.")
            return

        client = Client(account_sid, auth_token)
        message_body = f"🚀 Whale Scan Complete!\n\nTop Picks: {', '.join(top_tickers[:5])}\n\nCheck GitHub Actions for the full CSV."
        
        client.messages.create(
            from_='whatsapp:+14155238886', # Default Twilio Sandbox number
            body=message_body,
            to=my_number
        )
        print("WhatsApp alert sent successfully!")
    except Exception as e:
        print(f"Failed to send WhatsApp: {e}")

# --- MAIN SCREENER ---
def run_screener():
    print("Starting S&P 500 Whale Scan...")
    tickers = get_sp500_tickers()
    all_results = []
    
    # Scanning all 500 (Throttled for safety)
    for i, ticker in enumerate(tickers):
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y")
            if len(hist) < 200: continue

            price = hist['Close'].iloc[-1]
            sma200 = hist['Close'].rolling(200).mean().iloc[-1]
            rsi = calculate_rsi(hist['Close']).iloc[-1]
            poc_support = get_whale_support(hist.tail(90))
            
            # Options Greeks Estimation
            iv = stock.info.get('impliedVolatility', 0.25)
            target_strike = poc_support if poc_support < price else round(price * 0.95, 2)
            pop = calculate_pop(price, target_strike, iv)

            all_results.append({
                'Ticker': ticker,
                'Price': round(price, 2),
                'RSI': round(rsi, 2),
                'PoP_%': pop,
                'Match_Score': round((100 - rsi) + pop, 2),
                'Trend': 'BULL' if price > sma200 else 'BEAR'
            })
            
            if i % 25 == 0: print(f"Progress: {i}/{len(tickers)}...")
            time.sleep(1.2) # Avoid Yahoo Rate Limiting
            
        except Exception:
            continue

    # Process Final Table
    df = pd.DataFrame(all_results)
    df = df.sort_values(by='Match_Score', ascending=False).head(20)
    
    # Status Tagging
    df['Status'] = 'WATCH'
    df.loc[(df['PoP_%'] >= 80) & (df['RSI'] <= 45) & (df['Trend'] == 'BULL'), 'Status'] = 'PRIME MATCH'
    df.loc[(df['Trend'] == 'BEAR'), 'Status'] = 'RISKY (Downtrend)'

    # Save and Alert
    df.to_csv("Options_Whale_Screen_2026.csv", index=False)
    print("CSV Saved.")
    
    # Send WhatsApp with the top Tickers
    top_list = df[df['Status'] == 'PRIME MATCH']['Ticker'].tolist()
    if not top_list: # If no primes, just send the top scores
        top_list = df['Ticker'].head(5).tolist()
    
    send_whatsapp_alert(top_list)

if __name__ == "__main__":
    run_screener()
