#!/usr/bin/env python3
"""make-license.py — cấp .devin/license.json cho một cty. Chạy phía
VENDOR (mình) một lần lúc gói bộ cài — KHÔNG ship script này cùng
secret cho khách.

License là "đếm và báo" (gentle): máy nhân viên chỉ đọc expiry để hiện
banner vàng; enforcement thật nằm ở collector (verify sig + đếm ghế).

    TROLY_LICENSE_SECRET=<org-secret> \
        python3 tools/make-license.py --org IMA --seats 20 \
            --expiry 2027-01-01 --out .devin/license.json

    # kiểm tra lại một license (đối chiếu collector):
    TROLY_LICENSE_SECRET=<org-secret> \
        python3 tools/make-license.py --check .devin/license.json

sig = HMAC-SHA256(license_secret, "org|seats|expiry|issued") — chuỗi ký
phải khớp nguyên mẫu với phía verify trong tools/collector.py
(test-fleet.py bắt drift).
"""
import argparse, datetime, hmac, hashlib, json, os, sys


def license_sig(secret, org, seats, expiry, issued):
    payload = f"{org}|{seats}|{expiry}|{issued}"
    return hmac.new(secret.encode(), payload.encode(),
                    hashlib.sha256).hexdigest()


def main():
    ap = argparse.ArgumentParser(description="cấp/kiểm license.json")
    ap.add_argument("--org"); ap.add_argument("--seats", type=int)
    ap.add_argument("--expiry", help="YYYY-MM-DD")
    ap.add_argument("--issued", help="YYYY-MM-DD, mặc định hôm nay")
    ap.add_argument("--out", help="đường dẫn ghi license.json")
    ap.add_argument("--check", metavar="FILE",
                    help="verify sig của license có sẵn")
    a = ap.parse_args()
    secret = os.environ.get("TROLY_LICENSE_SECRET")
    if not secret:
        sys.exit("thiếu TROLY_LICENSE_SECRET — secret của org đó "
                 "(vendor giữ, cùng chuỗi cấu hình trong collector.json)")

    if a.check:
        lic = json.load(open(a.check, encoding="utf-8"))
        want = license_sig(secret, lic["org"], lic["seats"],
                           lic["expiry"], lic["issued"])
        if hmac.compare_digest(want, lic.get("sig") or ""):
            print("OK — sig hợp lệ")
        else:
            sys.exit("SAI — sig không khớp (sai secret hoặc license bị sửa)")
        return

    if not (a.org and a.seats and a.expiry):
        ap.error("cần --org --seats --expiry")
    datetime.date.fromisoformat(a.expiry)      # raise nếu sai định dạng
    issued = a.issued or datetime.date.today().isoformat()
    datetime.date.fromisoformat(issued)
    lic = {"org": a.org, "seats": a.seats, "expiry": a.expiry,
           "issued": issued,
           "sig": license_sig(secret, a.org, a.seats, a.expiry, issued)}
    out = json.dumps(lic, ensure_ascii=False, indent=2) + "\n"
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)),
                    exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"đã ghi {a.out} — nhét file này vào .devin/ của bộ cài "
              f"cho {a.org}")
    else:
        print(out, end="")


if __name__ == "__main__":
    main()
