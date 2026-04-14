import requests
import json

def inspect_tpex():
    url = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
    try:
        response = requests.get(url, verify=False, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"Total items: {len(data)}")
            if len(data) > 0:
                print("First item keys:", data[0].keys())
                print("First item sample:", json.dumps(data[0], indent=2, ensure_ascii=False))
                
                # Search for 3163
                for item in data:
                    # Check common field names
                    code = item.get('SecCode') or item.get('证券代号') or item.get('Code') or item.get('Symbol')
                    if code == '3163':
                        print("Found 3163:", item)
                        return
                print("3163 not found in top-level items.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    inspect_tpex()
