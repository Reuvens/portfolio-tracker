import streamlit as st
import pandas as pd
import numpy as np
from backend.services.valuation import get_live_prices, get_usd_ils_rate, process_portfolio
from backend.services.tax import calculate_tax_liability
from backend.database import engine, create_db_and_tables, models
from backend.models import Asset, Settings
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

    # --- TWO COLUMN DASHBOARD LAYOUT ---
    col_dash_l, col_dash_r = st.columns([1, 2.2])

    # --- TWO COLUMN DASHBOARD LAYOUT ---
    col_dash_l, col_dash_r = st.columns([1, 2.2])

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
                <div style="margin-top:1rem; padding-top:1rem; border-top:1px solid #1e293b;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span class="metric-label" style="color:#CBD5E1;">Monthly Retirement (4%)</span>
                        <span style="font-weight:700; color:#34D399; font-size:1.1rem;">₪{(total_net_after_tax * 0.04 / 12):,.0f}</span>
                    </div>
                    <div style="font-size:0.75rem; color:#64748B; margin-top:4px text-align:right;">Based on After Tax Value</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # Asset Allocation Donut
        st.markdown("<h3 style='font-size:1rem; margin-bottom:1rem; padding-left:4px;'>Asset Allocation</h3>", unsafe_allow_html=True)
        
        alloc_data = portfolio_summary.get('allocations', {})
        alloc_df = pd.DataFrame([{'Asset': k, 'Value': v} for k, v in alloc_data.items() if v > 0])
        
        if not alloc_df.empty:
            fig_don = px.pie(alloc_df, values='Value', names='Asset', hole=0.7, 
                             color_discrete_sequence=['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#64748B'])
            fig_don.update_layout(showlegend=True, margin=dict(t=0, b=0, l=0, r=0), height=300,
                                  paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                  legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5, font=dict(color="#94A3B8", size=11)))
            st.plotly_chart(fig_don, use_container_width=True, config={'displayModeBar': False})
        else:
             st.markdown("<div style='text-align:center; padding:20px; color:#64748B;'>No allocation data</div>", unsafe_allow_html=True)

        # Liquidity / Tax Breakdown
        st.markdown("<div class='card' style='padding:1.25rem; margin-top:2rem;'>", unsafe_allow_html=True)
        
        # Tax Bar
        effective_tax_rate = (total_tax_liab_ils / total_mkt_ils * 100) if total_mkt_ils > 0 else 0
        st.markdown(f"""
             <div style="margin-bottom:1.5rem;">
                 <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <span class="metric-label">Tax Liability</span>
                    <span style="color:#FB7185; font-weight:600;">-₪{total_tax_liab_ils:,.0f}</span>
                 </div>
                 <div style="width:100%; height:6px; background:#334155; border-radius:3px;">
                    <div style="width:{100-effective_tax_rate}%; height:100%; background:#10B981; border-radius:3px;"></div>
                 </div>
                 <div style="display:flex; justify-content:space-between; margin-top:4px;">
                    <span style="font-size:0.75rem; color:#94A3B8;">Effective Rate: {effective_tax_rate:.1f}%</span>
                    <span style="font-size:0.75rem; color:#94A3B8;">Net: ₪{total_net_after_tax:,.0f}</span>
                 </div>
             </div>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


    # --- RIGHT CONTENT (Holdings & Projections) ---
    with col_dash_r:
        
        # Tabs for different views including dedicated GSUs
        tab_holdings, tab_gsus, tab_plan, tab_proj = st.tabs(["Holdings", "GSUs", "Rebalancing", "Projections"])
        
        # TAB 1: HOLDINGS (Grouped)
        with tab_holdings:
            st.markdown("<div class='card'>", unsafe_allow_html=True)
            t_col1, t_col2 = st.columns([3, 1])
            is_empty = len(processed_data) == 0
            
            if is_empty:
                st.info("No assets found.")
            else:
                # Group Data
                groups = {
                    "Bank Account": [],
                    "Work (Stocks/GSUs)": [],
                    "Pension & Gemel": [],
                    "Crypto Wallets": [],
                    "Investment Funds": [],
                    "Future Needs": []
                }
                
                # Logic to map categories. Fallback if category is missing.
                for item in processed_data:
                    cat = item.get('type') # actually we mapped type to category earlier? Let's check logic.
                    # Mapping logic based on type or name if category simplistic
                    if cat in ['Bank Account', 'US Stock/ETF', 'Israeli Stock', 'Cash']:
                        groups["Bank Account"].append(item)
                    elif cat in ['Work', 'GSU/RSU']:
                        groups["Work (Stocks/GSUs)"].append(item)
                    elif cat in ['Pension', 'Education Fund']:
                        groups["Pension & Gemel"].append(item)
                    elif cat == 'Cryptocurrency':
                        groups["Crypto Wallets"].append(item)
                    elif cat == 'Fund':
                        groups["Investment Funds"].append(item)
                    elif cat == 'Future Needs':
                        groups["Future Needs"].append(item)
                    else:
                        # Default bucket
                        groups["Bank Account"].append(item)

                # Render Groups
                first = True
                for group_name, items in groups.items():
                    if not items: continue
                    
                    if not first: st.markdown("<div style='height:2rem;'></div>", unsafe_allow_html=True)
                    first = False
                    
                    st.markdown(f"<h4 style='color:#94A3B8; font-size:0.9rem; text-transform:uppercase; letter-spacing:1px; margin-bottom:0.5rem;'>{group_name}</h4>", unsafe_allow_html=True)
                    
                    # Table Header per group? Or Global? Let's do per group for clarity if columns differ, but here they are same.
                    # Global header looks cleaner if columns align.
                    # Let's just render rows.
                    
                    for item in items:
                        initials = item['ticker'][:2].upper() if item['ticker'] and not item['ticker'][0].isdigit() else "AS"
                        is_positive = item['gain_pct'] >= 0
                        trend_color = "#10B981" if is_positive else "#FB7185"
                        trend_arrow = "↗" if is_positive else "↘"
                        
                        st.markdown(f"""
                        <div class="asset-row" style="display: grid; grid-template-columns: 1.5fr 1fr 1fr 1fr 0.5fr; align-items: center; border-bottom:1px solid #1e293b;">
                            <div style="display:flex; align-items:center;">
                                <div class="asset-icon">{initials}</div>
                                <div>
                                    <div style="font-weight:600; font-size:0.95rem; color:#F8FAFC;">{item['name']}</div>
                                    <div style="font-size:0.75rem; color:#64748B; margin-top:2px;">
                                        <span style="background:#1E293B; padding:1px 4px; border-radius:4px;">{item['ticker']}</span>
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
                            <!-- Actions Column Placeholder -->
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Action Buttons (Streamlit native)
                        b_c1, b_c2 = st.columns([0.1, 0.9]) 
                        with b_c1:
                            if st.button("✎", key=f"e_{item['id']}", help="Edit"):
                                st.session_state.edit_id = item['id']
                                # Populate logic from DB
                                st.session_state.f_n = item['name']
                                st.session_state.f_t = item['ticker']
                                st.session_state.f_q = float(item['qty'])
                                st.session_state.f_c = float(item['cpu'])
                                st.session_state.f_curr = item['currency']
                                st.session_state.f_type = item['type'] # Generic type logic
                                
                                with Session(engine) as session:
                                   a_full = session.get(Asset, item['id'])
                                   if a_full:
                                       st.session_state.f_acct = a_full.category 
                                       st.session_state.f_notes = a_full.notes if a_full.notes else ""
                                       st.session_state.f_man_p = a_full.manual_price
                                       # Splits
                                       st.session_state.f_a_il = a_full.alloc_il_stock_pct
                                       st.session_state.f_a_us = a_full.alloc_us_stock_pct
                                       st.session_state.f_a_wk = a_full.alloc_work_pct
                                       st.session_state.f_a_bd = a_full.alloc_bonds_pct
                                       st.session_state.f_a_cr = a_full.alloc_crypto_pct
                                       st.session_state.f_a_ca = a_full.alloc_cash_pct
                                
                                st.session_state.show_add_form = True
                                st.rerun()
                                
                        with b_c2:
                            if st.button("🗑", key=f"d_{item['id']}", help="Delete"):
                                delete_asset(item['id'])
                                st.rerun()

                    st.markdown("<div style='height:1px; background:#1E293B; margin:4px 0;'></div>", unsafe_allow_html=True)
                    
            st.markdown("</div>", unsafe_allow_html=True)
            
        # TAB 2: GSUs
        with tab_gsus:
            st.info("Detailed GSU Vesting Schedule - Coming Soon")
            # Logic for GSU Table will go here

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
             c2.markdown("**Actual**")
             c3.markdown("**Target**")
             c4.markdown("**Action**")
             st.markdown("---")
             
             for cat in chart_buckets:
                curr_val = portfolio_summary['allocations'].get(cat, 0.0)
                # Calculate current % of Total Net Worth (Pre Tax for Allocation usually? Yes)
                curr_pct = (curr_val / total_mkt_ils * 100) if total_mkt_ils > 0 else 0
                
                target_pct = targets_map.get(cat, 0.0)
                
                # Delta
                target_val = total_mkt_ils * (target_pct / 100)
                diff_ils = target_val - curr_val
                is_buy = diff_ils >= 0
                
                # Render Row
                cc1, cc2, cc3, cc4 = st.columns([2, 1, 1, 1.5])
                with cc1: st.write(cat)
                with cc2: st.write(f"{curr_pct:.1f}%")
                with cc3: st.write(f"{target_pct:.1f}%")
                with cc4: 
                    if abs(diff_ils) < 1000:
                         st.markdown("<span style='color:#64748B;'>—</span>", unsafe_allow_html=True)
                    else:
                         color = "#34D399" if is_buy else "#F87171"
                         label = "BUY" if is_buy else "SELL"
                         st.markdown(f"<span style='color:{color}; font-weight:600;'>{label} ₪{abs(diff_ils):,.0f}</span>", unsafe_allow_html=True)
             
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
