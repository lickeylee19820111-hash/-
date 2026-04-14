import pandas as pd
import streamlit as st

from data_fetcher import fetch_stock_data, fetch_stock_info, fetch_fundamental_data, resolve_taiwan_stock, fetch_market_summary, fetch_institutional_flow, get_stock_info_from_api
from analyzer import add_technical_indicators, evaluate_entry_exit
from screener import screen_stocks, get_all_taiwan_tickers
from plotting import render_stock_chart

st.set_page_config(page_title="Stock Analyzer Pro", layout="wide", page_icon="📈")

# Sidebar
st.sidebar.title("📈 Stock Analyzer Pro")
st.sidebar.write("Analyze future potential and find the best entry/exit points.")

st.sidebar.divider()
if st.sidebar.button("📊 顯示大盤大數據"):
    st.session_state['show_market'] = not st.session_state.get('show_market', False)
st.sidebar.divider()
if 'active_ticker' not in st.session_state:
    st.session_state['active_ticker'] = "2330"
if 'input_key_suffix' not in st.session_state:
    st.session_state['input_key_suffix'] = 0

widget_key = f"ticker_input_{st.session_state['input_key_suffix']}"

ticker_val = st.sidebar.text_input(
    "輸入台股代碼或股名 (例如: 2330 或 台積電)", 
    value=st.session_state['active_ticker'],
    key=widget_key
)

if ticker_val and ticker_val != st.session_state['active_ticker']:
    st.session_state['active_ticker'] = ticker_val
    st.session_state['auto_analyze'] = True
    st.rerun()
period = st.sidebar.selectbox("分析區間", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=3)
interval_option = st.sidebar.radio("K線週期", ["日K", "週K", "月K"], index=0)
interval_map = {"日K": "1d", "週K": "1wk", "月K": "1mo"}
interval = interval_map[interval_option]

st.sidebar.divider()
st.sidebar.subheader("🌟 獨家進階功能")
if st.sidebar.button("🔎 我的選股 (快速掃描)"):
    st.session_state['mode'] = 'screener'
if st.sidebar.button("🏠 回到首頁 (個股分析)"):
    st.session_state['mode'] = 'home'

# Automatically format Taiwan stock tickers and resolve name
formatted_ticker, chinese_name = resolve_taiwan_stock(st.session_state['active_ticker'])

if st.session_state.get('mode', 'home') == 'screener':
    st.header("🔎 全台股大數據掃描 (獨家篩選器)")
    st.write("這是一個自動化掃描儀器，自動為您掃描 **全台灣上市/上櫃股票**，篩選同時符合：**週ＫＤ黃金交叉** ➕ **週成交量增溫** ➕ **資金流向轉正** 的飆股潛力股。")
    
    st.info("💡 提醒：掃描全台股約需 1-2 分鐘，請耐心等候掃描完成。結果會自動緩存 30 分鐘，避免重複抓取。")
    
    if st.button("🚀 開始掃描全台股個股"):
        all_tickers = get_all_taiwan_tickers()
        # Add a placeholder for liquidity filtering
        st.write(f"正在從 {len(all_tickers)} 檔股票中，篩選成交量大於 1000 張且符合起漲條件的個股...")
        res = screen_stocks(all_tickers, show_progress=True)
        st.session_state['scan_res_df'] = res
        st.session_state['scan_count'] = len(all_tickers)
        st.session_state['nav_list'] = res['股票代號'].astype(str).tolist() if not res.empty else []
            
    if 'scan_res_df' in st.session_state:
        res_df = st.session_state['scan_res_df']
        scan_count = st.session_state.get('scan_count', 0)
        if not res_df.empty:
            st.success(f"太棒了！在 {scan_count} 檔股票中，發現了 {len(res_df)} 檔近期符合所有『起漲吃貨條件』的潛力股 🎉")
            st.dataframe(res_df, width="stretch")
            
            st.markdown("### 🎯 點擊按鈕一鍵進行個股分析")
            cols = st.columns(4)
            for i, row in res_df.iterrows():
                col = cols[i % 4]
                code = row['股票代號']
                if col.button(f"📊 分析 {code}", key=f"analyze_{code}"):
                    st.session_state['active_ticker'] = str(code)
                    st.session_state['input_key_suffix'] += 1
                    st.session_state['mode'] = 'home'
                    st.session_state['auto_analyze'] = True
                    st.rerun()
        else:
            st.warning("目前這份觀察清單中，這週尚未有股票同時滿足所有條件哦。可以嘗試加入更多標的！")

