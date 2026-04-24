import yfinance as yf
import pandas as pd
import ta
import streamlit as st
import twstock
import time
import requests

@st.cache_data(ttl=600)
def screen_stocks(tickers: list[str], show_progress=False) -> pd.DataFrame:
    """
    全能選股器：一次掃描計算所有條件 (KD, MA, 基本面)
    """
    results = []
    if not tickers: return pd.DataFrame()

    # 1. 預先抓取全局基本面與融資數據
    margin_data = fetch_all_margin_data()
    pe_data = fetch_all_pe_data()

    total = len(tickers)
    batch_size = 30
    
    progress_bar = st.progress(0.0) if show_progress else None
    status_text = st.empty() if show_progress else None

    for i in range(0, total, batch_size):
        batch = tickers[i : i + batch_size]
        if show_progress:
            progress_bar.progress((i + len(batch)) / total)
            status_text.text(f"🔍 全方位大數據掃描中: {i+1} ~ {i+len(batch)} / {total}")
            
        try:
            data = yf.download(batch, period="1y", interval="1d", group_by='ticker', threads=True, progress=False, timeout=30)
        except: continue
        
        if data.empty: continue

        for ticker_sym in batch:
            try:
                df_daily = pd.DataFrame()
                if isinstance(data, pd.DataFrame):
                    if len(batch) > 1 and ticker_sym in data:
                        df_daily = data[ticker_sym].copy()
                    else:
                        df_daily = data.copy()
                            
                if isinstance(df_daily.columns, pd.MultiIndex):
                    df_daily.columns = df_daily.columns.get_level_values(0)
                df_daily = df_daily.dropna(subset=['Close'])
                
                if df_daily.empty or len(df_daily) < 65: continue
                        
                # 共通基礎條件：成交量 > 1000張
                last_vol = df_daily['Volume'].iloc[-1]
                if last_vol < 1000000: continue
                
                core_code = ticker_sym.split(".")[0]
                match_kd = False
                match_ma = False
                match_fund = False

                # --- [1] KD 轉強 ---
                stoch = ta.momentum.StochasticOscillator(high=df_daily['High'], low=df_daily['Low'], close=df_daily['Close'], window=9, smooth_window=3)
                df_daily['K'], df_daily['D'] = stoch.stoch(), stoch.stoch_signal()
                k_now, d_now, k_prev, d_prev = df_daily['K'].iloc[-1], df_daily['D'].iloc[-1], df_daily['K'].iloc[-2], df_daily['D'].iloc[-2]
                if (k_now > d_now and k_prev <= d_prev) and k_now < 85:
                    match_kd = True
                
                # --- [2] 均線糾結 ---
                df_daily['MA5'] = df_daily['Close'].rolling(5).mean()
                df_daily['MA10'] = df_daily['Close'].rolling(10).mean()
                df_daily['MA20'] = df_daily['Close'].rolling(20).mean()
                df_daily['MA60'] = df_daily['Close'].rolling(60).mean()
                ma_vals = [df_daily['MA5'].iloc[-1], df_daily['MA10'].iloc[-1], df_daily['MA20'].iloc[-1], df_daily['MA60'].iloc[-1]]
                if not any(pd.isna(ma_vals)):
                    diff = (max(ma_vals) - min(ma_vals)) / min(ma_vals)
                    price_recent = df_daily['Close'].tail(40)
                    amplitude = (price_recent.max() - price_recent.min()) / price_recent.min()
                    is_breaking_up = df_daily['Close'].iloc[-1] >= max(ma_vals)
                    if diff < 0.05 and amplitude < 0.22 and is_breaking_up:
                        match_ma = True

                # --- [3] 價值成長 ---
                pe = pe_data.get(core_code, 999)
                margin_rate = margin_data.get(core_code, 99)
                if pe < 22 and margin_rate < 30:
                    match_fund = True

                # 如果符合任一條件，加入結果
                if match_kd or match_ma or match_fund:
                    name = twstock.codes[core_code].name if core_code in twstock.codes else "未知"
                    match_count = sum([match_kd, match_ma, match_fund])
                    
                    results.append({
                        "股票代號": core_code,
                        "名稱": name,
                        "最新價": round(df_daily['Close'].iloc[-1], 2),
                        "成交量": f"{int(last_vol/1000):,} 張",
                        "本益比": "N/A" if pe == 999 else round(pe, 1),
                        "融資率": "N/A" if margin_rate == 99 else f"{margin_rate}%",
                        "KD": match_kd,
                        "MA": match_ma,
                        "FUND": match_fund,
                        "符合數": match_count
                    })
            except: continue
            
    if show_progress:
        progress_bar.empty()
        status_text.empty()
    
    return pd.DataFrame(results)


def fetch_all_margin_data():
    """ 抓取上市/上櫃融資使用率數據 """
    margins = {}
    try:
        # TWSE (上市)
        url = "https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN"
        res = requests.get(url, verify=False, timeout=10).json()
        for item in res:
            code = item.get('股票代號', '').strip()
            # 融資使用率 = (融資餘額 / 融資限額) * 100
            # 注意：API 欄位名稱可能變動，這裡用簡單邏輯或佔比
            try:
                bal = float(item.get('融資昨日餘額', 0).replace(',', ''))
                limit = float(item.get('融資限額', 1).replace(',', ''))
                margins[code] = round((bal / limit) * 100, 2)
            except: pass
    except: pass
    return margins

def fetch_all_pe_data():
    """ 抓取上市/上櫃本益比數據 """
    pes = {}
    try:
        # TWSE
        url = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
        res = requests.get(url, verify=False, timeout=10).json()
        for item in res:
            code = item.get('Code', '').strip()
            try:
                pes[code] = float(item.get('PEratio', 999).replace(',', ''))
            except: pes[code] = 999
            
        # TPEx
        url_tpex = "https://www.tpex.org.tw/web/stock/aftertrading/peratio_analysis/pera_result.php?l=zh-tw&o=json"
        res_tpex = requests.get(url_tpex, verify=False, timeout=10).json()
        if 'tables' in res_tpex:
            for r in res_tpex['tables'][0].get('data', []):
                code = r[0].strip()
                try:
                    pes[code] = float(r[2])
                except: pass
    except: pass
    return pes

def get_all_taiwan_tickers() -> list[str]:
    import requests
    tickers = []
    try:
        res = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL", verify=False, timeout=10).json()
        for item in res:
            code = item.get('Code')
            if code and len(code) == 4: tickers.append(f"{code}.TW")
    except: pass
    try:
        res = requests.get("https://www.tpex.org.tw/web/stock/aftertrading/peratio_analysis/pera_result.php?l=zh-tw&o=json", verify=False, timeout=10).json()
        if 'tables' in res:
            for r in res['tables'][0].get('data', []):
                if len(r[0]) == 4: tickers.append(f"{r[0]}.TWO")
    except: pass
    return sorted(list(set(tickers))) if tickers else ["2330.TW", "2317.TW"]
