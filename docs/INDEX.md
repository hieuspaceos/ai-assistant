# ai-assistant — Documentation Index

Chỉ là bản đồ điều hướng. Hành vi thật nằm trong source, skill và manifest.

---

## Start here

| Đối tượng | Đọc |
|---|---|
| Dev mới vào dự án | `project-overview-pdr.md` → `system-architecture.md` → `code-standards.md` |
| Sửa/thêm tính năng | `codebase-summary.md` → `api-reference.md` → `decision-log.md` |
| Làm việc với skill | `skills-system.md` → `.devin/skills/*/SKILL.md` |
| Pipeline clone web | `clone-pipeline.md` |
| Deploy / cài cho học viên | `../SETUP.md` → `troubleshooting-runbook.md` |
| Triển khai cty / fleet | `fleet.md` → `distribution.md` → `../deploy/DEPLOY.md` |
| Bảo mật / quyền truy cập | `SECURITY.md` |
| Biết dự án đi đâu | `project-roadmap.md` |

Entry gốc: [`README.md`](../README.md) · Quy tắc session: [`AGENTS.md`](../AGENTS.md)

---

## Authority map

| Document | Sở hữu |
|---|---|
| `project-overview-pdr.md` | Mục tiêu sản phẩm, đối tượng, non-goals |
| `system-architecture.md` | Ranh giới runtime, luồng dữ liệu giữa các process |
| `api-reference.md` | Endpoint của 3 bridge + action của extension. Truth: `tools/*.py` |
| `skills-system.md` | Skill packs, onboarding, contract SKILL.md |
| `clone-pipeline.md` | `/clone-trang` + `/trang-moi` + viewer + `data-cs-*` markers |
| `codebase-summary.md` | Bản đồ file (navigation). Inventory thật: `git ls-files` |
| `code-standards.md` | Quy ước code + pattern bị từ chối |
| `SECURITY.md` | Mô hình quyền, sandbox ghi file, ranh giới tin cậy |
| `decision-log.md` | Các quyết định kiến trúc và lý do (stateful) |
| `project-roadmap.md` | Hướng phát triển (stateful) |
| `troubleshooting-runbook.md` | Sự cố đã gặp + cách xử lý (stateful) |
| `extension-store-listing.md` | Hồ sơ submit Chrome Web Store cho extension |
| `fleet.md` | Beacon + collector: pairing, license, 3 tier deploy, privacy |
| `distribution.md` | Release ký ed25519 + update/rollback + config-pack per-cty |

---

## Quy ước đọc

- Doc viết tiếng Việt — khớp ngôn ngữ của chính dự án (`workspace/config.json` → `language`).
- Tên file, key JSON, tên skill: tiếng Anh.
- Doc nào ghi "(stateful)" là doc có trạng thái thời gian — cập nhật khi làm việc, không coi là spec bất biến.
