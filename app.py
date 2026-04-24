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
    st.write("這是一個自動化掃描儀器，自動為您掃描 **全台灣上市/上櫃股票**。")
    
    st.info("💡 提醒：掃描全台股約需 1-2 分鐘，請耐心等候掃描完成。結果會自動緩存 10 分鐘。")
    
    st.info("💡 提醒：點擊下方按鈕將一次掃描『技術面、籌碼面、基本面』所有條件。掃描全台股約需 1-2 分鐘，請耐心等候。")
    
    if st.button("🚀 開始全市場大數據掃描 (上市+上櫃)", use_container_width=True):
        all_tickers = get_all_taiwan_tickers()
        st.write(f"正在掃描全市場 {len(all_tickers)} 檔股票，計算多重指標中...")
        
        # 執行全能掃描
        res = screen_stocks(all_tickers, show_progress=True)
        st.session_state['scan_res_df'] = res
        st.session_state['scan_count'] = len(all_tickers)
        st.session_state['nav_list'] = res['股票代號'].astype(str).tolist() if not res.empty else []
            
    if 'scan_res_df' in st.session_state:
        res_df = st.session_state['scan_res_df']
        scan_count = st.session_state.get('scan_count', 0)
        
        if not res_df.empty:
            # 分類結果
            # 1. 重複兩次出現即可 (符合數 >= 2)
            dual_match = res_df[res_df['符合數'] >= 2].sort_values(by='符合數', ascending=False)
            # 2. 個別條件
            kd_res = res_df[res_df['KD'] == True]
            ma_res = res_df[res_df['MA'] == True]
            fund_res = res_df[res_df['FUND'] == True]

            st.success(f"掃描完成！在 {scan_count} 檔中發現了多個潛力標的。")
            
            # 使用分頁顯示
            t1, t2, t3, t4 = st.tabs([
                f"🏆 強勢組合 ({len(dual_match)})", 
                f"📈 KD轉強 ({len(kd_res)})", 
                f"🧘 均線糾結 ({len(ma_res)})", 
                f"💰 價值成長 ({len(fund_res)})"
            ])
            
            def render_analysis_buttons(df_target, prefix):
                if df_target.empty:
                    st.write("此分類目前無符合股票。")
                    return
                st.markdown("---")
                st.markdown(f"### 🎯 點擊按鈕進行個股分析 ({prefix})")
                cols = st.columns(4)
                for i, (idx, row) in enumerate(df_target.iterrows()):
                    if i >= 12: break # 每頁最多顯示 12 個按鈕以免太亂
                    col = cols[i % 4]
                    code = row['股票代號']
                    if col.button(f"📊 分析 {code}", key=f"analyze_{prefix}_{code}"):
                        st.session_state['active_ticker'] = str(code)
                        st.session_state['input_key_suffix'] += 1
                        st.session_state['mode'] = 'home'
                        st.session_state['auto_analyze'] = True
                        st.rerun()

            with t1:
                st.write("🎯 **強勢組合**：同時符合 **2 個或以上** 篩選條件的優質標的。")
                st.dataframe(dual_match, width="stretch")
                render_analysis_buttons(dual_match, "combo")
            with t2:
                st.write("📈 **KD 轉強**：日K黃金交叉，起漲動能強。")
                st.dataframe(kd_res, width="stretch")
                render_analysis_buttons(kd_res, "kd")
            with t3:
                st.write("🧘 **均線糾結**：均線高度靠攏後突破，適合波段佈局。")
                st.dataframe(ma_res, width="stretch")
                render_analysis_buttons(ma_res, "ma")
            with t4:
                st.write("💰 **價值成長**：低本益比 + 低融資率，下檔有撐且籌碼乾淨。")
                st.dataframe(fund_res, width="stretch")
                render_analysis_buttons(fund_res, "fund")
        else:
            st.warning("目前市場上尚未發現符合條件的股票。")

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
            # Safe string formatting for possible N/A
            mcap_str = str(fundamentals.get('Market Cap', 'N/A'))
                
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
