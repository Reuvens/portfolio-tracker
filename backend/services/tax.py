from .valuation import get_usd_ils_rate

def calculate_tax_liability(
    market_value_ils: float, 
    cost_basis_ils: float, 
    asset_type: str, 
    is_employee_equity: bool = False,
    marginal_tax_rate: float = 0.50
) -> float:
    """
    Calculate tax liability based on asset type and rules.
    - Capital Gains: 25% of profit (Market - Cost).
    - Employee Equity (RSU/GSU): Marginal Rate * Market Value (assuming vesting triggers tax event or purely income tax model).
      *Note*: Usually RSUs are taxed at vest as income, and then subsequent gains are capital gains. 
      For simplified logic here as requested: "set a marginal tax rate (e.g., 50%) applied to the full value upon vesting".
    """
    
    if is_employee_equity:
        # User specified: applied to full value upon vesting
        return market_value_ils * marginal_tax_rate
    
    gain = market_value_ils - cost_basis_ils
    if gain <= 0:
        return 0.0
    
    # Capital Gains Tax (25% default in IL)
    # TODO: Add inflation adjustment logic here
    tax_rate = 0.25 
    return gain * tax_rate

def normalize_to_ils(amount: float, currency: str, usd_rate: float) -> float:
    if currency == "ILS":
        return amount
    elif currency == "USD":
        return amount * usd_rate
    return amount # Default fallback
