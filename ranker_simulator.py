import pandas as pd
import yfinance as yf
import numpy as np
import time

def calculate_cagr(start_price, end_price, years=3):
    """Calculates the Compound Annual Growth Rate."""
    if start_price <= 0: return 0
    return ((end_price / start_price) ** (1 / years) - 1) * 100

def run_portfolio_analysis(tickers, initial_inv=10000):
    results = []
    print(f"📊 Analyzing {len(tickers)} stocks and ranking by Quality Score...")

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            # 3-year historical data for simulation
            hist = stock.history(period="3y")
            if hist.empty: continue
            
            info = stock.info
            start_p = hist['Close'].iloc[0]
            end_p = hist['Close'].iloc[-1]
            
            # 1. Performance Metrics
            total_ret = ((end_p - start_p) / start_p) * 100
            cagr = calculate_cagr(start_p, end_p, years=3)
            growth_val = initial_inv * (1 + (total_ret / 100))
            
            # 2. Fundamental Quality Metrics
            rev_growth = info.get('revenueGrowth', 0)
            roe = info.get('returnOnEquity', 0)
            div_yield = info.get('dividendYield', 0)
            pe = info.get('forwardPE', 100)
            
            # Custom Quality Score Formula
            q_score = (rev_growth * 100) + (roe * 100) + (div_yield * 200) - (pe / 5)

            results.append({
                'Ticker': ticker,
                'Quality_Score': round(q_score, 2),
                'CAGR_%': round(cagr, 2),
                'Total_Return_%': round(total_ret, 2),
                'Growth_of_10k': round(growth_val, 2),
                'Div_Yield_%': round(div_yield * 100, 2) if div_yield else 0,
                'Forward_PE': round(pe, 2)
            })
            time.sleep(0.5)
        except Exception as e:
            print(f"Skipping {ticker}: {e}")

    # Create DataFrame and apply Global Rank
    df = pd.DataFrame(results)
    # Sort by Quality Score (highest first)
    df = df.sort_values(by='Quality_Score', ascending=False).reset_index(drop=True)
    
    # Add the Rank column
    df.insert(0, 'Global_Rank', df.index + 1)

    return df

# Example with a mix of Growth, Tech, and Dividend stocks
my_watchist = ['AAPL', 'MSFT', 'NVDA', 'AVGO', 'COST', 'PG', 'JPM', 'V', 'ABBV', 'XOM']
final_report = run_portfolio_analysis(my_watchist)

final_report.to_csv("Global_Whale_Rankings_2026.csv", index=False)
print("\n🏆 TOP 10 RANKED CANDIDATES:")
print(final_report[['Global_Rank', 'Ticker', 'Quality_Score', 'CAGR_%', 'Growth_of_10k']].head(10))
