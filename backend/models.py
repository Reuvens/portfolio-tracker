from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime

class User(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    name: str

class Asset(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    type: str # Stock, Crypto, Cash
    name: str = "Unknown Asset"
    ticker: str
    quantity: float
    cost_per_unit: float = 0.0
    cost_basis: float = 0.0 # Total cost
    currency: str # USD, ILS
    date_acquired: datetime = Field(default_factory=datetime.utcnow)
    
    # Extended Fields
    category: str = "Bank Account" # Bank Account, Work, Pension, Future Needs, Crypto, Fund
    account_type: str = "Brokerage" # Deprecated/Secondary to category?
    liquidity: str = "Liquid"
    allocation_bucket: Optional[str] = None
    notes: Optional[str] = None
    manual_price: Optional[float] = None
    
    # Tax & Allocation overrides
    tax_rate: Optional[float] = None # e.g. 0.25
    alloc_il_stock_pct: float = 0.0
    alloc_us_stock_pct: float = 0.0
    alloc_crypto_pct: float = 0.0
    alloc_work_pct: float = 0.0 # NEW: For GSUs + MSFT bucket
    alloc_bonds_pct: float = 0.0
    alloc_cash_pct: float = 0.0 # Short term bonds / cash

class StockGrant(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    name: str # e.g. "GSU 2024"
    grant_date: datetime
    vest_date: datetime
    units: float
    grant_price: float
    vest_price: Optional[float] = None
    is_vested: bool = False

class Settings(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    base_currency: str = "ILS"
    
    # Global Assumptions
    usd_ils_rate: float = 3.6
    use_manual_fx: bool = False
    
    # Tax Assumptions
    tax_rate_income: float = 0.50
    tax_rate_capital_gains: float = 0.25
    gsu_tax_mode: str = "Average" # Current, Optimized, Average

    # Planning Settings
    swr_rate: float = 0.04 # 4% Rule
    include_crypto: bool = True # Include in NW totals?
    allocation_targets: str = "{}" # JSON string: {'US Stocks': 30, ...}
