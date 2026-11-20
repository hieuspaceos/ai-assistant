#!/usr/bin/env python3
"""Đối chiếu bản clone với số liệu/ảnh nguồn — hỗ trợ pha 4 của /clone-trang.

Ba chế độ (không cần cài thêm gì — BMP parse tay, không dùng Pillow):

  clone-compare.py styles <ref-styles.json> <clone-styles.json>
      So computed style theo thuộc tính `el` của từng phần tử đo được.
      Báo chỗ lệch: kích thước px lệch >2, màu rgb lệch >8 mỗi kênh,
      font-family khác. Phần tử clone có `data-cs-ref` (xem harvest)
      được khớp theo selector nguồn — không bị nhiễu tên class khác.

  clone-compare.py harvest <file-clone.html> <tabId> [--bridge URL]
      Đọc mọi data-cs-ref trong file clone, đo `styles` của từng phần
      tử đó trên tab clone qua bridge, ghi ra clone-styles.json —
      mỗi record gắn "ref" = selector nguồn để `styles` khớp chính xác.

  clone-compare.py shot <ref.png> <clone.png>
      Đổi 2 ảnh sang BMP bằng `sips` (có sẵn trên macOS), resize ảnh
      lớn về cùng khung nhỏ hơn rồi đếm % pixel lệch > ngưỡng.
      Kết quả: % pixel khác biệt — dưới ~12% thường là "khung khớp"
      (còn lại là nội dung ảnh placeholder khác ảnh gốc).
"""
import json, math, os, re, struct, subprocess, sys, tempfile, urllib.request

BRIDGE = os.environ.get("BROWSER_BRIDGE", "http://127.0.0.1:7684")

PX_TOL = 2.0
RGB_TOL = 8
SHOT_TOL = 40  # lệch kênh màu tính là "khác"


