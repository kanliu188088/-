#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
second_brain.py — 把所有硬碟裡的檔案收集成一個可搜尋的「第二大腦」

只需要 Python 3.8+ 的標準函式庫（SQLite + FTS5 全文檢索），不用安裝任何套件。
若有安裝 pypdf，會額外抽取 PDF 內文。

常用指令：
    python second_brain.py scan                    # 掃描所有硬碟（增量更新）
    python second_brain.py scan D:\\ E:\\資料        # 只掃描指定資料夾
    python second_brain.py search 永續 治理          # 全文搜尋（檔名 + 內容 + 筆記）
    python second_brain.py search --name 報告.docx   # 只搜檔名
    python second_brain.py recent --days 7          # 最近 7 天修改過的檔案
    python second_brain.py dupes                   # 找出重複檔案
    python second_brain.py stats                   # 統計：檔案類型、大小、大檔
    python second_brain.py tag  "D:\\文件\\A.docx" 工作 重要
    python second_brain.py note "D:\\文件\\A.docx" "這份是 2024 年董事會版本"
    python second_brain.py export ~/SecondBrain    # 匯出成 Markdown 知識庫（Obsidian 可直接開）

資料庫預設放在 ~/.second_brain/brain.db，可用 --db 指定。
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import sqlite3
import stat as stat_mod
import sys
import time
import zipfile
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

__version__ = "1.0.0"

# --------------------------------------------------------------------------- #
# 設定
# --------------------------------------------------------------------------- #

DEFAULT_DB = Path.home() / ".second_brain" / "brain.db"

# 一律略過的資料夾名稱（不分大小寫）
EXCLUDE_DIR_NAMES = {
    # Windows 系統
    "$recycle.bin", "system volume information", "windows", "program files",
    "program files (x86)", "programdata", "appdata", "$windows.~bt", "$windows.~ws",
    "recovery", "perflogs", "msocache", "windows.old", "onedrivetemp",
    # 開發用垃圾
    "node_modules", ".git", ".svn", ".hg", "__pycache__", ".venv", "venv", ".tox",
    ".cache", ".npm", ".gradle", ".m2", ".cargo", ".rustup", "target", "dist", "build",
    ".idea", ".vscode-server", "site-packages", ".pytest_cache", ".mypy_cache",
    # macOS
    ".trash", ".trashes", ".spotlight-v100", ".fseventsd", ".documentrevisions-v100",
    ".temporaryitems", "caches",
    # 其它
    ".second_brain",
}

# 一律略過的絕對路徑前綴（Linux / macOS 系統目錄）
EXCLUDE_PATH_PREFIXES = [
    "/proc", "/sys", "/dev", "/run", "/tmp", "/var", "/usr", "/bin", "/sbin", "/lib",
    "/lib32", "/lib64", "/etc", "/boot", "/snap", "/opt", "/srv", "/lost+found",
    "/System", "/Library", "/private", "/cores", "/Applications",
    "/Volumes/Recovery", "/Volumes/Preboot",
]

# 略過的檔案副檔名（暫存、快取、系統）
EXCLUDE_FILE_EXTS = {".tmp", ".temp", ".lnk", ".log", ".ds_store", ".ini", ".db-journal", ".pyc"}

# 會抽取內文做全文檢索的副檔名
TEXT_EXTS = {
    ".txt", ".md", ".markdown", ".rst", ".csv", ".tsv", ".json", ".xml", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".conf", ".log", ".html", ".htm", ".css", ".js", ".ts",
    ".jsx", ".tsx", ".py", ".java", ".c", ".h", ".cpp", ".hpp", ".cs", ".go", ".rs",
    ".rb", ".php", ".sh", ".bat", ".ps1", ".sql", ".r", ".m", ".swift", ".kt", ".tex",
    ".bib", ".srt", ".vtt", ".opml", ".eml", ".ics", ".vcf", ".org", ".adoc", ".textile",
}
OFFICE_EXTS = {".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp"}
PDF_EXTS = {".pdf"}

# 分類（stats / export 用）
KIND_BY_EXT = {
    "文件": {".doc", ".docx", ".odt", ".rtf", ".pdf", ".txt", ".md", ".pages", ".tex", ".epub"},
    "簡報": {".ppt", ".pptx", ".odp", ".key"},
    "試算表": {".xls", ".xlsx", ".xlsm", ".ods", ".csv", ".tsv", ".numbers"},
    "圖片": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp", ".heic",
             ".svg", ".raw", ".cr2", ".nef", ".psd", ".ai"},
    "影片": {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".m4v", ".webm", ".mts"},
    "音訊": {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".wma"},
    "壓縮檔": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso"},
    "程式碼": {".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".cs", ".go", ".rs", ".rb",
             ".php", ".sh", ".bat", ".ps1", ".sql", ".html", ".css", ".json", ".xml", ".yaml", ".yml"},
    "執行檔": {".exe", ".msi", ".dmg", ".pkg", ".app", ".apk", ".deb", ".rpm"},
    "筆記/資料": {".enex", ".opml", ".one", ".notes", ".sqlite", ".db"},
}
EXT_TO_KIND = {e: k for k, exts in KIND_BY_EXT.items() for e in exts}

DEFAULT_MAX_TEXT_BYTES = 2 * 1024 * 1024   # 抽取內文的檔案大小上限（2 MB）
MAX_STORED_CHARS = 200_000                  # 每個檔案最多存多少字的內文
PROGRESS_EVERY = 500

CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff66-\uff9f]")


# --------------------------------------------------------------------------- #
# 小工具
# --------------------------------------------------------------------------- #

def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:,.0f} {unit}" if unit == "B" else f"{n:,.1f} {unit}"
        n /= 1024
    return f"{n:,.1f} TB"


def ts_to_str(ts: Optional[float]) -> str:
    if not ts:
        return ""
    try:
        return dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except (OverflowError, OSError, ValueError):
        return ""


def kind_of(ext: str) -> str:
    return EXT_TO_KIND.get(ext, "其它")


def segment_cjk(text: str) -> str:
    """把每個中日韓字元前後補空白，讓 FTS5 的 unicode61 tokenizer 能逐字建索引。

    這樣「永續治理」會被存成「永 續 治 理」四個 token，
    搜尋時再把中文詞轉成 phrase query "永 續" 就能精準比對相鄰字。
    """
    return CJK_RE.sub(lambda m: f" {m.group(0)} ", text)


