import yfinance as yf
import pandas as pd
import ta
import streamlit as st
import twstock
import time
import requests

# Optimization: Use a shared session to avoid "Connection pool is full" warnings
session = requests.Session()
session.verify = False 

@st.cache_data(ttl=1800)
def screen_stocks(tickers: list[str], show_progress=False) -> pd.DataFrame:
    """
    Scans a list of stocks for:
    1. Weekly KD Golden Cross
    2. Weekly Volume Increasing
    3. Institutional Accumulation (OBV proxy)
    4. Daily Volume > 1000 lots (1,000,000 shares)
    
    Optimized for Streamlit Cloud using Bulk Download to bypass Rate Limits.
    """
    results = []
    if not tickers:
        return pd.DataFrame()

    total = len(tickers)
    batch_size = 50 # Process 50 tickers at a time to stay within limits and speed up
    
    progress_bar = None
    status_text = None
    if show_progress:
        progress_bar = st.progress(0.0)
        status_text = st.empty()

    for i in range(0, total, batch_size):
        batch = tickers[i : i + batch_size]
        
        if show_progress:
            progress_bar.progress((i + len(batch)) / total)
            status_text.text(f"🚀 批量大數據掃描中: {i+1} ~ {i+len(batch)} / {total}")
            
        try:
            # Multi-threading download for speed
            data = yf.download(batch, period="1y", interval="1d", group_by='ticker', threads=True, progress=False, timeout=30, session=session)
            
            for ticker_sym in batch:
                try:
                    df_daily = pd.DataFrame()
                    if len(batch) > 1:
                        if ticker_sym in data:
                            df_daily = data[ticker_sym].dropna(subset=['Close'])
                    else:
                        df_daily = data.dropna(subset=['Close'])
                    
                    # FALLBACK: If batch download failed for this ticker, try individual download with suffix swap
                    if df_daily.empty:
                        alt_suffix = ".TWO" if ".TW" in ticker_sym else ".TW"
                        alt_ticker = ticker_sym.split(".")[0] + alt_suffix
                        df_daily = yf.download(alt_ticker, period="1y", interval="1d", progress=False, timeout=10)
                        if not df_daily.empty:
                            df_daily = df_daily.dropna(subset=['Close'])

                    if df_daily.empty or len(df_daily) < 30:
                        continue
                        
                    # 1. LIQUIDITY CHECK: Daily Volume > 1000 lots (1,000,000 shares)
                    last_vol_daily = df_daily['Volume'].iloc[-1]
                    if last_vol_daily < 1000000:
                        continue

                    # 2. WEEKLY RESAMPLING (In-Memory, no extra network)
                    # This creates the weekly K-line from daily data
                    df_wk = df_daily.resample('W').agg({
                        'Open': 'first',
                        'High': 'max',
                        'Low': 'min',
                        'Close': 'last',
                        'Volume': 'sum'
                    }).dropna()

                    if len(df_wk) < 10:
                        continue
                        
                    # 3. KD Indicator
                    stoch = ta.momentum.StochasticOscillator(
                        high=df_wk['High'], low=df_wk['Low'], close=df_wk['Close'], 
                        window=9, smooth_window=3
                    )
                    df_wk['K'] = stoch.stoch()
                    df_wk['D'] = stoch.stoch_signal()
                    
                    # 4. OBV proxy for smart money
                    obv = ta.volume.OnBalanceVolumeIndicator(close=df_wk['Close'], volume=df_wk['Volume'])
                    df_wk['OBV'] = obv.on_balance_volume()
                    
                    # 5. Logical Checks
                    k_now, k_prev = df_wk['K'].iloc[-1], df_wk['K'].iloc[-2]
                    d_now, d_prev = df_wk['D'].iloc[-1], df_wk['D'].iloc[-2]
                    vol_wk_now, vol_wk_prev = df_wk['Volume'].iloc[-1], df_wk['Volume'].iloc[-2]
                    obv_now, obv_prev_2 = df_wk['OBV'].iloc[-1], df_wk['OBV'].iloc[-3]
                    
                    # Conditions
                    kd_cross = (k_now > d_now) and (k_prev <= d_prev)
                    vol_up = vol_wk_now > vol_wk_prev
                    acc_up = obv_now > obv_prev_2
                    
                    if kd_cross and vol_up and acc_up:
                        core_code = ticker_sym.split(".")[0]
                        results.append({
                            "股票代號": core_code,
                            "名稱": twstock.codes[core_code].name if core_code in twstock.codes else "未知",
                            "最新價": round(df_daily['Close'].iloc[-1], 2),
                            "昨日成交張數": f"{int(last_vol_daily/1000):,} 張",
                            "週K/D值": f"{k_now:.1f}/{d_now:.1f}",
                            "週量能": "📈 增溫"
                        })
                except Exception:
                    continue
            
            # Short cooldown to avoid IP blocking during large batches
            time.sleep(0.5)
            
        except Exception:
            continue
            
    if show_progress:
        progress_bar.empty()
        status_text.empty()
        
    return pd.DataFrame(results)

def get_all_taiwan_tickers() -> list[str]:
    """ 
    Returns all valid stock tickers from TWSE and TPEx mapped to yfinance suffixes.
    Uses official OpenAPIs for 100% accuracy.
    """
    import requests
    tickers = []
    
    # 1. Fetch Listed Stocks (TWSE)
    try:
        url_twse = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
        res = requests.get(url_twse, verify=False, timeout=10)
        if res.status_code == 200:
            data = res.json()
            twse_cnt = 0
            for item in data:
                code = item.get('Code')
                if code and len(code) == 4: # Regular stocks
                    tickers.append(f"{code}.TW")
                    twse_cnt += 1
            print(f"TWSE 上市：取得 {twse_cnt} 筆")
    except Exception as e:
        print(f"TWSE Fetch Error: {e}")

    # 2. Fetch OTC Stocks (TPEx)
    try:
        url_tpex = "https://www.tpex.org.tw/web/stock/aftertrading/peratio_analysis/pera_result.php?l=zh-tw&o=json"
        res = requests.get(url_tpex, verify=False, timeout=10)
        if res.status_code == 200:
            data = res.json()
            tpex_cnt = 0
            if 'tables' in data and len(data['tables']) > 0:
                rows = data['tables'][0].get('data', [])
                for r in rows:
                    code = r[0]
                    if code and len(code) == 4:
                        tickers.append(f"{code}.TWO")
                        tpex_cnt += 1
            print(f"TPEx 上櫃：取得 {tpex_cnt} 筆")
    except Exception as e:
        print(f"TPEx Fetch Error: {e}")

    if not tickers:
        print("Falling back to default watchlist...")
        return get_default_watchlist()
        
    print(f"全台股合計：{len(tickers)} 檔")
    return sorted(list(set(tickers)))

def get_default_watchlist() -> list[str]:
    """ Returns a hardcoded fallback watchlist """
    return ["2330.TW", "2317.TW", "2454.TW", "2308.TW", "2382.TW", "3231.TW", "2356.TW"]
