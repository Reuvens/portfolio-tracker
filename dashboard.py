import streamlit as st
import pandas as pd
import numpy as np
from backend.services.valuation import get_live_prices, get_usd_ils_rate
from backend.services.tax import calculate_tax_liability
from backend.database import engine, create_db_and_tables, models
from sqlmodel import Session, select
import plotly.graph_objects as go
import plotly.express as px

# Map the Asset model
Asset = models.Asset

# Ensure database and tables exist
@st.cache_resource
def init_db():
    create_db_and_tables()

init_db()

st.set_page_config(page_title="Portfolio Manager", layout="wide", initial_sidebar_state="collapsed")

# --- PREMIUM DARK UI CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Global Reset & Theme */
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Inter', sans-serif;
        background-color: #020617; /* bg-slate-950 */
        color: #F8FAFC; /* text-slate-50 */
    }
    
    /* Responsive Container */
    [data-testid="stMainBlockContainer"] {
        max-width: 1280px;
        margin: 0 auto;
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    [data-testid="stHeader"] {
        background-color: transparent;
    }
    
    /* Custom Responsive Columns */
    /* Force stacking on small screens if native Streamlit doesn't behave */
    @media (max-width: 768px) {
        [data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
        }
    }

    /* Headings */
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Inter', sans-serif;
        color: #F8FAFC;
    }

    /* Cards */
    .card {
        background-color: rgba(15, 23, 42, 0.6); /* bg-slate-900/60 */
        border: 1px solid #1E293B; /* border-slate-800 */
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        backdrop-filter: blur(8px);
    }
    
    .card h3 {
        margin-top: 0;
        font-size: 1.125rem;
        font-weight: 600;
        color: #CBD5E1; /* text-slate-300 */
        margin-bottom: 1rem;
    }

    /* Metrics */
    .metric-label {
        color: #94A3B8; /* text-slate-400 */
        font-size: 0.875rem;
        font-weight: 500;
    }
    
    .metric-value {
        color: #F8FAFC;
        font-size: 2.25rem;
        font-weight: 700;
        line-height: 1.2;
    }
    
    .metric-trend {
        font-size: 0.875rem;
        font-weight: 600;
        display: flex;
        align-items: center;
        gap: 0.25rem;
    }
    
    .text-emerald { color: #34D399; }
    .text-rose { color: #FB7185; }
    
    /* Asset Icon Fix - No White Overlay */
    .asset-icon {
        width: 40px;
        height: 40px;
        background-color: #1E293B; /* Slate 800 */
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        color: #F8FAFC;
        font-size: 0.875rem;
        margin-right: 1rem;
        flex-shrink: 0;
        z-index: 10; /* Ensure it stays above */
    }
    
    .badge {
        font-size: 0.7rem;
        padding: 0.15rem 0.5rem;
        border-radius: 9999px;
        font-weight: 600;
        background-color: #1E293B;
        color: #94A3B8;
        display: inline-block;
        margin-top: 0.25rem;
    }

    /* Buttons */
    .stButton button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s;
    }
    
    /* Add Position Button Style */
    div[data-testid="stHorizontalBlock"] button[kind="secondary"] {
         background-color: #059669; 
         color: white; border: none;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
        border-bottom: 1px solid #1E293B;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: nowrap;
        background-color: transparent;
        border: none;
        color: #94A3B8;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        color: #34D399; /* emerald-400 */
        border-bottom: 2px solid #34D399;
    }

    /* Inputs - Dark Theme Fix */
    .stTextInput input, .stNumberInput input, .stTextArea textarea, .stSelectbox [data-baseweb="select"] > div {
        background-color: #1E293B !important; /* bg-slate-800 */
        color: white !important;
        border: 1px solid #334155 !important;
        border-radius: 6px;
    }
    
    /* Modal / Form Styling */
    div[data-testid="stForm"] {
        background-color: #020617;
        border: 1px solid #1E293B;
        border-radius: 12px;
        padding: 2rem;
    }

</style>
""", unsafe_allow_html=True)

# --- Data Helpers ---
def get_assets():
    with Session(engine) as session:
        return session.exec(select(Asset)).all()

def add_asset(name, ticker, quantity, cost_per_unit, asset_type, currency, account_type, liquidity, allocation_bucket, notes, manual_price):
    with Session(engine) as session:
        asset = Asset(
            user_id=1,
            type=asset_type,
            name=name,
            ticker=ticker,
            quantity=quantity,
            cost_per_unit=cost_per_unit,
            cost_basis=quantity * cost_per_unit,
            currency=currency,
            account_type=account_type,
            liquidity=liquidity,
            allocation_bucket=allocation_bucket,
            notes=notes,
            manual_price=manual_price
        )

        session.add(asset)
        session.commit()

def update_asset(asset_id, name, ticker, quantity, cost_per_unit, asset_type, currency, account_type, liquidity, allocation_bucket, notes, manual_price):
    with Session(engine) as session:
        asset = session.get(Asset, asset_id)
        if asset:
            asset.name = name
            asset.ticker = ticker
            asset.quantity = quantity
            asset.cost_per_unit = cost_per_unit
            asset.cost_basis = quantity * cost_per_unit
            asset.type = asset_type
            asset.currency = currency
            asset.account_type = account_type
            asset.liquidity = liquidity
            asset.allocation_bucket = allocation_bucket
            asset.notes = notes
            asset.manual_price = manual_price
            session.add(asset)
            session.commit()
            return True
    return False

def delete_asset(asset_id):
    with Session(engine) as session:
        asset = session.get(Asset, asset_id)
        if asset:
            session.delete(asset)
            session.commit()
            return True
    return False

# --- FX Rate Fetching ---
if 'current_fx' not in st.session_state:
    st.session_state.current_fx = get_usd_ils_rate()
fx_rate = st.session_state.current_fx

# --- Top Header ---
st.markdown(f"""
<div class="main-header">
    <div>
        <h2 style='margin:0; font-size:1.5rem; font-weight:700; color:#F8FAFC;'>Portfolio Manager</h2>
        <div style='display:flex; align-items:center; gap:8px;'>
            <span style='font-size:0.875rem; color:#94A3B8;'>Welcome, User</span>
            <span style='font-size:0.75rem; background:#1E293B; padding:2px 6px; border-radius:4px; color:#64748B;'>USD/ILS: {fx_rate:.2f}</span>
        </div>
    </div>
    <div style="display:flex; gap:1rem; align-items:center;">
        <div style='color:#64748B; cursor:pointer;'>⚙️</div>
    </div>
</div>
""", unsafe_allow_html=True)

# "Add Position" button in a cleaner spot or just use the header action
# The reference has a primary button in the header. We can't easily put a st.button inside raw HTML.
# So we use a column layout just for the right side of the header effectively.
# Actually, let's keep it simple: Text on left, Button on right.

h_col1, h_col2 = st.columns([3, 1])
with h_col2:
    if st.button("✚ Add Position", key="add_pos_btn", use_container_width=True):
        # Clear edit state
        keys_to_clear = ['edit_id', 'f_n', 'f_t', 'f_q', 'f_c', 'f_curr', 'f_type', 'f_acct', 'f_liq', 'f_alloc', 'f_notes', 'f_man_p']
        for k in keys_to_clear:
            if k in st.session_state: del st.session_state[k]
        st.session_state.show_add_form = True

# --- Add Asset Dialog ---
if st.session_state.get('show_add_form', False):
    # CSS is handled globally now for div[data-testid="stForm"]
    
    with st.container():
        # Header with Close Button
        c_h1, c_h2 = st.columns([1, 0.1])
        is_edit = 'edit_id' in st.session_state
        c_h1.markdown(f"<h3 style='color:white; font-size:1.25rem; margin-bottom:1rem;'>{'Edit Position' if is_edit else 'Add New Position'}</h3>", unsafe_allow_html=True)
        
        if c_h2.button("✕", key="close_form_x"):
            st.session_state.show_add_form = False
            st.rerun()

        with st.form("add_asset_form_rev"):
            # Defaults
            d_name = st.session_state.get('f_n', '')
            d_ticker = st.session_state.get('f_t', '')
            d_qty = st.session_state.get('f_q', 0.0)
            d_cost = st.session_state.get('f_c', 0.0)
            d_curr = st.session_state.get('f_curr', 'USD')
            d_type = st.session_state.get('f_type', 'US Stock/ETF')
            d_acct = st.session_state.get('f_acct', 'Brokerage')
            d_liq = st.session_state.get('f_liq', 'Liquid')
            d_alloc = st.session_state.get('f_alloc', 'Auto-assign')
            d_notes = st.session_state.get('f_notes', '')
            d_man_p = st.session_state.get('f_man_p', '')

            # Asset Type (Full Width)
            curr_idx_type = ["US Stock/ETF", "Israeli Stock", "Israeli Corporate Bond", "Israeli Gov Bond", "Cryptocurrency", "Cash/Deposit", "GSU/RSU"].index(d_type) if d_type in ["US Stock/ETF", "Israeli Stock", "Israeli Corporate Bond", "Israeli Gov Bond", "Cryptocurrency", "Cash/Deposit", "GSU/RSU"] else 0
            ftype = st.selectbox("Asset Type", ["US Stock/ETF", "Israeli Stock", "Israeli Corporate Bond", "Israeli Gov Bond", "Cryptocurrency", "Cash/Deposit", "GSU/RSU"], index=curr_idx_type)
            
            # Row 2: Ticker | Name
            r2_1, r2_2 = st.columns(2)
            fticker = r2_1.text_input("Ticker / Symbol", value=d_ticker, placeholder="e.g., GOOG, 1184076")
            fname = r2_2.text_input("Name", value=d_name, placeholder="Display name")
            
            # Row 3: Quantity | Cost Basis
            r3_1, r3_2 = st.columns(2)
            fqty = r3_1.number_input("Quantity", value=float(d_qty), min_value=0.0, step=0.01, format="%.4f")
            fcost = r3_2.number_input("Cost Basis (per unit)", value=float(d_cost), min_value=0.0, step=0.01, format="%.2f")
            
            # Row 4: Currency | Current Price
            r4_1, r4_2 = st.columns(2)
            curr_opts = ["USD", "ILS"]
            c_idx = curr_opts.index(d_curr) if d_curr in curr_opts else 0
            fcurr = r4_1.selectbox("Currency", curr_opts, index=c_idx)
            fprice_override = r4_2.text_input("Current Price (optional override)", value=str(d_man_p) if d_man_p else "", placeholder="Auto-fetch if empty")
            
            # Row 5: Account Type | Liquidity
            r5_1, r5_2 = st.columns(2)
            acct_opts = ["Brokerage", "Tax Advantaged", "Pension", "Wallet"]
            a_idx = acct_opts.index(d_acct) if d_acct in acct_opts else 0
            f_acct_type = r5_1.selectbox("Account Type", acct_opts, index=a_idx)
            
            liq_opts = ["Liquid", "Semi-Liquid", "Illiquid"]
            l_idx = liq_opts.index(d_liq) if d_liq in liq_opts else 0
            f_liquidity = r5_2.selectbox("Liquidity", liq_opts, index=l_idx)
            
            # Allocation Bucket
            alo_opts = ["Auto-assign", "US Equity", "IL Equity", "Fixed Income", "Crypto", "Cash"]
            al_idx = alo_opts.index(d_alloc) if d_alloc in alo_opts else 0
            f_alloc = st.selectbox("Allocation Bucket", alo_opts, index=al_idx)
            
            # Notes
            f_notes = st.text_area("Notes", value=d_notes, placeholder="Optional notes")
            
            st.write("")
            st.write("")
            
            # Actions
            col_actions = st.columns([1, 0.3, 0.3])
            submitted = st.form_submit_button("💾 Update Position" if is_edit else "＋ Add Position", use_container_width=True, type="primary")
            
            if submitted:
                 alloc_val = None if f_alloc == "Auto-assign" else f_alloc
                 try:
                     man_p = float(fprice_override) if fprice_override.strip() else None
                 except ValueError:
                     man_p = None
                 
                 if is_edit:
                     update_asset(st.session_state.edit_id, fname, fticker, fqty, fcost, ftype, fcurr, f_acct_type, f_liquidity, alloc_val, f_notes, man_p)
                 else:
                     add_asset(fname, fticker, fqty, fcost, ftype, fcurr, f_acct_type, f_liquidity, alloc_val, f_notes, man_p)
                     
                 st.session_state.show_add_form = False
                 # Clear keys
                 for k in ['edit_id', 'f_n', 'f_t', 'f_q', 'f_c', 'f_curr', 'f_type', 'f_acct', 'f_liq', 'f_alloc', 'f_notes', 'f_man_p']:
                     if k in st.session_state: del st.session_state[k]
                 st.rerun()
                 
        if st.button("Cancel", key="cancel_form_btn"):
             st.session_state.show_add_form = False
             st.rerun()
             
        st.markdown("</div>", unsafe_allow_html=True)

# --- Main Dashboard Logic ---
assets_list = get_assets()

if not assets_list:
    st.info("Your portfolio is currently empty. Click 'Add Position' to begin.")
else:
    # Create Ticker List
    tickers_to_fetch = set()
    for asset in assets_list:
        sym = asset.ticker.strip()
        # Crypto handling
        if asset.type == 'Cryptocurrency' and '-' not in sym:
             sym = f"{sym}-{asset.currency}"
        tickers_to_fetch.add(sym)

    # Fetch Prices
    current_prices = get_live_prices(list(tickers_to_fetch))
    
    processed_data = []
    total_mkt_ils = 0
    total_tax_liab_ils = 0
    total_cost_basis_ils = 0

    for asset in assets_list:
        # Re-derive symbol to lookup price
        sym = asset.ticker.strip()
        if asset.type == 'Cryptocurrency' and '-' not in sym:
             sym = f"{sym}-{asset.currency}"
             
        p_live = current_prices.get(sym, 0.0)
        p = asset.manual_price if (asset.manual_price is not None and asset.manual_price > 0) else p_live
        
        # Determine Market Value
        mkt_v_local = p * asset.quantity
        
        if asset.currency == "USD":
             mkt_v_ils = mkt_v_local * fx_rate
             cost_v_ils = asset.cost_basis * fx_rate
        else:
             mkt_v_ils = mkt_v_local
             cost_v_ils = asset.cost_basis
             
        # Use simple tax calculation
        tax_v = calculate_tax_liability(mkt_v_ils, cost_v_ils, asset.type)
        
        total_mkt_ils += mkt_v_ils
        total_tax_liab_ils += tax_v
        total_cost_basis_ils += cost_v_ils
        
        gain_abs = mkt_v_ils - cost_v_ils
        gain_p = (gain_abs / cost_v_ils * 100) if cost_v_ils > 0 else 0
        
        processed_data.append({
            "id": asset.id,
            "ticker": asset.ticker,
            "name": asset.name,
            "type": asset.type,
            "qty": asset.quantity,
            "price": p,
            "val_ils": mkt_v_ils,
            "tax": tax_v,
            "net_after_tax": mkt_v_ils - tax_v,
            "gain_pct": gain_p,
            "currency": asset.currency,
            "cpu": asset.cost_per_unit
        })

    # --- TWO COLUMN DASHBOARD LAYOUT ---
    col_dash_l, col_dash_r = st.columns([1, 2.2])

    # --- LEFT SIDEBAR (Metrics) ---
    with col_dash_l:
        # Net Worth Card
        net_worth_trend = total_mkt_ils - total_cost_basis_ils
        nw_trend_pct = (net_worth_trend / total_cost_basis_ils * 100) if total_cost_basis_ils > 0 else 0
        
        st.markdown(f"""
            <div class="card">
                <div style="display:flex; justify-content:space-between; margin-bottom:0.5rem;">
                    <span class="metric-label">Total Net Worth</span>
                    <span class="badge" style="background:rgba(255,255,255,0.05);">ILS</span>
                </div>
                <div class="metric-value">{total_mkt_ils:,.0f}₪</div>
                <div class="metric-trend {'text-emerald' if net_worth_trend >=0 else 'text-rose'}" style="margin-top:0.5rem;">
                    {'↗' if net_worth_trend >=0 else '↘'} {nw_trend_pct:+.1f}% <span style="color:#64748B; font-weight:400; margin-left:4px;">(₪{abs(net_worth_trend):,.0f})</span>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # Asset Allocation Donut
        st.markdown("<h3 style='font-size:1rem; margin-bottom:1rem; padding-left:4px;'>Asset Allocation</h3>", unsafe_allow_html=True)
        df_p = pd.DataFrame(processed_data)
        allocation = df_p.groupby("type")["val_ils"].sum().reset_index()
        fig_don = px.pie(allocation, values='val_ils', names='type', hole=0.7, 
                         color_discrete_sequence=['#3B82F6', '#8B5CF6', '#F59E0B', '#10B981', '#EC4899', '#6366F1'])
        fig_don.update_layout(showlegend=True, margin=dict(t=0, b=0, l=0, r=0), height=300,
                              paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                              legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5, font=dict(color="#94A3B8", size=11)))
        st.plotly_chart(fig_don, use_container_width=True, config={'displayModeBar': False})

        # Liquidity Breakdown
        st.markdown("<div class='card' style='padding:1.25rem; margin-top:2rem;'>", unsafe_allow_html=True)
        st.markdown("<h3 style='margin-bottom:1rem;'>Liquidity</h3>", unsafe_allow_html=True)
        l_liq = sum(x['val_ils'] for x in processed_data if x['type'] in ['Cash/Deposit', 'Israeli Gov Bond', 'Israeli Corporate Bond'])
        l_semi = sum(x['val_ils'] for x in processed_data if x['type'] in ['US Stock/ETF', 'Israeli Stock', 'GSU/RSU'])
        l_illiq = sum(x['val_ils'] for x in processed_data if x['type'] == 'Cryptocurrency')
        
        for name, val, color in [("Liquid", l_liq, "#10B981"), ("Semi-Liquid", l_semi, "#3B82F6"), ("Illiquid", l_illiq, "#8B5CF6")]:
            pct = (val / total_mkt_ils * 100) if total_mkt_ils > 0 else 0
            st.markdown(f"""
                <div style="margin-bottom:1rem;">
                    <div style="display:flex; justify-content:space-between; font-size:0.8rem; font-weight:500; margin-bottom:4px;">
                        <span style="color:#CBD5E1;">{name}</span>
                        <span style="color:white;">{val:,.0f}₪</span>
                    </div>
                    <div class="progress-bar-bg"><div class="progress-bar-fill" style="width:{pct}%; background:{color};"></div></div>
                </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # Tax Info
        st.markdown(f"""
            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:1rem;">
                <div class="card" style="padding:1rem; margin-bottom:0;">
                    <div class="metric-label" style="font-size:0.75rem;">Est. Tax Liability</div>
                    <div style="font-size:1.1rem; font-weight:700; color:#F59E0B; margin-top:4px;">{total_tax_liab_ils:,.0f}₪</div>
                </div>
                <div class="card" style="padding:1rem; margin-bottom:0;">
                    <div class="metric-label" style="font-size:0.75rem;">Net After Tax</div>
                    <div style="font-size:1.1rem; font-weight:700; color:#10B981; margin-top:4px;">{(total_mkt_ils - total_tax_liab_ils):,.0f}₪</div>
                </div>
            </div>
        """, unsafe_allow_html=True)


    # --- RIGHT CONTENT (Holdings & Projections) ---
    with col_dash_r:
        
        # Tabs for differnet views
        tab_holdings, tab_plan, tab_proj = st.tabs(["Holdings", "Rebalancing Plan", "Projections"])
        
        # TAB 1: HOLDINGS
        with tab_holdings:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            t_col1, t_col2 = st.columns([3, 1])
            t_col1.markdown("<h3>Your Assets</h3>", unsafe_allow_html=True)
            if t_col2.button("🔄 Refresh Data", key="refresh_main"):
                 st.session_state.current_fx = get_usd_ils_rate()
                 st.rerun()

            st.write("")
            
            # Table Header
            st.markdown("""
            <div style="display: grid; grid-template-columns: 1.5fr 1fr 1fr 1fr 0.5fr; padding: 0.75rem 1rem; border-bottom: 1px solid #334155; color: #94A3B8; font-size: 0.75rem; font-weight: 600; text-transform: uppercase;">
                <div>Asset</div>
                <div style="text-align:right">Price</div>
                <div style="text-align:right">Value (ILS)</div>
                <div style="text-align:right">Return</div>
                <div style="text-align:center">Actions</div>
            </div>
            """, unsafe_allow_html=True)

            for item in processed_data:
                initials = item['ticker'][:2].upper() if not item['ticker'][0].isdigit() else "IL"
                is_positive = item['gain_pct'] >= 0
                trend_color = "#10B981" if is_positive else "#FB7185"
                trend_arrow = "↗" if is_positive else "↘"
                
                # Render Row
                st.markdown(f"""
                <div class="asset-row" style="display: grid; grid-template-columns: 1.5fr 1fr 1fr 1fr 0.5fr; align-items: center;">
                    <div style="display:flex; align-items:center;">
                        <div class="asset-icon">{initials}</div>
                        <div>
                            <div style="font-weight:600; font-size:0.95rem; color:#F8FAFC;">{item['name']}</div>
                            <div style="font-size:0.75rem; color:#64748B; margin-top:2px;">
                                <span style="background:#1E293B; padding:1px 4px; border-radius:4px;">{item['ticker']}</span> • {item['type']}
                            </div>
                        </div>
                    </div>
                    <div style="text-align:right;">
                        <div style="color:#E2E8F0; font-weight:500;">{item['currency']} {item['price']:,.2f}</div>
                        <div style="font-size:0.75rem; color:#64748B;">x {item['qty']}</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-weight:700; color:#F8FAFC;">{item['val_ils']:,.0f}₪</div>
                        <div style="font-size:0.75rem; color:#64748B;">Net: {(item['net_after_tax']):,.0f}₪</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="color:{trend_color}; font-weight:600; background:rgba(255,255,255,0.03); padding:2px 6px; border-radius:6px; display:inline-block;">
                            {trend_arrow} {item['gain_pct']:+.1f}%
                        </div>
                    </div>
                    <div style="text-align:center; display:flex; justify-content:center; gap:8px;">
                        <!-- Actions injected via python columns below to make buttons workable -->
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Hacky overlay for buttons because st.button cannot be inside HTML
                # We place a container matching the row height? No, standard streamlit buttons block flow.
                # Alternative: Use columns for the whole row.
                # Let's try re-implementing the row using st.columns to allow buttons.
                
            # --- RE-IMPLEMENTATION WITH COLUMNS FOR INTERACTIVITY ---
            # To fix the button issue, we must use st.columns for the row structure.
            # We will hide the previous HTML block and use this instead for the list.
            st.markdown("<style>.asset-row { display:none !important; }</style>", unsafe_allow_html=True) 
            
            for item in processed_data:
                initials = item['ticker'][:2].upper() if not item['ticker'][0].isdigit() else "IL"
                is_positive = item['gain_pct'] >= 0
                trend_color = "#10B981" if is_positive else "#FB7185"
                
                with st.container():
                     c1, c2, c3, c4, c5 = st.columns([1.8, 1, 1, 1, 0.6])
                     with c1:
                        st.markdown(f"""
                        <div style="display:flex; align-items:center; padding:0.5rem 0;">
                            <div class="asset-icon">{initials}</div>
                            <div>
                                <div style="font-weight:600; color:#F8FAFC; font-size:0.95rem;">{item['name']}</div>
                                <div style="display:flex; align-items:center; gap:6px; margin-top:2px;">
                                    <span style="font-size:0.75rem; color:#94A3B8;">{item['ticker']}</span>
                                    <span class="badge">{item['type']}</span>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                     with c2:
                         st.markdown(f"<div style='text-align:right; padding-top:10px; font-size:0.9rem;'>{item['currency']} {item['price']:,.2f}<br><span style='font-size:0.75rem; color:#64748B;'>x {item['qty']}</span></div>", unsafe_allow_html=True)
                     with c3:
                         st.markdown(f"<div style='text-align:right; padding-top:10px; font-weight:600;'>{item['val_ils']:,.0f}₪<br><span style='font-size:0.75rem; color:#64748B;'>Net: {item['net_after_tax']:,.0f}</span></div>", unsafe_allow_html=True)
                     with c4:
                         st.markdown(f"<div style='text-align:right; padding-top:12px; color:{trend_color}; font-weight:600;'>{item['gain_pct']:+.1f}%</div>", unsafe_allow_html=True)
                     with c5:
                         st.write("")
                         b_c1, b_c2 = st.columns(2)
                         with b_c1:
                             if st.button("✎", key=f"e_{item['id']}", help="Edit"):
                                 st.session_state.edit_id = item['id']
                                 # Populate logic (same as before)
                                 st.session_state.f_n = item['name']
                                 st.session_state.f_t = item['ticker']
                                 st.session_state.f_q = item['qty']
                                 st.session_state.f_c = item['cpu']
                                 st.session_state.f_curr = item['currency']
                                 st.session_state.f_type = item['type']
                                 
                                 with Session(engine) as session:
                                    a_full = session.get(Asset, item['id'])
                                    if a_full:
                                        st.session_state.f_acct = a_full.account_type
                                        st.session_state.f_liq = a_full.liquidity
                                        st.session_state.f_alloc = a_full.allocation_bucket if a_full.allocation_bucket else "Auto-assign"
                                        st.session_state.f_notes = a_full.notes if a_full.notes else ""
                                        st.session_state.f_man_p = a_full.manual_price
                                 
                                 st.session_state.show_add_form = True
                                 st.rerun()
                         with b_c2:
                             if st.button("✕", key=f"d_{item['id']}", help="Delete"):
                                 delete_asset(item['id'])
                                 st.rerun()
                     st.markdown("<div style='height:1px; background:#1E293B; margin:4px 0;'></div>", unsafe_allow_html=True)
                     
            st.markdown("</div>", unsafe_allow_html=True)

        # TAB 2: REBALANCING
        with tab_plan:
             st.markdown("<div class='card'>", unsafe_allow_html=True)
             st.markdown("<h3>Rebalancing Plan</h3>", unsafe_allow_html=True)
             targets_map = {
                "US Stock/ETF": 35, "GSU/RSU": 5, "Israeli Stock": 10, 
                "Israeli Gov Bond": 10, "Israeli Corporate Bond": 5,
                "Cryptocurrency": 5, "Cash/Deposit": 30
             }
             
             for cat, target_pct in targets_map.items():
                cat_sum = sum(x['val_ils'] for x in processed_data if x['type'] == cat)
                curr_pct = (cat_sum / total_mkt_ils * 100) if total_mkt_ils > 0 else 0
                diff_ils = (total_mkt_ils * target_pct / 100) - cat_sum
                is_buy = diff_ils >= 0
                
                st.markdown(f"""
                <div style="margin-bottom:1.5rem;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-weight:600; color:#E2E8F0;">{cat}</span>
                        <span class="badge" style="background:{'rgba(16, 185, 129, 0.2)' if is_buy else 'rgba(239, 68, 68, 0.2)'}; color:{'#34D399' if is_buy else '#F87171'};">
                            {'BUY' if is_buy else 'SELL'} {abs(diff_ils):,.0f}₪
                        </span>
                    </div>
                    <div style="display:flex; justify-content:space-between; font-size:0.75rem; color:#94A3B8; margin-top:4px;">
                        <span>Actual: {curr_pct:.1f}%</span>
                        <span>Target: {target_pct}%</span>
                    </div>
                    <div class="progress-bar-bg"><div class="progress-bar-fill" style="width:{min(curr_pct, 100)}%; background:#3B82F6;"></div></div>
                </div>
                """, unsafe_allow_html=True)
             st.markdown("</div>", unsafe_allow_html=True)
             
        # TAB 3: PROJECTIONS
        with tab_proj:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.markdown("<h3>Future Value Projection</h3>", unsafe_allow_html=True)
            x_yrs = np.arange(0, 31)
            y_vals = total_mkt_ils * (1.10 ** x_yrs)
            
            fig_p = px.line(x=x_yrs, y=y_vals, labels={'x':'Years', 'y':'Portfolio Value'})
            fig_p.update_traces(line_color='#10B981', line_width=3)
            fig_p.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
                                font=dict(color="#94A3B8"), margin=dict(t=20, b=20, l=20, r=20), height=300,
                                xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="#334155"))
            st.plotly_chart(fig_p, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