elif st.session_state.get('mode', 'home') == 'home':
    if st.session_state.get('show_market', False):
        st.header("💡 台股大盤總覽 (最新收盤日)")
        with st.spinner("抓取最新大盤數據中..."):
            mkt_data = fetch_market_summary()
            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("漲停家數", f"📈 {mkt_data['limit_up']} 家")
            m2.metric("跌停家數", f"📉 {mkt_data['limit_down']} 家")
            m3.metric("大盤總成交量", f"{mkt_data['volume_ntd']/100000000:,.0f} 億")
            m4.metric("上市融資餘額", f"{mkt_data['margin_balance_ntd']/100000000:,.0f} 億")
            m5.metric("台股總市值", f"{mkt_data['mcap_est_ntd']/1000000000000:,.2f} 兆", help="大盤市值使用台積電實時權重佔比做動態推算")
            m6.metric("融資占市值比例", f"{mkt_data['margin_perc']:.2f} %")
        st.divider()
        
        # --- Institutional Flow Section ---
        st.subheader("🏦 三大法人資金流向 (最新外資/投信買超)")
        with st.status("正在大數據分析法人流向...", expanded=False) as status:
            inst_data = fetch_institutional_flow()
            status.update(label="法人流向分析完成！", state="complete", expanded=True)
        
        if inst_data:
            i_col1, i_col2 = st.columns(2)
            
            with i_col1:
                st.markdown(f"🚩 **外資買超產業：** <span style='color:orange; font-size:20px;'>{inst_data['foreign_sector']}</span>", unsafe_allow_html=True)
                st.write("外資買超金額前十名：")
                for item in inst_data['foreign_buys']:
                    code = item['證券代號']
                    amt_m = item['外資買超金額']
                    if st.button(f"🏢 {code} {item['證券名稱']} | +{amt_m:,.0f} 百萬", key=f"fund_f_{code}", use_container_width=True):
                        st.session_state['active_ticker'] = str(code)
                        st.session_state['input_key_suffix'] += 1
                        st.session_state['mode'] = 'home'
                        st.session_state['auto_analyze'] = True
                        st.rerun()

            with i_col2:
                st.markdown(f"🚩 **投信買超產業：** <span style='color:lightgreen; font-size:20px;'>{inst_data['trust_sector']}</span>", unsafe_allow_html=True)
                st.write("投信買超金額前十名：")
                for item in inst_data['trust_buys']:
                    code = item['證券代號']
                    amt_m = item['投信買超金額']
                    if st.button(f"🏢 {code} {item['證券名稱']} | +{amt_m:,.0f} 百萬", key=f"fund_t_{code}", use_container_width=True):
                        st.session_state['active_ticker'] = str(code)
                        st.session_state['input_key_suffix'] += 1
                        st.session_state['mode'] = 'home'
                        st.session_state['auto_analyze'] = True
                        st.rerun()
        else:
            st.info("三大法人數據正由交易所計算更新中，請稍後再試。")
            
        st.divider()

    if st.sidebar.button("開始分析"):
        st.session_state['show_analysis'] = True
        
    if st.session_state.get('auto_analyze', False):
        st.session_state['show_analysis'] = True
        st.session_state['auto_analyze'] = False

    if st.session_state.get('show_analysis', False):
        with st.spinner(f"正在載入 {formatted_ticker} 的資料..."):
            df = fetch_stock_data(formatted_ticker, period, interval)
            info = fetch_stock_info(formatted_ticker)
            fundamentals = fetch_fundamental_data(formatted_ticker)

        if df is not None and not df.empty:
            # Navigation Bar (Next/Prev)
            nav_list = st.session_state.get('nav_list', [])
            if nav_list:
                core_code = formatted_ticker.split('.')[0]
                if core_code in nav_list:
                    current_idx = nav_list.index(core_code)
                    n_col1, n_col2, n_col3 = st.columns([1, 2, 1])
                    
                    if current_idx > 0:
                        prev_code = nav_list[current_idx - 1]
                        if n_col1.button(f"⬅️ 上一檔 ({prev_code})", key="btn_prev_nav"):
                            st.session_state['active_ticker'] = str(prev_code)
                            st.session_state['input_key_suffix'] += 1
                            st.session_state['auto_analyze'] = True
                            st.session_state['show_analysis'] = True
                            st.rerun()
                    
                    # Create labels for the selectbox: "Code Name"
                    opt_labels = {code: f"{code} {get_stock_info_from_api(code)}" for code in nav_list}
                    
                    selected_jump = n_col2.selectbox(
                        "快速選股",
                        options=nav_list,
                        index=current_idx,
                        format_func=lambda x: opt_labels.get(x, x),
                        label_visibility="collapsed",
                        key=f"nav_jump_{core_code}" # Unique key per stock to avoid conflict
                    )
                    
                    if selected_jump != core_code:
                        st.session_state['active_ticker'] = str(selected_jump)
                        st.session_state['input_key_suffix'] += 1
                        st.session_state['auto_analyze'] = True
                        st.session_state['show_analysis'] = True
                        st.rerun()
                    
                    if current_idx < len(nav_list) - 1:
                        next_code = nav_list[current_idx + 1]
                        if n_col3.button(f"下一檔 ({next_code}) ➡️", key="btn_next_nav"):
                            st.session_state['active_ticker'] = str(next_code)
                            st.session_state['input_key_suffix'] += 1
                            st.session_state['auto_analyze'] = True
                            st.session_state['show_analysis'] = True # Ensure analysis stays open
                            st.rerun()
                            
            # Title and basic info
            st.header(f"📊 分析報告: {chinese_name} ({formatted_ticker})")
            
            # Add Technical Indicators
            df_analyzed = add_technical_indicators(df)
            
            # Evaluate Entry/Exit
            eval_result = evaluate_entry_exit(df_analyzed)
            
            # Metrics Display
            # Detailed prediction and metrics
            st.subheader("🎯 核心指標與進出建議")
            t_col1, t_col2, t_col3, t_col4 = st.columns(4)
            
            # Determine trend text and color
            trend = eval_result.get('trend', 'Neutral')
            trend_map = {
                "Bullish": ("🚀 強勢多頭", "lightgreen"),
                "Bearish": ("📉 弱勢空頭", "lightcoral"),
                "Neutral": ("⚖️ 區間盤整", "gray")
            }
            trend_txt, trend_clr = trend_map.get(trend, ("⚖️ 盤整", "gray"))
            
            t_col1.metric("目前股價", f"${eval_result.get('current_price', 0):.2f}")
            t_col2.metric("建議承接價", f"${eval_result.get('suggested_entry', 0):.2f}")
            t_col3.metric("波段壓力位", f"${eval_result.get('suggested_exit', 0):.2f}")
            t_col4.markdown(f"**技術面趨勢:**<br><span style='color:{trend_clr}; font-size: 20px;'>{trend_txt}</span>", unsafe_allow_html=True)
            
            st.divider()
    
            # Fundamentals Section
            st.subheader("🏢 基本面財務數據")
            f_col1, f_col2, f_col3, f_col4 = st.columns(4)
            
            # Safe string formatting for possible N/A
            mcap_val = fundamentals.get('Market Cap', 0)
            mcap_str = f"${mcap_val / 1e8:.2f} 億" if isinstance(mcap_val, (int, float)) else "N/A"
                
            f_col1.metric("市值", mcap_str)
            f_col2.metric("本益比 (PE)", f"{fundamentals.get('Trailing P/E', 'N/A')}")
            f_col3.metric("每股盈餘 (EPS)", f"{fundamentals.get('EPS (Trailing)', 'N/A')}")
            f_col4.metric("殖利率 (Yield)", f"{fundamentals.get('Dividend Yield', 'N/A')}")
            
            st.divider()

            # Plotting
            st.subheader("📈 股價走勢與技術指標 (Price & Technicals)")
            
            # Generate and Display Modularized Plotly Chart
            fig = render_stock_chart(df_analyzed, eval_result)
            st.plotly_chart(fig, width="stretch")
            
            # Details section
            with st.expander("📝 如何解讀這些指標？"):
                st.markdown("""
                **技術指標:**
                - **K線圖 (Candlestick)**: 顯示時間段內的開盤、最高、最低及收盤價。
                - **布林通道 (Bollinger Bands)**: 灰色區間。協助判斷超買/超賣現象及波動率。觸及下軌通常是短線買點，觸及上軌是短線賣點。
                - **MACD (平滑異同移動平均線)**: 趨勢動能指標。綠色柱狀體表示多頭動能，紅色為空頭。
                - **RSI (相對強弱指標)**: 價格動能。RSI > 70 視為超買(賣出訊號)，RSI < 30 視為超賣(買進訊號)。
                - **KD (隨機指標)**: 衡量股價相對高低位置。K值向上交叉D值為黃金交叉(買進訊號)，K值向下交叉D值為死亡交叉(賣出訊號)。KD > 80 為超買，KD < 20 為超賣。
                
                **進出場邏輯 (技術面):**
                - 建議進場/出場點是根據近期的歷史支撐壓力位以及布林通道的標準差計算而出，提供量化的波段操作參考。 
                
                *免責聲明：此軟體提供之數據與分析僅供學習與參考，不構成任何投資建議。投資有風險，請謹慎評估。*
                """)
                
        else:
            st.warning("找不到該股票或時段的資料，請檢查代碼或名稱是否正確！(台股請直接輸入數字代碼或中文公司簡稱，例如: 2330 或 台積電)")
    else:
        st.info("👈 請在左邊側邊欄輸入股票代碼或股名 (例: 2330 或 鴻海)，並點擊「開始分析」。")
