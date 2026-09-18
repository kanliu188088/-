# 第二大腦 — Android APK

一個很薄的 Android 殼：`WebView` 載入 [`../second_brain_web/index.html`](../second_brain_web/index.html)（同一份網頁版），並用 JavaScript 橋接補上網頁做不到的能力：

- **選擇資料夾**：系統資料夾選擇器（Storage Access Framework），授權會持久保存，之後可直接重新掃描
- **掃描整個手機儲存空間**：Android 11+ 會請你開啟「允許存取所有檔案」；Android 8–10 用一般讀取權限。SD 卡等其它磁碟區也會一併加入
- 讀取檔案內容（抽內文、算雜湊）、用其它 App 開啟檔案、把匯出的 Markdown / JSON 存到「下載」

## 下載 APK

每次推送到 `second_brain_android/` 或 `second_brain_web/`，GitHub Actions（[`.github/workflows/android-apk.yml`](../.github/workflows/android-apk.yml)）會自動編譯並發佈到 Release：

**Releases → `apk-latest` → `second-brain.apk`**

安裝前請在手機允許「安裝未知來源的應用程式」。APK 用 debug 金鑰簽章，適合自用；要上架請改用自己的 keystore。

## 自己編譯

需要 JDK 17 與 Android SDK（Android Studio 會自動處理）：

```bash
cd second_brain_android
./gradlew assembleDebug
# 輸出：app/build/outputs/apk/debug/second-brain-debug-1.0.0.apk
```

或直接用 Android Studio 開啟 `second_brain_android` 資料夾。

## 結構

```
app/src/main/java/tw/secondbrain/app/MainActivity.java   WebView + JavaScript 橋接 + 掃描
app/src/main/AndroidManifest.xml                          權限、FileProvider
app/build.gradle                                          把 ../../second_brain_web 當成 assets
```

- minSdk 26（Android 8.0）、targetSdk 34
- 相依套件只有 `androidx.webkit`（`WebViewAssetLoader`，讓 IndexedDB 有正常的 origin）與 `androidx.core`（`FileProvider`）
- 網頁透過 `https://appassets.androidplatform.net/assets/index.html` 載入，`INTERNET` 權限只用於選用的 pdf.js
