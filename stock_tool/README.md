# 股價指標萃取工具

輸入一個股價 Excel 檔，自動算出與 `python.csv` 相同的指標，並輸出成新的 Excel。共有三種版本，公式完全相同：

| 版本 | 檔案 | 使用方式 |
|---|---|---|
| 網頁版 | `dist/股價指標萃取器.html` | 用 Chrome / Edge 直接開啟，不需安裝、不需網路 |
| Android App | `dist/股價指標萃取器.apk` | 傳到手機安裝（需允許「安裝不明來源應用程式」），Android 7.0 以上 |
| Python 版 | `stock_indicators.py` | 見下方「安裝」 |

網頁版與 App 都在本機計算，檔案不會上傳；可選擇工作表、手動指定欄位、搜尋與排序個股、查看走勢圖，並下載結果 Excel / CSV。

### 重新產生網頁版與 APK
```
python web/build.py          # 產生 dist/股價指標萃取器.html
android/build_apk.sh         # 產生 dist/股價指標萃取器.apk（需要 JDK 17+ 與 Python 3）
```
APK 為 WebView 外殼（`android/src`）加上離線網頁。第一次打包會產生簽章金鑰 `android/release.p12`（不會上傳到 git），之後更新 App 必須使用同一把金鑰。

## Python 版

### 安裝
```
pip install -r requirements.txt
```

### 使用
```
python stock_indicators.py 我的股價.xlsx          # 產生 我的股價_結果.xlsx
python stock_indicators.py 我的股價.xlsx --csv    # 另外產生與 python.csv 同格式的 CSV
python stock_indicators.py                        # 不加參數：跳出視窗選檔（Windows 可直接雙擊）
```

輸入檔只需要 4 欄（欄名中英文皆可，順序不拘、不必事先排序）：

| 標準欄名 | 可接受的名稱 |
|---|---|
| ID | 證券代碼、股票代碼、代號、code、ticker |
| Name | 名稱、股票名稱、公司簡稱（可省略） |
| Date | 日期、交易日、年月日（20260102、2026/01/02 或 Excel 日期皆可） |
| Closing_Price | 收盤價、收盤價(元)、close |

## 輸出內容
- **個股摘要**：累積報酬、平均日報酬、年化波動度、Sharpe、上漲天數比例、最大回撤、最新 MA5 / Volatility_20，依累積報酬排序
- **指標明細**：Lag_Price、Price_Change、Return、Return_Pct、Ln_Price、Ln1_Price、Log_Return、MA5、Volatility_20、Up_Dummy
- **欄位說明**：每個欄位的公式

## 對原 python.csv 的檢查（debug 結果）
已逐欄反推原檔公式並以 993 檔、171,657 筆資料驗證，本工具輸出與原檔完全一致（誤差 < 1e-15）。發現的問題：
1. **`Ln1_Price` 是 ln(1 + 價格)**，不是對數報酬。若原意是對數報酬，應使用新增的 `Log_Return = ln(P_t / P_t-1)`。
2. **`Up_Dummy` 第一天記為 0**，但第一天其實沒有前一天可比；做迴歸或計算上漲比例時應排除每檔第一筆（摘要中的上漲比例已排除）。
3. **`Volatility_20` 是日波動度**（20 日報酬樣本標準差），未年化；年化需乘以 √252（摘要提供年化值）。
4. 計算前務必依「代碼、日期」排序，否則前一日價格會跨股票錯位；本工具會自動排序並去除重複日期。
