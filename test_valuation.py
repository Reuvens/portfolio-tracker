from backend.services.valuation import get_live_prices

def test_prices():
    tickers = ["GOOG", "MSFT", "AAPL"]
    print(f"Fetching prices for: {tickers}")
    prices = get_live_prices(tickers)
    print(f"Results: {prices}")
    
    # Test single
    print("Fetching single: GOOG")
    p_single = get_live_prices(["GOOG"])
    print(f"Result: {p_single}")

if __name__ == "__main__":
    test_prices()
