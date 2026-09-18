# Second Brain — 把所有硬碟裡的檔案收集成可搜尋的第二大腦

一支 Python 程式 `second_brain.py`，做四件事：

1. **掃描**所有硬碟（或指定資料夾），把每個檔案的路徑、大小、時間、類型記進本機 SQLite 資料庫，之後只做增量更新。
2. **抽取內文**：txt / md / csv / json / 程式碼 / docx / xlsx / pptx / odt（免套件），以及 pdf（裝了 `pypdf` 才會）。中文用逐字索引，搜「永續治理」就找得到。
3. **搜尋、統計、找重複檔**、幫檔案加**標籤**與**筆記**。
4. **匯出 Markdown 知識庫**（首頁、依類型、依年份、依資料夾、標籤、筆記、重複檔），可直接用 Obsidian / Typora / VS Code 開。

所有資料只存在你自己的電腦，不會上傳任何地方。

## 需求

- Python 3.8 以上（Windows 到 [python.org](https://www.python.org/downloads/) 安裝，安裝時勾 **Add python.exe to PATH**）。
- 不需要任何第三方套件。想要索引 PDF 內文再另外裝：`pip install pypdf`。

## 快速開始

```bash
# 1. 第一次掃描（會自動偵測所有硬碟；Windows 是 C:\ D:\ E:\ …）
python second_brain.py scan

# 只掃某幾個地方會快很多
python second_brain.py scan D:\ "E:\工作資料"

# 2. 搜尋（檔名 + 內文 + 筆記 + 標籤，多個關鍵字要同時符合）
python second_brain.py search 永續 治理
python second_brain.py search 董事會 --ext docx pdf
python second_brain.py search --name 報告            # 只搜檔名/路徑
python second_brain.py search 合約 --under D:\客戶    # 只搜某資料夾底下

# 3. 其它
python second_brain.py recent --days 7              # 最近一週改過的檔案
python second_brain.py stats                        # 類型、年份、最大檔案、最肥資料夾
python second_brain.py dupes                        # 找出內容完全相同的重複檔（≥1MB）
python second_brain.py tag  "D:\文件\A.docx" 工作 重要
python second_brain.py note "D:\文件\A.docx" "這是 2024 董事會通過的版本"
python second_brain.py export ~/SecondBrain         # 匯出 Markdown 知識庫
```

Windows 使用者也可以直接雙擊 `掃描所有硬碟.bat`。

## 指令總覽

| 指令 | 說明 |
|---|---|
| `scan [路徑…]` | 掃描並增量更新索引。`--no-content` 只記檔名不讀內文（快很多）；`--reindex` 強制重抽內文；`--exclude 名稱…` 額外略過的資料夾；`--hidden` 連隱藏檔也掃 |
| `search 關鍵字…` | 全文搜尋。`--name` 只搜檔名；`--ext`、`--kind`、`--under`、`--tag`、`--min-size` 過濾；`--include-missing` 含已消失的檔案；`--json` 給程式用 |
| `recent` | 最近 N 天修改的檔案，過濾參數同 `search` |
| `dupes` | 依大小 → 前 64KB 雜湊 → 完整雜湊三階段找重複檔，結果會寫回資料庫供 `export` 使用 |
| `stats` | 統計總覽 |
| `tag 檔案 標籤…` | 加標籤（`--remove` 移除）。「檔案」可給完整路徑，或獨一無二的檔名 |
| `note 檔案 [文字]` | 加筆記；不給文字則列出既有筆記 |
| `export 資料夾` | 匯出 Markdown 知識庫。`--depth` 控制「依資料夾」分到第幾層 |
| `drives` | 列出偵測到的硬碟 |
| `forget 路徑 --yes` | 從資料庫移除某路徑底下的紀錄（不會動到實際檔案） |

共用參數：`--db 路徑` 指定資料庫位置（預設 `~/.second_brain/brain.db`）。

## 預設會略過什麼

- Windows：`Windows`、`Program Files`、`ProgramData`、`AppData`、`$Recycle.Bin`、`System Volume Information`、系統屬性檔
- macOS：`~/Library`、`/System`、`/Library`、`/Applications`、`.Trash`、Spotlight 快取
- Linux：`/proc` `/sys` `/dev` `/usr` `/var` `/etc` 等系統目錄
- 開發垃圾：`node_modules`、`.git`、`__pycache__`、`venv`、`.cache`、`dist`、`build`…
- 以 `.` 開頭的隱藏檔（`--hidden` 可關閉）、`.tmp` `.log` `.lnk` 等暫存檔（`--keep-temp` 可關閉）

如果你明確指定的根目錄本身在系統目錄裡（例如 `/opt/backup`），該系統目錄的排除規則不會套用。

## 中文搜尋怎麼運作

SQLite FTS5 內建的 tokenizer 不會斷中文詞，所以程式把每個中日韓字元前後補空白後再建索引，搜尋時把中文詞轉成 phrase query（「永續」→ `"永 續"`），就能精準比對相鄰字，不需要任何斷詞套件。英文字則做前綴比對（`report` 也會找到 `reporting`）。

舊的 Big5 / GB 編碼純文字檔會自動偵測解碼。

## 資料放在哪

`~/.second_brain/brain.db`（Windows 是 `C:\Users\你\.second_brain\brain.db`），單一檔案，備份直接複製即可。標籤與筆記也存在這裡，重新掃描不會弄丟。

## 建議的使用方式

1. 第一次用 `scan --no-content` 先把所有硬碟的檔名建起來（幾十萬個檔案大約幾分鐘）。
2. 再對真正放文件的資料夾跑一次完整 `scan D:\文件`，抽內文。
3. 用 Windows 工作排程器 / cron 每天執行一次 `scan`，維持索引新鮮。
4. `export` 到 Obsidian vault，把匯出的 Markdown 當成檔案系統的地圖，再用 Obsidian 自己的筆記連結過去。

## 測試

```bash
python -m unittest discover -s second_brain/tests -v
```
