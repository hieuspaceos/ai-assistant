-- schema D1 cho troly-fleet — y hệt MIGRATIONS[1] của collector.py
CREATE TABLE IF NOT EXISTS machines(
  machine_id   TEXT PRIMARY KEY,
  org          TEXT,
  hostname     TEXT,
  os           TEXT,
  approved     INTEGER DEFAULT 0,
  revoked      INTEGER DEFAULT 0,
  machine_key  TEXT,
  first_seen   INTEGER,
  last_seen    INTEGER,
  learner      TEXT,
  brain        TEXT,
  version      TEXT,
  ext_version  TEXT,
  pack_version TEXT,
  snapshot_json TEXT,
  license_json TEXT,
  license_status TEXT,
  ev_stats     TEXT,
  repair       INTEGER DEFAULT 0,
  pending_key  TEXT);
CREATE TABLE IF NOT EXISTS usage(
  machine_id TEXT, day TEXT, counts TEXT,
  PRIMARY KEY(machine_id, day));
CREATE TABLE IF NOT EXISTS org_pings(
  org TEXT, ts INTEGER, payload TEXT);
CREATE INDEX IF NOT EXISTS idx_machines_key ON machines(machine_key);

-- v2: orgs + tài khoản admin thật chuyển vào D1 — ORGS_JSON secret giờ
-- chỉ còn vai trò seed/fallback; org tạo trong UI master nằm ở đây
CREATE TABLE IF NOT EXISTS orgs(
  name           TEXT PRIMARY KEY,
  beacon_secret  TEXT,
  license_secret TEXT,
  admin_key      TEXT,          -- key cty-admin kiểu cũ (link ?key= vẫn sống)
  note           TEXT,
  created_ts     INTEGER);

CREATE TABLE IF NOT EXISTS admins(
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  username    TEXT UNIQUE,
  pass_hash   TEXT,             -- PBKDF2-HMAC-SHA256 hex
  salt        TEXT,
  role        TEXT,             -- 'master' (vendor) | 'admin' (IT cty)
  org         TEXT,             -- org của role=admin; master thì NULL
  disabled    INTEGER DEFAULT 0,
  created_ts  INTEGER);

CREATE TABLE IF NOT EXISTS sessions(
  token      TEXT PRIMARY KEY,
  admin_id   INTEGER,
  created_ts INTEGER,
  expires_ts INTEGER);
CREATE INDEX IF NOT EXISTS idx_sessions_exp ON sessions(expires_ts);

CREATE TABLE IF NOT EXISTS audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actor  TEXT,                  -- username, hoặc 'key:<org>' / 'vendor'
  action TEXT,                  -- pair-approve | license-issue | ...
  org    TEXT,                  -- org liên quan (admin chỉ đụng org mình)
  target TEXT,                  -- machine_id / org / pack version
  detail TEXT,
  ts     INTEGER);

-- MIGRATION v2 (MIGRATIONS[2] của collector.py — repair flow):
-- DB đã tồn tại trước khi có cột repair/pending_key thì worker tự
-- ALTER lazy lần đầu dùng (ensureV2 trong index.js). Muốn migrate tay:
--   wrangler d1 execute troly-fleet-db --command \
--     "ALTER TABLE machines ADD COLUMN repair INTEGER DEFAULT 0;
--      ALTER TABLE machines ADD COLUMN pending_key TEXT"
