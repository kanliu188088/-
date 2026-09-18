# 第二大腦（Second Brain）

把所有硬碟、手機裡的檔案收集成一個可搜尋的「第二大腦」。三個版本共用同一套想法：**掃描 → 抽內文 → 中文全文索引 → 搜尋 / 標籤 / 筆記 / 匯出**，所有資料只存在你自己的裝置。

| 版本 | 位置 | 適合誰 | 怎麼拿到 |
|---|---|---|---|
| **Python 命令列版** | [`second_brain/`](second_brain/) | 桌機、NAS、想排程每天自動掃全部硬碟 | `python second_brain.py scan` |
| **HTML 網頁版** | [`second_brain_web/`](second_brain_web/) | 不想裝 Python；用 Chrome / Edge 直接開 | 下載 `index.html` 雙擊開啟 |
| **Android APK** | [`second_brain_android/`](second_brain_android/) | 手機、平板；掃描整個儲存空間 | [Releases → apk-latest](../../releases/tag/apk-latest)（GitHub Actions 自動編譯） |

## 功能一覽

- 自動偵測所有硬碟 / 磁碟區，增量更新，略過系統與開發垃圾目錄
- 抽取 txt、md、csv、程式碼、docx、xlsx、pptx、odt 內文（免套件）；PDF 選用
- 中文逐字 + 二字詞索引，不需斷詞套件；英文前綴比對；Big5 舊檔自動解碼
- 搜尋（檔名、路徑、內文、筆記、標籤）、最近修改、統計、重複檔（雜湊比對）
- 標籤與筆記，讓檔案索引變成知識庫
- 匯出 Markdown（Obsidian 可開）與 JSON 備份

## 其它

- [`booklet/`](booklet/)：永續企業治理 A5 小冊子（docx / pdf 與排版原始檔）

## 開發

```bash
python -m unittest discover -s second_brain/tests -v      # Python 版
cd second_brain_web/tests && npm i playwright && npx playwright install chromium && node test_web.js   # 網頁版
cd second_brain_android && ./gradlew assembleDebug        # APK（需 Android SDK）
```
