# -*- coding: utf-8 -*-
"""
股價指標萃取工具（投資管理專題實作）

輸入：含「證券代碼、名稱、日期、收盤價」的 Excel / CSV 檔
輸出：Excel 檔，包含
  1. 指標明細：與 python.csv 相同欄位（Lag_Price、Return、MA5、Volatility_20 ...）
  2. 個股摘要：每檔股票的累積報酬、平均日報酬、波動度、上漲天數比例等
  3. 欄位說明

用法：
  python stock_indicators.py 輸入檔.xlsx              # 輸出 輸入檔_結果.xlsx
  python stock_indicators.py 輸入檔.xlsx -o 結果.xlsx --csv
  python stock_indicators.py                          # 不給參數則開啟視窗選檔
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# 欄位自動對應：左邊是標準欄名，右邊是可能出現在使用者 Excel 中的名稱（不分大小寫）
COLUMN_ALIASES = {
    "ID": ["id", "證券代碼", "股票代碼", "代碼", "代號", "公司代碼", "code", "stock_id", "ticker", "symbol"],
    "Name": ["name", "名稱", "股票名稱", "證券名稱", "公司名稱", "簡稱", "公司簡稱"],
    "Date": ["date", "日期", "年月日", "交易日", "交易日期"],
    "Closing_Price": ["closing_price", "close", "收盤價", "收盤價(元)", "收盤", "close_price", "price", "adj close"],
}

OUTPUT_COLUMNS = ["ID", "Name", "Date", "Closing_Price", "Lag_Price", "Price_Change", "Return",
                  "Return_Pct", "Ln_Price", "Ln1_Price", "Log_Return", "MA5", "Volatility_20", "Up_Dummy"]

COLUMN_NOTES = [
    ("Lag_Price", "前一交易日收盤價（同一檔股票內位移一期）"),
    ("Price_Change", "收盤價 − 前一日收盤價"),
    ("Return", "簡單日報酬 = 價差 / 前一日收盤價"),
    ("Return_Pct", "Return × 100（%）"),
    ("Ln_Price", "ln(收盤價)"),
    ("Ln1_Price", "ln(1 + 收盤價)，沿用原 python.csv 的定義（注意：這不是對數報酬）"),
    ("Log_Return", "對數報酬 = ln(P_t / P_t-1)，新增欄位，通常原意應是這個"),
    ("MA5", "5 日移動平均收盤價（不足 5 天為空白）"),
    ("Volatility_20", "最近 20 個日報酬的樣本標準差（ddof=1，日波動度，未年化）"),
    ("Up_Dummy", "當日上漲為 1，否則為 0（第一天無前值記為 0）"),
]


def _normalize(s):
    return str(s).strip().lower().replace(" ", "").replace("_", "")


def detect_columns(df):
    """把使用者的欄名對應成標準欄名。"""
    lookup = {_normalize(c): c for c in df.columns}
    mapping = {}
    for std, aliases in COLUMN_ALIASES.items():
        for alias in [std] + aliases:
            key = _normalize(alias)
            if key in lookup:
                mapping[lookup[key]] = std
                break
        else:
            # 允許部分比對，例如「收盤價(元)」「收盤價_調整前」
            for norm, orig in lookup.items():
                if orig not in mapping and any(_normalize(a) in norm for a in aliases if len(a) > 1):
                    mapping[orig] = std
                    break
    missing = [c for c in ("ID", "Date", "Closing_Price") if c not in mapping.values()]
    if missing:
        raise ValueError(f"找不到必要欄位 {missing}；目前的欄位為 {list(df.columns)}。"
                         f"請將欄名改為 ID / Name / Date / Closing_Price（或 證券代碼 / 名稱 / 日期 / 收盤價）。")
    return mapping


def read_input(path, sheet=None):
    path = Path(path)
    if path.suffix.lower() in (".csv", ".txt"):
        try:
            return pd.read_csv(path, encoding="utf-8-sig")
        except UnicodeDecodeError:
            return pd.read_csv(path, encoding="cp950")  # 台灣常見的 Big5 編碼
    return pd.read_excel(path, sheet_name=sheet if sheet is not None else 0)


def parse_dates(s):
    """支援 20260102、2026/01/02、Excel 日期格式；輸出 YYYYMMDD 整數（與 python.csv 一致）。"""
    if np.issubdtype(s.dtype, np.datetime64):
        d = s
    else:
        txt = s.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
        d = pd.to_datetime(txt, format="%Y%m%d", errors="coerce")
        d = d.fillna(pd.to_datetime(txt[d.isna()], errors="coerce"))
    return d


def compute_indicators(raw):
    df = raw.rename(columns=detect_columns(raw)).copy()
    if "Name" not in df.columns:
        df["Name"] = ""
    df = df[["ID", "Name", "Date", "Closing_Price"]]

    df["ID"] = df["ID"].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
    df["Closing_Price"] = pd.to_numeric(
        df["Closing_Price"].astype(str).str.replace(",", "").str.strip(), errors="coerce")
    dates = parse_dates(df["Date"])

    bad = dates.isna() | df["Closing_Price"].isna() | (df["Closing_Price"] <= 0)
    dropped = int(bad.sum())
    df = df[~bad].copy()
    df["Date"] = dates[~bad].dt.strftime("%Y%m%d").astype(int)

    # 必須先依股票、日期排序，否則前一日價格會錯位；重複日期只保留最後一筆
    df = (df.drop_duplicates(["ID", "Date"], keep="last")
            .sort_values(["ID", "Date"], kind="stable").reset_index(drop=True))

    g = df.groupby("ID", sort=False)["Closing_Price"]
    df["Lag_Price"] = g.shift(1)
    df["Price_Change"] = df["Closing_Price"] - df["Lag_Price"]
    df["Return"] = df["Price_Change"] / df["Lag_Price"]
    df["Return_Pct"] = df["Return"] * 100
    df["Ln_Price"] = np.log(df["Closing_Price"])
    df["Ln1_Price"] = np.log1p(df["Closing_Price"])
    df["Log_Return"] = np.log(df["Closing_Price"] / df["Lag_Price"])
    df["MA5"] = g.transform(lambda s: s.rolling(5).mean())
    df["Volatility_20"] = df.groupby("ID", sort=False)["Return"].transform(lambda s: s.rolling(20).std())
    df["Up_Dummy"] = (df["Price_Change"] > 0).astype(int)

    # 代碼若全為數字則轉回整數，與原檔一致
    if df["ID"].str.fullmatch(r"\d+").all():
        df["ID"] = df["ID"].astype(int)
    return df[OUTPUT_COLUMNS], dropped


def summarize(df):
    def one(x):
        r = x["Return"].dropna()
        first, last = x["Closing_Price"].iloc[0], x["Closing_Price"].iloc[-1]
        return pd.Series({
            "Name": x["Name"].iloc[0],
            "起始日": x["Date"].iloc[0],
            "結束日": x["Date"].iloc[-1],
            "交易天數": len(x),
            "起始價": first,
            "最新收盤價": last,
            "累積報酬率(%)": (last / first - 1) * 100,
            "平均日報酬(%)": r.mean() * 100,
            "日報酬標準差(%)": r.std() * 100,
            "年化波動度(%)": r.std() * np.sqrt(252) * 100,
            "年化Sharpe(rf=0)": r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else np.nan,
            "上漲天數比例(%)": x["Up_Dummy"].iloc[1:].mean() * 100 if len(x) > 1 else np.nan,
            "最新MA5": x["MA5"].iloc[-1],
            "收盤價>MA5": int(last > x["MA5"].iloc[-1]) if pd.notna(x["MA5"].iloc[-1]) else np.nan,
            "最新Volatility_20": x["Volatility_20"].iloc[-1],
            "最大回撤(%)": ((x["Closing_Price"] / x["Closing_Price"].cummax()) - 1).min() * 100,
        })
    out = df.groupby("ID", sort=False).apply(one, include_groups=False).reset_index()
    return out.sort_values("累積報酬率(%)", ascending=False).reset_index(drop=True)


def write_output(detail, summary, out_path, also_csv=False):
    out_path = Path(out_path)
    with pd.ExcelWriter(out_path, engine="openpyxl") as xw:
        summary.to_excel(xw, sheet_name="個股摘要", index=False)
        detail.to_excel(xw, sheet_name="指標明細", index=False)
        pd.DataFrame(COLUMN_NOTES, columns=["欄位", "說明"]).to_excel(xw, sheet_name="欄位說明", index=False)
        for ws in xw.book.worksheets:
            ws.freeze_panes = "A2"
            for col in ws.columns:
                ws.column_dimensions[col[0].column_letter].width = max(10, len(str(col[0].value)) * 2 + 2)
    if also_csv:
        detail.to_csv(out_path.with_suffix(".csv"), index=False, encoding="utf-8-sig")
    return out_path


def run(in_path, out_path=None, sheet=None, also_csv=False):
    in_path = Path(in_path)
    out_path = Path(out_path) if out_path else in_path.with_name(in_path.stem + "_結果.xlsx")
    detail, dropped = compute_indicators(read_input(in_path, sheet))
    summary = summarize(detail)
    write_output(detail, summary, out_path, also_csv)
    msg = (f"完成：{detail['ID'].nunique()} 檔股票、{len(detail)} 筆資料"
           f"{f'（略過 {dropped} 筆無效日期/價格）' if dropped else ''}\n輸出：{out_path}")
    return msg


def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox
    root = tk.Tk()
    root.withdraw()
    src = filedialog.askopenfilename(title="選擇股價 Excel 檔",
                                     filetypes=[("Excel / CSV", "*.xlsx *.xls *.csv"), ("所有檔案", "*.*")])
    if not src:
        return
    dst = filedialog.asksaveasfilename(title="儲存結果", defaultextension=".xlsx",
                                       initialfile=Path(src).stem + "_結果.xlsx",
                                       filetypes=[("Excel", "*.xlsx")])
    if not dst:
        return
    try:
        messagebox.showinfo("完成", run(src, dst))
    except Exception as e:
        messagebox.showerror("錯誤", str(e))


def main():
    if len(sys.argv) == 1:
        return gui()
    p = argparse.ArgumentParser(description="從股價 Excel 萃取報酬、均線、波動度等指標")
    p.add_argument("input", help="輸入的 Excel / CSV 檔")
    p.add_argument("-o", "--output", help="輸出 Excel 檔名（預設：輸入檔名_結果.xlsx）")
    p.add_argument("-s", "--sheet", help="工作表名稱（預設第一個）")
    p.add_argument("--csv", action="store_true", help="另外輸出與 python.csv 相同格式的 CSV")
    a = p.parse_args()
    try:
        print(run(a.input, a.output, a.sheet, a.csv))
    except Exception as e:
        sys.exit(f"錯誤：{e}")


if __name__ == "__main__":
    main()
