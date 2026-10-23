# -*- coding: utf-8 -*-
"""產生二進位 AndroidManifest.xml（AXML）。環境中沒有 aapt2，因此直接依 Android 的二進位 XML 格式編碼。"""
import struct
import sys

NS = "http://schemas.android.com/apk/res/android"
ATTR_IDS = {  # android 框架公開屬性 ID（public.xml）
    "theme": 0x01010000, "label": 0x01010001, "name": 0x01010003, "exported": 0x01010010,
    "configChanges": 0x0101001F, "minSdkVersion": 0x0101020C, "versionCode": 0x0101021B,
    "versionName": 0x0101021C, "targetSdkVersion": 0x01010270,
}
T_REF, T_STR, T_DEC, T_HEX, T_BOOL = 0x01, 0x03, 0x10, 0x11, 0x12


def manifest(package, version_code, version_name, label, activity, min_sdk, target_sdk):
    # (標籤, [(是否 android 命名空間, 屬性名, 型別, 值)], 子元素)
    return ("manifest", [(False, "package", T_STR, package),
                         (True, "versionCode", T_DEC, version_code),
                         (True, "versionName", T_STR, version_name)], [
        ("uses-sdk", [(True, "minSdkVersion", T_DEC, min_sdk), (True, "targetSdkVersion", T_DEC, target_sdk)], []),
        ("application", [(True, "theme", T_REF, 0x01030241),  # @android:style/Theme.Material.Light.NoActionBar
                         (True, "label", T_STR, label)], [
            ("activity", [(True, "name", T_STR, activity), (True, "exported", T_BOOL, True),
                          (True, "configChanges", T_HEX, 0x04A0)], [  # orientation|keyboardHidden|screenSize
                ("intent-filter", [], [
                    ("action", [(True, "name", T_STR, "android.intent.action.MAIN")], []),
                    ("category", [(True, "name", T_STR, "android.intent.category.LAUNCHER")], []),
                ]),
            ]),
        ]),
    ])


def encode(root):
    attr_names = [n for n in ATTR_IDS]           # 有資源 ID 的屬性名放在字串池最前面，對應 resource map
    strings = list(attr_names)

    def idx(s):
        if s not in strings:
            strings.append(s)
        return strings.index(s)

    idx("android"); idx(NS)

    def walk(el):
        tag, attrs, kids = el
        idx(tag)
        for ns, name, t, v in attrs:
            idx(name)
            if t == T_STR:
                idx(v)
        for k in kids:
            walk(k)
    walk(root)

    body = []
    line = [1]

    def chunk(typ, hsize, payload):
        return struct.pack("<HHI", typ, hsize, 8 + len(payload)) + payload

    def emit(el):
        tag, attrs, kids = el
        enc = []
        for ns, name, t, v in sorted(attrs, key=lambda a: (a[0], ATTR_IDS.get(a[1], 0))):
            raw = idx(v) if t == T_STR else 0xFFFFFFFF
            data = idx(v) if t == T_STR else (0xFFFFFFFF if v is True else 0 if v is False else v)
            enc.append(struct.pack("<IIIHBBI", idx(NS) if ns else 0xFFFFFFFF, idx(name), raw, 8, 0, t, data))
        hdr = struct.pack("<IIII", line[0], 0xFFFFFFFF, 0xFFFFFFFF, idx(tag))
        hdr += struct.pack("<HHHHHH", 20, 20, len(enc), 0, 0, 0)
        body.append(chunk(0x0102, 16, hdr + b"".join(enc)))
        line[0] += 1
        for k in kids:
            emit(k)
        body.append(chunk(0x0103, 16, struct.pack("<IIII", line[0], 0xFFFFFFFF, 0xFFFFFFFF, idx(tag))))
        line[0] += 1

    ns_payload = struct.pack("<IIII", 1, 0xFFFFFFFF, idx("android"), idx(NS))
    body.append(chunk(0x0100, 16, ns_payload))
    emit(root)
    body.append(chunk(0x0101, 16, ns_payload))

    # 字串池（UTF-16）
    offs, data = [], b""
    for s in strings:
        offs.append(len(data))
        u = s.encode("utf-16-le")
        data += struct.pack("<H", len(u) // 2) + u + b"\0\0"
    data += b"\0" * (-len(data) % 4)
    sp_hdr = struct.pack("<IIIII", len(strings), 0, 0, 28 + 4 * len(strings), 0)
    pool = chunk(0x0001, 28, sp_hdr + b"".join(struct.pack("<I", o) for o in offs) + data)
    resmap = chunk(0x0180, 8, b"".join(struct.pack("<I", ATTR_IDS[n]) for n in attr_names))
    return chunk(0x0003, 8, pool + resmap + b"".join(body))


if __name__ == "__main__":
    out = sys.argv[1]
    root = manifest("tw.edu.stocktool", 1, "1.0", "股價指標萃取器", "tw.edu.stocktool.MainActivity", 24, 34)
    open(out, "wb").write(encode(root))
