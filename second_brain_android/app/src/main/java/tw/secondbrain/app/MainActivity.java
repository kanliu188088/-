package tw.secondbrain.app;

import android.Manifest;
import android.app.Activity;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.storage.StorageManager;
import android.os.storage.StorageVolume;
import android.provider.DocumentsContract;
import android.provider.MediaStore;
import android.provider.Settings;
import android.util.Base64;
import android.webkit.JavascriptInterface;
import android.webkit.MimeTypeMap;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.core.content.FileProvider;
import androidx.webkit.WebViewAssetLoader;
import androidx.webkit.WebViewClientCompat;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 第二大腦 Android 殼：一個 WebView 載入 assets/index.html（與網頁版同一份），
 * 並透過 JavascriptInterface「Android」提供網頁做不到的事：
 *   - pickFolder()  用系統資料夾選擇器挑一個資料夾（SAF）
 *   - scanAll()     申請「所有檔案存取權」後掃描整個儲存空間
 *   - scan(token, srcId, hidden)  在背景執行緒列出檔案，分批回呼 window.sbAndroid.onFiles(token, [...])
 *   - readBase64(id, max)         讀檔內容（供抽取內文、計算雜湊）
 *   - openFile(id) / saveFile(name, content, mime)
 */
public class MainActivity extends Activity {
    private static final String START_URL = "https://appassets.androidplatform.net/assets/index.html";
    private static final int REQ_TREE = 1001, REQ_ALL_FILES = 1002, REQ_READ = 1003;
    private static final int BATCH = 300;
    private static final long MAX_READ = 64L * 1024 * 1024;

    private WebView web;
    private final ExecutorService exec = Executors.newSingleThreadExecutor();
    private volatile boolean cancel = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setSupportZoom(false);
        s.setMediaPlaybackRequiresUserGesture(false);
        if (Build.VERSION.SDK_INT >= 33) {
            s.setAlgorithmicDarkeningAllowed(true);
        }

