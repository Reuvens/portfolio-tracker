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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Inter', sans-serif;
        background-color: #0E131C;
        color: #E2E8F0;
    }

    [data-testid="stHeader"] {
        background-color: transparent;
    }

    .main-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.5rem 0;
        margin-bottom: 1.5rem;
    }
    
    .card {
        background: #151C27;
        border: 1px solid #232C3B;
        border-radius: 16px;
        padding: 1.25rem;
        margin-bottom: 1rem;
    }
    
    .metric-title {
        color: #94A3B8;
        font-size: 0.8rem;
        font-weight: 500;
        margin-bottom: 0.5rem;
    }
    
    .metric-value {
        font-size: 2.2rem;
        font-weight: 700;
        color: #FFFFFF;
        line-height: 1.1;
    }
    
    .metric-trend {
        font-size: 0.85rem;
        font-weight: 600;
        margin-top: 0.5rem;
    }
    
    .trend-up { color: #10B981; }
    .trend-down { color: #EF4444; }
    
    .asset-item {
        display: flex;
        align-items: center;
        padding: 0.85rem;
        background: #1C2431;
        border-radius: 12px;
        margin-bottom: 0.5rem;
    }
    
    .asset-icon-circle {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: #2D3748;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-right: 0.85rem;
        font-weight: 700;
        font-size: 0.8rem;
        color: #FFFFFF;
    }
    
    .tag {
        font-size: 0.65rem;
        padding: 1px 6px;
        border-radius: 4px;
        background: #2D3748;
        color: #A0AEC0;
        text-transform: uppercase;
        font-weight: 600;
    }

    .badge-buy { background: #10B98122; color: #10B981; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 0.7rem; }
    .badge-sell { background: #EF444422; color: #EF4444; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 0.7rem; }
    
    .rebalance-row { margin-bottom: 1.25rem; }
    
    .progress-bar-bg { height: 6px; background: #232C3B; border-radius: 3px; margin: 8px 0; overflow: hidden; }
    .progress-bar-fill { height: 100%; border-radius: 3px; background: #3B82F6; }

    /* Custom Streamlit component overrides */
    .stTabs [data-baseweb="tab-list"] { background-color: transparent; gap: 2rem; }
    .stTabs [data-baseweb="tab"] { background-color: transparent; border: none; color: #64748B; padding: 0.5rem 0.25rem; }
    .stTabs [aria-selected="true"] { color: #10B981 !important; border-bottom: 2px solid #10B981 !important; }
    
    .stButton button { border-radius: 8px; font-weight: 600; }
    .add-btn button { background-color: #10B981 !important; color: white !important; border: none !important; }
    .add-btn button:hover { background-color: #059669 !important; }

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

def delete_asset(asset_id):
    with Session(engine) as session:
        asset = session.get(Asset, asset_id)
        if asset:
            session.delete(asset)
            session.commit()
            return True
    return False

# --- Top Header ---
c_head1, c_head2 = st.columns([2, 1])
with c_head1:
    st.markdown("""
        <div>
            <h2 style='margin:0; color:#10B981; font-weight:700;'>Portfolio Manager</h2>
            <p style='margin:0; color:#64748B; font-size:0.85rem;'>Welcome, Reuven Sayag</p>
        </div>
    """, unsafe_allow_html=True)

# Fetch current FX rate for display and math
if 'current_fx' not in st.session_state:
    st.session_state.current_fx = get_usd_ils_rate()
fx_rate = st.session_state.current_fx

with c_head2:
    st.write("") # Spacer
    ch_sub1, ch_sub2, ch_sub3, ch_sub4 = st.columns([1, 0.4, 1.2, 0.4])
    ch_sub1.markdown(f"<p style='color:#64748B; font-size:0.75rem; margin-top:12px; text-align:right;'>🔄 FX: {fx_rate:.2f}</p>", unsafe_allow_html=True)
    ch_sub2.markdown("<div style='margin-top:10px; opacity:0.6; text-align:center;'>⚙️</div>", unsafe_allow_html=True)
    with ch_sub3:
        if st.button("✚ Add Position", key="add_pos_btn", use_container_width=True):
            st.session_state.show_add_form = True
    ch_sub4.markdown("<div style='margin-top:10px; opacity:0.6; text-align:center;'>↪️</div>", unsafe_allow_html=True)

# --- Add Asset Dialog ---
if st.session_state.get('show_add_form', False):
    st.markdown("""
        <style>
            .modal-overlay {
                position: fixed;
                top: 0; left: 0; width: 100%; height: 100%;
                background: rgba(0, 0, 0, 0.7);
                z-index: 999;
                display: flex;
                justify-content: center;
                align-items: center;
            }
            .stForm {
                background-color: #0E131C;
                border: 1px solid #232C3B;
                border-radius: 12px;
                padding: 2rem;
            }
        </style>
    """, unsafe_allow_html=True)
    
    with st.container():
        st.markdown("<div class='card' style='border: 1px solid #3B82F6; box-shadow: 0 4px 20px rgba(0,0,0,0.5);'>", unsafe_allow_html=True)
        # Header with Close Button
        c_h1, c_h2 = st.columns([1, 0.1])
        c_h1.subheader("Add New Position")
        if c_h2.button("✕", key="close_form_x"):
            st.session_state.show_add_form = False
            st.rerun()

        with st.form("add_asset_form_rev"):
            # Asset Type (Full Width)
            ftype = st.selectbox("Asset Type", ["US Stock/ETF", "Israeli Stock", "Israeli Corporate Bond", "Israeli Gov Bond", "Cryptocurrency", "Cash/Deposit", "GSU/RSU"])
            
            # Row 2: Ticker | Name
            r2_1, r2_2 = st.columns(2)
            fticker = r2_1.text_input("Ticker / Symbol", placeholder="e.g., GOOG, 1184076")
            fname = r2_2.text_input("Name", placeholder="Display name")
            
            # Row 3: Quantity | Cost Basis
            r3_1, r3_2 = st.columns(2)
            fqty = r3_1.number_input("Quantity", min_value=0.0, step=0.01, format="%.4f")
            fcost = r3_2.number_input("Cost Basis (per unit)", min_value=0.0, step=0.01, format="%.2f")
            
            # Row 4: Currency | Current Price
            r4_1, r4_2 = st.columns(2)
            fcurr = r4_1.selectbox("Currency", ["USD", "ILS"])
            fprice_override = r4_2.text_input("Current Price (optional override)", placeholder="Auto-fetch if empty")
            
            # Row 5: Account Type | Liquidity
            r5_1, r5_2 = st.columns(2)
            f_acct_type = r5_1.selectbox("Account Type", ["Brokerage", "Tax Advantaged", "Pension", "Wallet"])
            f_liquidity = r5_2.selectbox("Liquidity", ["Liquid", "Semi-Liquid", "Illiquid"])
            
            # Allocation Bucket
            f_alloc = st.selectbox("Allocation Bucket", ["Auto-assign", "US Equity", "IL Equity", "Fixed Income", "Crypto", "Cash"])
            
            # Notes
            f_notes = st.text_area("Notes", placeholder="Optional notes")
            
            st.write("")
            st.write("")
            
            # Footer Buttons
            sc1, sc2 = st.columns([6, 2])
            with sc1:
                 # Spacer to push buttons right
                 pass 
            with sc2:
                # We can't easily put two buttons side by side in a form submit area without hacks, 
                # but we can use columns inside the form.
                # Standard submit button is the primary action.
                pass
            
            # Actions
            col_actions = st.columns([1, 0.3, 0.3])
            # We must use st.form_submit_button for the submit action
            submitted = st.form_submit_button("＋ Add Position", use_container_width=True, type="primary")
            
            if submitted:
                 alloc_val = None if f_alloc == "Auto-assign" else f_alloc
                 try:
                     man_p = float(fprice_override) if fprice_override.strip() else None
                 except ValueError:
                     man_p = None
                     
                 add_asset(fname, fticker, fqty, fcost, ftype, fcurr, f_acct_type, f_liquidity, alloc_val, f_notes, man_p)
                 st.session_state.show_add_form = False
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
    all_tickers = [a.ticker for a in assets_list]
    current_prices = get_live_prices(all_tickers)
    
    processed_data = []
    total_mkt_ils = 0
    total_tax_liab_ils = 0
    total_cost_basis_ils = 0

    for asset in assets_list:
        p_live = current_prices.get(asset.ticker, 0.0)
        p = asset.manual_price if (asset.manual_price is not None and asset.manual_price > 0) else p_live
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

    # --- THREE COLUMN LAYOUT ---
    col_l, col_m, col_r = st.columns([1, 1.8, 1.2])

    # Left Column: Metrics & Allocation
    with col_l:
        # Net Worth Card
        net_worth_trend = total_mkt_ils - total_cost_basis_ils
        nw_trend_pct = (net_worth_trend / total_cost_basis_ils * 100) if total_cost_basis_ils > 0 else 0
        
        st.markdown(f"""
            <div class="card">
                <div style="display:flex; justify-content:space-between;">
                    <div class="metric-title">Total Net Worth<br><span style="font-size:0.7rem; color:#64748B;">Market Value</span></div>
                    <div style="text-align:right; font-size:0.65rem; color:#64748B;">USD/ILS<br><span style="font-size:0.8rem; color:#FFFFFF; font-weight:700;">{fx_rate:.2f}</span></div>
                </div>
                <div class="metric-value">{total_mkt_ils:,.0f}₪</div>
                <div class="metric-trend {'trend-up' if net_worth_trend >=0 else 'trend-down'}">
                    {'↗' if net_worth_trend >=0 else '↘'} ({nw_trend_pct:+.1f}%) ₪{abs(net_worth_trend):,.0f}
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # Sub Metrics Row
        l_sub1, l_sub2 = st.columns(2)
        l_sub1.markdown(f"""
            <div class="card" style="padding:1rem;">
                <div class="metric-title">Tax Liability</div>
                <div style="font-size:1.4rem; font-weight:700; color:#F59E0B;">{total_tax_liab_ils:,.0f}₪</div>
            </div>
        """, unsafe_allow_html=True)
        l_sub2.markdown(f"""
            <div class="card" style="padding:1rem;">
                <div class="metric-title">Net After Tax</div>
                <div style="font-size:1.4rem; font-weight:700; color:#10B981;">{(total_mkt_ils - total_tax_liab_ils):,.0f}₪</div>
            </div>
        """, unsafe_allow_html=True)

        # Asset Allocation Donut
        st.markdown("<div class='metric-title' style='margin-top:1.5rem; margin-left:5px;'>Asset Allocation</div>", unsafe_allow_html=True)
        df_p = pd.DataFrame(processed_data)
        allocation = df_p.groupby("type")["val_ils"].sum().reset_index()
        fig_don = px.pie(allocation, values='val_ils', names='type', hole=0.7, 
                         color_discrete_sequence=['#3B82F6', '#8B5CF6', '#F59E0B', '#10B981'])
        fig_don.update_layout(showlegend=True, margin=dict(t=0, b=0, l=0, r=0), height=220,
                              paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                              legend=dict(orientation="v", valign="middle", x=1.1, font=dict(color="#94A3B8", size=10)))
        st.plotly_chart(fig_don, use_container_width=True, config={'displayModeBar': False})

        # Liquidity Breakdown
        st.markdown("<div class='metric-title' style='margin-top:1.5rem; margin-left:5px;'>Liquidity Breakdown</div>", unsafe_allow_html=True)
        l_liq = sum(x['val_ils'] for x in processed_data if x['type'] in ['Cash/Deposit', 'Israeli Gov Bond', 'Israeli Corporate Bond'])
        l_semi = sum(x['val_ils'] for x in processed_data if x['type'] in ['US Stock/ETF', 'Israeli Stock', 'GSU/RSU'])
        l_illiq = sum(x['val_ils'] for x in processed_data if x['type'] == 'Cryptocurrency') # Simple mapping
        
        for name, val, color in [("Liquid", l_liq, "#10B981"), ("Semi-Liquid", l_semi, "#3B82F6"), ("Illiquid", l_illiq, "#8B5CF6")]:
            pct = (val / total_mkt_ils * 100) if total_mkt_ils > 0 else 0
            st.markdown(f"""
                <div style="margin-bottom:0.75rem;">
                    <div style="display:flex; justify-content:space-between; font-size:0.75rem; font-weight:600;">
                        <span>{name}</span><span>{val:,.0f}₪</span>
                    </div>
                    <div class="progress-bar-bg"><div class="progress-bar-fill" style="width:{pct}%; background:{color};"></div></div>
                </div>
            """, unsafe_allow_html=True)

        # By Account Type
        st.markdown("<div class='metric-title' style='margin-top:1.5rem; margin-left:5px;'>By Account Type</div>", unsafe_allow_html=True)
        acc1, acc2 = st.columns(2)
        acc1.markdown(f"""<div class="card" style="padding:0.75rem; margin-bottom:0;"><div class="metric-title" style="font-size:0.65rem;">Equity Comp</div><div style="font-weight:700; font-size:0.9rem;">{l_semi:,.0f}₪</div></div>""", unsafe_allow_html=True)
        acc2.markdown(f"""<div class="card" style="padding:0.75rem; margin-bottom:0;"><div class="metric-title" style="font-size:0.65rem;">Brokerage</div><div style="font-weight:700; font-size:0.9rem;">{l_liq:,.0f}₪</div></div>""", unsafe_allow_html=True)

    # Middle Column: Holdings & Rebalancing
    with col_m:
        st.markdown("<div class='card' style='padding:1.5rem;'>", unsafe_allow_html=True)
        m_h1, m_h2 = st.columns([2, 1])
        m_h1.markdown("<h3 style='margin:0; font-size:1.2rem; font-weight:700;'>Holdings</h3>", unsafe_allow_html=True)
        if m_h2.button("🔄 Refresh Prices", key="refresh_top", use_container_width=True):
             st.session_state.current_fx = get_usd_ils_rate()
             st.rerun()
             
        for item in processed_data:
            initials = item['ticker'][:2].upper() if not item['ticker'][0].isdigit() else "IL"
            
            with st.container():
                ci1, ci2, ci3 = st.columns([3, 1.5, 0.4])
                with ci1:
                    st.markdown(f"""
                        <div class="asset-item" style="margin-bottom:0; background:transparent;">
                            <div class="asset-icon-circle">{initials}</div>
                            <div style="flex-grow:1;">
                                <div style="display:flex; align-items:center; gap:8px;">
                                    <span style="font-weight:700; font-size:1.05rem;">{item['name']}</span>
                                    <span style="color:#64748B; font-size:0.8rem; font-weight:600;">{item['ticker']}</span>
                                </div>
                                <div style="display:flex; align-items:center; gap:8px; margin-top:4px;">
                                    <span class="tag">{item['type']}</span>
                                    <span style="color:#64748B; font-size:0.75rem;">{item['qty']} units @ {item['currency']}{item['price']:,.1f}</span>
                                </div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                with ci2:
                    st.markdown(f"""
                        <div style="text-align:right; margin-top:4px;">
                            <div style="font-weight:700; font-size:1.05rem;">{item['val_ils']:,.0f}₪</div>
                            <div style="display:flex; justify-content: flex-end; align-items:center; gap:4px; font-size:0.8rem;">
                                <span class="trend-up">↗ {item['gain_pct']:+.1f}%</span>
                                <span style="color:#64748B; margin-left:12px;">Net After Tax:</span><span style="color:#10B981; font-weight:700;">{item['net_after_tax']:,.0f}₪</span>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                with ci3:
                     # Invisible action buttons
                     st.write("") # Adjust vertical
                     if st.button("🗑️", key=f"del_v_{item['id']}", use_container_width=True):
                          if delete_asset(item['id']):
                               st.rerun()
            st.divider()
        st.markdown("</div>", unsafe_allow_html=True)

        # Rebalancing Plan
        st.markdown("<div class='card' style='padding:1.5rem;'>", unsafe_allow_html=True)
        st.markdown("<h3 style='margin:0 0 1rem 0; font-size:1.2rem; font-weight:700;'>⚖️ Rebalancing Plan</h3>", unsafe_allow_html=True)
        
        # Define Targets matching categories
        targets_map = {
            "US Stock/ETF": 35, 
            "GSU/RSU": 5,
            "Israeli Stock": 10, 
            "Israeli Gov Bond": 10, 
            "Israeli Corporate Bond": 5,
            "Cryptocurrency": 5, 
            "Cash/Deposit": 30
        }
        
        for cat, target_pct in targets_map.items():
            cat_sum = sum(x['val_ils'] for x in processed_data if x['type'] == cat)
            curr_pct = (cat_sum / total_mkt_ils * 100) if total_mkt_ils > 0 else 0
            
            diff_ils = (total_mkt_ils * target_pct / 100) - cat_sum
            is_buy = diff_ils >= 0
            
            st.markdown(f"""
                <div class="rebalance-row">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-weight:700; font-size:1rem;">{cat}</span>
                        <div style="text-align:right;">
                            <span class="{'badge-buy' if is_buy else 'badge-sell'}">{'↑ BUY' if is_buy else '↓ SELL'}</span>
                            <span style="font-weight:700; margin-left:8px; font-size:0.9rem; color:{'#10B981' if is_buy else '#EF4444'};">{diff_ils:,.0f}₪</span>
                        </div>
                    </div>
                    <div style="display:flex; justify-content:space-between; font-size:0.75rem; color:#64748B; margin-top:6px; font-weight:600;">
                        <span>Current: {curr_pct:.1f}%</span>
                        <span>Target: {target_pct}%</span>
                    </div>
                    <div class="progress-bar-bg"><div class="progress-bar-fill" style="width:{(curr_pct if curr_pct <= 100 else 100)}%; background:{'#3B82F6'};"></div></div>
                </div>
            """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # Right Column: Projections & SWR
    with col_r:
        st.markdown("<div class='card' style='padding:1.5rem;'>", unsafe_allow_html=True)
        st.markdown("""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
                <h3 style='margin:0; font-size:1rem; font-weight:700;'>Future Projections</h3>
                <div style="background:#1C2431; padding:2px; border-radius:6px; font-size:0.6rem; display:flex;">
                    <div style="background:#2D3748; padding:4px 8px; border-radius:4px; font-weight:700;">Portfolio Value</div>
                    <div style="padding:4px 8px; color:#64748B;">Monthly SWR</div>
                </div>
            </div>
            <p style='color:#64748B; font-size:0.7rem; margin-bottom:1.5rem;'>40 year outlook</p>
        """, unsafe_allow_html=True)
        
        # Projection Plot
        x_yrs = np.arange(0, 41)
        y_vals = total_mkt_ils * (1.10 ** x_yrs) # Assume 10% for the pretty line
        fig_pro = px.line(x=x_yrs, y=y_vals)
        fig_pro.update_traces(line_color='#10B981', fill='tozeroy', fillcolor='rgba(16, 185, 129, 0.1)')
        fig_pro.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                              xaxis=dict(showgrid=False, color="#4A5568", tickprefix="Y", tickfont=dict(size=8), nticks=10),
                              yaxis=dict(showgrid=True, gridcolor="#232C3B", color="#4A5568", tickfont=dict(size=8), title=None),
                              margin=dict(t=5, b=5, l=5, r=5), height=240)
        st.plotly_chart(fig_pro, use_container_width=True, config={'displayModeBar': False})
        
        # SWR Cards
        st.markdown("<div style='display:grid; grid-template-columns: 1fr; gap:12px; margin-top:1.5rem;'>", unsafe_allow_html=True)
        cons_swr = (total_mkt_ils * 0.03 / 12)
        aggr_swr = (total_mkt_ils * 0.04 / 12)
        
        st.markdown(f"""
            <div style="display:flex; gap:12px;">
                <div class="card" style="margin-bottom:0; flex:1; padding:1rem; background:#1C2431;">
                    <div class="metric-title" style="font-size:0.7rem;">Conservative SWR (Now)</div>
                    <div style="font-weight:700; font-size:1.3rem; color:#3B82F6;">{cons_swr:,.0f}₪/mo</div>
                </div>
                <div class="card" style="margin-bottom:0; flex:1; padding:1rem; background:#1C2431;">
                    <div class="metric-title" style="font-size:0.7rem;">Aggressive SWR (Now)</div>
                    <div style="font-weight:700; font-size:1.3rem; color:#3B82F6;">{aggr_swr:,.0f}₪/mo</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
