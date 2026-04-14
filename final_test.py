from data_fetcher import get_stock_data
import pandas as pd

def final_test():
    print("--- Testing Automated Fallback Logic ---")
    # TSMC (Listed)
    df_2330 = get_stock_data("2330.TW")
    print(f"2330.TW: {len(df_2330)} rows fetched.")
    
    # OTC stock (8069 - E Ink)
    # Even if we pass it as .TW, it should fallback to .TWO
    df_8069 = get_stock_data("8069.TW")
    print(f"8069.TW (should fallback to .TWO): {len(df_8069)} rows fetched.")

if __name__ == "__main__":
    final_test()
