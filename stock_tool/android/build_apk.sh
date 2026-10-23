#!/usr/bin/env bash
# 打包 APK：WebView 外殼 + 離線 HTML。只需要 JDK 與 Python，工具會從 Maven Central 下載。
set -euo pipefail
cd "$(dirname "$0")"
TOOLS=.tools; BUILD=build; OUT=../dist/股價指標萃取器.apk
M=https://repo1.maven.org/maven2
mkdir -p "$TOOLS"
get() { [ -s "$TOOLS/$1" ] || curl -sSfL --retry 4 -o "$TOOLS/$1" "$2"; }
get android-all.jar $M/org/robolectric/android-all/14-robolectric-10818077/android-all-14-robolectric-10818077.jar
get dx.jar $M/com/jakewharton/android/repackaged/dalvik-dx/16.0.1/dalvik-dx-16.0.1.jar
get apksig.jar $M/com/android/tools/build/apksig/2.3.0/apksig-2.3.0.jar

python3 ../web/build.py
rm -rf "$BUILD"; mkdir -p "$BUILD/classes" "$BUILD/apk/assets"
javac -nowarn --release 8 -encoding UTF-8 -cp "$TOOLS/android-all.jar" \
  -d "$BUILD/classes" src/tw/edu/stocktool/MainActivity.java 2>&1 | grep -v "warning" || true
java -cp "$TOOLS/dx.jar" com.android.dx.command.Main --dex --min-sdk-version=24 \
  --output="$BUILD/apk/classes.dex" "$BUILD/classes"
python3 axml.py "$BUILD/apk/AndroidManifest.xml"
cp "../dist/股價指標萃取器.html" "$BUILD/apk/assets/index.html"
(cd "$BUILD/apk" && rm -f ../unsigned.apk && zip -q -X -r ../unsigned.apk AndroidManifest.xml classes.dex assets)

# 簽章金鑰：第一次自動產生，之後更新 App 必須沿用同一把（請妥善保存，勿上傳）
KS=release.p12; PASS=${APK_KEY_PASS:-stocktool}
[ -f "$KS" ] || keytool -genkeypair -keystore "$KS" -storetype PKCS12 -storepass "$PASS" -alias stocktool \
  -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Stock Tool, O=Investment Management Course, C=TW" >/dev/null 2>&1
javac -nowarn -cp "$TOOLS/apksig.jar" -d "$BUILD" Signer.java
java --add-exports java.base/sun.security.x509=ALL-UNNAMED --add-exports java.base/sun.security.pkcs=ALL-UNNAMED -cp "$TOOLS/apksig.jar:$BUILD" Signer "$BUILD/unsigned.apk" "$BUILD/signed.apk" "$KS" "$PASS" stocktool
mv "$BUILD/signed.apk" "$OUT"   # Java 在無 UTF-8 locale 時無法寫中文檔名，先用英文檔名再改名
ls -la "$OUT"
