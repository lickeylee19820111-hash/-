import requests
import pandas as pd
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_institutional_flow():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        # 1. 抓取法人買賣超 (上市)
        url_fund = "https://openapi.twse.com.tw/v1/fund/T86_ALL_STK"
        res_fund = requests.get(url_fund, verify=False, timeout=15, headers=headers)
        if res_fund.status_code != 200:
            print(f"Fund API Error: {res_fund.status_code}")
            return None
        df_fund = pd.DataFrame(res_fund.json())
        
        # 2. 抓取產業分類
        url_cat = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
        res_cat = requests.get(url_cat, verify=False, timeout=15, headers=headers)
        if res_cat.status_code != 200:
            print(f"Cat API Error: {res_cat.status_code}")
            return None
        df_cat = pd.DataFrame(res_cat.json())
        
        # 合併與計算
        df_fund['外資買賣超'] = pd.to_numeric(df_fund['外陸資買賣超股數(不含外資自營商)'].str.replace(',', ''), errors='coerce')
        df_fund['投信買賣超'] = pd.to_numeric(df_fund['投信買賣超股數'].str.replace(',', ''), errors='coerce')
        
        df_final = pd.merge(df_fund, df_cat[['Code', 'Category']], left_on='證券代號', right_on='Code', how='left')
        
        # 加總產業流向
        sector_agg = df_final.groupby('Category').agg({
            '外資買賣超': 'sum',
            '投信買賣超': 'sum'
        })
        top_foreign_sector = sector_agg['外資買賣超'].idxmax() if not sector_agg.empty else "未知"
        top_trust_sector = sector_agg['投信買賣超'].idxmax() if not sector_agg.empty else "未知"
        
        top_foreign = df_final.sort_values(by='外資買賣超', ascending=False).head(3)
        top_trust = df_final.sort_values(by='投信買賣超', ascending=False).head(3)
        
        return {
            'foreign_sector': top_foreign_sector,
            'trust_sector': top_trust_sector,
            'foreign_buys': top_foreign[['證券代號', '證券名稱', '外資買賣超']].to_dict('records'),
            'trust_buys': top_trust[['證券代號', '證券名稱', '投信買賣超']].to_dict('records')
        }
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    print(fetch_institutional_flow())
