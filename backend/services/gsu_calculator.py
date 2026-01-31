
from typing import Dict, Any
from backend.models import StockGrant, Settings

def calculate_gsu_tax(
    grant: StockGrant, 
    current_price: float, 
    settings: Settings
) -> Dict[str, float]:
    """
    Calculates tax liability for a GSU grant based on the selected mode.
    Modes: 
      - Current: Full Income Tax (bracket) on gain? Or Gain from Grant to Vest?
                 Rules: (Vest Price - Grant Price) is income? Usually GSU is full income at Vest.
                 Then (Sale Price - Vest Price) is Cap Gains.
      - Optimized: Maybe implies lower assumed effective rate?
      - Average: Simple flat percentage.
    """
    
    # Basic GSU Logic (Israel Section 102 Capital Gains Track usually):
    # 1. Gain up to 'Benefit' is Income Tax (marginal).
    # 2. Gain above 'Benefit' is Capital Gains (25%).
    # Simplified here for the tracker "Engine":
    
    mode = settings.gsu_tax_mode
    units = grant.units
    gross_val = units * current_price
    
    vest_price = grant.vest_price if grant.vest_price else current_price # Fallback logic
    
    # Taxable Amount Calculations
    # Total Gain = Gross Value (since Grant Price often 0 for RSUs). 
    # If Options, would be (Current - Strike). Assuming RSUs/GSUs here roughly.
    
    tax_liability = 0.0
    
    if mode == "Average":
        # Flat blended rate (e.g. 35%)
        tax_liability = gross_val * 0.35
        
    elif mode == "Current":
        # Standard conservative calc
        # Income Tax part (approx 50%) + Cap Gains part (25%)
        # Simple for now: 45% flat aggressive
        tax_liability = gross_val * 0.45
        
    elif mode == "Optimized":
        # Optimistic scenario (e.g. held > 2 years, low income year)
        # Maybe 30% average
        tax_liability = gross_val * 0.30
        
    return {
        "gross_value": gross_val,
        "tax": tax_liability,
        "net_value": gross_val - tax_liability
    }
