import os
import time
import requests
import pandas as pd
import yfinance as yf

# --- SECURE CONFIGURATION ---
# These are pulled from GitHub Secrets for security
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# --- CORE HELPERS ---
from io import StringIO  # <--- Add this at the top

def get_sp500_tickers():
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        # Wrap response.text in StringIO to fix the FutureWarning
        table = pd.read_html(StringIO(response.text), flavor='bs4') 
        return table[0]['Symbol'].str.replace('.', '-').tolist()
    except Exception as e:
        print(f"Error fetching tickers: {e}")
        return []

def calculate_fair_value(info):
    eps = info.get('trailingEps', 0)
    growth = info.get('earningsGrowth', 0.05) * 100
    if eps <= 0: return 0
    intrinsic = eps * (8.5 + 1.5 * min(growth, 20))
    pe_basis = eps * 19 
    return round((intrinsic + pe_basis) / 2, 2)

def send_telegram_alert(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram credentials missing. Skipping alert.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

# --- MAIN ENGINE ---
def run_whale_system():
    print("🐋 Starting Ultimate Whale Master 2026...")
    tickers = get_sp500_tickers()
    all_data = []
    MCAP_THRESHOLD = 20_000_000_000 

    for i, ticker in enumerate(tickers):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            if info.get('marketCap', 0) < MCAP_THRESHOLD: continue

            # Financial Data
            curr_price = info.get('currentPrice', 0)
            fair_p = calculate_fair_value(info)
            roe = info.get('returnOnEquity', 0) * 100
            rev_growth = info.get('revenueGrowth', 0) * 100
            beta = info.get('beta', 1.0)
            
            # Valuation & Trap Logic
            upside = ((fair_p - curr_price) / curr_price) * 100
            is_trap = "YES" if (rev_growth < 0 or roe < 8) else "NO"
            
            # Exit Strategy
            risk_buffer = max(0.06, min(0.18, (beta or 1.0) * 0.08))
            stop_loss = round(curr_price * (1 - risk_buffer), 2)
            target_sell = round(max(fair_p, curr_price * (1 + risk_buffer * 2)), 2)

            all_data.append({
                'Ticker': ticker,
                'Name': info.get('shortName', 'N/A'),
                'Sector': info.get('sector', 'N/A'),
                'Price': curr_price,
                'Fair_Value': fair_p,
                'Upside_%': round(upside, 1),
                'Stop_Loss': stop_loss,
                'Target_Sell': target_sell,
                'ROE_%': round(roe, 1),
                'Rev_Growth_%': round(rev_growth, 1),
                'Trap_Warning': is_trap,
                'Dividend_Yield_%': round(info.get('dividendYield', 0) * 100, 2)
            })
            time.sleep(0.6)
        except: continue

    df = pd.DataFrame(all_data)

    # 1. GENERATE SECTOR REPORT
    if df.empty:
        print("❌ No data collected. Check ticker list or API status.")
        send_telegram_alert("⚠️ *Whale Scan Error:* No data collected this week.")
        return # Exit early instead of trying to group by 'Sector'

    # Now it is safe to generate reports
    sector_summary = df.groupby('Sector').agg({'Upside_%': 'mean', 'ROE_%': 'mean', 'Ticker': 'count'})

    # 2. GENERATE MASTER TOP 30
    df['Quality_Score'] = df['ROE_%'] + df['Upside_%']
    master_30 = df[df['Trap_Warning'] == "NO"].sort_values('Quality_Score', ascending=False).head(30)
    master_30.to_csv("Ultimate_Whale_Master_2026.csv", index=False)

    # 3. SEND TELEGRAM ALERT
    top_3 = master_30.head(3)
    msg = "🚀 *WEEKLY WHALE SCAN COMPLETE*\n\n"
    for _, row in top_3.iterrows():
        msg += f"🔥 *{row['Ticker']}* | Upside: {row['Upside_%']}% | ROE: {row['ROE_%']}%\n"
    msg += "\n📊 _Full CSVs uploaded to GitHub._"
    send_telegram_alert(msg)
    print("✅ System run complete.")

if __name__ == "__main__":
    run_whale_system()