def build_fts_query(terms: Sequence[str]) -> str:
    """把使用者輸入轉成 FTS5 查詢：中文詞 → phrase，英文 → 前綴比對。"""
    parts: List[str] = []
    for raw in terms:
        raw = raw.strip()
        if not raw:
            continue
        if CJK_RE.search(raw):
            # 混合字串拆成中文段與非中文段，各自變成 phrase
            chunks = re.findall(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+|[^\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+", raw)
            for ch in chunks:
                ch = ch.strip()
                if not ch:
                    continue
                if CJK_RE.search(ch):
                    parts.append('"' + " ".join(ch) + '"')
                else:
                    parts.append('"' + ch.replace('"', '""') + '"')
        else:
            safe = raw.replace('"', '""')
            parts.append(f'"{safe}"*' if len(safe) >= 2 else f'"{safe}"')
    return " AND ".join(parts) if parts else '""'


def file_url(path: str) -> str:
    return Path(path).resolve().as_uri() if os.path.isabs(path) else path


# --------------------------------------------------------------------------- #
# 硬碟偵測
# --------------------------------------------------------------------------- #

def detect_drives() -> List[str]:
    """回傳目前系統上所有硬碟/掛載點的根目錄。"""
    roots: List[str] = []
    if os.name == "nt":
        import string
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                roots.append(drive)
        return roots

    roots.append("/")
    for mount_parent in ("/Volumes", "/mnt", "/media", f"/media/{os.environ.get('USER', '')}", "/run/media"):
        if os.path.isdir(mount_parent):
            try:
                for entry in os.scandir(mount_parent):
                    if entry.is_dir(follow_symlinks=False):
                        roots.append(entry.path)
            except OSError:
                pass
    # 去重（保留順序）
    seen, result = set(), []
    for r in roots:
        real = os.path.realpath(r)
        if real not in seen:
            seen.add(real)
            result.append(r)
    return result


# --------------------------------------------------------------------------- #
# 內文抽取
# --------------------------------------------------------------------------- #

_ENCODINGS = ("utf-8-sig", "utf-8", "cp950", "big5hkscs", "gb18030", "shift_jis", "utf-16", "cp1252")


def decode_bytes(data: bytes) -> str:
    for enc in _ENCODINGS:
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


_TAG_RE = re.compile(r"<[^>]+>")


def _xml_to_text(xml_bytes: bytes) -> str:
    text = xml_bytes.decode("utf-8", errors="replace")
    # 段落 / 儲存格 / 換行標籤改成空白，避免字黏在一起
    text = re.sub(r"</(w:p|a:p|text:p|table:table-cell|w:tab)>|<w:br[^>]*/>|<text:line-break[^>]*/>", " ", text)
    text = _TAG_RE.sub("", text)
    return html.unescape(text)


def extract_office(path: str) -> str:
    """docx / xlsx / pptx / odt / ods / odp：直接讀 zip 內的 XML，不需第三方套件。"""
    ext = os.path.splitext(path)[1].lower()
    chunks: List[str] = []
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        if ext == ".docx":
            targets = [n for n in names if n.startswith("word/") and n.endswith(".xml")
                       and ("document" in n or "header" in n or "footer" in n or "footnotes" in n)]
        elif ext == ".xlsx":
            targets = [n for n in names if n == "xl/sharedStrings.xml"] + \
                      sorted(n for n in names if n.startswith("xl/worksheets/sheet") and n.endswith(".xml"))
        elif ext == ".pptx":
            targets = sorted(n for n in names if n.startswith("ppt/slides/slide") and n.endswith(".xml")) + \
                      sorted(n for n in names if n.startswith("ppt/notesSlides/") and n.endswith(".xml"))
        else:  # OpenDocument
            targets = [n for n in names if n == "content.xml"]
        # 也讀取 metadata（標題、作者、關鍵字）
        targets += [n for n in names if n in ("docProps/core.xml", "meta.xml")]
        for name in targets:
            try:
                chunks.append(_xml_to_text(zf.read(name)))
            except (KeyError, zipfile.BadZipFile, RuntimeError):
                continue
    return "\n".join(chunks)


_PYPDF = None  # None = 還沒試過；False = 沒有或壞掉；否則為模組


def _load_pypdf():
    global _PYPDF
    if _PYPDF is None:
        try:
            import pypdf  # type: ignore
            _PYPDF = pypdf
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException:  # 某些環境 pypdf 相依的 cryptography 會直接 panic，不只是 ImportError
            _PYPDF = False
            log("提示：沒有可用的 pypdf，PDF 只會索引檔名不會抽取內文（pip install pypdf 可啟用）。")
    return _PYPDF


def extract_pdf(path: str) -> str:
    pypdf = _load_pypdf()
    if not pypdf:
        return ""
    try:
        reader = pypdf.PdfReader(path)
        out: List[str] = []
        total = 0
        for page in reader.pages:
            t = page.extract_text() or ""
            out.append(t)
            total += len(t)
            if total > MAX_STORED_CHARS:
                break
        return "\n".join(out)
    except Exception:  # pypdf 對壞檔會丟各式例外
        return ""


def extract_text(path: str, ext: str, size: int, max_bytes: int) -> str:
    """回傳檔案的純文字內容（可能為空字串）。"""
    try:
        if ext in TEXT_EXTS:
            if size > max_bytes:
                return ""
            with open(path, "rb") as f:
                data = f.read(max_bytes)
            if b"\x00" in data[:4096]:  # 二進位檔誤判
                return ""
            text = decode_bytes(data)
        elif ext in OFFICE_EXTS:
            if size > max_bytes * 25:  # Office 檔壓縮過，放寬上限（50 MB）
                return ""
            text = extract_office(path)
        elif ext in PDF_EXTS:
            if size > max_bytes * 50:
                return ""
            text = extract_pdf(path)
        else:
            return ""
    except (OSError, zipfile.BadZipFile, ValueError, RuntimeError):
        return ""
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    return text[:MAX_STORED_CHARS]


# --------------------------------------------------------------------------- #
# 資料庫
# --------------------------------------------------------------------------- #

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id          INTEGER PRIMARY KEY,
    path        TEXT NOT NULL UNIQUE,
    dir         TEXT NOT NULL,
    name        TEXT NOT NULL,
    ext         TEXT NOT NULL,
    kind        TEXT NOT NULL,
    size        INTEGER NOT NULL,
    mtime       REAL NOT NULL,
    ctime       REAL,
    hash        TEXT,
    root        TEXT NOT NULL,
    first_seen  REAL NOT NULL,
    last_seen   REAL NOT NULL,
    present     INTEGER NOT NULL DEFAULT 1,
    has_content INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_files_ext   ON files(ext);
CREATE INDEX IF NOT EXISTS idx_files_size  ON files(size);
CREATE INDEX IF NOT EXISTS idx_files_mtime ON files(mtime);
CREATE INDEX IF NOT EXISTS idx_files_hash  ON files(hash);
CREATE INDEX IF NOT EXISTS idx_files_root  ON files(root);

CREATE TABLE IF NOT EXISTS notes (
    id        INTEGER PRIMARY KEY,
    file_id   INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    note      TEXT NOT NULL,
    created   REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS tags (
    file_id   INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    tag       TEXT NOT NULL,
    PRIMARY KEY (file_id, tag)
);
CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);

CREATE TABLE IF NOT EXISTS scans (
    id        INTEGER PRIMARY KEY,
    started   REAL NOT NULL,
    finished  REAL,
    roots     TEXT NOT NULL,
    seen      INTEGER DEFAULT 0,
    added     INTEGER DEFAULT 0,
    updated   INTEGER DEFAULT 0,
    removed   INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""

FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(
    name, path, content, notes, tags,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""


class Brain:
    def __init__(self, db_path: Path):
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = NORMAL")
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        try:
            self.conn.executescript(FTS_SCHEMA)
            self.has_fts = True
        except sqlite3.OperationalError:
            self.has_fts = False
            log("警告：這個 Python 的 SQLite 沒有 FTS5，全文搜尋會退回較慢的 LIKE 比對。")
        self.conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('version', ?)", (__version__,))
        self.conn.commit()

    def close(self) -> None:
        self.conn.commit()
        self.conn.close()

    # ---- FTS 同步 -------------------------------------------------------- #

    def _fts_row(self, file_id: int) -> Tuple[str, str, str, str, str]:
        row = self.conn.execute("SELECT name, path FROM files WHERE id=?", (file_id,)).fetchone()
        notes = " ".join(r[0] for r in self.conn.execute(
            "SELECT note FROM notes WHERE file_id=? ORDER BY created", (file_id,)))
        tags = " ".join(r[0] for r in self.conn.execute(
            "SELECT tag FROM tags WHERE file_id=? ORDER BY tag", (file_id,)))
        return row["name"], row["path"], notes, tags

    def upsert_fts(self, file_id: int, content: Optional[str] = None) -> None:
        """重建某個檔案的 FTS 資料列。content=None 時保留原本的內文。"""
        if not self.has_fts:
            return
        name, path, notes, tags = self._fts_row(file_id)
        if content is None:
            old = self.conn.execute("SELECT content FROM fts WHERE rowid=?", (file_id,)).fetchone()
            content_seg = old["content"] if old else ""
        else:
            content_seg = segment_cjk(content)
        self.conn.execute("DELETE FROM fts WHERE rowid=?", (file_id,))
        self.conn.execute(
            "INSERT INTO fts(rowid, name, path, content, notes, tags) VALUES (?,?,?,?,?,?)",
            (file_id, segment_cjk(name), segment_cjk(path.replace(os.sep, " ")),
             content_seg, segment_cjk(notes), segment_cjk(tags)),
        )

    # ---- 查詢 ------------------------------------------------------------ #

    def find_file(self, path_or_name: str) -> Optional[sqlite3.Row]:
        """用完整路徑、或獨一無二的檔名找檔案。"""
        p = os.path.abspath(os.path.expanduser(path_or_name)) if os.path.exists(path_or_name) else path_or_name
        row = self.conn.execute("SELECT * FROM files WHERE path=?", (p,)).fetchone()
        if row:
            return row
        rows = self.conn.execute("SELECT * FROM files WHERE name=? AND present=1", (path_or_name,)).fetchall()
        if len(rows) == 1:
            return rows[0]
        if len(rows) > 1:
            log(f"有 {len(rows)} 個檔案叫「{path_or_name}」，請改用完整路徑：")
            for r in rows[:20]:
                log("  " + r["path"])
        return None


# --------------------------------------------------------------------------- #
# 掃描
# --------------------------------------------------------------------------- #

def is_excluded_dir(path: str, name: str, extra_excludes: Sequence[str], home: str,
                    path_prefixes: Sequence[str] = EXCLUDE_PATH_PREFIXES) -> bool:
    lname = name.lower()
    if lname in EXCLUDE_DIR_NAMES or lname in extra_excludes:
        return True
    norm = path.replace("\\", "/")
    if os.name != "nt":
        for prefix in path_prefixes:
            if norm == prefix or norm.startswith(prefix + "/"):
                return True
        # macOS 使用者家目錄裡的 ~/Library 很大且都是快取
        if norm == os.path.join(home, "Library").replace("\\", "/"):
            return True
    return False


def walk_files(root: str, extra_excludes: Sequence[str], follow_hidden: bool) -> Iterator[Tuple[str, os.stat_result]]:
    """用 scandir 遞迴列出檔案，不追蹤 symlink，遇到權限錯誤直接略過。"""
    home = str(Path.home())
    # 使用者明確指定的根目錄若本身就在系統目錄裡（例：/tmp/資料、/opt/backup），
    # 該系統目錄的排除規則就不套用，否則什麼都掃不到。
    root_norm = root.replace("\\", "/")
    path_prefixes = [p for p in EXCLUDE_PATH_PREFIXES
                     if not (root_norm == p or root_norm.startswith(p + "/"))]
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            it = os.scandir(current)
        except (PermissionError, FileNotFoundError, NotADirectoryError, OSError):
            continue
        with it:
            for entry in it:
                name = entry.name
                if not follow_hidden and name.startswith(".") and name not in (".", ".."):
                    # 隱藏檔預設略過；但仍保留 .md/.txt 這類人看的檔？— 保守起見一律略過
                    continue
                try:
                    if entry.is_symlink():
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        if not is_excluded_dir(entry.path, name, extra_excludes, home, path_prefixes):
                            stack.append(entry.path)
                        continue
                    if not entry.is_file(follow_symlinks=False):
                        continue
                    st = entry.stat(follow_symlinks=False)
                except (PermissionError, FileNotFoundError, OSError):
                    continue
                if os.name == "nt":
                    # 略過 Windows 隱藏 / 系統屬性檔
                    attrs = getattr(st, "st_file_attributes", 0)
                    if attrs & (stat_mod.FILE_ATTRIBUTE_SYSTEM if hasattr(stat_mod, "FILE_ATTRIBUTE_SYSTEM") else 0x4):
                        continue
                yield entry.path, st


def cmd_scan(brain: Brain, args: argparse.Namespace) -> None:
    roots = [os.path.abspath(os.path.expanduser(r)) for r in args.roots] if args.roots else detect_drives()
    roots = [r for r in roots if os.path.isdir(r)]
    if not roots:
        log("找不到可以掃描的資料夾。")
        return
    extra_excludes = [e.lower() for e in (args.exclude or [])]
    max_bytes = int(args.max_text_mb * 1024 * 1024)
    started = time.time()
    conn = brain.conn
    scan_id = conn.execute("INSERT INTO scans(started, roots) VALUES (?,?)",
                           (started, json.dumps(roots, ensure_ascii=False))).lastrowid
    conn.commit()

    log(f"開始掃描 {len(roots)} 個位置：" + "、".join(roots))
    log(f"資料庫：{brain.db_path}" + ("" if args.content else "（不抽取內文）"))

    seen = added = updated = removed = content_count = 0
    seen_paths_per_root: Dict[str, set] = {}

    for root in roots:
        seen_paths: set = set()
        seen_paths_per_root[root] = seen_paths
        log(f"→ {root}")
        batch = 0
        for path, st in walk_files(root, extra_excludes, args.hidden):
            seen += 1
            seen_paths.add(path)
            name = os.path.basename(path)
            ext = os.path.splitext(name)[1].lower()
            if ext in EXCLUDE_FILE_EXTS and not args.keep_temp:
                continue
            row = conn.execute("SELECT id, size, mtime, has_content FROM files WHERE path=?", (path,)).fetchone()
            now = time.time()
            changed = row is None or row["size"] != st.st_size or abs(row["mtime"] - st.st_mtime) > 1
            need_content = args.content and (ext in TEXT_EXTS or ext in OFFICE_EXTS or ext in PDF_EXTS)

            if row is None:
                cur = conn.execute(
                    "INSERT INTO files(path, dir, name, ext, kind, size, mtime, ctime, root, first_seen, last_seen, present)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,1)",
                    (path, os.path.dirname(path), name, ext, kind_of(ext), st.st_size, st.st_mtime,
                     getattr(st, "st_birthtime", st.st_ctime), root, now, now))
                file_id = cur.lastrowid
                added += 1
            else:
                file_id = row["id"]
                if changed:
                    conn.execute("UPDATE files SET size=?, mtime=?, ctime=?, hash=NULL, last_seen=?, present=1, root=? WHERE id=?",
                                 (st.st_size, st.st_mtime, getattr(st, "st_birthtime", st.st_ctime), now, root, file_id))
                    updated += 1
                else:
                    conn.execute("UPDATE files SET last_seen=?, present=1 WHERE id=?", (now, file_id))

            if need_content and (changed or not row["has_content"] or args.reindex):
                text = extract_text(path, ext, st.st_size, max_bytes)
                brain.upsert_fts(file_id, text)
                conn.execute("UPDATE files SET has_content=? WHERE id=?", (1 if text else 0, file_id))
                if text:
                    content_count += 1
            elif row is None:
                brain.upsert_fts(file_id, "")

            batch += 1
            if batch % 200 == 0:
                conn.commit()
            if seen % PROGRESS_EVERY == 0:
                log(f"   已看過 {seen:,} 個檔案（新增 {added:,}、更新 {updated:,}）… {os.path.dirname(path)[:70]}")
        conn.commit()

    # 標記這次掃描的根目錄底下、已經不存在的檔案
    for root, seen_paths in seen_paths_per_root.items():
        rows = conn.execute("SELECT id, path FROM files WHERE root=? AND present=1", (root,)).fetchall()
        for r in rows:
            if r["path"] not in seen_paths and not os.path.exists(r["path"]):
                conn.execute("UPDATE files SET present=0 WHERE id=?", (r["id"],))
                removed += 1
    conn.execute("UPDATE scans SET finished=?, seen=?, added=?, updated=?, removed=? WHERE id=?",
                 (time.time(), seen, added, updated, removed, scan_id))
    conn.commit()
    if brain.has_fts and (added or updated):
        conn.execute("INSERT INTO fts(fts) VALUES ('optimize')")
        conn.commit()

    elapsed = time.time() - started
    log("")
    log(f"完成！耗時 {elapsed/60:.1f} 分鐘")
    log(f"  看過檔案：{seen:,}")
    log(f"  新增：{added:,}    更新：{updated:,}    已消失：{removed:,}")
    if args.content:
        log(f"  有抽取內文：{content_count:,}")
    total = conn.execute("SELECT COUNT(*), COALESCE(SUM(size),0) FROM files WHERE present=1").fetchone()
    log(f"  資料庫現有 {total[0]:,} 個檔案，共 {human_size(total[1])}")


# --------------------------------------------------------------------------- #
# 搜尋
# --------------------------------------------------------------------------- #

def _apply_filters(sql: str, params: list, args: argparse.Namespace) -> str:
    if getattr(args, "ext", None):
        exts = [("." + e.lstrip(".")).lower() for e in args.ext]
        sql += " AND f.ext IN (%s)" % ",".join("?" * len(exts))
        params.extend(exts)
    if getattr(args, "kind", None):
        sql += " AND f.kind=?"
        params.append(args.kind)
    if getattr(args, "under", None):
        prefix = os.path.abspath(os.path.expanduser(args.under))
        sql += " AND (f.path LIKE ? ESCAPE '\\')"
        params.append(prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
    if getattr(args, "tag", None):
        sql += " AND f.id IN (SELECT file_id FROM tags WHERE tag=?)"
        params.append(args.tag)
    if getattr(args, "min_size", None):
        sql += " AND f.size >= ?"
        params.append(parse_size(args.min_size))
    if getattr(args, "include_missing", False) is False:
        sql += " AND f.present=1"
    return sql


def parse_size(s: str) -> int:
    m = re.fullmatch(r"\s*([\d.]+)\s*([kmgt]?)b?\s*", s.lower())
    if not m:
        raise SystemExit(f"看不懂的大小：{s}（例：500MB、2G）")
    n = float(m.group(1))
    return int(n * {"": 1, "k": 1024, "m": 1024**2, "g": 1024**3, "t": 1024**4}[m.group(2)])


def print_rows(rows: Iterable[sqlite3.Row], show_snippet: bool = False, as_json: bool = False) -> int:
    rows = list(rows)
    if as_json:
        print(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=1, default=str))
        return len(rows)
    for r in rows:
        keys = r.keys()
        line = f"{ts_to_str(r['mtime']):16}  {human_size(r['size']):>10}  {r['path']}"
        if "tags" in keys and r["tags"]:
            line += f"   #{' #'.join(r['tags'].split(','))}"
        print(line)
        if show_snippet and "snippet" in keys and r["snippet"]:
            snippet = re.sub(r"\s+", " ", r["snippet"]).strip()
            # 把 segment_cjk 補進去的空白拿掉（只針對中日韓字之間）
            snippet = re.sub(r"(?<=[\u3400-\u9fff\u3040-\u30ff]) (?=[\u3400-\u9fff\u3040-\u30ff])", "", snippet)
            snippet = re.sub(r"(?<=[\u3400-\u9fff]) (?=[，。、：；！？「」（）])|(?<=[，。、：；！？「」（）]) (?=[\u3400-\u9fff])", "", snippet)
            print(f"{'':30}» {snippet[:200]}")
    return len(rows)


def cmd_search(brain: Brain, args: argparse.Namespace) -> None:
    conn = brain.conn
    terms = args.terms
    if not terms:
        raise SystemExit("請輸入要搜尋的關鍵字。")
    limit = args.limit

    if brain.has_fts and not args.like:
        cols = "{name path}" if args.name else "{name path content notes tags}"
        query = build_fts_query(terms)
        sql = (
            "SELECT f.*, snippet(fts, 2, '[', ']', '…', 24) AS snippet, "
            "(SELECT group_concat(tag) FROM tags t WHERE t.file_id=f.id) AS tags, bm25(fts, 10.0, 2.0, 1.0, 5.0, 8.0) AS rank "
            "FROM fts JOIN files f ON f.id = fts.rowid "
            f"WHERE fts MATCH ? "
        )
        params: list = [f"{cols} : ({query})"]
        sql = _apply_filters(sql, params, args)
        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)
        try:
            rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError as e:
            raise SystemExit(f"搜尋語法錯誤：{e}\n（FTS 查詢：{query}）")
    else:
        like = "%" + "%".join(terms) + "%"
        sql = ("SELECT f.*, NULL AS snippet, (SELECT group_concat(tag) FROM tags t WHERE t.file_id=f.id) AS tags "
               "FROM files f WHERE (f.name LIKE ? OR f.path LIKE ?)")
        params = [like, like]
        sql = _apply_filters(sql, params, args)
        sql += " ORDER BY f.mtime DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()

    n = print_rows(rows, show_snippet=not args.name, as_json=args.json)
    if not args.json:
        log(f"\n共 {n} 筆" + ("（已達上限，可用 --limit 調高）" if n >= limit else ""))


def cmd_recent(brain: Brain, args: argparse.Namespace) -> None:
    since = time.time() - args.days * 86400
    sql = ("SELECT f.*, (SELECT group_concat(tag) FROM tags t WHERE t.file_id=f.id) AS tags "
           "FROM files f WHERE f.mtime >= ?")
    params: list = [since]
    sql = _apply_filters(sql, params, args)
    sql += " ORDER BY f.mtime DESC LIMIT ?"
    params.append(args.limit)
    n = print_rows(brain.conn.execute(sql, params), as_json=args.json)
    if not args.json:
        log(f"\n最近 {args.days} 天內修改：{n} 筆")


# --------------------------------------------------------------------------- #
# 重複檔
# --------------------------------------------------------------------------- #

def hash_file(path: str, full: bool = True, chunk: int = 1 << 20) -> Optional[str]:
    h = hashlib.blake2b(digest_size=20)
    try:
        with open(path, "rb") as f:
            if not full:
                h.update(f.read(65536))
                return "p:" + h.hexdigest()
            while True:
                b = f.read(chunk)
                if not b:
                    break
                h.update(b)
    except OSError:
        return None
    return h.hexdigest()


def cmd_dupes(brain: Brain, args: argparse.Namespace) -> None:
    conn = brain.conn
    min_size = parse_size(args.min_size)
    sizes = conn.execute(
        "SELECT size FROM files WHERE present=1 AND size >= ? GROUP BY size HAVING COUNT(*) > 1 ORDER BY size DESC",
        (min_size,)).fetchall()
    log(f"有 {len(sizes)} 組大小相同的檔案要比對…")
    groups: Dict[str, List[sqlite3.Row]] = {}
    hashed = 0
    for i, (size,) in enumerate(sizes, 1):
        rows = conn.execute("SELECT id, path, size, mtime, hash FROM files WHERE present=1 AND size=?", (size,)).fetchall()
        # 先用前 64 KB 的部分雜湊篩掉明顯不同的
        partial: Dict[str, List[sqlite3.Row]] = {}
        for r in rows:
            p = hash_file(r["path"], full=False)
            if p:
                partial.setdefault(p, []).append(r)
        for cand in partial.values():
            if len(cand) < 2:
                continue
            for r in cand:
                h = r["hash"]
                if not h:
                    h = hash_file(r["path"])
                    hashed += 1
                    if h:
                        conn.execute("UPDATE files SET hash=? WHERE id=?", (h, r["id"]))
                if h:
                    groups.setdefault(h, []).append(r)
        if i % 50 == 0:
            conn.commit()
            log(f"   {i}/{len(sizes)} 組，已計算 {hashed} 個完整雜湊")
    conn.commit()

    dupes = [(h, rs) for h, rs in groups.items() if len(rs) > 1]
    dupes.sort(key=lambda x: x[1][0]["size"] * (len(x[1]) - 1), reverse=True)
    wasted = sum(rs[0]["size"] * (len(rs) - 1) for _, rs in dupes)

    if args.json:
        print(json.dumps([{"hash": h, "size": rs[0]["size"], "paths": [r["path"] for r in rs]} for h, rs in dupes],
                         ensure_ascii=False, indent=1))
        return
    for h, rs in dupes[:args.limit]:
        print(f"\n[{human_size(rs[0]['size'])}] × {len(rs)}  ({h[:12]})")
        for r in sorted(rs, key=lambda r: r["mtime"]):
            print(f"    {ts_to_str(r['mtime'])}  {r['path']}")
    log(f"\n共 {len(dupes)} 組重複檔，重複部分佔用 {human_size(wasted)}"
        + (f"（只顯示前 {args.limit} 組）" if len(dupes) > args.limit else ""))


# --------------------------------------------------------------------------- #
# 統計
# --------------------------------------------------------------------------- #

def cmd_stats(brain: Brain, args: argparse.Namespace) -> None:
    conn = brain.conn
    total = conn.execute("SELECT COUNT(*), COALESCE(SUM(size),0) FROM files WHERE present=1").fetchone()
    missing = conn.execute("SELECT COUNT(*) FROM files WHERE present=0").fetchone()[0]
    with_content = conn.execute("SELECT COUNT(*) FROM files WHERE present=1 AND has_content=1").fetchone()[0]
    last = conn.execute("SELECT * FROM scans ORDER BY id DESC LIMIT 1").fetchone()
    print(f"資料庫：{brain.db_path}")
    print(f"檔案總數：{total[0]:,}    總大小：{human_size(total[1])}    已抽取內文：{with_content:,}    已消失：{missing:,}")
    if last:
        print(f"上次掃描：{ts_to_str(last['started'])} → {ts_to_str(last['finished'])}   位置：{', '.join(json.loads(last['roots']))}")

    print("\n■ 依硬碟 / 根目錄")
    for r in conn.execute("SELECT root, COUNT(*) c, SUM(size) s FROM files WHERE present=1 GROUP BY root ORDER BY s DESC"):
        print(f"  {r['root']:<30} {r['c']:>10,}  {human_size(r['s']):>12}")

    print("\n■ 依類型")
    for r in conn.execute("SELECT kind, COUNT(*) c, SUM(size) s FROM files WHERE present=1 GROUP BY kind ORDER BY s DESC"):
        print(f"  {r['kind']:<10} {r['c']:>10,}  {human_size(r['s']):>12}")

    print("\n■ 最多的副檔名（前 20）")
    for r in conn.execute("SELECT ext, COUNT(*) c, SUM(size) s FROM files WHERE present=1 GROUP BY ext ORDER BY c DESC LIMIT 20"):
        print(f"  {(r['ext'] or '(無)'):<10} {r['c']:>10,}  {human_size(r['s']):>12}")

    print("\n■ 依修改年份")
    for r in conn.execute("SELECT strftime('%Y', mtime, 'unixepoch') y, COUNT(*) c, SUM(size) s "
                          "FROM files WHERE present=1 GROUP BY y ORDER BY y DESC LIMIT 25"):
        print(f"  {r['y'] or '?':<10} {r['c']:>10,}  {human_size(r['s']):>12}")

    print(f"\n■ 最大的 {args.top} 個檔案")
    for r in conn.execute("SELECT path, size, mtime FROM files WHERE present=1 ORDER BY size DESC LIMIT ?", (args.top,)):
        print(f"  {human_size(r['size']):>10}  {ts_to_str(r['mtime'])}  {r['path']}")

    print(f"\n■ 檔案最多的 {args.top} 個資料夾")
    for r in conn.execute("SELECT dir, COUNT(*) c, SUM(size) s FROM files WHERE present=1 GROUP BY dir ORDER BY c DESC LIMIT ?", (args.top,)):
        print(f"  {r['c']:>8,}  {human_size(r['s']):>10}  {r['dir']}")

    tags = conn.execute("SELECT tag, COUNT(*) c FROM tags GROUP BY tag ORDER BY c DESC LIMIT 30").fetchall()
    if tags:
        print("\n■ 標籤")
        print("  " + "  ".join(f"#{t['tag']}({t['c']})" for t in tags))


# --------------------------------------------------------------------------- #
# 筆記與標籤
# --------------------------------------------------------------------------- #

def cmd_tag(brain: Brain, args: argparse.Namespace) -> None:
    row = brain.find_file(args.file)
    if not row:
        raise SystemExit(f"資料庫裡找不到：{args.file}（請先 scan）")
    for t in args.tags:
        t = t.lstrip("#").strip()
        if not t:
            continue
        if args.remove:
            brain.conn.execute("DELETE FROM tags WHERE file_id=? AND tag=?", (row["id"], t))
        else:
            brain.conn.execute("INSERT OR IGNORE INTO tags(file_id, tag) VALUES (?,?)", (row["id"], t))
    brain.upsert_fts(row["id"])
    brain.conn.commit()
    tags = [r[0] for r in brain.conn.execute("SELECT tag FROM tags WHERE file_id=? ORDER BY tag", (row["id"],))]
    print(f"{row['path']}\n  標籤：{' '.join('#' + t for t in tags) or '(無)'}")


def cmd_note(brain: Brain, args: argparse.Namespace) -> None:
    row = brain.find_file(args.file)
    if not row:
        raise SystemExit(f"資料庫裡找不到：{args.file}（請先 scan）")
    if args.text:
        brain.conn.execute("INSERT INTO notes(file_id, note, created) VALUES (?,?,?)",
                           (row["id"], " ".join(args.text), time.time()))
        brain.upsert_fts(row["id"])
        brain.conn.commit()
    print(row["path"])
    for n in brain.conn.execute("SELECT note, created FROM notes WHERE file_id=? ORDER BY created", (row["id"],)):
        print(f"  [{ts_to_str(n['created'])}] {n['note']}")


# --------------------------------------------------------------------------- #
# 匯出 Markdown 知識庫
# --------------------------------------------------------------------------- #

def md_link(path: str, name: Optional[str] = None) -> str:
    label = (name or os.path.basename(path)).replace("[", "［").replace("]", "］")
    return f"[{label}]({file_url(path)})"


def safe_filename(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|]+', "_", s).strip(" .")
    return s or "_"


def cmd_export(brain: Brain, args: argparse.Namespace) -> None:
    conn = brain.conn
    out = Path(os.path.expanduser(args.out))
    out.mkdir(parents=True, exist_ok=True)
    (out / "依類型").mkdir(exist_ok=True)
    (out / "依年份").mkdir(exist_ok=True)
    (out / "依資料夾").mkdir(exist_ok=True)
    (out / "標籤").mkdir(exist_ok=True)
    today = dt.date.today().isoformat()

    def write(rel: str, lines: List[str]) -> None:
        (out / rel).write_text("\n".join(lines) + "\n", encoding="utf-8")

    def table(rows: Iterable[sqlite3.Row], limit: Optional[int] = None) -> List[str]:
        lines = ["| 檔案 | 修改時間 | 大小 | 位置 |", "|---|---|---|---|"]
        for i, r in enumerate(rows):
            if limit and i >= limit:
                lines.append(f"| … | | | （只列前 {limit} 筆） |")
                break
            lines.append(f"| {md_link(r['path'])} | {ts_to_str(r['mtime'])} | {human_size(r['size'])} | `{r['dir']}` |")
        return lines

    # 依類型
    kinds = conn.execute("SELECT kind, COUNT(*) c, SUM(size) s FROM files WHERE present=1 GROUP BY kind ORDER BY c DESC").fetchall()
    for k in kinds:
        rows = conn.execute("SELECT * FROM files WHERE present=1 AND kind=? ORDER BY mtime DESC", (k["kind"],))
        write(f"依類型/{safe_filename(k['kind'])}.md",
              [f"# {k['kind']}", "", f"{k['c']:,} 個檔案，共 {human_size(k['s'])}", ""] + table(rows, args.max_rows))

    # 依年份
    years = conn.execute("SELECT strftime('%Y', mtime, 'unixepoch') y, COUNT(*) c FROM files WHERE present=1 GROUP BY y ORDER BY y DESC").fetchall()
    for y in years:
        rows = conn.execute("SELECT * FROM files WHERE present=1 AND strftime('%Y', mtime, 'unixepoch')=? ORDER BY mtime DESC", (y["y"],))
        write(f"依年份/{safe_filename(y['y'] or '未知')}.md", [f"# {y['y']} 年修改的檔案", "", f"{y['c']:,} 個檔案", ""] + table(rows, args.max_rows))

    # 依資料夾（第 depth 層）
    depth = args.depth
    folder_groups: Dict[str, List[sqlite3.Row]] = {}
    for r in conn.execute("SELECT * FROM files WHERE present=1 ORDER BY path"):
        rel = os.path.relpath(r["dir"], r["root"]) if r["dir"].startswith(r["root"]) else r["dir"]
        parts = [p for p in re.split(r"[\\/]+", rel) if p and p != "."]
        key = os.path.join(r["root"], *parts[:depth]) if parts else r["root"]
        folder_groups.setdefault(key, []).append(r)
    folder_index = ["# 依資料夾", ""]
    for key in sorted(folder_groups):
        rows = folder_groups[key]
        fname = safe_filename(key.replace(os.sep, "／").replace("/", "／").lstrip("／"))[:120] + ".md"
        size = sum(r["size"] for r in rows)
        write(f"依資料夾/{fname}", [f"# {key}", "", f"{len(rows):,} 個檔案，共 {human_size(size)}", "",
                                   f"[在檔案總管開啟]({file_url(key)})", ""] + table(sorted(rows, key=lambda r: -r["mtime"]), args.max_rows))
        folder_index.append(f"- [{key}](依資料夾/{fname.replace(' ', '%20')}) — {len(rows):,} 個檔案，{human_size(size)}")
    write("依資料夾.md", folder_index)

    # 標籤與筆記
    tag_rows = conn.execute("SELECT tag, COUNT(*) c FROM tags GROUP BY tag ORDER BY tag").fetchall()
    for t in tag_rows:
        rows = conn.execute("SELECT f.* FROM files f JOIN tags g ON g.file_id=f.id WHERE g.tag=? ORDER BY f.mtime DESC", (t["tag"],))
        write(f"標籤/{safe_filename(t['tag'])}.md", [f"# #{t['tag']}", ""] + table(rows))
    notes_lines = ["# 筆記", ""]
    for n in conn.execute("SELECT n.note, n.created, f.path FROM notes n JOIN files f ON f.id=n.file_id ORDER BY n.created DESC"):
        notes_lines.append(f"- **{ts_to_str(n['created'])}** {md_link(n['path'])}：{n['note']}")
    write("筆記.md", notes_lines)

    # 最近與重複
    recent = conn.execute("SELECT * FROM files WHERE present=1 ORDER BY mtime DESC LIMIT 200").fetchall()
    write("最近修改.md", ["# 最近修改的 200 個檔案", ""] + table(recent))
    dup_rows = conn.execute("SELECT hash, COUNT(*) c, size FROM files WHERE present=1 AND hash IS NOT NULL "
                            "GROUP BY hash HAVING c > 1 ORDER BY size*(c-1) DESC").fetchall()
    dup_lines = ["# 重複檔案", "", "（先執行 `dupes` 指令才會有資料）", ""]
    for d in dup_rows:
        dup_lines.append(f"## {human_size(d['size'])} × {d['c']}")
        for r in conn.execute("SELECT path FROM files WHERE hash=? AND present=1 ORDER BY path", (d["hash"],)):
            dup_lines.append(f"- {md_link(r['path'], r['path'])}")
        dup_lines.append("")
    write("重複檔案.md", dup_lines)

    # 首頁
    total = conn.execute("SELECT COUNT(*), COALESCE(SUM(size),0) FROM files WHERE present=1").fetchone()
    index = [
        f"# 我的第二大腦 — 檔案索引", "",
        f"更新日期：{today}　　檔案：{total[0]:,} 個　　總大小：{human_size(total[1])}", "",
        "## 入口", "",
        "- [最近修改](最近修改.md)", "- [依資料夾](依資料夾.md)", "- [筆記](筆記.md)", "- [重複檔案](重複檔案.md)", "",
        "## 依類型", "",
    ]
    index += [f"- [{k['kind']}](依類型/{safe_filename(k['kind'])}.md) — {k['c']:,} 個，{human_size(k['s'])}" for k in kinds]
    index += ["", "## 依年份", ""]
    index += [f"- [{y['y'] or '未知'}](依年份/{safe_filename(y['y'] or '未知')}.md) — {y['c']:,} 個" for y in years]
    if tag_rows:
        index += ["", "## 標籤", ""]
        index += [f"- [#{t['tag']}](標籤/{safe_filename(t['tag'])}.md) — {t['c']} 個" for t in tag_rows]
    index += ["", "---", "", "搜尋內文請用：`python second_brain.py search 關鍵字`"]
    write("首頁.md", index)
    log(f"已匯出到 {out}（用 Obsidian / Typora / VS Code 開啟 首頁.md）")


# --------------------------------------------------------------------------- #
# 其它小指令
# --------------------------------------------------------------------------- #

def cmd_drives(brain: Brain, args: argparse.Namespace) -> None:
    for d in detect_drives():
        try:
            st = os.statvfs(d) if hasattr(os, "statvfs") else None
            extra = f"  可用 {human_size(st.f_bavail * st.f_frsize)} / 共 {human_size(st.f_blocks * st.f_frsize)}" if st else ""
        except OSError:
            extra = ""
        print(f"{d}{extra}")


def cmd_forget(brain: Brain, args: argparse.Namespace) -> None:
    prefix = os.path.abspath(os.path.expanduser(args.path))
    like = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    ids = [r[0] for r in brain.conn.execute("SELECT id FROM files WHERE path LIKE ? ESCAPE '\\' OR path=?", (like, prefix))]
    if not ids:
        log("沒有符合的檔案。")
        return
    if not args.yes:
        log(f"將從資料庫移除 {len(ids):,} 筆紀錄（不會刪除實際檔案）。加上 --yes 確認執行。")
        return
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        q = ",".join("?" * len(chunk))
        if brain.has_fts:
            brain.conn.execute(f"DELETE FROM fts WHERE rowid IN ({q})", chunk)
        brain.conn.execute(f"DELETE FROM files WHERE id IN ({q})", chunk)
    brain.conn.commit()
    log(f"已移除 {len(ids):,} 筆。")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="second_brain.py",
        description="把所有硬碟裡的檔案收集成可搜尋的第二大腦（純標準函式庫，資料只存在本機）。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("常用指令：", 1)[1] if "常用指令：" in (__doc__ or "") else None,
    )
    p.add_argument("--db", default=str(DEFAULT_DB), help=f"資料庫路徑（預設 {DEFAULT_DB}）")
    p.add_argument("--version", action="version", version=f"second_brain {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="掃描硬碟並建立/更新索引（增量）")
    s.add_argument("roots", nargs="*", help="要掃描的資料夾；不給就掃描所有硬碟")
    s.add_argument("--no-content", dest="content", action="store_false", help="只記錄檔名與屬性，不抽取內文（快很多）")
    s.add_argument("--reindex", action="store_true", help="強制重新抽取所有檔案內文")
    s.add_argument("--exclude", nargs="*", help="額外要略過的資料夾名稱")
    s.add_argument("--hidden", action="store_true", help="也掃描以 . 開頭的隱藏檔/資料夾")
    s.add_argument("--keep-temp", action="store_true", help="不要略過 .tmp .log .lnk 等暫存檔")
    s.add_argument("--max-text-mb", type=float, default=DEFAULT_MAX_TEXT_BYTES / 1024 / 1024,
                   help="純文字檔抽取內文的大小上限（MB，預設 2）")
    s.set_defaults(func=cmd_scan)

    def add_filters(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--ext", nargs="*", help="只看這些副檔名，例：--ext docx pdf")
        sp.add_argument("--kind", choices=sorted(KIND_BY_EXT) + ["其它"], help="只看某類型")
        sp.add_argument("--under", help="只看某個資料夾底下")
        sp.add_argument("--tag", help="只看有某個標籤的")
        sp.add_argument("--min-size", help="只看大於這個大小的，例：10MB")
        sp.add_argument("--include-missing", action="store_true", help="連已經消失的檔案也列出")
        sp.add_argument("--limit", type=int, default=50, help="最多顯示幾筆（預設 50）")
        sp.add_argument("--json", action="store_true", help="以 JSON 輸出")

    s = sub.add_parser("search", help="全文搜尋（檔名、路徑、內文、筆記、標籤）")
    s.add_argument("terms", nargs="*", help="關鍵字，多個字全部都要符合")
    s.add_argument("--name", action="store_true", help="只搜檔名與路徑")
    s.add_argument("--like", action="store_true", help="不用全文索引，改用單純的字串包含比對")
    add_filters(s)
    s.set_defaults(func=cmd_search)

    s = sub.add_parser("recent", help="最近修改的檔案")
    s.add_argument("--days", type=float, default=7, help="幾天內（預設 7）")
    add_filters(s)
    s.set_defaults(func=cmd_recent)

    s = sub.add_parser("dupes", help="找出內容完全相同的重複檔案")
    s.add_argument("--min-size", default="1MB", help="只比對大於這個大小的檔案（預設 1MB）")
    s.add_argument("--limit", type=int, default=100, help="最多顯示幾組")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_dupes)

    s = sub.add_parser("stats", help="統計總覽")
    s.add_argument("--top", type=int, default=15)
    s.set_defaults(func=cmd_stats)

    s = sub.add_parser("tag", help="幫檔案加標籤")
    s.add_argument("file", help="檔案完整路徑（或獨一無二的檔名）")
    s.add_argument("tags", nargs="+", help="一個或多個標籤")
    s.add_argument("--remove", action="store_true", help="移除標籤")
    s.set_defaults(func=cmd_tag)

    s = sub.add_parser("note", help="幫檔案寫筆記（不給文字則列出既有筆記）")
    s.add_argument("file", help="檔案完整路徑（或獨一無二的檔名）")
    s.add_argument("text", nargs="*", help="筆記內容")
    s.set_defaults(func=cmd_note)

    s = sub.add_parser("export", help="匯出成 Markdown 知識庫（可用 Obsidian 開啟）")
    s.add_argument("out", help="輸出資料夾")
    s.add_argument("--depth", type=int, default=2, help="「依資料夾」分頁到第幾層（預設 2）")
    s.add_argument("--max-rows", type=int, default=2000, help="每頁最多列幾個檔案")
    s.set_defaults(func=cmd_export)

    s = sub.add_parser("drives", help="列出偵測到的硬碟")
    s.set_defaults(func=cmd_drives)

    s = sub.add_parser("forget", help="從資料庫移除某路徑底下的紀錄（不刪實際檔案）")
    s.add_argument("path")
    s.add_argument("--yes", action="store_true")
    s.set_defaults(func=cmd_forget)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    if sys.platform == "win32":
        # 讓中文檔名在 Windows 主控台正常顯示
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
            except AttributeError:
                pass
    parser = build_parser()
    args = parser.parse_args(argv)
    brain = Brain(Path(args.db))
    try:
        args.func(brain, args)
    except KeyboardInterrupt:
        brain.conn.commit()
        log("\n已中斷，目前為止的進度已存檔；再執行一次 scan 會從頭比對但只補上缺的部分。")
        return 130
    except BrokenPipeError:
        # 輸出被 head / more 截斷是正常的，不要噴錯誤
        try:
            sys.stdout = open(os.devnull, "w")
        except OSError:
            pass
        return 0
    finally:
        brain.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
