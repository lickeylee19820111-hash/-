import pandas as pd
import numpy as np
import ta
from typing import Dict

def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add basic technical indicators like MACD, RSI, and Bollinger Bands.
    """
    # Make a copy to avoid SettingWithCopyWarning
    if df.empty:
        return df
    df = df.copy()
    
    # 1. MACD
    macd = ta.trend.MACD(close=df['Close'])
    df['MACD'] = macd.macd()
    df['MACD_Signal'] = macd.macd_signal()
    df['MACD_Diff'] = macd.macd_diff()
    
    # 2. RSI
    df['RSI'] = ta.momentum.RSIIndicator(close=df['Close']).rsi()
    
    # 3. Bollinger Bands
    bollinger = ta.volatility.BollingerBands(close=df['Close'])
    df['BB_High'] = bollinger.bollinger_hband()
    df['BB_Low'] = bollinger.bollinger_lband()
    df['BB_Mid'] = bollinger.bollinger_mavg()
    
    # 4. Moving Averages
    df['SMA_20'] = ta.trend.SMAIndicator(close=df['Close'], window=20).sma_indicator()
    df['SMA_50'] = ta.trend.SMAIndicator(close=df['Close'], window=50).sma_indicator()
    df['SMA_200'] = ta.trend.SMAIndicator(close=df['Close'], window=200).sma_indicator()
    
    # 5. KD Indicator (Stochastic Oscillator)
    stoch = ta.momentum.StochasticOscillator(high=df['High'], low=df['Low'], close=df['Close'], window=9, smooth_window=3)
    df['K_line'] = stoch.stoch()
    df['D_line'] = stoch.stoch_signal()
    
    return df
def evaluate_entry_exit(df: pd.DataFrame) -> Dict[str, float]:
    """
    A simple logical algorithm to suggest entry and exit price ranges 
    based on Support/Resistance and Bollinger Bands.
    """
    if df.empty or len(df) < 10:
        return {}
    
    last_close = df['Close'].iloc[-1]
    
    # Simple support and resistance using recent lows and highs (last 50 days)
    recent_data = df.tail(50)
    support_level = float(recent_data['Low'].min())
    resistance_level = float(recent_data['High'].max())
    
    # Entry point proposal
    # Good entry is typically near support or lower bollinger band.
    lower_bb = float(df['BB_Low'].iloc[-1])
    suggested_entry = max(support_level, lower_bb)
    # Ensure entry isn't higher than current price just due to BB calculation
    suggested_entry = min(suggested_entry, last_close * 0.99)
    
    # Exit point proposal
    # Good exit is near resistance or upper bollinger band.
    upper_bb = float(df['BB_High'].iloc[-1])
    suggested_exit = min(resistance_level, upper_bb)
    # Ensure exit is reasonably higher
    suggested_exit = max(suggested_exit, last_close * 1.01)
    
    # Basic prediction of "future development" (Trend)
    trend = "Neutral"
    if df['SMA_20'].iloc[-1] > df['SMA_50'].iloc[-1] and df['MACD_Diff'].iloc[-1] > 0:
        trend = "Bullish"
    elif df['SMA_20'].iloc[-1] < df['SMA_50'].iloc[-1] and df['MACD_Diff'].iloc[-1] < 0:
        trend = "Bearish"

    return {
        "current_price": float(last_close),
        "support": support_level,
        "resistance": resistance_level,
        "suggested_entry": suggested_entry,
        "suggested_exit": suggested_exit,
        "trend": trend
    }

# Compatibility alias
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    return add_technical_indicators(df)


