import yfinance as yf
import pandas as pd
import ta
import twstock

def debug_stock(ticker_sym, kd_mode="多頭排列 (K > D 即可)"):
    print(f"\n--- 偵錯股票: {ticker_sym} ---")
    df_daily = yf.download(ticker_sym, period="1y", interval="1d", progress=False)
    if isinstance(df_daily.columns, pd.MultiIndex):
        df_daily.columns = df_daily.columns.get_level_values(0)
    
    if df_daily.empty:
        print("下載失敗。")
        return

    # Weekly resampling
    df_wk = df_daily.resample('W').agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna()
    
    # KD
    stoch = ta.momentum.StochasticOscillator(
        high=df_wk['High'], low=df_wk['Low'], close=df_wk['Close'], window=9, smooth_window=3
    )
    df_wk['K'] = stoch.stoch()
    df_wk['D'] = stoch.stoch_signal()
    
    # OBV
    obv = ta.volume.OnBalanceVolumeIndicator(close=df_wk['Close'], volume=df_wk['Volume'])
    df_wk['OBV'] = obv.on_balance_volume()
    
    # Logic
    k_now, k_prev = df_wk['K'].iloc[-1], df_wk['K'].iloc[-2]
    d_now, d_prev = df_wk['D'].iloc[-1], df_wk['D'].iloc[-2]
    vol_wk_last = df_wk['Volume'].iloc[-2]
    vol_wk_prev = df_wk['Volume'].iloc[-3]
    obv_last = df_wk['OBV'].iloc[-2]
    obv_prev = df_wk['OBV'].iloc[-4] if len(df_wk) > 4 else df_wk['OBV'].iloc[-3]
    
    print(f"週KD: K={k_now:.1f}, D={d_now:.1f} (前週 K={k_prev:.1f}, D={d_prev:.1f})")
    print(f"週成交量: 上週={vol_wk_last/1000:.0f}張, 前週={vol_wk_prev/1000:.0f}張")
    print(f"OBV大戶: 上週={obv_last/1000:.0f}, 前週={obv_prev/1000:.0f}")
    
    kd_condition = (k_now > d_now)
    vol_up = vol_wk_last > vol_wk_prev
    acc_up = obv_last > obv_prev
    
    print(f"結果 -> KD多頭: {kd_condition}, 量能增溫: {vol_up}, 大戶吸籌: {acc_up}")
    if kd_condition and vol_up and acc_up:
        print("✅ 符合所有條件！")
    else:
        print("❌ 未能符合所有條件。")

if __name__ == "__main__":
    # Test a few popular ones to see where it fails
    debug_stock("2330.TW") # 台積電
    debug_stock("2454.TW") # 聯發科
    debug_stock("2317.TW") # 鴻海
    debug_stock("1101.TW") # 台泥
