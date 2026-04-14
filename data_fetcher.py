import yfinance as yf
import pandas as pd
import requests
import urllib3
import streamlit as st

# Disable SSL warnings for TWSE/TPEx government sites if their certs are missing in Cloud environment
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

@st.cache_data(ttl=3600)
def get_stock_data(symbol, period="1y", interval="1d"):
    """
    Fetch historical data with robustness for Streamlit Cloud.
    Handles NaNs, multi-index issues, and automatically retries .TWO for OTC stocks.
    """
    def _do_fetch(sym):
        try:
            df = yf.download(sym, period=period, interval=interval, progress=False, timeout=20)
            if df.empty:
                ticker = yf.Ticker(sym)
                df = ticker.history(period=period, interval=interval)
            return df
        except Exception:
            return pd.DataFrame()

    df = _do_fetch(symbol)
    
    # Auto-fallback: if .TW fails and it's a 4-digit code, try .TWO
    if df.empty and ".TW" in symbol:
        otc_sym = symbol.replace(".TW", ".TWO")
        df = _do_fetch(otc_sym)
    elif df.empty and ".TWO" in symbol:
        listed_sym = symbol.replace(".TWO", ".TW")
        df = _do_fetch(listed_sym)

    if not df.empty:
        # Reset index if multi-index from yf.download(batch)
        if hasattr(df.columns, 'nlevels') and df.columns.nlevels > 1:
            df.columns = df.columns.get_level_values(0)
            
        # Crucial: Clean data!
        if 'Close' in df.columns:
            df = df.dropna(subset=['Close'])
        elif not df.empty:
            # If 'Close' is missing but dataframe is not empty, it might be Ticker.history with lowercase or something else
            # But standard yfinance uses 'Close'
            pass
        
        # Ensure index is datetime
        df.index = pd.to_datetime(df.index)
        
    return df

@st.cache_data(ttl=3600)
def get_stock_info_from_api(symbol_code):
    """
    Fetch real-time stock name from twstock (local) or TWSE/TPEx Open APIs.
    """
    # Strip suffix if present (e.g. 3163.TW -> 3163)
    symbol_code = symbol_code.split('.')[0]
    
    # 0. Try local twstock (Very fast)
    import twstock
    if symbol_code in twstock.codes:
        return twstock.codes[symbol_code].name

    # 1. Try TWSE (Listed)
    try:
        url_twse = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        response = requests.get(url_twse, verify=False, timeout=5)
        if response.status_code == 200:
            data = response.json()
            for item in data:
                if item['Code'] == symbol_code:
                    return item['Name']
    except Exception:
        pass

    # 2. Try TPEx (OTC) 
    try:
        url_tpex = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
        response = requests.get(url_tpex, verify=False, timeout=5)
        if response.status_code == 200:
            data = response.json()
            for item in data:
                if item.get('SecuritiesCompanyCode') == symbol_code:
                    return item.get('CompanyName', "上櫃股票")
    except Exception:
        pass

    return f"台股 {symbol_code}"

# --- COMPATIBILITY ALIASES (Fixing the ImportError) ---
def fetch_stock_data(symbol, period="1y", interval="1d"):
    return get_stock_data(symbol, period, interval)

def fetch_stock_info(symbol_code):
    return get_stock_info_from_api(symbol_code)

