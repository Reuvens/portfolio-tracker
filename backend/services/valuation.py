import yfinance as yf
from typing import Dict, List
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re

def fetch_bizportal_price(ticker_id: str) -> float:
    """Fallback: Fetch price from Bizportal for TASE securities."""
    try:
        # Remove .TA suffix if present for the ID
        clean_id = ticker_id.replace('.TA', '')
        
        # Bizportal URL structure
        url = f"https://www.bizportal.co.il/capitalmarket/quote/general/{clean_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code != 200:
            return 0.0
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Selector found: .paper_rate .num
        price_span = soup.select_one('.paper_rate .num')
        if price_span:
            # Price might contain commas
            price_text = price_span.text.replace(',', '')
            return float(price_text)
            
        return 0.0
    except Exception as e:
        print(f"Error fetching from Bizportal for {ticker_id}: {e}")
        return 0.0

def get_live_prices(tickers: List[str]) -> Dict[str, float]:
    """
    Fetch live prices for a list of tickers using yfinance.
    Handles US tickers (e.g. 'GOOG') and potentially IL tickers if suffixed correctly (e.g. '1184076.TA').
    Falls back to Bizportal for numeric TASE tickers if yfinance fails.
    """
    if not tickers:
        return {}
    
    # yfinance allows bulk download
    # Use 5d to ensure we get data even if market is closed (e.g. Friday for TASE)
    try:
        data = yf.download(tickers, period="5d", group_by="ticker", progress=False)
    except Exception as e:
        print(f"yfinance bulk download failed: {e}")
        return {}
    
    prices = {}
    
    # Check if data is empty
    if data.empty:
        return prices

    for ticker in tickers:
        try:
            price_found = False
            last_price = None

            # 1. Handle Multi-Level Column (Result of multiple tickers)
            if isinstance(data.columns, pd.MultiIndex):
                if ticker in data.columns:
                    ticker_df = data[ticker]
                    if 'Close' in ticker_df.columns:
                        series = ticker_df['Close'].dropna()
                        if not series.empty:
                            last_price = series.iloc[-1]
                            price_found = True
            
            # 2. Handle Single Level Column (Result of single ticker or flattened)
            elif 'Close' in data.columns:
                # If only one ticker was requested, or yf returned flat structure
                if len(tickers) == 1 and tickers[0] == ticker:
                     series = data['Close'].dropna()
                     if not series.empty:
                        last_price = series.iloc[-1]
                        price_found = True
                else: 
                     # Should ideally be caught by MultiIndex case, but safety net
                     pass

            if price_found and last_price is not None:
                if hasattr(last_price, 'item'):
                     prices[ticker] = float(last_price.item())
                else:
                     prices[ticker] = float(last_price)
            else:
                # Fallback Logic for TASE tickers (numeric)
                if re.match(r'^\d+(\.TA)?$', ticker):
                    print(f"yfinance failed for {ticker}, trying Bizportal fallback...")
                    fallback_price = fetch_bizportal_price(ticker)
                    if fallback_price > 0:
                        prices[ticker] = fallback_price

            if ticker not in prices:
                 prices[ticker] = 0.0 # Default to 0.0 if absolutely nothing found

        except Exception as e:
            print(f"Error extracting price for {ticker}: {e}")
            prices[ticker] = 0.0
            
    return prices

def get_usd_ils_rate() -> float:
    """Fetch realtime USD/ILS exchange rate."""
    try:
        ticker = "ILS=X"
        data = yf.download(ticker, period="1d", progress=False)
        rate = data['Close'].iloc[-1]
        if hasattr(rate, 'item'):
             rate = rate.item()
        return float(rate)
    except Exception:
        return 3.5 # Fallback conservative rate
