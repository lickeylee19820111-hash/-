import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime
import time

# Internal modular imports
from data_fetcher import get_stock_data, get_stock_info_from_api, resolve_taiwan_stock
from analyzer import add_technical_indicators as calculate_indicators
from screener import screen_stocks, get_all_taiwan_tickers
from plotting import render_stock_chart

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="台股大數據分析儀表板",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Style for Premium Look
st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #eee; }
    .stAlert { border-radius: 10px; }
    .stProgress > div > div > div > div { background-image: linear-gradient(to right, #00C9FF, #92FE9D); }
    [data-testid="stSidebarNav"] { display: none; }
</style>
""", unsafe_allow_html=True)

# --- SESSION STATE ---
if 'active_ticker' not in st.session_state:
    st.session_state.active_ticker = "2330.TW"
# Force refresh on ticker switch
if 'last_loaded' not in st.session_state:
    st.session_state.last_loaded = ""
if 'screen_results' not in st.session_state:
    st.session_state.screen_results = pd.DataFrame()

# --- SIDEBAR: SCANNER ---
with st.sidebar:
    st.title("🛡️ 智慧選股掃描")
    st.info("條件：週K金叉、週量齊揚、大戶吃貨(OBV)")
    
    if st.button("🚀 開始全市場大掃描 (上市+上櫃)", use_container_width=True):
        all_tickers = get_all_taiwan_tickers()
        if all_tickers:
            with st.spinner("🔍 正在聯網大數據分析..."):
                results = screen_stocks(all_tickers, show_progress=True)
                st.session_state.screen_results = results
        else:
            st.warning("⚠️ 無法獲取代碼清單，請稍後再試。")
    
    if not st.session_state.screen_results.empty:
        df_res = st.session_state.screen_results
        st.success(f"✅ 掃描完成！發現 {len(df_res)} 支強勢股")
        
        # Display clickable results in sidebar
        for idx, row in df_res.iterrows():
            code = str(row['股票代號'])
            full_code, name = resolve_taiwan_stock(code)
            if st.button(f"{code} {name} | {row['最新價']}", 
                         key=f"sc_btn_{code}", 
                         width="stretch"):
                st.session_state.active_ticker = full_code
                st.rerun()
    else:
        st.write("目前尚未點擊掃描")

# --- MAIN PAGE ---
st.title("📈 台股個股精確分析")

# Navigation & Search Row
c1, c2, c3, c4 = st.columns([2, 1, 1, 2])
with c1:
    user_input = st.text_input("輸入台股代碼或股名", 
                                  value=st.session_state.active_ticker.split('.')[0],
                                  key=f"search_input_{st.session_state.last_loaded}")
    
    if user_input:
        resolved_ticker, resolved_name = resolve_taiwan_stock(user_input)
        if resolved_ticker != st.session_state.active_ticker:
            st.session_state.active_ticker = resolved_ticker
            # We don't rerun immediately here because it might be middle of typing, 
            # but for simplicity in scanner.py let's just let it be.

with c2:
    if st.button("⏮️ 上一檔"):
        if not st.session_state.screen_results.empty:
            df = st.session_state.screen_results
            codes = df['股票代號'].tolist()
            # Find current in codes
            current_code = st.session_state.active_ticker.split('.')[0]
            if current_code in codes:
                curr_idx = codes.index(current_code)
                next_raw = codes[(curr_idx - 1) % len(codes)]
                next_full, _ = resolve_taiwan_stock(next_raw)
                st.session_state.active_ticker = next_full
                st.rerun()

with c3:
    if st.button("下一檔 ⏭️"):
        if not st.session_state.screen_results.empty:
            df = st.session_state.screen_results
            codes = df['股票代號'].tolist()
            current_code = st.session_state.active_ticker.split('.')[0]
            if current_code in codes:
                curr_idx = codes.index(current_code)
                next_raw = codes[(curr_idx + 1) % len(codes)]
                next_full, _ = resolve_taiwan_stock(next_raw)
                st.session_state.active_ticker = next_full
                st.rerun()

with c4:
    st.write(f"當前關注：**{st.session_state.active_ticker}**")

# --- DATA PROCESSING ---
try:
    with st.spinner(f"📥 載入 {st.session_state.active_ticker} 資料中..."):
        # Fix suffix if needed (.TWO handling)
        current_ticker = st.session_state.active_ticker
        df = get_stock_data(current_ticker)
        
        # ROBUSTNESS: If .TW fails, try .TWO automatically (for OTC stocks)
        if df.empty or len(df) < 5:
            otc_ticker = current_ticker.replace(".TW", ".TWO")
            df = get_stock_data(otc_ticker)
            if not df.empty:
                st.session_state.active_ticker = otc_ticker
                current_ticker = otc_ticker

        if not df.empty and len(df) > 5:
            # Drop NaNs to prevent $nan in metrics
            df = df.dropna(subset=['Close'])
            
            # 1. Fetch info
            ticker_pure_code = current_ticker.split('.')[0]
            stock_name = get_stock_info_from_api(ticker_pure_code)
            
            # 2. Indicators
            df = calculate_indicators(df)
            
            # ROBUST PRICE HANDLING
            last_valid_close = df['Close'].dropna().iloc[-1]
            prev_close = df['Close'].dropna().iloc[-2] if len(df) > 1 else last_valid_close
            change_val = last_valid_close - prev_close
            change_pct = (change_val / prev_close * 100) if prev_close != 0 else 0
            
            # 3. METRICS
            st.header(f"{ticker_pure_code} {stock_name}")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("目前股價", f"${last_valid_close:.2f}", f"{change_val:+.2f} ({change_pct:+.2f}%)")
            
            last_row = df.iloc[-1]
            m2.metric("MA20 月線", f"{last_row['MA20']:.2f}", 
                      f"偏離 {((last_valid_close/last_row['MA20']-1)*100):.1f}%")
            m3.metric("RSI (14)", f"{last_row['RSI']:.1f}")
            m4.metric("布林通道", "正向" if last_valid_close > last_row['BB_Mid'] else "震盪")
            
            # 4. CHART
            fig = render_stock_chart(df, f"{ticker_pure_code} {stock_name}")
            st.plotly_chart(fig, use_container_width=True, theme="streamlit")
            
            # 5. STRATEGY SUMMARY
            with st.expander("📝 技術分析總總結 (核心分析)"):
                st.write(f"目前 {stock_name} 的趨勢判斷如下：")
                if last_valid_close > last_row['MA20'] and last_row['RSI'] < 70:
                    st.success("✅ 多頭排列：股價位於均線之上，動力充足。")
                elif last_row['RSI'] > 80:
                    st.warning("⚠️ 短線過熱：RSI 大於 80，請留意回檔風險。")
                else:
                    st.info("ℹ️ 區間震盪：均線走平，建議觀望突破。")

        else:
            st.error(f"❌ 無法取得股票資料 ({current_ticker})。原因：代碼錯誤、Yahoo Finance 暫時限制 IP、或該股票今日無成交。")
            st.info("建議：請確認代碼是否正確 (例如 2330)，或換一支股票試試。")

except Exception as e:
    st.error(f"⚠️ 系統異常: {str(e)}")
    st.info("請嘗試重新整理整理頁面。")
