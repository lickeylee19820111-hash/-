import plotly.graph_objects as go
from plotly.subplots import make_subplots

def render_stock_chart(df_analyzed, eval_result):
    """
    Renders the Plotly chart containing Price, BB, MACD, RSI, and KD.
    Adds technical indicator names to each subplot to improve readability.
    """
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.06, row_heights=[0.4, 0.2, 0.2, 0.2],
                        subplot_titles=("股價走勢與布林通道 (Price & Bollinger Bands)", 
                                        "MACD (平滑異同移動平均線)", 
                                        "RSI (相對強弱指標)", 
                                        "KD (隨機指標)"))

    # Candlestick
    fig.add_trace(go.Candlestick(x=df_analyzed.index,
                    open=df_analyzed['Open'], high=df_analyzed['High'],
                    low=df_analyzed['Low'], close=df_analyzed['Close'],
                    name='Price'), row=1, col=1)
    
    # Bollinger Bands
    fig.add_trace(go.Scatter(x=df_analyzed.index, y=df_analyzed['BB_High'], 
                             line=dict(color='rgba(128, 128, 128, 0.5)', width=1, dash='dot'), name='Upper BB'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df_analyzed.index, y=df_analyzed['BB_Low'], 
                             line=dict(color='rgba(128, 128, 128, 0.5)', width=1, dash='dot'), name='Lower BB', 
                             fill='tonexty', fillcolor='rgba(128, 128, 128, 0.1)'), row=1, col=1)

    # entry/exit lines
    if eval_result.get('suggested_entry'):
        fig.add_hline(y=eval_result.get('suggested_entry'), line_dash="dash", line_color="green", annotation_text="建議進場區", row=1, col=1)
    if eval_result.get('suggested_exit'):
        fig.add_hline(y=eval_result.get('suggested_exit'), line_dash="dash", line_color="red", annotation_text="建議出場區", row=1, col=1)

    # MACD
    colors = ['red' if val < 0 else 'green' for val in df_analyzed['MACD_Diff']]
    fig.add_trace(go.Bar(x=df_analyzed.index, y=df_analyzed['MACD_Diff'], name='MACD Histogram', marker_color=colors), row=2, col=1)
    fig.add_trace(go.Scatter(x=df_analyzed.index, y=df_analyzed['MACD'], line=dict(color='blue', width=1), name='MACD'), row=2, col=1)
    fig.add_trace(go.Scatter(x=df_analyzed.index, y=df_analyzed['MACD_Signal'], line=dict(color='orange', width=1), name='Signal'), row=2, col=1)
    
    # RSI
    fig.add_trace(go.Scatter(x=df_analyzed.index, y=df_analyzed['RSI'], line=dict(color='purple', width=1), name='RSI'), row=3, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="green", row=3, col=1)

    # KD
    fig.add_trace(go.Scatter(x=df_analyzed.index, y=df_analyzed['K_line'], line=dict(color='orange', width=1), name='K值 (快線)'), row=4, col=1)
    fig.add_trace(go.Scatter(x=df_analyzed.index, y=df_analyzed['D_line'], line=dict(color='blue', width=1), name='D值 (慢線)'), row=4, col=1)
    fig.add_hline(y=80, line_dash="dot", line_color="red", row=4, col=1)
    fig.add_hline(y=20, line_dash="dot", line_color="green", row=4, col=1)

    fig.update_layout(
        height=1200, 
        xaxis_rangeslider_visible=False, 
        template='plotly_dark',
        margin=dict(l=20, r=20, t=60, b=20),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5
        )
    )
    
    # Update subplot titles to make them stand out
    fig.update_annotations(font_size=16)
    
    return fig
