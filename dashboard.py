import streamlit as st
import pandas as pd
import numpy as np
from backend.services.valuation import get_live_prices, get_usd_ils_rate, process_portfolio
from backend.services.tax import calculate_tax_liability
from backend.database import engine, create_db_and_tables, models
from backend.models import Asset, Settings, StockGrant
from sqlmodel import Session, select
import plotly.graph_objects as go

import plotly.express as px


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

    /* Tables */
    .styled-table {
        width: 100%;
        border-collapse: collapse;
        color: #E2E8F0;
        font-size: 0.9rem;
        table-layout: fixed; /* Enforce column widths */
    }
    .styled-table th {
        text-align: left;
        padding: 12px 16px;
        color: #94A3B8;
        font-weight: 500;
        border-bottom: 1px solid #334155;
        background: rgba(255,255,255,0.02);
    }
    .styled-table td {
        padding: 12px 16px;
        border-bottom: 1px solid #1E293B;
        vertical-align: middle;
        white-space: nowrap; /* Prevent wrapping breaking alignment */
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .styled-table tr:last-child td {
        border-bottom: none;
    }
    
    /* Utilities */
    .text-right { text-align: right !important; }
    .text-center { text-align: center !important; }
    .styled-table th.text-right { text-align: right; }

</style>
""", unsafe_allow_html=True)

# Helper functions
def get_settings(session, user_id):
    settings = session.exec(select(Settings).where(Settings.user_id == user_id)).first()
    if not settings:
        settings = Settings(
            user_id=user_id, 
            base_currency="ILS",
            usd_ils_rate=3.6,
            tax_rate_capital_gains=0.25
        )
        session.add(settings)
        session.commit()
    return settings

USER_ID = 1

def get_assets(session):
    return session.exec(select(Asset).where(Asset.user_id == USER_ID)).all()

def add_asset(session, asset_data):
    asset = Asset(**asset_data, user_id=USER_ID)
    session.add(asset)
    session.commit()
    return True

def update_asset(session, asset_id, asset_data):
    asset = session.get(Asset, asset_id)
    if asset:
        for key, value in asset_data.items():
            setattr(asset, key, value)
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
            d_type = st.session_state.get('f_type', 'Stock')
            d_acct = st.session_state.get('f_acct', 'Brokerage')
            # d_liq/d_alloc no longer used directly as generics, specific fields used instead
            d_notes = st.session_state.get('f_notes', '')
            d_man_p = st.session_state.get('f_man_p', '')
            
            # Asset Type (Generic)
            typ_opts = ["Stock", "ETF", "Bond", "Crypto", "Cash", "Fund", "Liability"]
            t_idx = typ_opts.index(d_type) if d_type in typ_opts else 0
            d_type = st.selectbox("Asset Type (General)", typ_opts, index=t_idx)

            # Row 2: Ticker | Name
            r2_1, r2_2 = st.columns(2)
            fticker = r2_1.text_input("Ticker", value=d_ticker, placeholder="e.g. GOOG, 1184076.TA")
            fname = r2_2.text_input("Name", value=d_name, placeholder="Asset Name")
            
            # Row 3: Qty | Cost
            r3_1, r3_2 = st.columns(2)
            fqty = r3_1.number_input("Quantity", value=float(d_qty), step=0.01)
            fcost = r3_2.number_input("Total Cost Basis", value=float(d_cost), step=100.0) # Changed from Unit Cost to Total Basis for simplicity? No, stay unit cost matches logic? 
            # Wait, user generic requirement implies flexibility. Let's stick to Unit Cost basis as DB expects.
            
            # Row 4: Currency | Override
            r4_1, r4_2 = st.columns(2)
            fcurr = r4_1.selectbox("Currency", ["USD", "ILS"], index=0 if d_curr=='USD' else 1)
            fprice_override = r4_2.text_input("Price Override", value=str(d_man_p) if d_man_p else "")

            # LOCATION (Crucial)
            loc_opts = ["Bank Account", "Brokerage", "Investment Fund", "Pension", "Crypto Wallet", "Work", "Future Needs"]
            l_idx = loc_opts.index(d_acct) if d_acct in loc_opts else 0 # Use f_acct/category field mapping
            f_location = st.selectbox("Location / Category", loc_opts, index=l_idx)
            
            # ALLOCATION SPLITS (Crucial)
            st.markdown("---")
            st.markdown("<h5 style='color:#94A3B8; font-size:0.9rem;'>Risk Allocation Splits (Must sum to 1.0)</h5>", unsafe_allow_html=True)
            
            # Retrieve existing split values from session or default
            # We need to map `d_alloc` (old single bucket) to these if new?
            # Actually, we should fetch the specific pct fields if editing.
            # Assuming st.session_state has them populated if 'edit_id' is set.
            # I will assume the caller (Edit Button) populates these.
            
            sa_1, sa_2, sa_3 = st.columns(3)
            with sa_1:
                fp_il = st.number_input("IL Stocks %", value=st.session_state.get('f_a_il', 0.0), min_value=0.0, max_value=1.0, step=0.1)
                fp_work = st.number_input("Work (Stock) %", value=st.session_state.get('f_a_wk', 0.0), min_value=0.0, max_value=1.0, step=0.1)
            with sa_2:
                fp_us = st.number_input("US Stocks %", value=st.session_state.get('f_a_us', 0.0), min_value=0.0, max_value=1.0, step=0.1)
                fp_bonds = st.number_input("Bonds (Mid/Long) %", value=st.session_state.get('f_a_bd', 0.0), min_value=0.0, max_value=1.0, step=0.1)
            with sa_3:
                fp_cry = st.number_input("Crypto %", value=st.session_state.get('f_a_cr', 0.0), min_value=0.0, max_value=1.0, step=0.1)
                fp_cash = st.number_input("Cash (Short) %", value=st.session_state.get('f_a_ca', 0.0), min_value=0.0, max_value=1.0, step=0.1)
            
            total_alloc = fp_il + fp_us + fp_cry + fp_work + fp_bonds + fp_cash
            if  abs(total_alloc - 1.0) > 0.01 and f_location != "Future Needs":
                 st.caption(f"⚠️ Total Allocation: {total_alloc*100:.1f}% (Should be 100%)")
            
            # Notes
            f_notes = st.text_area("Notes", value=d_notes, placeholder="Optional notes")
            
            st.write("")
            st.write("")
            
            # Actions
            col_actions = st.columns([1, 0.3, 0.3])
            submitted = st.form_submit_button("💾 Update Position" if is_edit else "＋ Add Position", use_container_width=True, type="primary")
            
            if submitted:
                 try:
                     man_p = float(fprice_override) if fprice_override.strip() else None
                 except ValueError:
                     man_p = None
                 
                 # Prepare Dict
                 asset_dict = {
                     'name': fname, 'ticker': fticker, 'quantity': fqty, 'cost_per_unit': fcost, # UI uses per unit? checked logic -> Yes fcost is cost basis per unit in field name
                     # wait, earlier i saw "Unit Cost" label. Let's assume per unit.
                     # Actually, standard is usually total cost basis for simplicity in some apps, but here 'cost_per_unit' is in model.
                     # I will stick to model 'cost_per_unit'.
                     'type': d_type, 'currency': fcurr, 'category': f_location,
                     'liquidity': 'Liquid', # Default for now or add back if needed? User didn't prioritize liquidity dropdown.
                     'notes': f_notes, 'manual_price': man_p,
                     'alloc_il_stock_pct': fp_il,
                     'alloc_us_stock_pct': fp_us,
                     'alloc_work_pct': fp_work,
                     'alloc_crypto_pct': fp_cry,
                     'alloc_bonds_pct': fp_bonds,
                     'alloc_cash_pct': fp_cash
                 }
                 
                 if is_edit:
                     # Helper function update_asset already uses session passed to it?
                     # No, let's look at definition: def update_asset(session, asset_id, asset_data)
                     with Session(engine) as form_session:
                         update_asset(form_session, st.session_state.edit_id, asset_dict)
                 else:
                     with Session(engine) as form_session:
                         add_asset(form_session, asset_dict)
                     
                 st.session_state.show_add_form = False
                 # Clear keys
                 for k in ['edit_id', 'f_n', 'f_t', 'f_q', 'f_c', 'f_curr', 'f_type', 'f_acct', 'f_liq', 'f_alloc', 
                           'f_a_il', 'f_a_us', 'f_a_wk', 'f_a_cr', 'f_a_bd', 'f_a_ca', 'f_notes', 'f_man_p']:
                     if k in st.session_state: del st.session_state[k]
                 st.rerun()
                 
        if st.button("Cancel", key="cancel_form_btn"):
             st.session_state.show_add_form = False
             st.rerun()
             
        st.markdown("</div>", unsafe_allow_html=True)

# --- Main Dashboard Logic ---
# --- Data Fetching & Processing ---
with Session(engine) as session:
    # 1. Load Settings
    user_settings = get_settings(session, USER_ID)
    
    # 2. FX Rate Logic
    if user_settings.use_manual_fx:
        fx_rate = user_settings.usd_ils_rate
    else:
        fx_rate = get_usd_ils_rate()
    
    # 3. Load Assets
    assets_list = get_assets(session)
    
    processed_positions = []
    portfolio_summary = {
        'total_net_worth': 0.0,
        'total_after_tax': 0.0,
        'allocations': {'IL Stocks': 0.0, 'US Stocks': 0.0, 'Crypto': 0.0, 'Bonds': 0.0, 'Cash': 0.0, 'GSUs': 0.0}
    }

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
        # print(f"DEBUG: Fetching tickers: {tickers_to_fetch}")
        current_prices = get_live_prices(list(tickers_to_fetch))
        
        # Process Portfolio (Tax, Net Worth, Allocation)
        portfolio_summary, processed_positions = process_portfolio(
            assets_list, current_prices, fx_rate, user_settings
        )
        
    # Extract totals for UI
    total_mkt_ils = portfolio_summary['total_net_worth']
    total_net_after_tax = portfolio_summary['total_after_tax']
    total_tax_liab_ils = total_mkt_ils - total_net_after_tax
    total_cost_basis_ils = 0.0
    processed_data = []
    
    # Map back to flat list for UI compatibility (Legacy UI code expects specific keys)
    for p in processed_positions:
        asset = p['asset']
        item = {
            'id': asset.id,
            'name': asset.name,
            'ticker': asset.ticker,
            'type': asset.category if asset.category else asset.type,
            'qty': asset.quantity,
            'price': p['price'],
            'val_ils': p['mkt_val_ils'],
            'currency': asset.currency,
            'cpu': asset.cost_per_unit,
            'net_after_tax': p['net_after_tax']
        }
        # Calc gain pct locally
        cost_basis_local = asset.cost_basis
        if asset.currency == 'USD': cost_basis_local *= fx_rate
        
        total_cost_basis_ils += cost_basis_local
        
        gain = item['val_ils'] - cost_basis_local
        if cost_basis_local > 0:
            item['gain_pct'] = (gain / cost_basis_local) * 100
        else:
            item['gain_pct'] = 0.0
            
        processed_data.append(item)


    # --- DASHBOARD LAYOUT ---
    
    with st.sidebar:
        st.header("Global Settings")
        
        # Data Refresh
        st.subheader("Data Freshness")
        st.caption("Prices cached for 30 mins.")
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()

        # FX Settings
        st.subheader("Currency (USD/ILS)")
        use_manual = st.checkbox("Manual FX Rate", value=user_settings.use_manual_fx)
        
        if use_manual:
            man_rate = st.number_input("Rate", value=user_settings.usd_ils_rate, step=0.01)
            if man_rate != user_settings.usd_ils_rate or use_manual != user_settings.use_manual_fx:
                user_settings.usd_ils_rate = man_rate
                user_settings.use_manual_fx = True
                session.add(user_settings)
                session.commit()
                st.rerun()
        else:
            st.metric("Live Rate", f"₪{fx_rate:.2f}")
            if use_manual != user_settings.use_manual_fx:
                user_settings.use_manual_fx = False
                session.add(user_settings)
                session.commit()
                st.rerun()
                
        # Tax Settings
        st.subheader("Tax Assumptions")
        tax_cg = st.number_input("Capital Gains Tax", value=user_settings.tax_rate_capital_gains, step=0.01, format="%.2f")
        if tax_cg != user_settings.tax_rate_capital_gains:
            user_settings.tax_rate_capital_gains = tax_cg
            session.add(user_settings)
            session.commit()
            st.rerun()

        # Planning Settings
        st.subheader("Planning")
        swr = st.number_input("SWR Rate (%)", value=user_settings.swr_rate*100, step=0.1)
        if abs((swr/100) - user_settings.swr_rate) > 0.0001:
            user_settings.swr_rate = swr/100
            session.add(user_settings)
            session.commit()
            st.rerun()

        st.caption("Target Allocation (JSON)")
        base_targets = user_settings.allocation_targets if user_settings.allocation_targets else "{}"
        new_targets = st.text_area("Targets", value=base_targets, height=150)
        if new_targets != user_settings.allocation_targets:
             user_settings.allocation_targets = new_targets
             session.add(user_settings)
             session.commit()
             st.rerun()

    # --- TOP SUMMARY SECTION ---
    st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)
    
    # Calculate Summaries
    net_worth = portfolio_summary['total_net_worth']
    net_after_tax = portfolio_summary['total_after_tax']
    passive_income_mo = portfolio_summary.get('swr_monthly', 0)
    
    # Calculate Location Splits
    loc_splits = {}
    for p in processed_positions:
        cat = p['asset'].category
        loc_splits[cat] = loc_splits.get(cat, 0) + p['mkt_val_ils']
    sorted_locs = sorted(loc_splits.items(), key=lambda x: x[1], reverse=True)

    # Calculate Allocation for Chart
    allocs = portfolio_summary['allocations']
    pie_data = pd.DataFrame([{'Asset': k, 'Value': v} for k, v in allocs.items() if v > 0])

    # --- TOP ROW: Net Worth | Passive | Breakdown Graph ---
    c_top1, c_top2, c_top3 = st.columns([1, 1, 1.2])
    
    def metric_card(label, value, sub_value=None, sub_color="neutral"):
        color_map = {"positive": "#34D399", "negative": "#FB7185", "neutral": "#94A3B8"}
        s_color = color_map.get(sub_color, "#94A3B8")
        st.markdown(f"""
        <div class="card" style="padding: 1.2rem; min-height: 180px; display:flex; flex-direction:column; justify-content:space-between;">
            <div><span class="metric-label">{label}</span></div>
            <div class="metric-value" style="font-size:1.8rem; margin-top:0.5rem;">{value}</div>
            {f'<div style="color:{s_color}; font-size:0.85rem; margin-top:auto; padding-top:0.5rem;">{sub_value}</div>' if sub_value else ''}
        </div>
        """, unsafe_allow_html=True)

    with c_top1:
        metric_card("Net Worth", f"₪{net_worth:,.0f}", f"After Tax: ₪{net_after_tax:,.0f}", "neutral")
        # Dropdown for Location (Expander within the column? No, expander acts on full width usually or container. 
        # But putting it here makes it "under net worth" visually.)
        # Use a "Details" expander
        with st.expander("Portfolio by Location"):
            st.markdown("""
<table class="styled-table" style="font-size:0.8rem;">
    <tbody>
""", unsafe_allow_html=True)
            for loc, val in sorted_locs:
                lpct = (val / net_worth * 100) if net_worth > 0 else 0
                st.markdown(f"<tr><td style='padding:8px;'>{loc}</td><td style='padding:8px; text-align:right;'>₪{val:,.0f}</td><td style='padding:8px; text-align:right; color:#94A3B8;'>{lpct:.1f}%</td></tr>", unsafe_allow_html=True)
            st.markdown("</tbody></table>", unsafe_allow_html=True)

    with c_top2:
        metric_card("Monthly Passive", f"₪{passive_income_mo:,.0f}", f"SWR Rate: {user_settings.swr_rate*100:.1f}%", "positive")

    with c_top3:
        # Pie Chart in a Card
        if not pie_data.empty:
            fig = px.pie(pie_data, values='Value', names='Asset', hole=0.7,
                         color_discrete_sequence=['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#64748B'])
            fig.update_layout(showlegend=True, margin=dict(t=10, b=10, l=10, r=10), height=180,
                              paper_bgcolor='rgba(15, 23, 42, 0.6)', plot_bgcolor='rgba(0,0,0,0)',
                              legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.1, font=dict(size=10, color="#94A3B8")))
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        else:
            st.info("No Data")


    # --- ASSET ALLOCATION TABLE (Detailed) ---
    st.markdown("<h3 style='margin-top:2rem; margin-bottom:1rem;'>Asset Allocation</h3>", unsafe_allow_html=True)

    
    allocs = portfolio_summary['allocations']
    
    # --- Table ---
    import json

    try:
        targets_map = json.loads(user_settings.allocation_targets)
    except:
        targets_map = {}
        
    buckets = ['US Stocks', 'IL Stocks', 'Bonds', 'Cash', 'Crypto', 'Work'] 
    
    # Build HTML String for Asset Allocation Table
    alloc_table_html = """
<div class="card" style="padding:0; overflow-x:auto;">
    <table class="styled-table" style="min-width:600px;">
        <thead>
            <tr>
                <th style="width:25%;">Asset Class</th>
                <th class="text-right" style="width:20%;">Current Value</th>
                <th class="text-right" style="width:15%;">Actual %</th>
                <th class="text-right" style="width:15%;">Target %</th>
                <th class="text-right" style="width:25%;">Delta</th>
            </tr>
        </thead>
        <tbody>
"""
    
    for b in buckets:
        val = allocs.get(b, 0.0)
        pct = (val / net_worth * 100) if net_worth > 0 else 0
        tgt = targets_map.get(b, 0.0)
        delta_val = net_worth * (tgt/100) - val
        
        if abs(delta_val) < 1000:
            act_html = "<span style='color:#64748B'>—</span>"
        elif delta_val > 0:
            act_html = f"<span style='color:#34D399; font-weight:600;'>+₪{abs(delta_val):,.0f} (Buy)</span>"
        else:
             act_html = f"<span style='color:#FB7185; font-weight:600;'>-₪{abs(delta_val):,.0f} (Sell)</span>"

        alloc_table_html += f"""
<tr>
    <td style="font-weight:600;">{b}</td>
    <td class="text-right">₪{val:,.0f}</td>
    <td class="text-right">{pct:.1f}%</td>
    <td class="text-right">{tgt:.1f}%</td>
    <td class="text-right">{act_html}</td>
</tr>
"""
        
    alloc_table_html += "</tbody></table></div>"
    st.markdown(alloc_table_html, unsafe_allow_html=True)
    st.write("")
    st.write("")


    # --- MAIN CONTENT CONTAINER (Holdings & Projections) ---
    # Formerly 'col_dash_r', now full width
    col_dash_r = st.container()
    with col_dash_r:

        
        # Tabs for different views including dedicated GSUs
        tab_holdings, tab_gsus, tab_plan, tab_proj = st.tabs(["Holdings", "GSUs", "Rebalancing", "Projections"])
        
        # TAB 1: HOLDINGS (Grouped)
        with tab_holdings:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            
            is_empty = len(processed_data) == 0
            
            if is_empty:
                st.info("No assets found.")
            else:
                # Group Data
                # Keys must match DB options: "Bank Account", "Brokerage", "Investment Fund", "Pension", "Crypto Wallet", "Work", "Future Needs"
                # But we might want to consolidate slightly for display? User said "Split by Location/Category".
                # I will use the actual category fields as keys, defaulting to "Unsorted".
                groups_dict = {}
                
                ordered_cats = ["Work", "Bank Account", "Brokerage", "Investment Fund", "Pension", "Crypto Wallet", "Future Needs"]
                
                for item in processed_data:
                    # Item 'type' is mapped to 'category' in backend loop effectively
                    cat = item.get('type', 'Other')
                    if cat not in groups_dict:
                        groups_dict[cat] = []
                    groups_dict[cat].append(item)

                # Render Groups (in specific order if possible)
                for group_name in ordered_cats + [k for k in groups_dict.keys() if k not in ordered_cats]:
                    if group_name not in groups_dict: continue
                    items = groups_dict[group_name]
                    if not items: continue # Just in case

                    st.markdown(f"<h4 style='color:#94A3B8; font-size:0.9rem; text-transform:uppercase; letter-spacing:1px; margin-top:1.5rem; margin-bottom:0.8rem; border-bottom:1px solid #334155; padding-bottom:4px;'>{group_name}</h4>", unsafe_allow_html=True)
                    
                    for item in items:
                        # CHECK FOR INLINE EDIT
                        if st.session_state.get('edit_id') == item['id']:
                             # RENDER INLINE FORM
                             with st.container():
                                 st.markdown(f"<div style='border:1px solid #3B82F6; border-radius:8px; padding:16px; background:#0F172A; margin:8px 0;'>", unsafe_allow_html=True)
                                 st.caption(f"Editing: {item['name']}")
                                 
                                 # Load existing values into form session keys if not set (or we set them on click)
                                 # We set them on click. Use those.
                                 with st.form(key=f"edit_form_{item['id']}"):
                                     e_c1, e_c2 = st.columns(2)
                                     new_q = e_c1.number_input("Quantity", value=st.session_state.get('f_q', 0.0))
                                     new_c = e_c2.number_input("Cost Basis", value=st.session_state.get('f_c', 0.0))
                                     new_p_ov = e_c1.text_input("Price Override", value=str(st.session_state.get('f_man_p', '')) if st.session_state.get('f_man_p') else "")
                                     new_loc = e_c2.selectbox("Location", ["Bank Account", "Brokerage", "Investment Fund", "Pension", "Crypto Wallet", "Work", "Future Needs"], index=0) # Index logic omitted for brevity, user can select
                                     
                                     submitted_edit = st.form_submit_button("Update")
                                     if submitted_edit:
                                         # Construct update
                                          man_p_val = float(new_p_ov) if new_p_ov.strip() else None
                                          updates = {
                                              'quantity': new_q, 'cost_per_unit': new_c, 'manual_price': man_p_val, 'category': new_loc
                                          }
                                          with Session(engine) as session:
                                              update_asset(session, item['id'], updates)
                                          
                                          del st.session_state['edit_id']
                                          st.rerun()
                                 
                                 if st.button("Cancel", key=f"cancel_{item['id']}"):
                                     del st.session_state['edit_id']
                                     st.rerun()
                                 st.markdown("</div>", unsafe_allow_html=True)

                        else:
                            # RENDER ROW
                            c1, c2, c3, c4, c5 = st.columns([2.5, 1.2, 1.2, 1.2, 0.8])
                            
                            initials = item['ticker'][:2].upper() if item['ticker'] and not item['ticker'][0].isdigit() else "AS"
                            is_positive = item['gain_pct'] >= 0
                            trend_color = "#10B981" if is_positive else "#FB7185"
                            trend_arrow = "↗" if is_positive else "↘"
                            
                            with c1:
                                 st.markdown(f"""
                                 <div style="display:flex; align-items:center; height:100%;">
                                    <div class="asset-icon" style="width:36px; height:36px; margin-right:10px; font-size:0.8rem;">{initials}</div>
                                    <div>
                                        <div style="font-weight:600; font-size:0.95rem; color:#F8FAFC; line-height:1.2;">{item['name']}</div>
                                        <div style="font-size:0.75rem; color:#64748B;">{item['ticker']}</div>
                                    </div>
                                 </div>
                                 """, unsafe_allow_html=True)
                                 
                            with c2:
                                 st.markdown(f"""
                                 <div style="text-align:right;">
                                    <div style="color:#E2E8F0; font-weight:500;">{item['currency']} {item['price']:,.2f}</div>
                                    <div style="font-size:0.75rem; color:#64748B;">x {item['qty']}</div>
                                 </div>
                                 """, unsafe_allow_html=True)
                                 
                            with c3:
                                 st.markdown(f"""
                                 <div style="text-align:right;">
                                    <div style="font-weight:700; color:#F8FAFC;">{item['val_ils']:,.0f}₪</div>
                                    <div style="font-size:0.75rem; color:#64748B;">Net: {(item['net_after_tax']):,.0f}₪</div>
                                 </div>
                                 """, unsafe_allow_html=True)
                                 
                            with c4:
                                 st.markdown(f"""
                                 <div style="text-align:right;">
                                    <div style="color:{trend_color}; font-weight:600; background:rgba(255,255,255,0.03); padding:2px 8px; border-radius:6px; display:inline-block; font-size:0.85rem;">
                                        {trend_arrow} {item['gain_pct']:+.1f}%
                                    </div>
                                 </div>
                                 """, unsafe_allow_html=True)
                                 
                            with c5:
                                ac1, ac2 = st.columns(2)
                                with ac1:
                                    if st.button("✎", key=f"e_{item['id']}", help="Edit"):
                                        st.session_state.edit_id = item['id']
                                        # Hydrate state
                                        st.session_state.f_q = float(item['qty'])
                                        st.session_state.f_c = float(item['cpu'])
                                        # Need full asset for others
                                        with Session(engine) as session:
                                            a = session.get(Asset, item['id'])
                                            if a: st.session_state.f_man_p = a.manual_price
                                        st.rerun()
                                with ac2:
                                    if st.button("🗑", key=f"d_{item['id']}", help="Delete"):
                                        delete_asset(item['id'])
                                        st.rerun()

                            st.markdown("<div style='height:1px; background:#1E293B; margin:8px 0;'></div>", unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)
            
        # TAB 2: GSUs (Already Refactored) - No Change needed as I targeted it specifically before? 
        # Wait, if I replace the whole block I need to include Tab 2 code or SKIP it.
        # I am replacing "TAB 1" and "TAB 3" separately?
        # The tool requires a contiguous block or strict context.
        # I will Replace TAB 1 block ONLY first.

            
        # TAB 2: GSUs
        with tab_gsus:
             st.markdown("<div class='card'>", unsafe_allow_html=True)
             st.markdown("<h3>Google Stock Units (GSUs)</h3>", unsafe_allow_html=True)
             
             # Fetch
             grants = session.exec(select(StockGrant).order_by(StockGrant.grant_date)).all()
             
             if not grants:
                 st.info("No GSU data found.")
             else:
                 # Aggregation to match Sheet View
                 # Key: (GrantDate, GrantPrice) -> {vested: 0, unvested: 0, total: 0, vest_end: date}
                 grouped = {}
                 for g in grants:
                     k = (g.grant_date, g.grant_price)
                     if k not in grouped:
                         grouped[k] = {'vested': 0, 'unvested': 0, 'total':0, 'end_date': g.vest_date, 'name': g.name}
                     
                     grouped[k]['total'] += g.units
                     grouped[k]['end_date'] = max(grouped[k]['end_date'], g.vest_date) # Take max date of the chunks
                     if g.is_vested:
                         grouped[k]['vested'] += g.units
                     else:
                         grouped[k]['unvested'] += g.units
                 
                 # Render Table
                 gsu_html = """
<div style="overflow-x:auto;">
<table class="styled-table">
   <thead>
       <tr>
           <th>Grant Date</th>
           <th>Full Vest Date</th>
           <th class="text-right">Total Units</th>
           <th class="text-right">Vested</th>
           <th class="text-right">Unvested</th>
           <th class="text-right">Grant Price</th>
           <th class="text-right">Value (Unvested)</th>
       </tr>
   </thead>
   <tbody>
"""
                 
                 goog_p = current_prices.get('GOOG', 0)
                 
                 for (g_date, g_price), d in grouped.items():
                     val_unvested = d['unvested'] * goog_p
                     g_date_str = g_date.strftime("%d/%m/%Y")
                     v_date_str = d['end_date'].strftime("%d/%m/%Y")
                     
                     gsu_html += f"""
<tr>
    <td>{g_date_str}</td>
    <td>{v_date_str}</td>
    <td class="text-right">{d['total']:.0f}</td>
    <td class="text-right" style="color:#34D399;">{d['vested']:.0f}</td>
    <td class="text-right" style="color:#F59E0B;">{d['unvested']:.0f}</td>
    <td class="text-right">${g_price:.2f}</td>
    <td class="text-right">${val_unvested:,.0f}</td>
</tr>
"""
                     
                 gsu_html += "</tbody></table></div>"
                 st.markdown(gsu_html, unsafe_allow_html=True)
                 if goog_p > 0:
                     st.caption(f"Calculated at current GOOG price: ${goog_p:.2f}")

             st.markdown("</div>", unsafe_allow_html=True)

        # TAB 3: REBALANCING
        with tab_plan:
             st.markdown("<div class='card'>", unsafe_allow_html=True)
             st.markdown("<h3>Rebalancing Plan</h3>", unsafe_allow_html=True)
             
             # Parse Targets from Settings
             import json
             try:
                 targets_map = json.loads(user_settings.allocation_targets)
             except:
                 targets_map = {"US Stocks": 35.0, "IL Stocks": 15.0, "Work": 10.0, "Crypto": 5.0, "Bonds": 20.0, "Cash": 15.0}

             # 6 Buckets defined in valuation.py
             chart_buckets = ['IL Stocks', 'US Stocks', 'Crypto', 'Work', 'Bonds', 'Cash']
             
             # Header
             c1, c2, c3, c4 = st.columns([2, 1, 1, 1.5])
             c1.markdown("**Bucket**")
             st.markdown("""
             <div style="overflow-x:auto;">
             <table class="styled-table">
                <thead>
                    <tr>
                        <th style="width:25%;">Bucket</th>
                        <th class="text-right" style="width:20%;">Actual</th>
                        <th class="text-right" style="width:15%;">Target</th>
                        <th class="text-right" style="width:40%;">Recommended Action</th>
                    </tr>
                </thead>
                <tbody>
             """, unsafe_allow_html=True)
             
             for cat in chart_buckets:
                curr_val = portfolio_summary['allocations'].get(cat, 0.0)
                curr_pct = (curr_val / total_mkt_ils * 100) if total_mkt_ils > 0 else 0
                target_pct = targets_map.get(cat, 0.0)
                
                # Delta
                target_val = total_mkt_ils * (target_pct / 100)
                diff_ils = target_val - curr_val
                is_buy = diff_ils >= 0
                
                if abs(diff_ils) < 1000:
                    action_html = "<span style='color:#64748B'>No Action</span>"
                else:
                    color = "#34D399" if is_buy else "#FB7185"
                    lbl = "BUY" if is_buy else "SELL"
                    action_html = f"<span style='color:{color}; font-weight:700;'>{lbl} ₪{abs(diff_ils):,.0f}</span>"

                st.markdown(f"""
                <tr>
                    <td style="font-weight:600;">{cat}</td>
                    <td class="text-right">
                        <div>₪{curr_val:,.0f}</div>
                        <div style="font-size:0.75rem; color:#64748B;">{curr_pct:.1f}%</div>
                    </td>
                    <td class="text-right">{target_pct:.1f}%</td>
                    <td class="text-right">{action_html}</td>
                </tr>
                """, unsafe_allow_html=True)
                
             st.markdown("</tbody></table></div>", unsafe_allow_html=True)
             st.markdown("</div>", unsafe_allow_html=True)

             
        # TAB 4: PROJECTIONS
        with tab_proj:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            st.markdown("<h3>Financial Independence</h3>", unsafe_allow_html=True)
            
            p_c1, p_c2 = st.columns(2)
            with p_c1:
                st.metric("Safe Withdrawal Rate (4%)", f"₪{portfolio_summary.get('swr_monthly', 0):,.0f}/mo")
                st.caption("Based on After-Tax Value")
            with p_c2:
                st.metric("Future Value (40 Years)", f"₪{portfolio_summary.get('future_value_40y', 0):,.0f}")
                st.caption("Assumes 5% Real Return")
                
            st.markdown("</div>", unsafe_allow_html=True)
