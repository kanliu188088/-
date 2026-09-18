# 第二大腦 — HTML 網頁版

單一檔案 `index.html`，純前端，不需要伺服器、不需要安裝任何東西。所有資料存在瀏覽器的 IndexedDB，不會離開你的電腦。

## 使用方式

1. 下載 `index.html`，用 **Chrome 或 Edge** 直接開啟（雙擊即可，也可以放到任何網頁空間）。
2. 到「掃描」分頁 →「選擇資料夾並掃描」→ 選整個 D 槽或「文件」資料夾 → 允許讀取。
3. 回「搜尋」分頁輸入關鍵字。點任一結果可加標籤、寫筆記、開啟檔案。
4. 之後在「掃描」分頁按「重新掃描」做增量更新（瀏覽器會記住資料夾授權）。

Firefox / Safari 沒有 File System Access API，會改用一次性匯入模式：可以掃描與搜尋，但重新整理後需要重選資料夾才能重新掃描或開啟檔案。

## 功能

| 分頁 | 內容 |
|---|---|
| 搜尋 | 檔名 / 路徑 / 內文 / 筆記 / 標籤 全文搜尋，支援類型、位置、標籤過濾與排序，結果標黃、顯示內文摘要 |
| 掃描 | 加入多個資料夾、增量更新、消失的檔案自動標記、可停止；選項：抽取內文、包含隱藏檔、內文大小上限 |
| 統計 | 檔案數、總大小、依類型 / 年份 / 副檔名 / 位置、最大檔案、檔案最多的資料夾 |
| 重複檔 | 大小分組 → SHA-256 → 只有內容完全相同才算重複 |
| 標籤與筆記 | 標籤雲、最近筆記 |
| 匯出與備份 | Markdown 索引（Obsidian 可開）、JSON 備份 / 還原、重建索引、清除、深淺色切換 |

## 內文抽取

- 純文字、Markdown、CSV、JSON、程式碼：自動偵測 UTF-8 / Big5 / GB18030 / Shift-JIS / UTF-16
- docx / xlsx / pptx / odt / ods / odp：內建迷你 zip 解析器（用瀏覽器原生 `DecompressionStream`），不需任何套件
- PDF：第一次遇到 PDF 時從 jsDelivr 載入 pdf.js；離線時略過 PDF 內文，其它功能不受影響

## 中文搜尋

每個中日韓字元建立單字與相鄰二字詞索引，搜尋時把「永續治理」拆成「永續」「續治」「治理」取交集，再用原文比對確認相鄰，不需要斷詞套件。英文做前綴比對（`reven` 找得到 `revenue`）。

## 測試

```bash
cd tests
npm i playwright
npx playwright install chromium
node test_web.js
```

## Android

同一份 `index.html` 也是 APK 的畫面：Android 專案透過 `WebViewAssetLoader` 載入它，並用 JavaScript 橋接（`window.Android`）提供資料夾選擇、全機掃描與讀檔。橋接介面：

| 網頁呼叫 | 說明 |
|---|---|
| `Android.pickFolder()` | 開啟系統資料夾選擇器，完成後回呼 `sbAndroid.onPicked(srcId, label)` |
| `Android.scanAll()` | 申請「所有檔案存取權」後，對每個磁碟區回呼 `onPicked` |
| `Android.scan(token, srcId, hidden)` | 背景列出檔案，分批回呼 `sbAndroid.onFiles(token, [...])`，結束呼叫 `onDone(token)` |
| `Android.readBase64(id, max)` | 讀取檔案內容（base64） |
| `Android.openFile(id)` / `Android.saveFile(name, text, mime)` | 用其它 App 開啟檔案 / 存到「下載」 |
