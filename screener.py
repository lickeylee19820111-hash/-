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
    還原至昨日穩定版本：
    1. 週 KD 金叉
    2. 週量增
    3. OBV 趨勢向上
    4. 日成交量 > 1000 張
    """
    results = []
    if not tickers:
        return pd.DataFrame()

    total = len(tickers)
    batch_size = 20 # 降低批次，減少被阻斷機率
    
    progress_bar = st.progress(0.0) if show_progress else None
    status_text = st.empty() if show_progress else None

    for i in range(0, total, batch_size):
        batch = tickers[i : i + batch_size]
        if show_progress:
            progress_bar.progress((i + len(batch)) / total)
            status_text.text(f"🚀 掃描中: {i+1} ~ {i+len(batch)} / {total}")
            
        data = yf.download(batch, period="1y", interval="1d", group_by='ticker', threads=True, progress=False, timeout=30)
        
        if data.empty:
            print(f"⚠️ 批次素材下載失敗: {batch[:3]}...")
            continue

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
                
                # FALLBACK: 如果批量失敗，嘗試個股下載
                if df_daily.empty:
                    alt_suffix = ".TWO" if ".TW" in ticker_sym else ".TW"
                    alt_ticker = ticker_sym.split(".")[0] + alt_suffix
                    df_daily = yf.download(alt_ticker, period="1y", interval="1d", progress=False, timeout=10)
                    if isinstance(df_daily.columns, pd.MultiIndex):
                        df_daily.columns = df_daily.columns.get_level_values(0)
                    if not df_daily.empty:
                        df_daily = df_daily.dropna(subset=['Close'])

                if df_daily.empty: continue
                    
                # 1. 嚴格流動性過濾 (日量 > 1000張 = 1,000,000 股)
                last_vol = df_daily['Volume'].iloc[-1]
                if last_vol < 1000000: continue

                # 2. 技術指標
                df_wk = df_daily.resample('W').agg({
                    'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
                }).dropna()

                if len(df_wk) < 10: continue
                    
                stoch = ta.momentum.StochasticOscillator(high=df_wk['High'], low=df_wk['Low'], close=df_wk['Close'], window=9, smooth_window=3)
                df_wk['K'], df_wk['D'] = stoch.stoch(), stoch.stoch_signal()
                df_wk['OBV'] = ta.volume.OnBalanceVolumeIndicator(close=df_wk['Close'], volume=df_wk['Volume']).on_balance_volume()
                
                k_now, d_now = df_wk['K'].iloc[-1], df_wk['D'].iloc[-1]
                k_prev, d_prev = df_wk['K'].iloc[-2], df_wk['D'].iloc[-2]
                
                # 比較上一完整週與再前一週的量能判定 (避免週初數據不足)
                vol_wk_last, vol_wk_prev = df_wk['Volume'].iloc[-2], df_wk['Volume'].iloc[-3]
                obv_last, obv_prev = df_wk['OBV'].iloc[-2], df_wk['OBV'].iloc[-4] if len(df_wk) > 4 else df_wk['OBV'].iloc[-3]

                # 嚴格條件判定
                kd_cross = (k_now > d_now) and (k_prev <= d_prev)  # 剛剛黃金交叉
                vol_up = vol_wk_last > vol_wk_prev                # 週成交量增溫
                acc_up = obv_last > obv_prev                      # 資金流向轉正
                
                if kd_cross and vol_up and acc_up:
                    core_code = ticker_sym.split(".")[0]
                    name = twstock.codes[core_code].name if core_code in twstock.codes else "未知"
                    results.append({
                        "股票代號": core_code,
                        "名稱": name,
                        "最新價": round(df_daily['Close'].iloc[-1], 2),
                        "昨日成交量": f"{int(last_vol/1000):,} 張",
                        "週指標狀態": f"K:{k_now:.1f} / D:{d_now:.1f}"
                    })
            except Exception as e:
                print(f"❌ 處理 {ticker_sym} 時出錯: {e}")
                continue
            
    if show_progress:
        progress_bar.empty()
        status_text.empty()
        
    return pd.DataFrame(results)

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
