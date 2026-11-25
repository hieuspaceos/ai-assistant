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
  ev_stats     TEXT);
CREATE TABLE IF NOT EXISTS usage(
  machine_id TEXT, day TEXT, counts TEXT,
  PRIMARY KEY(machine_id, day));
CREATE TABLE IF NOT EXISTS org_pings(
  org TEXT, ts INTEGER, payload TEXT);
CREATE INDEX IF NOT EXISTS idx_machines_key ON machines(machine_key);