def fetch_fundamental_data(symbol):
    """ 
    Fetch fundamental data using a hybrid of yfinance and TWSE/TPEx Open APIs.
    Prioritizes official TWSE/TPEx data for ratios.
    """
    code = symbol.split('.')[0]
    data = {
        'Market Cap': 'N/A',
        'Trailing P/E': 'N/A',
        'EPS (Trailing)': 'N/A',
        'Dividend Yield': 'N/A'
    }
    
    # 1. Try yfinance for basics (Market Cap and EPS)
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        if info:
            data['Market Cap'] = info.get('marketCap', 'N/A')
            data['EPS (Trailing)'] = info.get('trailingEps', 'N/A')
            # Fallback ratios if others fail
            data['Trailing P/E'] = info.get('trailingPE', 'N/A')
            dy = info.get('dividendYield')
            if isinstance(dy, (int, float)):
                data['Dividend Yield'] = f"{dy*100:.2f}%" if dy < 1 else f"{dy:.2f}%"
    except Exception:
        pass

    # 2. Prefer TWSE (Listed) for ratios
    try:
        url_cat = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
        res_cat = requests.get(url_cat, verify=False, timeout=5)
        if res_cat.status_code == 200:
            json_data = res_cat.json()
            if isinstance(json_data, list):
                df_cat = pd.DataFrame(json_data)
                matches = df_cat[df_cat['Code'] == code]
                if not matches.empty:
                    row = matches.iloc[0]
                    pe = row.get('PEratio')
                    if pe and pe != '0.00' and pe != 'N/A':
                        data['Trailing P/E'] = pe
                    dy = row.get('DividendYield')
                    if dy and dy != 'N/A':
                        data['Dividend Yield'] = f"{dy}%"
                    return data # Found authoritative data for listed stock
    except Exception:
        pass

    # 3. Prefer TPEx (OTC) for ratios
    try:
        url_tpex = "https://www.tpex.org.tw/web/stock/aftertrading/peratio_analysis/pera_result.php?l=zh-tw&o=json"
        res_tpex = requests.get(url_tpex, verify=False, timeout=5)
        if res_tpex.status_code == 200:
            tpex_json = res_tpex.json()
            if 'tables' in tpex_json and len(tpex_json['tables']) > 0:
                rows = tpex_json['tables'][0].get('data', [])
                for r in rows:
                    if r[0] == code:
                        pe = r[2]
                        if pe and pe != '0.00' and pe != 'N/A':
                            data['Trailing P/E'] = str(pe)
                        dy = r[5]
                        if dy and dy != 'N/A':
                            data['Dividend Yield'] = f"{dy}%"
                        return data # Found authoritative data for OTC stock
    except Exception:
        pass
    
    return data

def resolve_taiwan_stock(symbol):
    """
    Returns (formatted_ticker, stock_name)
    Handles: 
    1. Code only "2330" -> "2330.TW"
    2. Name "台積電" -> "2330.TW"
    3. Code with suffix "3163.TWO" -> "3163.TWO"
    """
    import twstock
    symbol = symbol.strip()
    
    # Check if it's already a code with suffix
    if '.' in symbol:
        code = symbol.split('.')[0]
        name = get_stock_info_from_api(code)
        return symbol, name

    # Try to see if it's a code or name in twstock
    # search name first
    for code, info in twstock.codes.items():
        if info.name == symbol:
            suffix = ".TW" if info.market == "上市" else ".TWO"
            return f"{code}{suffix}", info.name
            
    # Then check if it's a code
    if symbol in twstock.codes:
        info = twstock.codes[symbol]
        suffix = ".TW" if info.market == "上市" else ".TWO"
        return f"{symbol}{suffix}", info.name

    # Default fallback
    return f"{symbol}.TW", f"台股 {symbol}"

def fetch_market_summary():
    """ 
    Fetch real market summary from TWSE Open API. 
    Returns counts of limit ups/downs and estimated volume.
    """
    try:
        url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        response = requests.get(url, verify=False, timeout=10)
        data = response.json()
        df = pd.DataFrame(data)
        
        # Clean price data
        df['ClosingPrice'] = pd.to_numeric(df['ClosingPrice'].str.replace(',', ''), errors='coerce')
        df['Change'] = pd.to_numeric(df['Change'].str.replace('+', '').replace(' ', '0'), errors='coerce')
        df['TradeValue'] = pd.to_numeric(df['TradeValue'].str.replace(',', ''), errors='coerce')
        
        # Avoid division by zero
        df = df[df['ClosingPrice'] > 0]
        
        # Estimate Limit Up/Down (Taiwan's limit is 10%)
        # Note: Change is compared to previous close (Price - Change)
        limit_up = len(df[df['Change'] / (df['ClosingPrice'] - df['Change']) >= 0.098])
        limit_down = len(df[df['Change'] / (df['ClosingPrice'] - df['Change']) <= -0.098])
        total_volume = df['TradeValue'].sum()
        
        # Estimated Market Cap: Using TSMC as a pivot or summing (if caps were in this API)
        # Since STOCK_DAY_ALL doesn't have shares outstanding, we use a placeholder or 
        # a more realistic 70 Trillion TWD if calculations fail.
        market_cap_estimate = 72000000000000 # Approx 72 Trillion TWD
        
        return {
            'limit_up': limit_up,
            'limit_down': limit_down,
            'volume_ntd': total_volume,
            'margin_balance_ntd': 280000000000, # Approx 2800 Billion TWD placeholder
            'mcap_est_ntd': market_cap_estimate,
            'margin_perc': 0.38
        }
    except Exception:
        return {
            'limit_up': 0,
            'limit_down': 0,
            'volume_ntd': 0,
            'margin_balance_ntd': 0,
            'mcap_est_ntd': 0,
            'margin_perc': 0.0
        }

