import yfinance as yf
import pandas as pd

def test_fetch(symbol):
    print(f"--- Testing {symbol} ---")
    try:
        df = yf.download(symbol, period="1mo", progress=False)
        print(f"yf.download returned {len(df)} rows.")
        if df.empty:
            print("Fallback to Ticker.history...")
            t = yf.Ticker(symbol)
            df = t.history(period="1mo")
            print(f"Ticker.history returned {len(df)} rows.")
        return df
    except Exception as e:
        print(f"Exception: {e}")
        return pd.DataFrame()

if __name__ == "__main__":
    # Test valid TSMC
    test_fetch("2330.TW")
    # Test OTC stock with .TW (should fail)
    test_fetch("8069.TW")
    # Test OTC stock with .TWO (should succeed)
    test_fetch("8069.TWO")
