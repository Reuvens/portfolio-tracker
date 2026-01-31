
from sqlmodel import Session, select, delete
from backend.database import engine, create_db_and_tables
from backend.models import User, Asset, Settings, StockGrant
import pandas as pd

def wipe_data(session: Session):
    """Deletes all rows from Asset and StockGrant tables."""
    print("Wiping existing Asset and StockGrant data...")
    session.exec(delete(Asset))
    session.exec(delete(StockGrant))
    session.commit()
    print("Data wiped.")

def seed_data():
    create_db_and_tables()
    with Session(engine) as session:
        # 1. Wipe
        wipe_data(session)
        
        # 2. Add Dummy User
        user = session.exec(select(User).where(User.email == "user@example.com")).first()
        if not user:
            user = User(email="user@example.com", name="Portfolio Owner")
            session.add(user)
            session.commit()
            session.refresh(user)
        
        print(f"Seeding for User ID: {user.id}")
        
        assets_to_add = []

        # --- 1. Bank ---
        # Bank Cash (Rows 36-37)
        assets_to_add.append(Asset(user_id=user.id, name="Checking ILS", ticker="ILS", quantity=26, cost_per_unit=1, type="Cash/Deposit", currency="ILS", category="Bank Account", alloc_cash_pct=1.0))
        assets_to_add.append(Asset(user_id=user.id, name="Checking USD", ticker="USD", quantity=32, cost_per_unit=3.09, type="Cash/Deposit", currency="USD", category="Bank Account", alloc_cash_pct=1.0))
        
        # Bonds & Govt (Rows 38-42) - Dividing Cost by 100 to match Agorot Fix logic if inputs were agorot? 
        # Actually user sheet said Cost 1.08... implies cost is already normalized. 
        # But Price fetcher will fetch 108.0 from TASE. We divide by 100 -> 1.08. Perfect.
        assets_to_add.append(Asset(user_id=user.id, name="Mizrahi Bond 2030", ticker="2310381", quantity=4724, cost_per_unit=1.08, type="Israeli Corporate Bond", currency="ILS", category="Bank Account", alloc_bonds_pct=1.0))
        assets_to_add.append(Asset(user_id=user.id, name="Govt Shekel 0330", ticker="1160985", quantity=5255, cost_per_unit=0.91, type="Israeli Gov Bond", currency="ILS", category="Bank Account", alloc_bonds_pct=1.0))
        assets_to_add.append(Asset(user_id=user.id, name="Govt Shekel 0432", ticker="1180660", quantity=12847, cost_per_unit=0.88, type="Israeli Gov Bond", currency="ILS", category="Bank Account", alloc_bonds_pct=1.0))
        assets_to_add.append(Asset(user_id=user.id, name="Govt Shekel 1152", ticker="1184076", quantity=8580, cost_per_unit=0.75, type="Israeli Gov Bond", currency="ILS", category="Bank Account", alloc_bonds_pct=1.0))
        assets_to_add.append(Asset(user_id=user.id, name="Govt Shekel 0537", ticker="1166180", quantity=19041, cost_per_unit=0.79, type="Israeli Gov Bond", currency="ILS", category="Bank Account", alloc_bonds_pct=1.0))
        
        # Funds (Rows 43-44)
        assets_to_add.append(Asset(user_id=user.id, name="IBI Leveraged Strat", ticker="5130067", quantity=2706, cost_per_unit=1.89, type="Israeli Stock", currency="ILS", category="Brokerage", alloc_us_stock_pct=1.0)) 
        assets_to_add.append(Asset(user_id=user.id, name="Yelin Lapid Liq", ticker="5139258", quantity=959, cost_per_unit=1.05, type="Cash/Deposit", currency="ILS", category="Bank Account", alloc_cash_pct=1.0))
        
        # Other (Row 45)
        assets_to_add.append(Asset(user_id=user.id, name="Ostar 12/24", ticker="ILS_BOND_OS", quantity=213, cost_per_unit=3.0, type="Israeli Corporate Bond", currency="ILS", category="Bank Account", alloc_bonds_pct=1.0))
        
        # US Funds (Rows 46-47)
        assets_to_add.append(Asset(user_id=user.id, name="Invesco S&P 500", ticker="1183441", quantity=875, cost_per_unit=42.73, type="Israeli Stock", currency="ILS", category="Brokerage", alloc_us_stock_pct=1.0))
        assets_to_add.append(Asset(user_id=user.id, name="iShares S&P 500", ticker="1159250", quantity=4.15, cost_per_unit=2295.7, type="Israeli Stock", currency="ILS", category="Brokerage", alloc_us_stock_pct=1.0)) 
        assets_to_add.append(Asset(user_id=user.id, name="AAA MTF Indexed", ticker="5133210", quantity=6244.42, cost_per_unit=1.13, type="Israeli Gov Bond", currency="ILS", category="Bank Account", alloc_bonds_pct=1.0))
        
        # Corporate Bonds (Rows 49-53) - NEW
        assets_to_add.append(Asset(user_id=user.id, name="Azrieli Bond H", ticker="1178656", quantity=50000, cost_per_unit=1.12, type="Israeli Corporate Bond", currency="ILS", category="Bank Account", alloc_bonds_pct=1.0))
        assets_to_add.append(Asset(user_id=user.id, name="Melisron Bond YH", ticker="1184076_DUP", quantity=30000, cost_per_unit=1.09, type="Israeli Corporate Bond", currency="ILS", category="Bank Account", alloc_bonds_pct=1.0)) # Note: Ticker conflict in sheet
        assets_to_add.append(Asset(user_id=user.id, name="Fattal Holdings Bond D", ticker="1184340", quantity=25000, cost_per_unit=1.10, type="Israeli Corporate Bond", currency="ILS", category="Bank Account", alloc_bonds_pct=1.0))
        assets_to_add.append(Asset(user_id=user.id, name="Gazit Globe Bond YZ", ticker="1159110", quantity=20000, cost_per_unit=1.13, type="Israeli Corporate Bond", currency="ILS", category="Bank Account", alloc_bonds_pct=1.0))
        assets_to_add.append(Asset(user_id=user.id, name="Alony Hetz Bond YA", ticker="1181825", quantity=15000, cost_per_unit=1.08, type="Israeli Corporate Bond", currency="ILS", category="Bank Account", alloc_bonds_pct=1.0))
        
        # Manual Funds (Rows 54-55) - NEW
        assets_to_add.append(Asset(user_id=user.id, name="Altshuler Shaham", ticker="ALTSHULER", quantity=1, cost_per_unit=27814, type="Fund", currency="ILS", category="Bank Account", alloc_il_stock_pct=1.0, manual_price=27814))
        assets_to_add.append(Asset(user_id=user.id, name="IBI General", ticker="IBI_GEN", quantity=1, cost_per_unit=11200, type="Fund", currency="ILS", category="Bank Account", alloc_il_stock_pct=1.0, manual_price=11200))

        # --- Work ---
        assets_to_add.append(Asset(user_id=user.id, name="Google GSUs", ticker="GOOG", quantity=72120/850, cost_per_unit=0.0, type="GSU/RSU", currency="USD", category="Work", alloc_work_pct=1.0)) # Qty in sheet=72120 (Value?), assuming ~85 units at $850? No, Value is 54682. 54k NIS is ~15k USD. ~80 shares. I'll put 85.
        assets_to_add.append(Asset(user_id=user.id, name="Microsoft", ticker="MSFT", quantity=2, cost_per_unit=430.0, type="US Stock/ETF", currency="USD", category="Work", alloc_work_pct=1.0))

        # --- Crypto (Rows 61-64) ---
        assets_to_add.append(Asset(user_id=user.id, name="Bitcoin", ticker="BTC", quantity=0.033, cost_per_unit=82989.0, type="Cryptocurrency", currency="USD", category="Crypto Wallet", alloc_crypto_pct=1.0))
        assets_to_add.append(Asset(user_id=user.id, name="Ethereum", ticker="ETH", quantity=0.49, cost_per_unit=2645.0, type="Cryptocurrency", currency="USD", category="Crypto Wallet", alloc_crypto_pct=1.0))
        assets_to_add.append(Asset(user_id=user.id, name="Solana", ticker="SOL", quantity=15, cost_per_unit=145.0, type="Cryptocurrency", currency="USD", category="Crypto Wallet", alloc_crypto_pct=1.0))
        assets_to_add.append(Asset(user_id=user.id, name="Cardano", ticker="ADA", quantity=1200, cost_per_unit=0.35, type="Cryptocurrency", currency="USD", category="Crypto Wallet", alloc_crypto_pct=1.0))

        # --- Investment Funds 2 (Rows 65-69) ---
        assets_to_add.append(Asset(user_id=user.id, name="USD Cash Fund", ticker="USD", quantity=3.31, cost_per_unit=3.09, type="Cash/Deposit", currency="USD", category="Investment Fund", alloc_cash_pct=1.0))
        assets_to_add.append(Asset(user_id=user.id, name="Inv. Invesco S&P", ticker="1183441", quantity=420, cost_per_unit=43.0, type="Israeli Stock", currency="ILS", category="Investment Fund", alloc_us_stock_pct=1.0))
        assets_to_add.append(Asset(user_id=user.id, name="Blackrock ETH ETF", ticker="ETHA", quantity=24, cost_per_unit=20.17, type="US Stock/ETF", currency="USD", category="Investment Fund", alloc_crypto_pct=1.0))
        assets_to_add.append(Asset(user_id=user.id, name="Ethereum Eur", ticker="AETH-USD", quantity=11, cost_per_unit=30.07, type="Cryptocurrency", currency="USD", category="Investment Fund", alloc_crypto_pct=1.0))
        assets_to_add.append(Asset(user_id=user.id, name="Inv. VOO", ticker="VOO", quantity=2.5, cost_per_unit=636.22, type="US Stock/ETF", currency="USD", category="Investment Fund", alloc_us_stock_pct=1.0))

        # --- Pensions (Rows 73-76) ---
        assets_to_add.append(Asset(user_id=user.id, name="Clal Rishon (Pension)", ticker="CLAL_PEN", quantity=1, cost_per_unit=17180, type="Fund", currency="ILS", category="Pension", manual_price=17180,
                                   alloc_il_stock_pct=0.157, alloc_us_stock_pct=0.385, alloc_bonds_pct=0.458))
        assets_to_add.append(Asset(user_id=user.id, name="Harel Rishon", ticker="HAR_PEN", quantity=1, cost_per_unit=25089, type="Fund", currency="ILS", category="Pension", manual_price=25089,
                                   alloc_il_stock_pct=0.19, alloc_us_stock_pct=0.62, alloc_bonds_pct=0.19))
        assets_to_add.append(Asset(user_id=user.id, name="Orit Pension", ticker="MIG_PEN", quantity=1, cost_per_unit=9253, type="Fund", currency="ILS", category="Pension", manual_price=9253,
                                   alloc_il_stock_pct=0.70, alloc_bonds_pct=0.30))
        assets_to_add.append(Asset(user_id=user.id, name="Orit Manager", ticker="PHX_MAN", quantity=1, cost_per_unit=5701, type="Fund", currency="ILS", category="Pension", manual_price=5701,
                                   alloc_il_stock_pct=1.0))


        # Add all to session
        for a in assets_to_add:
            session.add(a)

        # 4. Seed Settings if needed
        settings = session.exec(select(Settings).where(Settings.user_id == user.id)).first()
        if not settings:
            settings = Settings(user_id=user.id)
            session.add(settings)
        
        # Update default Targets
        settings.allocation_targets = '{"US Stocks": 35.0, "IL Stocks": 15.0, "Work": 10.0, "Crypto": 5.0, "Bonds": 20.0, "Cash": 15.0}'
        settings.swr_rate = 0.04
        settings.include_crypto = True
        session.add(settings)

        session.commit()
        print(f"Seeded {len(assets_to_add)} assets.")

if __name__ == "__main__":
    seed_data()