def fetch_institutional_flow():
    """ 
    抓取三大法人買賣超金額與產業別分佈 (上市數據)
    """
    try:
        # 1. 抓取法人買賣超數據
        url_fund = "https://www.twse.com.tw/rwd/zh/fund/T86?response=json&selectType=ALL"
        res_fund = requests.get(url_fund, verify=False, timeout=15)
        fund_data = res_fund.json()
        if fund_data.get('stat') != 'OK':
            return None
        df_fund = pd.DataFrame(fund_data['data'], columns=fund_data['fields'])
        
        # 2. 抓取今日收盤價 (計算買超金額用)
        url_price = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        res_price = requests.get(url_price, verify=False, timeout=10)
        df_price = pd.DataFrame(res_price.json())
        df_price['Close'] = pd.to_numeric(df_price['ClosingPrice'].str.replace(',', ''), errors='coerce')
        
        # 合併價格數據
        df_fund = pd.merge(df_fund, df_price[['Code', 'Close']], left_on='證券代號', right_on='Code', how='left')
        
        # 計算買賣超股數
        f_col = '外資買賣超股數' if '外資買賣超股數' in df_fund.columns else '外陸資買賣超股數(不含外資自營商)'
        df_fund['外資買超張數'] = pd.to_numeric(df_fund[f_col].str.replace(',', ''), errors='coerce') / 1000
        df_fund['投信買超張數'] = pd.to_numeric(df_fund['投信買賣超股數'].str.replace(',', ''), errors='coerce') / 1000
        
        # 計算買超金額 (單位: 百萬 TWD)
        # 金額 = 張數 * 1000 * 股價 / 1,000,000 = 張數 * 股價 / 1000
        df_fund['外資買超金額'] = df_fund['外資買超張數'] * df_fund['Close'] / 1000
        df_fund['投信買超金額'] = df_fund['投信買超張數'] * df_fund['Close'] / 1000
        
        # 3. 產業別映射
        import twstock
        def get_category(code):
            code = str(code).strip()
            try:
                if code in twstock.codes:
                    info = twstock.codes[code]
                    if info.type == 'ETF':
                        return "ETF/基金"
                    return info.group if info.group else "其他"
                return "其他"
            except:
                return "其他"
        df_fund['Category'] = df_fund['證券代號'].apply(get_category)
        
        # 統計產業金額流向
        sector_agg = df_fund.groupby('Category').agg({'外資買超金額': 'sum', '投信買超金額': 'sum'})
        top_foreign_sector = sector_agg['外資買超金額'].idxmax() if not sector_agg.empty else "未知"
        top_trust_sector = sector_agg['投信買超金額'].idxmax() if not sector_agg.empty else "未知"
        
        # 取得買超金額前十名
        top_foreign = df_fund.sort_values(by='外資買超金額', ascending=False).head(10)
        top_trust = df_fund.sort_values(by='投信買超金額', ascending=False).head(10)
        
        return {
            'foreign_sector': top_foreign_sector,
            'trust_sector': top_trust_sector,
            'foreign_buys': top_foreign[['證券代號', '證券名稱', '外資買超金額']].to_dict('records'),
            'trust_buys': top_trust[['證券代號', '證券名稱', '投信買超金額']].to_dict('records')
        }
    except Exception:
        return None
