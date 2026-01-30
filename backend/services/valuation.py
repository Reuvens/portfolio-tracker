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
    data = yf.download(tickers, period="5d", group_by="ticker", progress=False)
    
    prices = {}
    for ticker in tickers:
        try:
            price_found = False
            ticker_data = None
            
            # Check structure: MultiIndex with Ticker at Level 0
            if ticker in data.columns:
                ticker_data = data[ticker]
            # Check structure: Flat (if single ticker might have been flattened)
            elif 'Close' in data.columns:
                ticker_data = data
            
            if ticker_data is not None and not ticker_data.empty:
                 if 'Close' in ticker_data.columns:
                    price = ticker_data['Close'].iloc[-1]
                    if hasattr(price, 'item'): 
                         price = price.item() # convert numpy to native float
                    
                    if not pd.isna(price):
                        prices[ticker] = float(price)
                        price_found = True

            if not price_found:
                # Fallback Logic for TASE tickers (numeric)
                if re.match(r'^\d+(\.TA)?$', ticker):
                    print(f"yfinance failed for {ticker}, trying Bizportal fallback...")
                    fallback_price = fetch_bizportal_price(ticker)
                    if fallback_price > 0:
                        prices[ticker] = fallback_price
                        price_found = True
            
            if not price_found:
                 prices[ticker] = 0.0 # Final Fallback

        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            prices[ticker] = 0.0 # Fallback
            
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
