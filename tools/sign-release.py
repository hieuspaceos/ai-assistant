#!/usr/bin/env python3
"""sign-release.py — ký release manifest bằng ed25519 (phía VENDOR,
private key giữ OFFLINE — không nằm trong repo, không lên máy khách).

Chữ ký bất đối xứng là điểm cốt lõi: máy nhân viên chỉ nhúng PUBLIC
key (tools/vendor-pubkey — public key lộ không sao) → kẻ chiếm
collector hay sửa file trên máy vẫn KHÔNG forge được release, vì không
có private key. Đây là lý do KHÔNG dùng HMAC: khoá đối xứng phải nằm
trên máy để verify → trích ra được → forge release cho cả org.

    # một lần: sinh cặp khoá — giữ private key ở chỗ an toàn (offline)
    python3 tools/sign-release.py --gen-key

    # mỗi release: ký manifest (build-release.sh gọi bước này)
    python3 tools/sign-release.py --key ~/.troly-release-key \
        --zip releases/1.1.0/troly-1.1.0.zip --version 1.1.0 \
        --min-ver 1.0.0 --out releases/1.1.0/manifest.json

Manifest: {"version","url","sha256","min_ver","sig"} — sig =
ed25519(bytes.fromhex(sha256)) — update.py verify đúng chuỗi này.
"""
import argparse, hashlib, json, os, secrets, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ed25519 import publickey, signature  # noqa: E402

PUBKEY_FP = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "vendor-pubkey")


def main():
    ap = argparse.ArgumentParser(description="ký release manifest")
    ap.add_argument("--gen-key", action="store_true",
                    help="sinh cặp khoá mới — private key IN RA MÀN HÌNH, "
                         "copy ra chỗ an toàn rồi xoá shell history")
    ap.add_argument("--key", help="file chứa private key hex (64 ký tự)")
    ap.add_argument("--zip"); ap.add_argument("--version")
    ap.add_argument("--min-ver", default="0.0.0")
    ap.add_argument("--url", help="tên file zip trong manifest — mặc "
                                  "định basename của --zip")
    ap.add_argument("--out")
    a = ap.parse_args()

    if a.gen_key:
        sk = secrets.token_bytes(32)
        pk = publickey(sk)
        with open(PUBKEY_FP, "w") as f:
            f.write(pk.hex() + "\n")
        print(f"public key đã ghi {PUBKEY_FP} — file này đi theo "
              f"release, công khai được")
        print(f"PRIVATE KEY (giữ OFFLINE, không commit, không gửi ai):")
        print(sk.hex())
        return

    if not (a.key and a.zip and a.version and a.out):
        ap.error("cần --key --zip --version --out (hoặc --gen-key)")
    key_src = os.path.expanduser(a.key)
    sk = bytes.fromhex(open(key_src).read().strip()
                       if os.path.isfile(key_src) else a.key.strip())
    if len(sk) != 32:
        sys.exit("private key phải là 32 byte (hex 64 ký tự)")
    pk = publickey(sk)
    pub = open(PUBKEY_FP).read().strip() if os.path.isfile(PUBKEY_FP) \
        else ""
    if pub and pub != pk.hex():
        sys.exit("private key không khớp tools/vendor-pubkey — máy NV "
                 "nhúng pubkey khác sẽ verify fail")
    sha = hashlib.sha256(open(a.zip, "rb").read()).hexdigest()
    sig = signature(bytes.fromhex(sha), sk, pk).hex()
    man = {"version": a.version,
           "url": a.url or os.path.basename(a.zip),
           "sha256": sha, "min_ver": a.min_ver, "sig": sig}
    with open(a.out, "w") as f:
        json.dump(man, f, indent=2)
        f.write("\n")
    print(f"đã ký {a.out} — {a.version} sha256={sha[:16]}…")


if __name__ == "__main__":
    main()