        final WebViewAssetLoader loader = new WebViewAssetLoader.Builder()
                .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this))
                .build();
        web.setWebViewClient(new WebViewClientCompat() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                return loader.shouldInterceptRequest(request.getUrl());
            }

            @Override
            public boolean shouldOverrideUrlLoading(@NonNull WebView view, @NonNull WebResourceRequest request) {
                Uri u = request.getUrl();
                if ("appassets.androidplatform.net".equals(u.getHost())) return false;
                try { startActivity(new Intent(Intent.ACTION_VIEW, u)); } catch (Exception ignored) { }
                return true;
            }
        });
        web.setWebChromeClient(new WebChromeClient());
        web.addJavascriptInterface(new Bridge(), "Android");
        setContentView(web);
        if (savedInstanceState == null) web.loadUrl(START_URL); else web.restoreState(savedInstanceState);
    }

    @Override
    protected void onSaveInstanceState(@NonNull Bundle outState) {
        super.onSaveInstanceState(outState);
        web.saveState(outState);
    }

    @Override
    public void onBackPressed() {
        if (web.canGoBack()) web.goBack(); else super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        cancel = true;
        exec.shutdownNow();
        super.onDestroy();
    }

    /* ------------------------------------------------------------------ */
    /* 與網頁溝通                                                            */
    /* ------------------------------------------------------------------ */

    private void js(final String code) {
        runOnUiThread(() -> web.evaluateJavascript(code, null));
    }

    private static String q(String s) {
        return JSONObject.quote(s == null ? "" : s);
    }

    private void toast(final String msg) {
        runOnUiThread(() -> Toast.makeText(this, msg, Toast.LENGTH_LONG).show());
    }

    private void picked(String srcId, String label) {
        js("window.sbAndroid && window.sbAndroid.onPicked(" + q(srcId) + "," + q(label) + ")");
    }

    /* ------------------------------------------------------------------ */
    /* JavaScript 介面                                                       */
    /* ------------------------------------------------------------------ */

    private class Bridge {
        @JavascriptInterface
        public String version() { return "1.0.0"; }

        @JavascriptInterface
        public void pickFolder() {
            runOnUiThread(() -> {
                Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
                i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION);
                try { startActivityForResult(i, REQ_TREE); }
                catch (Exception e) { toast("這台裝置沒有可用的資料夾選擇器"); }
            });
        }

        @JavascriptInterface
        public void scanAll() {
            runOnUiThread(() -> {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                    if (Environment.isExternalStorageManager()) { startScanAllRoots(); return; }
                    toast("請開啟「允許存取所有檔案」，再回到 App");
                    try {
                        Intent i = new Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION, Uri.parse("package:" + getPackageName()));
                        startActivityForResult(i, REQ_ALL_FILES);
                    } catch (Exception e) {
                        startActivityForResult(new Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION), REQ_ALL_FILES);
                    }
                } else {
                    if (checkSelfPermission(Manifest.permission.READ_EXTERNAL_STORAGE) == PackageManager.PERMISSION_GRANTED) startScanAllRoots();
                    else requestPermissions(new String[]{Manifest.permission.READ_EXTERNAL_STORAGE}, REQ_READ);
                }
            });
        }

        @JavascriptInterface
        public void scan(final String token, final String srcId, final boolean hidden) {
            cancel = false;
            exec.execute(() -> {
                try {
                    if (srcId.startsWith("file:")) walkFiles(token, new File(srcId.substring(5)), hidden);
                    else walkTree(token, Uri.parse(srcId), hidden);
                    js("window.sbAndroid.onDone(" + q(token) + ")");
                } catch (Throwable t) {
                    js("window.sbAndroid.onError(" + q(token) + "," + q(String.valueOf(t.getMessage())) + ")");
                }
            });
        }

        @JavascriptInterface
        public void cancelScan() { cancel = true; }

        /** 讀取檔案內容（max = 0 代表全部，上限 64 MB），回傳 base64；失敗回傳空字串 */
        @JavascriptInterface
        public String readBase64(String id, int max) {
            long limit = max > 0 ? Math.min(max, MAX_READ) : MAX_READ;
            try (InputStream in = openInput(id)) {
                if (in == null) return "";
                ByteArrayOutputStream bos = new ByteArrayOutputStream();
                byte[] buf = new byte[65536];
                long total = 0; int n;
                while (total < limit && (n = in.read(buf, 0, (int) Math.min(buf.length, limit - total))) > 0) {
                    bos.write(buf, 0, n); total += n;
                }
                return Base64.encodeToString(bos.toByteArray(), Base64.NO_WRAP);
            } catch (Throwable t) {
                return "";
            }
        }

        @JavascriptInterface
        public void openFile(final String id) {
            runOnUiThread(() -> {
                try {
                    Uri uri;
                    String name;
                    if (id.startsWith("file:")) {
                        File f = new File(id.substring(5));
                        uri = FileProvider.getUriForFile(MainActivity.this, getPackageName() + ".files", f);
                        name = f.getName();
                    } else {
                        uri = Uri.parse(id);
                        name = uri.getLastPathSegment() == null ? "" : uri.getLastPathSegment();
                    }
                    Intent i = new Intent(Intent.ACTION_VIEW);
                    i.setDataAndType(uri, mimeOf(name));
                    i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    startActivity(Intent.createChooser(i, "開啟檔案"));
                } catch (Exception e) {
                    toast("無法開啟：" + e.getMessage());
                }
            });
        }

        /** 把匯出的 Markdown / JSON 存到「下載」資料夾 */
        @JavascriptInterface
        public void saveFile(final String name, final String content, final String mime) {
            exec.execute(() -> {
                try {
                    byte[] data = content.getBytes(StandardCharsets.UTF_8);
                    String type = mime == null || mime.isEmpty() ? "application/octet-stream" : mime.split(";")[0];
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                        ContentValues v = new ContentValues();
                        v.put(MediaStore.Downloads.DISPLAY_NAME, name);
                        v.put(MediaStore.Downloads.MIME_TYPE, type);
                        v.put(MediaStore.Downloads.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS);
                        ContentResolver cr = getContentResolver();
                        Uri uri = cr.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, v);
                        if (uri == null) throw new IllegalStateException("MediaStore insert failed");
                        try (OutputStream out = cr.openOutputStream(uri)) { out.write(data); }
                    } else {
                        File dir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS);
                        dir.mkdirs();
                        try (OutputStream out = new java.io.FileOutputStream(new File(dir, name))) { out.write(data); }
                    }
                    toast("已儲存到「下載」：" + name);
                } catch (Exception e) {
                    toast("儲存失敗：" + e.getMessage());
                }
            });
        }
    }

    /* ------------------------------------------------------------------ */
    /* 掃描                                                                  */
    /* ------------------------------------------------------------------ */

    private void startScanAllRoots() {
        File primary = Environment.getExternalStorageDirectory();
        picked("file:" + primary.getAbsolutePath(), "手機儲存空間");
        // 其它磁碟區（SD 卡、USB）
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            try {
                StorageManager sm = (StorageManager) getSystemService(STORAGE_SERVICE);
                List<StorageVolume> vols = sm.getStorageVolumes();
                for (StorageVolume v : vols) {
                    if (v.isPrimary()) continue;
                    File dir = v.getDirectory();
                    if (dir != null && dir.canRead()) {
                        String desc = v.getDescription(this);
                        picked("file:" + dir.getAbsolutePath(), desc == null ? dir.getName() : desc);
                    }
                }
            } catch (Exception ignored) { }
        }
    }

    private static boolean skipDir(String name, boolean hidden) {
        if (!hidden && name.startsWith(".")) return true;
        String l = name.toLowerCase(Locale.ROOT);
        return l.equals("android") || l.equals("lost.dir") || l.equals(".thumbnails") || l.equals("node_modules") || l.equals(".git");
    }

    private void walkFiles(String token, File root, boolean hidden) {
        Deque<File> stack = new ArrayDeque<>();
        stack.push(root);
        JSONArray batch = new JSONArray();
        String rootPath = root.getAbsolutePath();
        while (!stack.isEmpty() && !cancel) {
            File dir = stack.pop();
            File[] kids = dir.listFiles();
            if (kids == null) continue;
            for (File f : kids) {
                if (cancel) break;
                String name = f.getName();
                if (f.isDirectory()) {
                    if (!skipDir(name, hidden)) stack.push(f);
                    continue;
                }
                if (!f.isFile()) continue;
                if (!hidden && name.startsWith(".")) continue;
                String abs = f.getAbsolutePath();
                String rel = abs.length() > rootPath.length() ? abs.substring(rootPath.length() + 1) : name;
                try {
                    JSONObject o = new JSONObject();
                    o.put("id", "file:" + abs);
                    o.put("rel", rel);
                    o.put("name", name);
                    o.put("size", f.length());
                    o.put("mtime", f.lastModified());
                    batch.put(o);
                } catch (Exception ignored) { }
                if (batch.length() >= BATCH) { emit(token, batch); batch = new JSONArray(); }
            }
        }
        if (batch.length() > 0) emit(token, batch);
    }

    private void walkTree(String token, Uri treeUri, boolean hidden) {
        final String[] cols = {
                DocumentsContract.Document.COLUMN_DOCUMENT_ID, DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                DocumentsContract.Document.COLUMN_MIME_TYPE, DocumentsContract.Document.COLUMN_SIZE,
                DocumentsContract.Document.COLUMN_LAST_MODIFIED };
        Deque<String[]> stack = new ArrayDeque<>(); // [docId, rel]
        stack.push(new String[]{DocumentsContract.getTreeDocumentId(treeUri), ""});
        JSONArray batch = new JSONArray();
        ContentResolver cr = getContentResolver();
        while (!stack.isEmpty() && !cancel) {
            String[] cur = stack.pop();
            Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(treeUri, cur[0]);
            try (Cursor c = cr.query(children, cols, null, null, null)) {
                if (c == null) continue;
                while (c.moveToNext() && !cancel) {
                    String docId = c.getString(0);
                    String name = c.getString(1);
                    String mime = c.getString(2);
                    if (name == null) continue;
                    String rel = cur[1].isEmpty() ? name : cur[1] + "/" + name;
                    if (DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)) {
                        if (!skipDir(name, hidden)) stack.push(new String[]{docId, rel});
                        continue;
                    }
                    if (!hidden && name.startsWith(".")) continue;
                    try {
                        JSONObject o = new JSONObject();
                        o.put("id", DocumentsContract.buildDocumentUriUsingTree(treeUri, docId).toString());
                        o.put("rel", rel);
                        o.put("name", name);
                        o.put("size", c.isNull(3) ? 0 : c.getLong(3));
                        o.put("mtime", c.isNull(4) ? 0 : c.getLong(4));
                        batch.put(o);
                    } catch (Exception ignored) { }
                    if (batch.length() >= BATCH) { emit(token, batch); batch = new JSONArray(); }
                }
            } catch (Exception ignored) {
                // 沒有權限的子資料夾直接略過
            }
        }
        if (batch.length() > 0) emit(token, batch);
    }

    private void emit(String token, JSONArray batch) {
        js("window.sbAndroid.onFiles(" + q(token) + "," + batch.toString() + ")");
    }

    private InputStream openInput(String id) throws Exception {
        if (id == null) return null;
        if (id.startsWith("file:")) return new FileInputStream(new File(id.substring(5)));
        return getContentResolver().openInputStream(Uri.parse(id));
    }

    private static String mimeOf(String name) {
        int i = name.lastIndexOf('.');
        String ext = i >= 0 ? name.substring(i + 1).toLowerCase(Locale.ROOT) : "";
        String m = MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext);
        return m == null ? "*/*" : m;
    }

    /* ------------------------------------------------------------------ */
    /* 系統回呼                                                              */
    /* ------------------------------------------------------------------ */

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQ_TREE) {
            if (resultCode != RESULT_OK || data == null || data.getData() == null) return;
            Uri uri = data.getData();
            try {
                getContentResolver().takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION);
            } catch (Exception ignored) { }
            picked(uri.toString(), treeLabel(uri));
        } else if (requestCode == REQ_ALL_FILES) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R && Environment.isExternalStorageManager()) startScanAllRoots();
            else toast("沒有取得「所有檔案存取權」，可改用「選擇資料夾」");
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQ_READ) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) startScanAllRoots();
            else toast("沒有讀取權限，可改用「選擇資料夾」");
        }
    }

    /** "primary:Documents/工作" → "Documents/工作"；"primary:" → "內部儲存空間"；"1234-5678:" → "SD 卡 1234-5678" */
    private static String treeLabel(Uri uri) {
        String id;
        try { id = DocumentsContract.getTreeDocumentId(uri); } catch (Exception e) { id = uri.getLastPathSegment(); }
        if (id == null) return "資料夾";
        int colon = id.indexOf(':');
        String vol = colon >= 0 ? id.substring(0, colon) : "";
        String path = colon >= 0 ? id.substring(colon + 1) : id;
        if (path.isEmpty()) return vol.equals("primary") ? "內部儲存空間" : "SD 卡 " + vol;
        return vol.equals("primary") || vol.isEmpty() ? path : vol + "/" + path;
    }
}
