#!/usr/bin/env python3
"""ensure-deps.py — cài các gói Python skill cần vào `.venv/` RIÊNG trong
folder dữ liệu, không đụng Python hệ thống (tránh lỗi
"externally-managed-environment" trên Homebrew/macOS mới).

Chạy tay:  python3 tools/ensure-deps.py [DATA]
Tự động:  launcher gọi nền mỗi lần mở app — idempotent, đã đủ thì về ngay.

Skills dùng `.venv/bin/python` (Windows: `.venv\\Scripts\\python.exe`)
khi file đó tồn tại — xem AGENTS.md.
"""
import os, subprocess, sys, venv

DATA = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.getcwd())
VENV = os.path.join(DATA, ".venv")
REQ = os.path.join(DATA, "requirements.txt")

WIN = sys.platform == "win32"
VPY = os.path.join(VENV, "Scripts" if WIN else "bin",
                   "python.exe" if WIN else "python")


def _ok():
    """True khi venv đã import được mọi gói trong requirements."""
    if not os.path.isfile(VPY):
        return False
    pkgs = []
    try:
        for ln in open(REQ, encoding="utf-8"):
            ln = ln.strip()
            if ln and not ln.startswith("#"):
                # "openpyxl>=3.1.0,<4" -> "openpyxl"; python-docx -> docx
                name = ln.split(">=")[0].split("==")[0].split("<")[0].strip()
                pkgs.append({"python-docx": "docx"}.get(name, name))
    except OSError:
        return False
    if not pkgs:
        return True
    return subprocess.run(
        [VPY, "-c", "import " + ", ".join(pkgs)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def main():
    if _ok():
        return 0                                    # đã đủ — không làm gì
    if not os.path.isfile(VPY):
        print("Đang chuẩn bị môi trường Python riêng cho trợ lý…")
        try:
            venv.create(VENV, with_pip=True)
        except Exception as e:
            print(f"Không tạo được .venv: {e}")
            return 1
    print("Đang cài gói Python cho skill Excel/Word (lần đầu ~1 phút)…")
    pip = [VPY, "-m", "pip", "install", "--disable-pip-version-check",
           "-r", REQ]
    if subprocess.run(pip).returncode != 0:
        print("Cài gói Python chưa được — kiểm tra mạng rồi chạy lại.")
        return 1
    if not _ok():
        print("Cài xong nhưng kiểm tra lại không qua — chạy lại giúp.")
        return 1
    print("Xong — skill Excel/Word dùng được rồi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
