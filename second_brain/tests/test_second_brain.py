# -*- coding: utf-8 -*-
"""second_brain.py 的單元測試（只用標準函式庫）。執行：
    python -m unittest discover -s second_brain/tests -v
"""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import second_brain as sb  # noqa: E402


def make_docx(path: Path, text: str) -> None:
    body = "".join(f"<w:p><w:r><w:t>{line}</w:t></w:r></w:p>" for line in text.split("\n"))
    doc = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           f"<w:body>{body}</w:body></w:document>")
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", doc)


class TempTree(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sb_test_"))
        self.root = self.tmp / "data"
        (self.root / "文件" / "2024").mkdir(parents=True)
        (self.root / "node_modules" / "pkg").mkdir(parents=True)
        (self.root / "文件" / "2024" / "永續治理筆記.txt").write_text(
            "永續企業治理的三個線索：金剛組、柯達與富士、屏東基督教醫院。", encoding="utf-8")
        (self.root / "文件" / "report.md").write_text("quarterly report\nrevenue grew 12%\n", encoding="utf-8")
        (self.root / "文件" / "舊檔.txt").write_bytes("董事會決議通過".encode("cp950"))
        make_docx(self.root / "文件" / "簡介.docx", "屏東基督教醫院\n新大樓貸款")
        (self.root / "node_modules" / "pkg" / "a.js").write_text("ignored", encoding="utf-8")
        (self.root / "文件" / "x.tmp").write_text("temp", encoding="utf-8")
        (self.root / "dup1.bin").write_bytes(b"\x00" * 4096 + b"same")
        (self.root / "文件" / "dup2.bin").write_bytes(b"\x00" * 4096 + b"same")
        (self.root / "other.bin").write_bytes(b"\x00" * 4096 + b"diff")
        self.db = self.tmp / "brain.db"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, *argv: str) -> str:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = sb.main(["--db", str(self.db), *argv])
        self.assertEqual(code, 0, err.getvalue())
        return out.getvalue()

    def scan(self, *extra: str) -> str:
        return self.run_cli("scan", str(self.root), *extra)


class TestHelpers(unittest.TestCase):
    def test_segment_cjk(self):
        self.assertEqual(sb.segment_cjk("永續abc治理").split(), ["永", "續", "abc", "治", "理"])

    def test_build_fts_query(self):
        self.assertEqual(sb.build_fts_query(["永續"]), '"永 續"')
        self.assertEqual(sb.build_fts_query(["report"]), '"report"*')
        self.assertEqual(sb.build_fts_query(["永續", "report"]), '"永 續" AND "report"*')
        self.assertEqual(sb.build_fts_query(["A5小冊子"]), '"A5" AND "小 冊 子"')

    def test_decode_bytes_big5(self):
        self.assertEqual(sb.decode_bytes("董事會".encode("cp950")), "董事會")
        self.assertEqual(sb.decode_bytes("董事會".encode("utf-8-sig")), "董事會")

    def test_parse_size(self):
        self.assertEqual(sb.parse_size("10MB"), 10 * 1024 ** 2)
        self.assertEqual(sb.parse_size("2g"), 2 * 1024 ** 3)
        self.assertEqual(sb.parse_size("512"), 512)

    def test_kind_of(self):
        self.assertEqual(sb.kind_of(".docx"), "文件")
        self.assertEqual(sb.kind_of(".xyz"), "其它")

    def test_human_size(self):
        self.assertEqual(sb.human_size(512), "512 B")
        self.assertEqual(sb.human_size(1536), "1.5 KB")


