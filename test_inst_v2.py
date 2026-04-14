import requests
import pandas as pd
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_institutional_flow():
    """ 
    抓取三大法人買賣超與產業別分佈
    """
    try:
        # 1. 抓取法人買賣超 (上市)
        url_fund = "https://openapi.twse.com.tw/v1/fund/T86_ALL_STK"
        res_fund = requests.get(url_fund, verify=False, timeout=10)
        df_fund = pd.DataFrame(res_fund.json())
        
        # 2. 抓取產業分類
        url_cat = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
        res_cat = requests.get(url_cat, verify=False, timeout=10)
        df_cat = pd.DataFrame(res_cat.json())
        # BWIBBU_ALL 有 'Code' 和 'Category'
        
        # 合併數據
        df_fund['外資買賣超'] = pd.to_numeric(df_fund['外陸資買賣超股數(不含外資自營商)'].str.replace(',', ''), errors='coerce')
        df_fund['投信買賣超'] = pd.to_numeric(df_fund['投信買賣超股數'].str.replace(',', ''), errors='coerce')
        
        # 關聯產業別
        df_final = pd.merge(df_fund, df_cat[['Code', 'Category']], left_on='證券代號', right_on='Code', how='left')
        
        # 分析產業流向 (以外資總買賣額加總計算)
        sector_flow = df_final.groupby('Category')['外資買賣超'].sum().sort_values(ascending=False)
        top_sector = sector_flow.index[0] if not sector_flow.empty else "未知"
        
        # 取得外資買超前三
        top_foreign = df_final.sort_values(by='外資買賣超', ascending=False).head(3)
        # 取得投信買超前三
        top_trust = df_final.sort_values(by='投信買賣超', ascending=False).head(3)
        
        return {
            'top_sector': top_sector,
            'foreign_buys': top_foreign[['證券代號', '證券名稱', '外資買賣超']].to_dict('records'),
            'trust_buys': top_trust[['證券代號', '證券名稱', '投信買賣超']].to_dict('records')
        }
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    result = fetch_institutional_flow()
    print(result)
