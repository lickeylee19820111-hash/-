import requests
import urllib3
import pandas as pd

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_market_summary():
    """ 測試抓取真實大盤數據 """
    try:
        # 1. 抓取上市所有股票最新行情 (以此估計漲跌停)
        url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        response = requests.get(url, verify=False, timeout=10)
        data = response.json()
        df = pd.DataFrame(data)
        
        # 轉數字，處理空值
        df['ClosingPrice'] = pd.to_numeric(df['ClosingPrice'].str.replace(',', ''), errors='coerce')
        df['Change'] = pd.to_numeric(df['Change'].str.replace('+', '').replace(' ', '0'), errors='coerce')
        
        # 估計漲停 (漲幅 > 9.8%)
        limit_up = len(df[df['Change'] / (df['ClosingPrice'] - df['Change']) >= 0.098])
        limit_down = len(df[df['Change'] / (df['ClosingPrice'] - df['Change']) <= -0.098])
        
        # 2. 抓取大盤融資融券 (這裡使用示例 API 或硬編碼，因為某些 API 需要日期)
        # 融資餘額 API: https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN
        # 這裡簡化：我們先抓總覽
        
        print(f"漲停數: {limit_up}")
        print(f"跌停數: {limit_down}")
        print(f"總標的數: {len(df)}")
        
        return {
            'limit_up': limit_up,
            'limit_down': limit_down,
            'volume_ntd': 0, # 需要其他 API
            'margin_balance_ntd': 0,
            'mcap_est_ntd': 0,
            'margin_perc': 0.0
        }
    except Exception as e:
        print(f"Error: {e}")
        return {}

if __name__ == "__main__":
    test_market_summary()
