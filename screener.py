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
    batch_size = 100 # 增加批次大小以減少請求次數
    
    progress_bar = st.progress(0.0) if show_progress else None
    status_text = st.empty() if show_progress else None

    for i in range(0, total, batch_size):
        batch = tickers[i : i + batch_size]
        if show_progress:
            progress_bar.progress((i + len(batch)) / total)
            status_text.text(f"🔍 全方位大數據掃描中: {i+1} ~ {i+len(batch)} / {total}")
            
        try:
            # 縮短抓取期間從 1y 到 6mo，因為 MA60 只需約 65 天資料
            data = yf.download(batch, period="6mo", interval="1d", group_by='ticker', threads=True, progress=False, timeout=30)
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
                match_whale = False

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

                # --- [4] 主力吃貨 (OBV 資金量能) ---
                df_daily['OBV'] = ta.volume.OnBalanceVolumeIndicator(close=df_daily['Close'], volume=df_daily['Volume']).on_balance_volume()
                df_daily['OBV_MA10'] = df_daily['OBV'].rolling(10).mean()
                if len(df_daily) >= 20:
                    obv_recent = df_daily['OBV'].tail(20)
                    # 條件：OBV 創 20 日新高，且短期資金均線向上，代表主力越買越積極
                    if df_daily['OBV'].iloc[-1] >= obv_recent.max() and df_daily['OBV_MA10'].iloc[-1] > df_daily['OBV_MA10'].iloc[-5]:
                        match_whale = True

                # 如果符合任一條件，加入結果
                if match_kd or match_ma or match_fund or match_whale:
                    name = twstock.codes[core_code].name if core_code in twstock.codes else "未知"
                    match_count = sum([match_kd, match_ma, match_fund, match_whale])
                    
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
                        "WHALE": match_whale,
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


def get_financial_tickers() -> list[tuple[str, str, str]]:
    """ 獲取所有金融保險股 (代號, 名稱, yfinance symbol) """
    import twstock
    tickers = []
    for code, info in twstock.codes.items():
        if getattr(info, 'group', '') == "金融保險業" and len(code) == 4:
            suffix = ".TW" if info.market == "上市" else ".TWO"
            tickers.append((code, info.name, f"{code}{suffix}"))
    return sorted(tickers, key=lambda x: x[0])


@st.cache_data(ttl=3600)
def fetch_gold_stock_data(show_progress=False) -> pd.DataFrame:
    """
    抓取金融/證券/壽險股的殖利率、PEG、除息日與是否已除息資訊
    """
    import yfinance as yf
    from datetime import datetime
    
    fin_tickers = get_financial_tickers()
    results = []
    
    total = len(fin_tickers)
    progress_bar = st.progress(0.0) if show_progress else None
    status_text = st.empty() if show_progress else None
    
    # 批次獲取最新股價
    symbols = [item[2] for item in fin_tickers]
    try:
        price_data = yf.download(symbols, period="5d", interval="1d", group_by='ticker', threads=True, progress=False, timeout=20)
    except:
        price_data = pd.DataFrame()
        
    for idx, (code, name, sym) in enumerate(fin_tickers):
        if show_progress:
            progress_bar.progress((idx + 1) / total)
            status_text.text(f"⏳ 正在抓取金融股數據 ({idx + 1}/{total}): {code} {name}")
            
        price = None
        if not price_data.empty:
            try:
                if len(symbols) > 1 and sym in price_data:
                    ticker_df = price_data[sym].dropna(subset=['Close'])
                    if not ticker_df.empty:
                        price = float(ticker_df['Close'].iloc[-1])
                else:
                    ticker_df = price_data.dropna(subset=['Close'])
                    if not ticker_df.empty:
                        price = float(ticker_df['Close'].iloc[-1])
            except:
                price = None
                
        peg = "N/A"
        div_date = "N/A"
        has_paid = "N/A"
        cash_div = 0.0
        stock_div = 0.0
        cash_yield = 0.0
        stock_yield = 0.0
        total_yield = 0.0
        
        try:
            ticker = yf.Ticker(sym)
            
            # 1. 抓取 PEG
            info = ticker.info
            peg_val = info.get('pegRatio')
            if isinstance(peg_val, (int, float)):
                peg = round(peg_val, 2)
                
            # 2. 獲取最新配息事件 (從 actions)
            actions = ticker.actions
            if actions is not None and not actions.empty:
                actions_sorted = actions.sort_index(ascending=False)
                div_events = actions_sorted[(actions_sorted['Dividends'] > 0) | (actions_sorted['Stock Splits'] > 1.0)]
                if not div_events.empty:
                    latest_date = div_events.index[0]
                    div_date = latest_date.strftime('%Y-%m-%d')
                    
                    row = div_events.iloc[0]
                    cash_div = float(row['Dividends'])
                    
                    split_ratio = float(row['Stock Splits'])
                    if split_ratio > 1.0:
                        stock_div = round((split_ratio - 1.0) * 10, 2)
                    else:
                        stock_div = 0.0
                        
                    # 以 2026-07-15 基準判斷是否已除息
                    today_date = datetime(2026, 7, 15).date()
                    event_date = latest_date.date()
                    if event_date <= today_date:
                        has_paid = "已除息"
                    else:
                        has_paid = "未除息"
                        
            # 備份價格抓取
            if price is None or pd.isna(price):
                try:
                    hist = ticker.history(period="1d")
                    if not hist.empty:
                        price = float(hist['Close'].iloc[-1])
                except:
                    price = None
                    
            # 計算殖利率
            if price and price > 0:
                cash_yield = round((cash_div / price) * 100, 2)
                stock_yield = round((stock_div / 10) * 100, 2)
                total_yield = round(cash_yield + stock_yield, 2)
                
        except Exception as e:
            print(f"Error fetching {sym}: {e}")
            
        results.append({
            "股票代號": code,
            "名稱": name,
            "目前股價": round(price, 2) if price else "N/A",
            "PEG": peg,
            "最新除息日": div_date,
            "是否已除息": has_paid,
            "現金股利": cash_div,
            "股票股利": stock_div,
            "現金殖利率 (%)": cash_yield,
            "股票殖利率 (%)": stock_yield,
            "綜合殖利率 (%)": total_yield
        })
        
    if show_progress:
        progress_bar.empty()
        status_text.empty()
        
    return pd.DataFrame(results)