class TestScanAndSearch(TempTree):
    def test_scan_indexes_and_excludes(self):
        self.scan()
        brain = sb.Brain(self.db)
        try:
            paths = {r[0] for r in brain.conn.execute("SELECT path FROM files WHERE present=1")}
        finally:
            brain.close()
        names = {os.path.basename(p) for p in paths}
        self.assertIn("永續治理筆記.txt", names)
        self.assertIn("簡介.docx", names)
        self.assertNotIn("a.js", names, "node_modules 應被略過")
        self.assertNotIn("x.tmp", names, ".tmp 應被略過")

    def test_root_inside_system_prefix_is_scanned(self):
        # /tmp 在排除清單裡，但使用者明確指定的根目錄底下仍要掃得到
        self.scan()
        out = self.run_cli("search", "--name", "report")
        self.assertIn("report.md", out)

    def test_chinese_fulltext(self):
        self.scan()
        out = self.run_cli("search", "永續", "治理")
        self.assertIn("永續治理筆記.txt", out)
        self.assertNotIn("report.md", out)

    def test_big5_content_search(self):
        self.scan()
        out = self.run_cli("search", "董事會")
        self.assertIn("舊檔.txt", out)

    def test_docx_content_search(self):
        self.scan()
        out = self.run_cli("search", "新大樓", "--ext", "docx")
        self.assertIn("簡介.docx", out)

    def test_english_prefix_and_filters(self):
        self.scan()
        self.assertIn("report.md", self.run_cli("search", "reven"))
        self.assertNotIn("report.md", self.run_cli("search", "revenue", "--ext", "txt"))
        self.assertIn("report.md", self.run_cli("search", "revenue", "--under", str(self.root / "文件")))

    def test_incremental_update_and_removal(self):
        self.scan()
        (self.root / "文件" / "report.md").write_text("now about 第二大腦\n", encoding="utf-8")
        (self.root / "文件" / "舊檔.txt").unlink()
        self.scan()
        self.assertIn("report.md", self.run_cli("search", "第二大腦"))
        self.assertNotIn("舊檔.txt", self.run_cli("search", "董事會"))
        self.assertIn("舊檔.txt", self.run_cli("search", "董事會", "--include-missing"))

    def test_no_content_flag(self):
        self.scan("--no-content")
        self.assertNotIn("report.md", self.run_cli("search", "revenue"))
        self.assertIn("report.md", self.run_cli("search", "--name", "report"))

    def test_json_output(self):
        import json
        self.scan()
        data = json.loads(self.run_cli("search", "revenue", "--json"))
        self.assertEqual(len(data), 1)
        self.assertTrue(data[0]["path"].endswith("report.md"))


class TestDupesTagsNotesExport(TempTree):
    def test_dupes(self):
        self.scan()
        out = self.run_cli("dupes", "--min-size", "1KB")
        self.assertIn("dup1.bin", out)
        self.assertIn("dup2.bin", out)
        self.assertNotIn("other.bin", out)

    def test_tag_and_note_searchable(self):
        self.scan()
        target = str(self.root / "文件" / "report.md")
        self.run_cli("tag", target, "工作", "#季報")
        self.run_cli("note", "report.md", "給董事會看的版本")
        self.assertIn("report.md", self.run_cli("search", "季報"))
        self.assertIn("report.md", self.run_cli("search", "董事會", "--tag", "工作"))
        self.run_cli("tag", target, "季報", "--remove")
        self.assertNotIn("report.md", self.run_cli("search", "季報"))

    def test_export_and_forget(self):
        self.scan()
        self.run_cli("tag", str(self.root / "文件" / "report.md"), "工作")
        out_dir = self.tmp / "vault"
        self.run_cli("export", str(out_dir))
        index = (out_dir / "首頁.md").read_text(encoding="utf-8")
        self.assertIn("依類型/文件.md", index)
        self.assertIn("標籤/工作.md", index)
        self.assertTrue((out_dir / "依類型" / "文件.md").exists())
        self.assertIn("report.md", (out_dir / "標籤" / "工作.md").read_text(encoding="utf-8"))

        self.run_cli("forget", str(self.root / "文件"), "--yes")
        self.assertNotIn("report.md", self.run_cli("search", "--name", "report", "--include-missing"))
        self.assertIn("dup1.bin", self.run_cli("search", "--name", "dup1"))

    def test_stats_runs(self):
        self.scan()
        out = self.run_cli("stats", "--top", "3")
        self.assertIn("檔案總數", out)
        self.assertIn("文件", out)


if __name__ == "__main__":
    unittest.main()
