import yfinance as yf
from typing import Dict, List
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re

import streamlit as st

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
        
        response = requests.get(url, headers=headers, timeout=3) # Reduced timeout to 3s
        if response.status_code != 200:
            return 0.0
            
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Selector found: .paper_rate .num
        price_span = soup.select_one('.paper_rate .num')
        if price_span:
            # Price might contain commas
            price_text = price_span.text.replace(',', '')
            # TASE prices are in Agorot, convert to Shekels
            return float(price_text) / 100.0
            
        return 0.0
    except Exception as e:
        print(f"Error fetching from Bizportal for {ticker_id}: {e}")
        return 0.0

@st.cache_data(ttl=1800, show_spinner=False)
def get_live_prices(tickers: List[str]) -> Dict[str, float]:
    """
    Fetch live prices with Smart Routing and Caching.
    - Numeric Tickers (e.g. 1184076) -> Direct to Bizportal (Fast)
    - Alpha Tickers (e.g. GOOG, BTC) -> Direct to Yahoo (Batch)
    Cache TTL: 30 minutes.
    """
    if not tickers:
        return {}
    
    prices = {}
    yf_tickers = []
    biz_tickers = []
    
    # 1. Sort Tickers
    for t in tickers:
        # Check if numeric (with optional .TA suffix)
        if re.match(r'^\d+(\.TA)?$', t):
            biz_tickers.append(t)
        else:
            yf_tickers.append(t)
            
    # 2. Fetch Bizportal (Sequential but fast for few items, can be async later)
    for t in biz_tickers:
        # print(f"DEBUG: Smart Routing {t} -> Bizportal")
        p = fetch_bizportal_price(t)
        prices[t] = p

    # 3. Fetch Yahoo (Batch)
    if yf_tickers:
        # print(f"DEBUG: Smart Routing {yf_tickers} -> Yahoo")
        try:
            # Use 5d to ensure data continuity
            data = yf.download(yf_tickers, period="5d", group_by="ticker", progress=False, threads=True)
            
            if not data.empty:
                for ticker in yf_tickers:
                    try:
                        price_found = False
                        last_price = None

                        # Handle Multi-Level Column
                        if isinstance(data.columns, pd.MultiIndex):
                            if ticker in data.columns:
                                ticker_df = data[ticker]
                                if 'Close' in ticker_df.columns:
                                    series = ticker_df['Close'].dropna()
                                    if not series.empty:
                                        last_price = series.iloc[-1]
                                        price_found = True
                        
                        # Handle Single Level (Flattened)
                        elif 'Close' in data.columns:
                            if len(yf_tickers) == 1 and yf_tickers[0] == ticker:
                                 series = data['Close'].dropna()
                                 if not series.empty:
                                    last_price = series.iloc[-1]
                                    price_found = True

                        if price_found and last_price is not None:
                            if hasattr(last_price, 'item'):
                                 prices[ticker] = float(last_price.item())
                            else:
                                 prices[ticker] = float(last_price)
                        else:
                            prices[ticker] = 0.0
                            
                    except Exception:
                        prices[ticker] = 0.0
        except Exception as e:
            print(f"Yahoo Batch Failed: {e}")
            
    # Ensure all requested tickers have a key (default 0)
    for t in tickers:
        if t not in prices:
            prices[t] = 0.0

    return prices

@st.cache_data(ttl=3600, show_spinner=False)
def get_usd_ils_rate() -> float:
    """Fetch realtime USD/ILS exchange rate. Cached for 1 hour."""
    try:
        ticker = "ILS=X"
        data = yf.download(ticker, period="1d", progress=False)
        rate = data['Close'].iloc[-1]
        if hasattr(rate, 'item'):
             rate = rate.item()
        return float(rate)
    except Exception:
        return 3.5 # Fallback conservative rate

def calculate_tax(asset, mkt_val, cost_basis, tax_settings):
    """
    Calculate tax liability based on asset category and specific rules.
    """
    tax = 0.0
    
    # 1. Pension / Fund (often flat tax on total or profit depending on type)
    if asset.category == 'Pension':
        # Assumption: 25% tax on total if withdrawn early, or standard rule
        # Using simple flat rate from settings for now
        tax = mkt_val * (asset.tax_rate if asset.tax_rate else 0.25)
        
    # 2. Bank / Brokerage / Crypto (Capital Gains)
    elif asset.category in ['Bank Account', 'Crypto', 'Fund']:
        gain = mkt_val - cost_basis
        if gain > 0:
            rate = asset.tax_rate if asset.tax_rate else tax_settings.tax_rate_capital_gains
            tax = gain * rate
            
    # 3. Work / GSUs (Income + Capital Gains)
    elif asset.category == 'Work':
        # Simplified: Treat entire amount or gain based on vesting.
        # For now, simplistic approach: (Mkt - Cost) * CapGains
        # Real GSU logic will be handled in separate GSU module, this is for standard 'Work' stocks
        gain = mkt_val - cost_basis
        if gain > 0:
            # Usually work stocks have income tax component on vest
            # Here we assume post-vest holding
            tax = gain * tax_settings.tax_rate_capital_gains

    return tax

