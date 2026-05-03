#!/bin/bash
# 自動重啟 Streamlit 的腳本

echo "啟動台股分析儀表板..."

# 進入虛擬環境
source venv/bin/activate

# 無限迴圈，只要當機就重啟
while true; do
    echo "正在啟動 Streamlit..."
    streamlit run app.py
    
    echo "Streamlit 伺服器已關閉或崩潰，3 秒後自動重新啟動..."
    sleep 3
done
