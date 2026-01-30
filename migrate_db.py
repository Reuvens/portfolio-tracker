import sqlite3

db_path = "database.db"

commands = [
    "ALTER TABLE asset ADD COLUMN account_type VARCHAR DEFAULT 'Brokerage'",
    "ALTER TABLE asset ADD COLUMN liquidity VARCHAR DEFAULT 'Liquid'",
    "ALTER TABLE asset ADD COLUMN allocation_bucket VARCHAR",
    "ALTER TABLE asset ADD COLUMN notes VARCHAR",
    "ALTER TABLE asset ADD COLUMN manual_price FLOAT"
]

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

for cmd in commands:
    try:
        cursor.execute(cmd)
        print(f"Executed: {cmd}")
    except sqlite3.OperationalError as e:
        print(f"Skipped (probably exists): {cmd} - {e}")

conn.commit()
conn.close()
