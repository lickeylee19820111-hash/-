import requests
import pandas as pd
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequest_Warning)

def test_institutional_data():
    """ 測試抓取三大法人買賣超數據 """
    try:
        # 1. 上市三大法人買賣超 API
        url = "https://openapi.twse.com.tw/v1/fund/T86_ALL_STK"
        response = requests.get(url, verify=False, timeout=10)
        data = response.json()
        df = pd.DataFrame(data)
        
        # 欄位說明:
        # '外陸資買賣超股數(不含外資自營商)' -> 外資
        # '投信買賣超股數' -> 投信
        # '證券代號' / '證券名稱'
        
        # 轉數字
        df['外資買賣超'] = pd.to_numeric(df['外陸資買賣超股數(不含外資自營商)'].str.replace(',', ''), errors='coerce')
        df['投信買賣超'] = pd.to_numeric(df['投信買賣超股數'].str.replace(',', ''), errors='coerce')
        
        # 取得外資買超前三
        top_foreign = df.sort_values(by='外資買賣超', ascending=False).head(3)
        # 取得投信買超前三
        top_trust = df.sort_values(by='投信買賣超', ascending=False).head(3)
        
        print("外資買超前三:")
        for _, row in top_foreign.iterrows():
            print(f"{row['證券代號']} {row['證券名稱']}: {int(row['外資買賣超']/1000):,} 張")
            
        print("\n投信買超前三:")
        for _, row in top_trust.iterrows():
            print(f"{row['證券代號']} {row['證券名稱']}: {int(row['投信買賣超']/1000):,} 張")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_institutional_data()
