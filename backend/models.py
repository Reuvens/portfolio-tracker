from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    name: str

class Asset(SQLModel, table=True):
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

class Settings(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    base_currency: str = "ILS"
    capital_gains_tax_rate: float = 0.25
