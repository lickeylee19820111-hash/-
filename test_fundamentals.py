import sys
from data_fetcher import fetch_fundamental_data

def test_stock(symbol):
    print(f"\n--- 測試代碼: {symbol} ---")
    try:
        data = fetch_fundamental_data(symbol)
        print(f"市值: {data.get('Market Cap')}")
        print(f"PE: {data.get('Trailing P/E')}")
        print(f"EPS: {data.get('EPS (Trailing)')}")
        print(f"殖利率: {data.get('Dividend Yield')}")
        
        # Check if they are all N/A
        all_na = all(v == 'N/A' for v in data.values())
        if all_na:
            print("❌ 結果：全部為 N/A (抓取失敗)")
        else:
            print("✅ 結果：成功抓取到關鍵數據")
    except Exception as e:
        print(f"❌ 發生崩潰: {e}")

if __name__ == "__main__":
    test_stock("2330")  # 純數字測試 (上市)
    test_stock("8069")  # 純數字測試 (上櫃)
    test_stock("台積電") # 中文名稱測試