def _px(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _rgb(v):
    m = re.match(r"rgba?\((\d+)[, ]+(\d+)[, ]+(\d+)", str(v or ""))
    return tuple(int(x) for x in m.groups()) if m else None


def styles_mode(ref_fp, clone_fp):
    ref = json.load(open(ref_fp, encoding="utf-8"))
    cln = json.load(open(clone_fp, encoding="utf-8"))
    ref_items = {i["el"]: i for i in ref.get("items", [])}
    # clone khớp theo "ref" (=selector nguồn từ data-cs-ref) nếu có
    cln_items = {}
    for i in cln.get("items", []):
        cln_items[i.get("ref") or i["el"]] = i
    only_ref = sorted(set(ref_items) - set(cln_items))
    only_cln = sorted(set(cln_items) - set(ref_items))
    diffs = []
    for el in sorted(set(ref_items) & set(cln_items)):
        rc, cc = ref_items[el].get("css", {}), cln_items[el].get("css", {})
        rb, cb = ref_items[el].get("box", {}), cln_items[el].get("box", {})
        for prop in sorted(set(rc) & set(cc)):
            a, b = rc[prop], cc[prop]
            if a == b:
                continue
            ra, rb_ = _rgb(a), _rgb(b)
            if ra and rb_:
                if any(abs(x - y) > RGB_TOL for x, y in zip(ra, rb_)):
                    diffs.append(f"  {el} {prop}: {a} ≠ {b}")
                continue
            pa, pb = _px(str(a).replace("px", "")), _px(str(b).replace("px", ""))
            if pa is not None and pb is not None:
                if abs(pa - pb) > PX_TOL:
                    diffs.append(f"  {el} {prop}: {a} ≠ {b}")
            elif prop == "font-family":
                diffs.append(f"  {el} font-family: {a} ≠ {b}")
            else:
                diffs.append(f"  {el} {prop}: {a} ≠ {b}")
        dw = abs((rb.get("w") or 0) - (cb.get("w") or 0))
        if dw > PX_TOL:
            diffs.append(f"  {el} box.width: {rb.get('w')} ≠ {cb.get('w')}")
    if only_ref:
        print("CHỈ CÓ Ở NGUỒN (clone thiếu phần tử?):")
        for el in only_ref[:15]:
            print("  -", el)
    if only_cln:
        print("CHỈ CÓ Ở CLONE (khớp selector khác nguồn):")
        for el in only_cln[:15]:
            print("  +", el)
    print(f"\n{len(diffs)} điểm lệch (ngưỡng px>{PX_TOL}, rgb>{RGB_TOL}):")
    for d in diffs[:60]:
        print(d)
    if len(diffs) > 60:
        print(f"  … và {len(diffs) - 60} chỗ nữa")


def _to_bmp(png_fp, outdir, maxw=800):
    bmp = os.path.join(outdir, os.path.basename(png_fp) + ".bmp")
    subprocess.run(["sips", "-s", "format", "bmp", "--resampleWidth", str(maxw),
                    png_fp, "--out", bmp], check=True, capture_output=True)
    return bmp


def _read_bmp(fp):
    d = open(fp, "rb").read()
    off = struct.unpack_from("<I", d, 10)[0]
    w, h = struct.unpack_from("<ii", d, 18)
    bpp = struct.unpack_from("<H", d, 28)[0]
    row = ((w * bpp // 8) + 3) & ~3
    px = []
    for y in range(abs(h)):
        base = off + y * row
        px.append(d[base:base + w * (bpp // 8)])
    if h > 0:  # BMP lưu từ dưới lên
        px.reverse()
    return w, abs(h), bpp // 8, px


def shot_mode(ref_fp, clone_fp):
    with tempfile.TemporaryDirectory() as td:
        a = _read_bmp(_to_bmp(ref_fp, td))
        b = _read_bmp(_to_bmp(clone_fp, td))
    w = min(a[0], b[0]); h = min(a[1], b[1])
    diff = tot = 0
    for y in range(h):
        ra, rb = a[3][y], b[3][y]
        for x in range(w):
            i = x * a[2]; j = x * b[2]
            if (abs(ra[i] - rb[j]) > SHOT_TOL or
                abs(ra[i+1] - rb[j+1]) > SHOT_TOL or
                abs(ra[i+2] - rb[j+2]) > SHOT_TOL):
                diff += 1
            tot += 1
    pct = diff / tot * 100
    print(f"{os.path.basename(ref_fp)} vs {os.path.basename(clone_fp)}")
    print(f"  khung so {w}×{h} — {pct:.1f}% pixel khác (ngưỡng {SHOT_TOL}/kênh)")
    print("  <12%: khung rất khớp · 12-30%: kiểm lại bố cục/màu · >30%: sai lớn")


def harvest_mode(clone_fp, tab_id, bridge, out_fp):
    """Đo styles của mọi phần tử có data-cs-ref trên tab clone."""
    html = open(clone_fp, encoding="utf-8").read()
    refs = re.findall(r'data-cs-ref="([^"]+)"', html)
    if not refs:
        sys.exit("file không có data-cs-ref nào — gắn marker trước đã")
    items = []
    for ref in refs:
        sel = f'[data-cs-ref="{ref}"]'
        body = json.dumps({"action": "styles", "tabId": int(tab_id), "sel": sel}).encode()
        req = urllib.request.Request(bridge + "/api/browser", data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            res = json.load(urllib.request.urlopen(req, timeout=15))
        except Exception as e:
            print(f"  bỏ qua {ref}: {e}")
            continue
        for it in res.get("items", [])[:1]:
            it["ref"] = ref
            items.append(it)
    json.dump({"items": items}, open(out_fp, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{out_fp}: {len(items)}/{len(refs)} phần tử đã đo")


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "harvest":
        bridge = BRIDGE
        if "--bridge" in sys.argv:
            bridge = sys.argv[sys.argv.index("--bridge") + 1]
        out = sys.argv[sys.argv.index("-o") + 1] if "-o" in sys.argv else "clone-styles.json"
        harvest_mode(sys.argv[2], sys.argv[3], bridge, out)
        sys.exit(0)
    if len(sys.argv) != 4 or sys.argv[1] not in ("styles", "shot"):
        sys.exit(__doc__)
    try:
        (styles_mode if sys.argv[1] == "styles" else shot_mode)(sys.argv[2], sys.argv[3])
    except subprocess.CalledProcessError:
        sys.exit("sips không đổi được ảnh — chỉ chạy được trên macOS")
    except Exception as e:
        sys.exit(f"lỗi: {e}")
