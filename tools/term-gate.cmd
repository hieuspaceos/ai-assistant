@echo off
rem term-gate.cmd — DEPRECATED, chỉ còn là vỏ chuyển tiếp.
rem
rem .cmd KHÔNG THỂ đọc argv/input an toàn: expansion %1/%t% trong batch
rem được re-parse — payload chứa " phá quote → & <lệnh> chạy trực tiếp
rem (RCE qua link localhost:7681/?arg=%22%26<cmd> mở trong trình duyệt).
rem Toàn bộ gate sống ở term-gate.ps1. File này forward KHÔNG kèm arg
rem (autofill ?arg= tắt khi gọi qua đây — luôn hỏi tay, an toàn tuyệt đối).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0term-gate.ps1"
