# -*- coding: utf-8 -*-
"""把 index.src.html 與 SheetJS 合併成單一離線 HTML（dist/股價指標萃取器.html），APK 也使用這個檔案。"""
from pathlib import Path

here = Path(__file__).resolve().parent
src = (here / "index.src.html").read_text(encoding="utf-8")
lib = (here / "vendor" / "xlsx.full.min.js").read_text(encoding="utf-8")
tag = '<script src="vendor/xlsx.full.min.js"></script>'
assert tag in src and "</script" not in lib.lower()
out = here.parent / "dist" / "股價指標萃取器.html"
out.parent.mkdir(exist_ok=True)
out.write_text(src.replace(tag, "<script>/* SheetJS 0.18.5, Apache-2.0 */\n" + lib + "</script>"), encoding="utf-8")
print(out, f"{out.stat().st_size / 1024:.0f} KB")
