from data_fetcher import get_stock_info_from_api

def test_name():
    print("Testing 3163 Name Lookup...")
    name = get_stock_info_from_api("3163")
    print(f"Result for 3163: {name}")
    
    print("\nTesting 2330 Name Lookup...")
    name = get_stock_info_from_api("2330")
    print(f"Result for 2330: {name}")

if __name__ == "__main__":
    test_name()