def process_portfolio(assets, prices, fx_rate, settings):
    """
    Process all assets to calculate Market Value, Tax, and Allocations.
    Returns:
        - summary: Dict of totals (Net Worth, Post Tax, SWR, FV, Bucket Allocations)
        - positions: List of processed asset dicts
    """
    summary = {
        'total_net_worth': 0.0,
        'total_after_tax': 0.0,
        'swr_monthly': 0.0,
        'future_value_40y': 0.0,
        'allocations': {
            'IL Stocks': 0.0, 
            'US Stocks': 0.0, 
            'Crypto': 0.0, 
            'Work': 0.0, # Maps to GSUs + MSFT
            'Bonds': 0.0, # Mid-Long
            'Cash': 0.0   # Short Term
        }
    }
    
    processed_positions = []
    
    for asset in assets:
        # 1. Price Lookup
        sym = asset.ticker.strip()
        if asset.type == 'Cryptocurrency' and '-' not in sym:
             sym = f"{sym}-{asset.currency}"
             
        p_live = prices.get(sym, 0.0)
        p = asset.manual_price if (asset.manual_price is not None and asset.manual_price > 0) else p_live
        
        # 2. Market Value (in ILS)
        qty = asset.quantity
        mkt_val_local = p * qty
        cost_basis_local = asset.cost_basis
        
        if asset.currency == 'USD':
            mkt_val_ils = mkt_val_local * fx_rate
            cost_basis_ils = cost_basis_local * fx_rate
        else:
            mkt_val_ils = mkt_val_local
            cost_basis_ils = cost_basis_local
            
        # 3. Tax Liability
        # Use settings for generic logic, or asset specific overrides
        # Future Needs (Liability) usually has 0 tax, just negative value
        tax_ils = calculate_tax(asset, mkt_val_ils, cost_basis_ils, settings)
        net_after_tax = mkt_val_ils - tax_ils
        
        # 4. Aggregation
        summary['total_net_worth'] += mkt_val_ils
        summary['total_after_tax'] += net_after_tax
        
        # 5. Allocation Mapping (Risk Buckets)
        # Verify if asset is a "Liability" (Future Needs) -> Exclude from Buckets
        if asset.category == "Future Needs" or mkt_val_ils < 0:
            pass # Do not add to investment buckets
        else:
            # Check for Splits (Stored as 0.0 - 1.0 floats)
            total_split = (asset.alloc_il_stock_pct + asset.alloc_us_stock_pct + 
                           asset.alloc_crypto_pct + asset.alloc_work_pct +
                           asset.alloc_bonds_pct + asset.alloc_cash_pct)
            
            # If splits defined (allow for float rounding errors close to 1.0)
            if total_split > 0.01:
                summary['allocations']['IL Stocks'] += mkt_val_ils * asset.alloc_il_stock_pct
                summary['allocations']['US Stocks'] += mkt_val_ils * asset.alloc_us_stock_pct
                summary['allocations']['Crypto']    += mkt_val_ils * asset.alloc_crypto_pct
                summary['allocations']['Work']      += mkt_val_ils * asset.alloc_work_pct
                summary['allocations']['Bonds']     += mkt_val_ils * asset.alloc_bonds_pct
                summary['allocations']['Cash']      += mkt_val_ils * asset.alloc_cash_pct
            else:
                # Fallback Logic (Auto-Categorize) based on Type/Ticker
                if asset.type == 'Cryptocurrency': 
                     summary['allocations']['Crypto'] += mkt_val_ils
                elif asset.category == 'Work' or asset.ticker == 'MSFT': 
                     summary['allocations']['Work'] += mkt_val_ils
                elif "Bond" in asset.name or "Gov" in asset.name: 
                     summary['allocations']['Bonds'] += mkt_val_ils
                elif asset.type == 'Cash' or "Deposit" in asset.name:
                     summary['allocations']['Cash'] += mkt_val_ils
                elif asset.currency == 'USD': 
                     summary['allocations']['US Stocks'] += mkt_val_ils
                else: 
                     summary['allocations']['IL Stocks'] += mkt_val_ils

        processed_positions.append({
            'asset': asset,
            'price': p,
            'mkt_val_ils': mkt_val_ils,
            'tax_ils': tax_ils,
            'net_after_tax': net_after_tax
        })

    # 6. Projections
    # SWR: Based on After Tax Value (and if crypto included? User setting handles this visibility, 
    # but math often excludes high-volatility? Let's assume inclusive for now based on 'Total')
    swr_rate = settings.swr_rate if hasattr(settings, 'swr_rate') else 0.04
    summary['swr_monthly'] = (summary['total_after_tax'] * swr_rate) / 12
    
    # Future Value (Simplistic Compound Interest for illustration)
    # Assume global real return of 5% conservative
    fv_rate = 1.05
    summary['future_value_40y'] = summary['total_after_tax'] * (fv_rate ** 40)
    
    return summary, processed_positions
