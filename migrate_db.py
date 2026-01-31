from sqlmodel import create_engine, text
from backend.models import Asset, Settings, StockGrant

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
engine = create_engine(sqlite_url)

def run_migrations():
    with engine.connect() as connection:
        # 1. Migrate Asset Table
        print("Migrating Asset table...")
        columns_to_add = [
            ("category", "TEXT DEFAULT 'Bank Account'"),
            ("tax_rate", "FLOAT"),
            ("alloc_il_stock_pct", "FLOAT DEFAULT 0.0"),
            ("alloc_us_stock_pct", "FLOAT DEFAULT 0.0"),
            ("alloc_crypto_pct", "FLOAT DEFAULT 0.0"),
            ("alloc_work_pct", "FLOAT DEFAULT 0.0"),
            ("alloc_bonds_pct", "FLOAT DEFAULT 0.0"),
            ("alloc_cash_pct", "FLOAT DEFAULT 0.0")
        ]
        
        for col_name, col_type in columns_to_add:
            try:
                connection.execute(text(f"ALTER TABLE asset ADD COLUMN {col_name} {col_type}"))
                print(f"Added column {col_name} to Asset")
            except Exception as e:
                if "duplicate column name" in str(e):
                    print(f"Column {col_name} already exists in Asset")
                else:
                    print(f"Error adding {col_name}: {e}")

        # 2. Migrate Settings Table
        print("Migrating Settings table...")
        settings_cols = [
            ("usd_ils_rate", "FLOAT DEFAULT 3.6"),
            ("use_manual_fx", "BOOLEAN DEFAULT 0"),
            ("tax_rate_income", "FLOAT DEFAULT 0.50"),
            ("tax_rate_capital_gains", "FLOAT DEFAULT 0.25"),
            ("gsu_tax_mode", "TEXT DEFAULT 'Average'"),
            ("swr_rate", "FLOAT DEFAULT 0.04"),
            ("include_crypto", "BOOLEAN DEFAULT 1"),
            ("allocation_targets", "TEXT DEFAULT '{}'")
        ]

        for col_name, col_type in settings_cols:
            try:
                connection.execute(text(f"ALTER TABLE settings ADD COLUMN {col_name} {col_type}"))
                print(f"Added column {col_name} to Settings")
            except Exception as e:
                 if "duplicate column name" in str(e):
                    print(f"Column {col_name} already exists in Settings")
                 else:
                    print(f"Error adding {col_name}: {e}")

        # 3. Create StockGrant Table (if not exists)
        # SQLModel create_all usually handles this safely
        pass

    # Force create new tables
    from sqlmodel import SQLModel
    SQLModel.metadata.create_all(engine)
    print("Migration complete.")

if __name__ == "__main__":
    run_migrations()
