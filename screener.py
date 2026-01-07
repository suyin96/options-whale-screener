import os
import pandas as pd
import yfinance as yf
import numpy as np
from scipy.stats import norm
import requests
import time
from twilio.rest import Client

# --- NOTIFICATION FUNCTION ---
def send_whatsapp(body_text):
    """Utility to send WhatsApp messages via Twilio with error handling."""
    try:
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        my_number = os.getenv('MY_PHONE_NUMBER')
        
        # The Twilio Sandbox 'From' number is standard. 
        # Ensure your MY_PHONE_NUMBER secret starts with 'whatsapp:+'
        from_number = 'whatsapp:+18569345648'
        
        if not all([account_sid, auth_token, my_number]):
            print("WhatsApp Error: Secrets are missing.")
            return

        client = Client(account_sid, auth_token)
        client.messages.create(
            from_=from_number,
            body=body_text,
            to=my_number
        )
        print("✅ WhatsApp notification sent!")
    except Exception as e:
        print(f"⚠️ WhatsApp Error: {e}")

# --- METRICS CALCULATIONS ---
def get_advanced_metrics(ticker, hist, info):
    # 1. Momentum: 14-day Rate of Change
    momentum = ((hist['Close'].iloc[-1] - hist['Close'].iloc[-14]) / hist['Close'].iloc[-14]) * 100
    
    # 2. Institutional Support: Volume Profile (Point of Control)
    support_hist = hist.tail(126) # 6 months
    price_bins = pd.cut(support_hist['Close'], bins=15)
    inst_support = support_hist.groupby(price_bins, observed=True)['Volume'].sum().idxmax().left
    
    # 3. UOA Proxy: Current Volume vs 20-Day Average
    avg_vol = hist['Volume'].tail(20).mean()
    current_vol = hist['Volume'].iloc[-1]
    uoa = "HIGH" if (current_vol / avg_vol) > 1.8 else "NORMAL"
    
    # 4. Last Price Date
    last_date = hist.index[-1].strftime('%Y-%m-%d')
    
    sector = info.get('sector', 'N/A')
    return round(momentum, 2), round(inst_support, 2), uoa, sector, last_date

def calculate_pop(S, K, IV, T=30/365):
    """Calculates Probability of Profit using the d2 component of Black-Scholes."""
    if IV <= 0 or T <= 0: return 50.0
    r = 0.045 # Risk-free rate (approx 4.5%)
    d2 = (np.log(S / K) + (r - 0.5 * IV**2) * T) / (IV * np.sqrt(T))
    return round(norm.cdf(d2) * 100, 2)

def get_sp500_tickers():
    """Scrapes S&P 500 list with headers to avoid 403 Forbidden error."""
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    table = pd.read_html(response.text, flavor='bs4')
    return table[0]['Symbol'].str.replace('.', '-').tolist()

# --- MAIN SCREENER ---
def run_screener():
    print("🚀 Initializing Ultra-Whale Scan...")
    tickers = get_sp500_tickers()
    all_results = []
    
    for i, ticker in enumerate(tickers):
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y")
            info = stock.info
            if len(hist) < 200: continue

            price = hist['Close'].iloc[-1]
            sma200 = hist['Close'].rolling(200).mean().iloc[-1]
            
            momentum, inst_support, uoa, sector, last_date = get_advanced_metrics(ticker, hist, info)
            
            # Recommended Strike: Institutional Support or 7% below price
            rec_strike = inst_support if inst_support < (price * 0.98) else round(price * 0.93, 2)
            
            # Cushion %: The gap between Price and Strike
            cushion = ((price - rec_strike) / price) * 100
            
            # Options IV for PoP calculation
            iv = info.get('impliedVolatility', 0.25)
            pop = calculate_pop(price, rec_strike, iv)

            # Whale Score Logic: High PoP + Momentum + UOA Bonus
            uoa_bonus = 20 if uoa == "HIGH" else 0
            whale_score = pop + (momentum * 1.5) + uoa_bonus

            all_results.append({
                'Ticker': ticker,
                'Sector': sector,
                'Last_Date': last_date,
                'Price': round(price, 2),
                'Inst_Support': inst_support,
                'Momentum_%': momentum,
                'UOA': uoa,
                'Rec_Strike': rec_strike,
                'Cushion_%': round(cushion, 2),
                'PoP_%': pop,
                'Whale_Score': round(whale_score, 2),
                'Trend': 'BULL' if price > sma200 else 'BEAR'
            })
            
            if i % 50 == 0: print(f"Progress: {i}/{len(tickers)} scanned...")
            time.sleep(1.3) # Avoid Yahoo Rate Limiting

        except Exception:
            continue

    # Sorting & Final Report Generation
    df = pd.DataFrame(all_results)
    # Get top 30 based on Whale Score
    df = df.sort_values(by='Whale_Score', ascending=False).head(30)
    
    # Save CSV
    df.to_csv("Options_Whale_Screen_2026.csv", index=False)
    print("✅ CSV Report Created.")
    
    # Final WhatsApp Alert (Only once to save credits)
    top_5 = df['Ticker'].head(5).tolist()
    alert_msg = f"🐋 Whale Scan Done!\n\nTop 5: {', '.join(top_5)}\n\nReport includes 30 items with Cushion % and Support levels."
    send_whatsapp(alert_msg)

if __name__ == "__main__":
    run_screener()
