import yfinance as yf
import pandas as pd
import ta
import streamlit as st
import twstock
import time
import requests

@st.cache_data(ttl=600) 
def screen_stocks(tickers: list[str], show_progress=False, mode="KD轉強") -> pd.DataFrame:
    """
    雙模式選股器：
    1. KD轉強 (昨日設定)
    2. 均線糾結 (我的選股)
    """
    results = []
    if not tickers: return pd.DataFrame()

    total = len(tickers)
    batch_size = 20
    
    progress_bar = st.progress(0.0) if show_progress else None
    status_text = st.empty() if show_progress else None

    for i in range(0, total, batch_size):
        batch = tickers[i : i + batch_size]
        if show_progress:
            progress_bar.progress((i + len(batch)) / total)
            status_text.text(f"🚀 {mode} 掃描中: {i+1} ~ {i+len(batch)} / {total}")
            
        data = yf.download(batch, period="1y", interval="1d", group_by='ticker', threads=True, progress=False, timeout=30)
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
                
                # FALLBACK
                if df_daily.empty:
                    alt_suffix = ".TWO" if ".TW" in ticker_sym else ".TW"
                    alt_ticker = ticker_sym.split(".")[0] + alt_suffix
                    df_daily = yf.download(alt_ticker, period="1y", interval="1d", progress=False, timeout=10)
                    if isinstance(df_daily.columns, pd.MultiIndex): df_daily.columns = df_daily.columns.get_level_values(0)
                    if not df_daily.empty: df_daily = df_daily.dropna(subset=['Close'])

                if df_daily.empty or len(df_daily) < 65: continue
                        
                # 共通條件：日量 > 1000張
                last_vol = df_daily['Volume'].iloc[-1]
                if last_vol < 1000000: continue

                if mode == "KD轉強":
                    # --- [模式1] 週KD交叉相關邏輯 ---
                    df_wk = df_daily.resample('W').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}).dropna()
                    if len(df_wk) < 10: continue
                    stoch = ta.momentum.StochasticOscillator(high=df_wk['High'], low=df_wk['Low'], close=df_wk['Close'], window=9, smooth_window=3)
                    df_wk['K'], df_wk['D'] = stoch.stoch(), stoch.stoch_signal()
                    df_wk['OBV'] = ta.volume.OnBalanceVolumeIndicator(close=df_wk['Close'], volume=df_wk['Volume']).on_balance_volume()
                    k_now, d_now, k_prev, d_prev = df_wk['K'].iloc[-1], df_wk['D'].iloc[-1], df_wk['K'].iloc[-2], df_wk['D'].iloc[-2]
                    vol_wk_last, vol_wk_prev = df_wk['Volume'].iloc[-2], df_wk['Volume'].iloc[-3]
                    obv_last, obv_prev = df_wk['OBV'].iloc[-2], df_wk['OBV'].iloc[-3]
                    
                    if (k_now > d_now and k_prev <= d_prev) and (vol_wk_last > vol_wk_prev) and (obv_last > obv_prev):
                        pass # 符合條件，後續統一加入
                    else: continue

                elif mode == "均線糾結":
                    # --- [模式2] 均線糾結邏輯 ---
                    # 計算 5, 10, 20, 60 MA
                    df_daily['MA5'] = df_daily['Close'].rolling(5).mean()
                    df_daily['MA10'] = df_daily['Close'].rolling(10).mean()
                    df_daily['MA20'] = df_daily['Close'].rolling(20).mean()
                    df_daily['MA60'] = df_daily['Close'].rolling(60).mean()
                    
                    # 取最新一天的 MA 值
                    ma_vals = [df_daily['MA5'].iloc[-1], df_daily['MA10'].iloc[-1], df_daily['MA20'].iloc[-1], df_daily['MA60'].iloc[-1]]
                    if any(pd.isna(ma_vals)): continue
                    
                    # 判斷糾結度 (最高均線與最低均線價差在 3% 以內)
                    diff = (max(ma_vals) - min(ma_vals)) / min(ma_vals)
                    is_converged = diff < 0.03 
                    
                    # 判斷橫盤整理 (最近 40 天股價高低震幅 < 15%)
                    price_recent = df_daily['Close'].tail(40)
                    amplitude = (price_recent.max() - price_recent.min()) / price_recent.min()
                    is_sideways = amplitude < 0.15
                    
                    # 即將往上 (收盤價站上所有均線，且當天不跌)
                    is_breaking_up = df_daily['Close'].iloc[-1] >= max(ma_vals) and df_daily['Close'].iloc[-1] >= df_daily['Close'].iloc[-2]
                    
                    if is_converged and is_sideways and is_breaking_up:
                        pass # 符合條件
                    else: continue

                # 通過篩選，加入結果清單
                core_code = ticker_sym.split(".")[0]
                name = twstock.codes[core_code].name if core_code in twstock.codes else "未知"
                results.append({
                    "股票代號": core_code,
                    "名稱": name,
                    "最新價": round(df_daily['Close'].iloc[-1], 2),
                    "昨日成交量": f"{int(last_vol/1000):,} 張",
                    "篩選模式": mode
                })
            except: continue
            
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
