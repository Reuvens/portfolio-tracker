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
    account_type: str = "Brokerage" 
    liquidity: str = "Liquid"
    allocation_bucket: Optional[str] = None
    notes: Optional[str] = None
    manual_price: Optional[float] = None

class Settings(SQLModel, table=True):
    __table_args__ = {"extend_existing": True}
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    base_currency: str = "ILS"
    capital_gains_tax_rate: float = 0.25
