# Phase 1 — CI build `troly.exe` cho Windows

> **Status: CI xanh E2E — Release `v1.0.2` có đủ `troly` + `TroLyAI.exe`
> (run 44725484816).** Còn lại: verify exe trên Windows thật (gộp chung
> với fix-audit ph-5). Lỗi đã gặp và vá: snippet gốc dùng
> `{ shell: ${{ matrix.shell }} }` — `${{` trong flow mapping làm YAML
> parser gãy, run chết 0s; bản thật dùng block `shell: bash` (cả hai
> runner đều có Git Bash). Tag `v1.0.1` mồ côi trỏ commit lỗi — xoá bằng
> `git push --delete origin v1.0.1` khi tiện.

## Mục tiêu

Mỗi tag `v*` tự động ra GitHub Release có CẢ `troly` (macOS) lẫn
`TroLyAI.exe` (Windows) — không cần máy Windows thật để build.

## File động

| File | Action | Việc |
|---|---|---|
| `.github/workflows/build.yml` | create | matrix macos+windows, test, build, artifact, release |
| `tools/build.sh` | modify | thêm `--hidden-import winreg` (chỉ tồn tại trên Windows — PyInstaller macOS bỏ qua kèm warning, không fail); chấp nhận tên output theo OS |
| `docs/troubleshooting-runbook.md` | modify | ghi cách build/release (tag → CI → release) |

## Chi tiết

### 1a. Workflow `.github/workflows/build.yml`

```yaml
name: build
on:
  push:
    tags: ["v*"]
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: |
          python tools/test-bridges.py
          python tools/test-parity.py
          python tools/test-packs.py

  build:
    needs: test
    strategy:
      matrix:
        include:
          - { os: macos-latest,   name: troly }
          - { os: windows-latest, name: TroLyAI.exe }
    runs-on: ${{ matrix.os }}
    defaults:
      run:
        shell: bash   # Git Bash có sẵn trên windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: python -m pip install pyinstaller
      - run: bash tools/build.sh
      - name: rename artifact
        run: mv dist/troly* "dist/${{ matrix.name }}" || true
      - uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.name }}
          path: dist/${{ matrix.name }}

  release:
    if: startsWith(github.ref, 'refs/tags/')
    needs: build
    runs-on: ubuntu-latest
    permissions: { contents: write }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        # `gh release upload` CHẾT nếu tag chưa có release object —
        # `gh release create` vừa tạo vừa upload trong một lệnh.
        # Đồng thời chặn lệch tag↔VERSION: banner portal so VERSION
        # với release mới nhất, tag `v1.0.1` mà VERSION còn `1.0.0`
        # thì banner báo sai.
      - run: |
          test "v$(cat VERSION)" = "$GITHUB_REF_NAME" || {
            echo "tag $GITHUB_REF_NAME != VERSION $(cat VERSION)"; exit 1; }
          gh release create "$GITHUB_REF_NAME" \
            troly/troly "TroLyAI.exe/TroLyAI.exe" \
            --generate-notes --verify-tag \
          || gh release upload "$GITHUB_REF_NAME" \
            troly/troly "TroLyAI.exe/TroLyAI.exe" --clobber
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Ghi chú: `windows-latest` + `shell: bash` = Git Bash có sẵn trên runner —
`build.sh` chạy nguyên (nhánh `MINGW64_NT` đổi SEP thành `;` đã xử lý).
Không dùng action bên thứ ba cho release — `gh` CLI có sẵn trên runner,
đúng triết lý tối thiểu dependency.

### 1b. `tools/build.sh` — điều chỉnh nhỏ

- Thêm `--hidden-import winreg` (module Windows-only dùng trong
  `register_startup`; PyInstaller phân tích được import lồng hàm nhưng
  khai tường minh tránh drift). Trên macOS build sẽ warning "not found"
  — chấp nhận, không fail.
- Sau `pyinstaller`, echo đường dẫn artifact thực tế (`dist/troly` hoặc
  `dist\troly.exe`) cho CI dễ đọc log.

### 1c. Quy trình release (ghi vào runbook)

```
sửa VERSION → commit → git tag v<VERSION> → git push --tags
→ CI chạy test → build 2 OS → attach vào Release của tag
```

Banner "Có bản mới" trong portal đã trỏ tới Releases — không cần đổi
phía client.

## Acceptance

- Push tag `v*` → Release có đủ `troly` + `TroLyAI.exe`
- Trên Windows thật: `TroLyAI.exe` chạy → bung `~/TroLyAI` → mở portal,
  chat với não cài sẵn hoạt động (checklist tay — gỡ luôn mục "chờ test
  Windows" trong PLAN.md)
- `tools/test-*.py` fail → build không chạy (test là gate)
- macOS artifact vẫn chạy như bản build tay hiện tại

## Rủi ro

- PyInstaller trên `windows-latest` có thể thiếu hidden-import khác
  (mỗi `tools/*.py` chỉ stdlib nên rủi ro thấp; lỗi sẽ hiện ngay ở child
  spawn — check `.logs/` của user dir khi verify).
- SmartScreen chặn exe lạ: chấp nhận + hướng dẫn "More info → Run
  anyway" trong SETUP (phase 4 viết lại copy — gộp luôn).
- Lần đầu `troly.exe` chạy trên Windows thật có thể lòi lỗi path
  (`os.path.expanduser`, `chmod` no-op…) — phase này chỉ cam kết CI ra
  artifact; việc fix lỗi Windows-runtime thuộc checklist verify, vá
  trong cùng plan nếu phát hiện.
