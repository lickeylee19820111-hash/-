import yfinance as yf
import twstock
import time

codes = []
for code, info in twstock.codes.items():
    if info.type == '股票':
        suffix = ".TW" if info.market == "上市" else ".TWO"
        codes.append(f"{code}{suffix}")

print(f"Total stocks: {len(codes)}")
start_t = time.time()
df = yf.download(codes[:500], period="6mo", interval="1wk", threads=True)
print(f"Time taken for 500 stocks: {time.time() - start_t:.2f}s")
