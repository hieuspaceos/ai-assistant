#!/usr/bin/env python3
"""collector.py — fleet collector của một công ty: nhận beacon từ các
máy nhân viên, lưu SQLite, phục vụ dashboard cho IT/quản trị.

Single-file, stdlib-only — chạy được ngay trên máy IT có Python mà
không cần cài gì thêm. Ba tier triển khai, CÙNG file này:
  - LAN self-hosted:  máy IT trong LAN       → http://<ip>:8790
  - Customer-hosted:  VPS/domain CỦA KHÁCH    → https://fleet.<cty>  (nginx)
  - Vendor-hosted:    troly.hieuspace.com/fleet/ (một process per org)

    python3 tools/collector.py --config collector.json \
        [--port 8790] [--bind 0.0.0.0] [--data collector-data] \
        [--web collector-web]

collector.json (KHÔNG commit — chứa secret):
{
  "orgs": {
    "IMA": {"beacon_secret": "vé-vào-cửa", "license_secret": "...",
            "admin_key": "khoá-dashboard"}
  },
  "telemetry": {"url": "https://troly.hieuspace.com/fleet/api/org-ping",
                "key": "vendor-key"},       # bỏ trống = không ping;
                # inbound chỉ mở POST /api/org-ping, không quyền admin
  "vendor_read_key": "khoá-đọc-rollup",  # CHỈ đặt trên collector của
                # vendor — GET rollup org-level (org-pings/license/
                # packs), không machine-level, không write
  "release_key": "khoá-đẩy-release",     # ai được POST /api/releases;
                # không set = upload tắt (chỉ mirror/copy tay)
  "trust_proxy": true    # CHỈ khi sau nginx/proxy — rate limit theo
}                        # X-Forwarded-For; bật khi không có proxy =
                         # client tự forge IP né rate limit

Các lớp khoá — GIỮ RIÊNG, không trộn:
  beacon_secret : máy NV trình khi PAIR (chung cả org — chỉ là vé vào
                  cửa; sau khi duyệt, mỗi máy có machine_key riêng;
                  re-pair máy đã duyệt → flag repair chờ admin, không
                  trả lại key)
  admin_key     : IT cty đọc dashboard (máy NV không bao giờ có —
                  không đọc được data máy khác)
  vendor_read_key: vendor đọc rollup org-level (chỉ trên collector
                  vendor — config khách không có)
  release_key   : đẩy release xuống fleet (không set = upload tắt)
  telemetry.key : CHỈ outbound — máy khách ghi org-ping lên vendor,
                  không quyền gì khác

License check là "đếm và báo" (gentle): sai/hết hạn vẫn lưu snapshot,
đánh dấu license_status → dashboard flag, máy NV không bị khoá.
"""
import datetime, hmac, hashlib, http.server, json, os, secrets
import re, sqlite3, sys, threading, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PORT, BIND = 8790, "0.0.0.0"
DATA = os.path.join(HERE, "..", "collector-data")
WEB = os.path.join(HERE, "..", "collector-web")
CONFIG_FP = os.path.join(HERE, "..", "collector.json")
i = 1
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--port":
        PORT = int(sys.argv[i + 1]); i += 1
    elif a == "--bind":
        BIND = sys.argv[i + 1]; i += 1
    elif a == "--data":
        DATA = sys.argv[i + 1]; i += 1
    elif a == "--web":
        WEB = sys.argv[i + 1]; i += 1
    elif a == "--config":
        CONFIG_FP = sys.argv[i + 1]; i += 1
    i += 1
DATA, WEB = os.path.abspath(DATA), os.path.abspath(WEB)
BODY_CAP = 1_000_000

# ---------- cấu hình + khoá ----------

def load_config():
    cfg = json.load(open(CONFIG_FP, encoding="utf-8"))
    orgs = cfg.get("orgs") or {}
    if not orgs:
        raise SystemExit("collector.json: cần ít nhất một org trong "
                         "\"orgs\" — mỗi org có beacon_secret, "
                         "license_secret, admin_key")
    return cfg

CFG = load_config()
ORGS = CFG["orgs"]
# admin_key → org (đọc dashboard chỉ trong org mình; key rỗng/trùng
# nhau giữa các org → hành vi không xác định, vendor phải cấp khác nhau)
ADMIN2ORG = {o["admin_key"]: name for name, o in ORGS.items()
             if o.get("admin_key")}
# telemetry.key = credential OUTBOUND (ghi org-ping lên vendor) —
# inbound chỉ mở POST /api/org-ping, KHÔNG có quyền admin. Key này nằm
# plaintext trong collector.json của mọi khách nên không được làm
# god-mode. Đọc rollup mọi org cần vendor_read_key riêng — chỉ đặt
# trên collector của vendor, không bao giờ ship trong config khách.
TELE = CFG.get("telemetry") or {}
PING_KEY = TELE.get("key") or ""
VENDOR_READ = CFG.get("vendor_read_key") or ""
# release_key: ai được đẩy release xuống fleet — release là artifact
# vendor đã ký, không phải việc của org admin. Không set = upload tắt,
# release chỉ lên qua mirror_loop hoặc copy tay vào DATA/releases/.
RELEASE_KEY = CFG.get("release_key") or ""

def _eq(a, b):
    return hmac.compare_digest((a or "").encode("utf-8", "replace"),
                               (b or "").encode())

# ---------- DB: SQLite + schema_version (migrate tuần tự) ----------

DB_FP = os.path.join(DATA, "fleet.db")
# RLock (không phải Lock): q() tự acquire lock — bọc read+write ngoài
# bằng `with _db_lock` (merge counts trong _beacon) cần re-entrant
_db_lock = threading.RLock()

MIGRATIONS = {
    1: [
        """CREATE TABLE machines(
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
             ev_stats     TEXT)""",
        """CREATE TABLE usage(
             machine_id TEXT, day TEXT, counts TEXT,
             PRIMARY KEY(machine_id, day))""",
        """CREATE TABLE org_pings(
             org TEXT, ts INTEGER, payload TEXT)""",
    ],
    2: [
        # repair flow (audit-4 1.3): re-pair máy approved chỉ set flag,
        # admin duyệt → key mới vào pending_key, máy nhận ở pair kế
        "ALTER TABLE machines ADD COLUMN repair INTEGER DEFAULT 0",
        "ALTER TABLE machines ADD COLUMN pending_key TEXT",
    ],
}

def db():
    os.makedirs(DATA, exist_ok=True)
    conn = sqlite3.connect(DB_FP)
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT)")
    cur = conn.execute("SELECT v FROM meta WHERE k='schema_version'")
    row = cur.fetchone()
    ver = int(row[0]) if row else 0
    while ver < max(MIGRATIONS):
        ver += 1
        for sql in MIGRATIONS[ver]:
            conn.execute(sql)
        conn.execute(
            "INSERT INTO meta(k,v) VALUES('schema_version',?) "
            "ON CONFLICT(k) DO UPDATE SET v=excluded.v", (str(ver),))
    conn.commit()
    return conn

def q(sql, args=(), one=False, write=False):
    with _db_lock:
        conn = db()
        try:
            cur = conn.execute(sql, args)
            rows = cur.fetchone() if one else cur.fetchall()
            if write:
                conn.commit()
            return rows
        finally:
            conn.close()

# ---------- license ----------

def license_status(lic, org_name):
    """Verify sig HMAC bằng license_secret của org + check hạn. Trả một
    trong: missing / invalid / expired / expiring / ok."""
    if not isinstance(lic, dict):
        return "missing"
    if lic.get("org") != org_name:
        # máy khai org nào thì verify bằng secret org đó — license org B
        # sẽ "ok" trên máy org A. Ép org theo máy (row), không theo lời
        # máy khai trong license.
        return "invalid"
    sec = (ORGS.get(org_name) or {}).get("license_secret")
    if not sec:
        return "invalid"
    payload = "{}|{}|{}|{}".format(
        lic.get("org"), lic.get("seats"), lic.get("expiry"),
        lic.get("issued"))
    want = hmac.new(sec.encode(), payload.encode(),
                    hashlib.sha256).hexdigest()
    if not _eq(want, lic.get("sig")):
        return "invalid"
    try:
        exp = datetime.date.fromisoformat(str(lic["expiry"]))
    except Exception:
        return "invalid"
    today = datetime.date.today()
    if exp < today:
        return "expired"
    if (exp - today).days <= 30:
        return "expiring"
    return "ok"

def _as_dict(x):
    # body JSON hợp lệ nhưng field sai kiểu (snapshot=[1], counts=[1])
    # vẫn crash handler khi .get/.items — bọc mọi nested dict vào đây
    return x if isinstance(x, dict) else {}

# ---------- HTTP ----------

def find_static(name):
    """Static của dashboard: ưu tiên collector-web/ (deploy độc lập);
    chạy từ repo thì adm-render.js còn bản canonical trong web/ —
    tìm cả hai để không phải copy file trong repo."""
    for base in (WEB, os.path.join(HERE, "..", "web")):
        fp = os.path.realpath(os.path.join(base, name))
        if fp.startswith(os.path.realpath(base) + os.sep) \
                and os.path.isfile(fp):
            return fp
    return None

MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript",
        ".css": "text/css", ".svg": "image/svg+xml",
        ".json": "application/json; charset=utf-8"}

# rate limit đơn giản theo IP — cùng triết lý bridge: máy cty bị flood
# vẫn là máy cty, nhưng một máy hỏng/spam không được kéo chết collector
_rate = {}
_rate_lock = threading.Lock()
RATE_GET, RATE_POST = 240, 60          # req/phút/IP

def rate_ok(ip, post):
    lim = RATE_POST if post else RATE_GET
    now = time.time()
    with _rate_lock:
        w, n = _rate.get(ip, (now, 0))
        if now - w > 60:
            w, n = now, 0
        n += 1
        _rate[ip] = (w, n)
        # dọn bớt entry cũ mỗi ~1000 request để dict không phình
        if len(_rate) > 10000:
            for k in [k for k, (ww, _) in _rate.items() if now - ww > 300]:
                del _rate[k]
        return n <= lim

class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a):
        pass
    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def _client_ip(self):
        # Sau reverse proxy (customer-hosted tier) mọi request cùng IP
        # proxy → cả fleet chia một bucket rate limit. Chỉ tin XFF khi
        # config "trust_proxy" bật; bật mà không có proxy = client tự
        # forge XFF né rate limit (lỗi deploy, không phải lỗi code).
        if CFG.get("trust_proxy"):
            xff = self.headers.get("X-Forwarded-For")
            if xff:
                return xff.split(",")[0].strip()
        return self.client_address[0]

    def _admin_org(self):
        """X-Admin-Key → tên org được phép xem; vendor_read_key → "*"
        (mọi org, nhưng chỉ rollup — gate ở do_GET/do_POST)."""
        k = self.headers.get("X-Admin-Key") or ""
        if VENDOR_READ and _eq(k, VENDOR_READ):
            return "*"
        return ADMIN2ORG.get(k) if any(_eq(k, ak) for ak in ADMIN2ORG) \
            else None

    def _machine_row(self):
        """X-Beacon-Key = machine_key → row máy đã duyệt (release/pack
        download không public — chỉ máy trong fleet mới tải được)."""
        key = self.headers.get("X-Beacon-Key") or ""
        return q("SELECT * FROM machines WHERE machine_key=? "
                 "AND approved=1 AND revoked=0", (key,), one=True)

    def _body(self):
        try:
            cl = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            cl = 0
        cl = max(0, cl)
        if cl > BODY_CAP:
            self._json({"err": "body quá lớn"}, 413)
            return None
        try:
            b = json.loads(self.rfile.read(cl) or b"{}")
        except Exception:
            self._json({"err": "json không hợp lệ"}, 400)
            return None
        # [1,2,3] hoặc "str" qua được json.loads — b.get() ở handler sẽ
        # AttributeError → traceback + connection rớt không response
        if not isinstance(b, dict):
            self._json({"err": "body phải là json object"}, 400)
            return None
        return b

    # ----- machine-side endpoints (X-Beacon-Key) -----

    def _pair(self):
        org_name = self._pair_org or ""
        org = ORGS.get(org_name)
        if not org:
            return self._json({"err": "org không tồn tại"}, 401)
        b = self._body()
        if b is None:
            return
        mid = str(b.get("machine_id") or "")[:200]
        if not mid:
            return self._json({"err": "thiếu machine_id"}, 400)
        now = int(time.time())
        row = q("SELECT * FROM machines WHERE machine_id=?", (mid,),
                one=True)
        if row and row["org"] != org_name:
            # mid đã đăng ký org khác — secret org này không được
            # đụng vào (re-pair trả key / đổi org đều bị chặn)
            return self._json({"status": "pending"})
        if row and row["approved"] and not row["revoked"]:
            if row["pending_key"]:
                # admin đã duyệt (cấp mới hoặc cấp lại) — key LUÔN đi
                # qua pending_key, máy chỉ nhận qua pair: phát key và
                # set machine_key tại đây (rotate nếu key cũ tồn tại —
                # kẻ cầm key cũ mất quyền ngay)
                mk = row["pending_key"]
                q("UPDATE machines SET machine_key=?, repair=0, "
                  "pending_key=NULL WHERE machine_id=?",
                  (mk, mid), write=True)
                return self._json({"status": "approved",
                                   "machine_key": mk})
            # re-pair máy approved ĐÃ CÓ key (mất machine.key) → KHÔNG
            # trả key chỉ vì biết beacon_secret — shared toàn org.
            # Flag repair → /api/pending hiện cho admin duyệt cấp lại
            if not row["repair"]:
                q("UPDATE machines SET repair=1 WHERE machine_id=?",
                  (mid,), write=True)
            return self._json({"status": "pending"})
        if row and row["revoked"]:
            return self._json({"status": "revoked"})
        q("""INSERT INTO machines(machine_id,org,hostname,os,approved,
                                 first_seen,last_seen,license_json,
                                 license_status)
             VALUES(?,?,?,?,0,?,?,?,?)
             ON CONFLICT(machine_id) DO UPDATE SET
               hostname=excluded.hostname,
               os=excluded.os, last_seen=excluded.last_seen,
               license_json=excluded.license_json,
               license_status=excluded.license_status""",
          (mid, org_name, str(b.get("hostname") or "")[:200],
           str(b.get("os") or "")[:100], now, now,
           json.dumps(b.get("license"), ensure_ascii=False),
           license_status(b.get("license"), org_name)), write=True)
        return self._json({"status": "pending"})

    def _beacon(self):
        # X-Beacon-Key lúc này là machine_key (đã pair) — tra thẳng
        key = self.headers.get("X-Beacon-Key") or ""
        row = q("SELECT * FROM machines WHERE machine_key=?", (key,),
                one=True)
        if not row:
            return self._json({"err": "máy chưa pair hoặc key sai"}, 403)
        if row["revoked"] or not row["approved"]:
            return self._json({"status": "revoked"}, 403)
        b = self._body()
        if b is None:
            return
        now = int(time.time())
        snap = _as_dict(b.get("snapshot"))
        cfg = _as_dict(snap.get("config"))
        brain = _as_dict(_as_dict(snap.get("brain")).get("current"))
        health = _as_dict(snap.get("health"))
        counts = _as_dict(b.get("counts"))
        lic_st = license_status(b.get("license"), row["org"])
        q("""UPDATE machines SET hostname=?, os=?, last_seen=?,
             learner=?, brain=?, version=?, ext_version=?, pack_version=?,
             snapshot_json=?, license_json=?, license_status=?, ev_stats=?
             WHERE machine_id=?""",
          (str(b.get("hostname") or row["hostname"])[:200],
           str(b.get("os") or row["os"])[:100], now,
           str(cfg.get("learner_name") or "")[:100],
           str(brain.get("label") or brain.get("id") or "")[:100],
           str(b.get("version") or health.get("version") or "")[:40],
           str(health.get("extVersion") or "")[:40],
           str(b.get("pack_version") or "")[:40],
           json.dumps(snap, ensure_ascii=False),
           json.dumps(b.get("license"), ensure_ascii=False),
           lic_st,
           json.dumps(counts, ensure_ascii=False),
           row["machine_id"]), write=True)
        # gộp counts vào bucket NGÀY — dashboard hỏi "hôm nay dùng mấy
        # lượt" mà không cần giữ từng event. Read+write trong MỘT lock —
        # hai beacon cùng máy song song không được mất nhánh cộng
        if counts:
            day = datetime.date.today().isoformat()
            with _db_lock:
                old = q("SELECT counts FROM usage WHERE machine_id=? "
                        "AND day=?", (row["machine_id"], day), one=True)
                merged = dict(json.loads(old[0])) if old else {}
                for k, v in counts.items():
                    try:
                        merged[k] = merged.get(k, 0) + int(v)
                    except (TypeError, ValueError):
                        pass
                q("""INSERT INTO usage(machine_id,day,counts) VALUES(?,?,?)
                     ON CONFLICT(machine_id,day) DO UPDATE SET
                       counts=excluded.counts""",
                  (row["machine_id"], day, json.dumps(merged)), write=True)
        # plan 2 cắm vào đây: file releases.json/packs.json trong DATA
        resp = {"ok": True}
        rel = _release_hint(b)
        if rel:
            resp["update"] = rel
        pack = _pack_hint(b, row["org"])
        if pack:
            resp["pack"] = pack
        return self._json(resp)

    # ----- admin endpoints (X-Admin-Key, scope theo org) -----

    def _scope(self):
        org = self._admin_org()
        if org is None:
            self._json({"err": "thiếu hoặc sai X-Admin-Key"}, 401)
            return None
        return org

    def _path(self):
        """Vendor-hosted tier đi sau nginx path troly.hieuspace.com/fleet/
        — normalize bỏ prefix /fleet để cùng một route table."""
        p = urllib.parse.urlparse(self.path).path
        if p == "/fleet":
            return "/"
        if p.startswith("/fleet/"):
            return p[len("/fleet"):]
        return p

    def do_GET(self):
        if not rate_ok(self._client_ip(), False):
            return self._json({"err": "quá nhiều request"}, 429)
        path = self._path()
        # ----- machine-side download (X-Beacon-Key = machine_key) -----
        # release zip + pack JSON không public — chỉ máy đã pair mới
        # tải; manifest cũng vậy (máy chủ động pull khi boot/update)
        if path == "/api/releases/latest" or \
                path.startswith("/releases/") or \
                path.startswith("/packs/"):
            row = self._machine_row()
            if not row:
                return self._json({"err": "máy chưa pair"}, 403)
            if path == "/api/releases/latest":
                try:
                    man = json.load(open(
                        os.path.join(REL_DIR, "latest.json"),
                        encoding="utf-8"))
                    man["url"] = "/releases/" + os.path.basename(
                        man.get("url") or "")
                    return self._json(man)
                except Exception:
                    return self._json({"err": "chưa có release"}, 404)
            # /releases/<file> hoặc /packs/<org>/<ver>.json — chặn path
            # traversal; pack chỉ máy cùng org mới lấy được
            if path.startswith("/packs/") and \
                    not path.startswith(f"/packs/{row['org']}/"):
                return self._json({"err": "pack org khác"}, 403)
            if ".." in path:
                return self._json({"err": "not found"}, 404)
            fp = os.path.join(DATA, path.lstrip("/"))
            if not os.path.isfile(fp):
                return self._json({"err": "not found"}, 404)
            data = open(fp, "rb").read()
            self.send_response(200)
            self.send_header("Content-Type",
                             "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if not path.startswith("/api/"):
            # dashboard tĩnh — data endpoints vẫn đòi X-Admin-Key; trang
            # trần không lộ gì (pattern portal: file public, API khoá)
            name = "index.html" if path == "/" else path.lstrip("/")
            fp = find_static(name)
            if not fp:
                return self._json({"err": "not found"}, 404)
            data = open(fp, "rb").read()
            self.send_response(200)
            self.send_header("Content-Type",
                             MIME.get(os.path.splitext(fp)[1],
                                      "application/octet-stream"))
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return
        org = self._scope()
        if org is None:
            return
        # "*" (vendor_read_key) = read-rollup-only — KHÔNG machine-level:
        # /api/fleet, /api/pending, /api/fleet/<mid> chứa hostname,
        # learner, perms (PII) nên 403; chỉ rollup org-level được qua
        if org == "*" and path not in ("/api/org-pings", "/api/license",
                                       "/api/packs"):
            return self._json(
                {"err": "vendor key chỉ đọc rollup org-level"}, 403)
        if path == "/api/fleet":
            rows = q("SELECT * FROM machines WHERE approved=1 "
                     "AND revoked=0" + ("" if org == "*"
                                       else " AND org=?"),
                     () if org == "*" else (org,))
            day = datetime.date.today().isoformat()
            out = []
            for r in rows:
                snap = json.loads(r["snapshot_json"] or "{}")
                u = q("SELECT counts FROM usage WHERE machine_id=? "
                      "AND day=?", (r["machine_id"], day), one=True)
                out.append({
                    "machine_id": r["machine_id"], "org": r["org"],
                    "hostname": r["hostname"], "os": r["os"],
                    "learner": r["learner"], "brain": r["brain"],
                    "version": r["version"], "ext": r["ext_version"],
                    "pack_version": r["pack_version"],
                    "last_seen": r["last_seen"],
                    "license_status": r["license_status"],
                    "bot": (snap.get("bots") or {}).get("active"),
                    "today": json.loads(u[0]) if u else {},
                })
            return self._json({"machines": out,
                               "ts": int(time.time())})
        if path == "/api/pending":
            rows = q("SELECT machine_id,org,hostname,os,first_seen,"
                     "last_seen,license_status,repair FROM machines "
                     "WHERE (approved=0 OR repair=1) AND revoked=0"
                     + ("" if org == "*" else " AND org=?"),
                     () if org == "*" else (org,))
            return self._json({"pending": [dict(r) for r in rows]})
        if path.startswith("/api/fleet/"):
            mid = path[len("/api/fleet/"):]
            r = q("SELECT * FROM machines WHERE machine_id=?", (mid,),
                  one=True)
            if not r or (org != "*" and r["org"] != org):
                return self._json({"err": "not found"}, 404)
            usage = q("SELECT day,counts FROM usage WHERE machine_id=? "
                      "ORDER BY day DESC LIMIT 14", (mid,))
            return self._json({
                "machine_id": mid, "org": r["org"],
                "hostname": r["hostname"], "os": r["os"],
                "approved": bool(r["approved"]),
                "revoked": bool(r["revoked"]),
                "first_seen": r["first_seen"], "last_seen": r["last_seen"],
                "license": json.loads(r["license_json"] or "null"),
                "license_status": r["license_status"],
                "ev_stats": json.loads(r["ev_stats"] or "{}"),
                "snapshot": json.loads(r["snapshot_json"] or "{}"),
                "usage": [{"day": u[0], "counts": json.loads(u[1])}
                          for u in usage],
            })
        if path == "/api/license":
            rows = q("SELECT machine_id,org,last_seen,license_json,"
                     "license_status FROM machines WHERE approved=1 "
                     "AND revoked=0" + ("" if org == "*"
                                       else " AND org=?"),
                     () if org == "*" else (org,))
            active30 = 0
            cutoff = int(time.time()) - 30 * 86400
            seats, expiry, worst = None, None, "ok"
            rank = {"ok": 0, "expiring": 1, "expired": 2, "invalid": 3,
                    "missing": 4}
            for r in rows:
                if r["last_seen"] and r["last_seen"] > cutoff:
                    active30 += 1
                # seats/expiry chỉ tin license SIG HỢP LỆ — license bị
                # sửa (invalid) mà vẫn đếm ghế thì kẻ gian tự nâng ghế
                lic = json.loads(r["license_json"] or "null")
                if isinstance(lic, dict) and r["license_status"] in (
                        "ok", "expiring", "expired"):
                    seats = seats if seats is not None else lic.get("seats")
                    expiry = expiry or lic.get("expiry")
                if rank.get(r["license_status"], 0) > rank.get(worst, 0):
                    worst = r["license_status"]
            status = "exceeded" if seats and active30 > seats else worst
            return self._json({"org": org, "seats": seats,
                               "active30": active30, "expiry": expiry,
                               "status": status})
        if path == "/api/org-pings":
            if org != "*":
                return self._json({"err": "chỉ vendor key"}, 403)
            rows = q("SELECT org,ts,payload FROM org_pings "
                     "ORDER BY ts DESC LIMIT 500")
            return self._json({"pings": [
                {"org": r[0], "ts": r[1], "data": json.loads(r[2])}
                for r in rows]})
        if path == "/api/packs":
            # danh sách pack đang phát cho org mình — admin xem để biết
            # pack nào đang chạy trước khi đẩy bản mới
            names = sorted(os.listdir(PACK_DIR)) \
                if os.path.isdir(PACK_DIR) else []
            latest = {}
            for n in names:
                if n.startswith("latest-") and n.endswith(".json"):
                    oname = n[7:-5]
                    if org != "*" and oname != org:
                        continue
                    try:
                        latest[oname] = json.load(open(
                            os.path.join(PACK_DIR, n)))
                    except Exception:
                        pass
            return self._json({"latest": latest})
        return self._json({"err": "not found"}, 404)

    def do_POST(self):
        if not rate_ok(self._client_ip(), True):
            return self._json({"err": "quá nhiều request"}, 429)
        path = self._path()
        if path == "/api/pair":
            # org lấy từ beacon_secret trình lên — secret nào khớp org
            # nào thì pair vào org đó (máy không tự chọn org)
            key = self.headers.get("X-Beacon-Key") or ""
            self._pair_org = next(
                (n for n, o in ORGS.items()
                 if _eq(key, o.get("beacon_secret"))), None)
            return self._pair()
        if path == "/api/beacon":
            return self._beacon()
        if path in ("/api/pair-approve", "/api/pair-revoke"):
            org = self._scope()
            if org is None:
                return
            if org == "*":
                return self._json(
                    {"err": "vendor key chỉ đọc, không write"}, 403)
            b = self._body()
            if b is None:
                return
            mid = str(b.get("machine_id") or "")
            r = q("SELECT org FROM machines WHERE machine_id=?", (mid,),
                  one=True)
            if not r or r["org"] != org:
                return self._json({"err": "not found"}, 404)
            if path.endswith("approve"):
                mk = secrets.token_hex(24)
                # key LUÔN vào pending_key — máy nhận qua pair lần kế
                # (phát ở _pair). Cấp mới lẫn cấp lại đều một đường:
                # approve response cho admin xem, máy không đọc được —
                # beacon_secret một mình không lấy được key.
                q("UPDATE machines SET approved=1, revoked=0, "
                  "pending_key=? WHERE machine_id=?", (mk, mid),
                  write=True)
                return self._json({"ok": True, "machine_key": mk})
            # GIỮ machine_key: máy bị revoke vẫn tra ra được row → trả
            # status:"revoked" rõ ràng thay vì "key sai" — beacon biết
            # đường xoá key local và re-pair hiện pending cho admin.
            # Dọn cờ repair/pending_key cũ — revoke là reset sạch.
            q("UPDATE machines SET approved=0, revoked=1, repair=0, "
              "pending_key=NULL WHERE machine_id=?", (mid,),
              write=True)
            return self._json({"ok": True})
        if path == "/api/org-ping":
            # rollup org-level từ collector khác gửi về vendor — chỉ
            # vendor key mới ghi được, và chỉ lưu payload nguyên trạng
            if not (PING_KEY and
                    _eq(self.headers.get("X-Admin-Key"), PING_KEY)):
                return self._json({"err": "thiếu hoặc sai key"}, 401)
            b = self._body()
            if b is None:
                return
            # cắt thẳng [:8000] có thể phá JSON giữa chừng → /api/org-pings
            # json.loads crash → mỗi GET dashboard rớt. Telemetry key là
            # semi-public nên ai cũng đầu độc được — payload quá dài thì
            # thu về bản tóm tắt hợp lệ thay vì lưu rác
            payload = json.dumps(b, ensure_ascii=False)
            if len(payload) > 8000:
                payload = json.dumps(
                    {"org": str(b.get("org") or "?")[:80],
                     "_truncated": True})
            q("INSERT INTO org_pings(org,ts,payload) VALUES(?,?,?)",
              (str(b.get("org") or "?")[:80], int(time.time()),
               payload), write=True)
            # bảng phình vô hạn nếu không prune — ping là rollup gần
            # nhất, giữ 90 ngày là dư cho LIMIT 500 lúc đọc
            q("DELETE FROM org_pings WHERE ts<?",
              (int(time.time()) - 90 * 86400,), write=True)
            return self._json({"ok": True})
        # ----- admin phát hành (X-Admin-Key) -----
        # upload 2 bước: POST /api/releases/<file> (zip raw) rồi POST
        # /api/releases (manifest json trỏ tên file đó) — tránh
        # base64/multipart, zip có thể vài chục MB
        if path.startswith("/api/releases/"):
            # release là artifact vendor đã ký ed25519 — upload bằng
            # release_key RIÊNG, không phải admin_key org (admin org A
            # không được đẩy release xuống máy org B). Chưa set
            # release_key → upload tắt, chỉ mirror/copy tay
            if not (RELEASE_KEY and
                    _eq(self.headers.get("X-Admin-Key"), RELEASE_KEY)):
                return self._json(
                    {"err": "thiếu hoặc sai release_key"}, 401)
            fn = os.path.basename(path[len("/api/releases/"):])
            # latest.json là manifest do POST /api/releases quản — upload
            # đè trực tiếp = /api/releases/latest trả rác → fleet update
            # hỏng. Regex bắt đầu alnum cũng chặn dotfile; giữ ("." ,
            # "..") tường minh cho chắc.
            if not fn or fn in (".", "..") or \
                    fn.lower() == "latest.json" or \
                    not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", fn):
                return self._json({"err": "tên file lạ"}, 400)
            try:
                cl = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                cl = 0
            if cl <= 0 or cl > REL_CAP:
                return self._json({"err": "kích thước zip lạ"}, 413)
            data = self.rfile.read(cl)
            os.makedirs(REL_DIR, exist_ok=True)
            with open(os.path.join(REL_DIR, fn), "wb") as f:
                f.write(data)
            return self._json({"ok": True, "file": fn,
                               "sha256": hashlib.sha256(data).hexdigest()})
        if path == "/api/releases":
            if not (RELEASE_KEY and
                    _eq(self.headers.get("X-Admin-Key"), RELEASE_KEY)):
                return self._json(
                    {"err": "thiếu hoặc sai release_key"}, 401)
            b = self._body()
            if b is None:
                return
            if not all(b.get(k) for k in ("version", "url", "sha256",
                                          "sig")):
                return self._json(
                    {"err": "manifest thiếu version/url/sha256/sig"},
                    400)
            fn = os.path.basename(b["url"])
            if not os.path.isfile(os.path.join(REL_DIR, fn)):
                return self._json(
                    {"err": f"chưa upload {fn} (bước 1)"}, 400)
            man = {"version": str(b["version"]), "url": fn,
                   "sha256": b["sha256"], "sig": b["sig"],
                   "min_ver": str(b.get("min_ver") or "0.0.0")}
            _write_rel_manifest(man)
            return self._json({"ok": True})
        if path == "/api/packs":
            org = self._scope()
            if org is None:
                return
            if org == "*":
                return self._json(
                    {"err": "vendor key chỉ đọc, không write"}, 403)
            b = self._body()
            if b is None:
                return
            porg = str(b.get("org") or "")
            ver = b.get("pack_version")
            # porg phải là org đã khai trong config — "../.." trước đây
            # đi thẳng vào os.path.join = ghi JSON ra ngoài DATA/, và
            # porg chứa '/' crash ở latest-{porg}.json (FileNotFoundError
            # → handler chết, connection rớt)
            if porg not in ORGS or type(ver) is not int or ver < 0:
                return self._json(
                    {"err": "pack cần org trong config + "
                            "pack_version int >= 0"}, 400)
            if porg != org:
                return self._json(
                    {"err": "admin_key chỉ đẩy pack org mình"}, 403)
            sub = os.path.join(PACK_DIR, porg)
            os.makedirs(sub, exist_ok=True)
            raw = json.dumps(b, ensure_ascii=False)
            with open(os.path.join(sub, f"{ver}.json"), "w",
                      encoding="utf-8") as f:
                f.write(raw)
            # latest-<org>.json nằm ở PACK_DIR (không trong sub) —
            # _pack_hint đọc từ đó; sha256 để máy kiểm file kéo về
            with open(os.path.join(PACK_DIR, f"latest-{porg}.json"),
                      "w") as f:
                json.dump({"version": ver,
                           "sha256": hashlib.sha256(
                               raw.encode()).hexdigest()}, f)
            return self._json({"ok": True})
        return self._json({"err": "not found"}, 404)

# ---------- release/pack store (plan 2) ----------
#
# DATA/releases/ : latest.json (manifest) + <file>.zip — zip đã ký
#   ed25519 từ vendor. Lên đây bằng: mirror_loop (config "upstream"),
#   POST /api/releases (admin upload), hoặc IT copy tay vào dir.
# DATA/packs/<org>/<ver>.json + latest-<org>.json — pack cty do admin
#   đẩy qua POST /api/packs.
# Beacon trả {update, pack} tính từ store; url là path LOCAL của
# collector — update.py resolve lại host. sig/sha256 đi nguyên trạng:
# máy verify bằng vendor-pubkey, collector chỉ là bưu điện.

REL_DIR = os.path.join(DATA, "releases")
PACK_DIR = os.path.join(DATA, "packs")
REL_CAP = 200_000_000            # zip upload tối đa 200MB

def _write_rel_manifest(man):
    # tmp + os.replace — máy pull /api/releases/latest giữa chừng ghi
    # không được thấy half-JSON (json.dump không atomic)
    tmp = os.path.join(REL_DIR, ".latest.json.tmp")
    with open(tmp, "w") as f:
        json.dump(man, f, indent=2)
    os.replace(tmp, os.path.join(REL_DIR, "latest.json"))

def _ver_tuple(s):
    try:
        return tuple(int(x) for x in str(s).split("."))
    except Exception:
        return ()

def _release_hint(body):
    try:
        man = json.load(open(os.path.join(REL_DIR, "latest.json"),
                             encoding="utf-8"))
    except Exception:
        return None
    if _ver_tuple(man.get("version")) > _ver_tuple(body.get("version")):
        m = dict(man)
        m["url"] = "/releases/" + os.path.basename(m.get("url") or "")
        return m
    return None

def _pack_hint(body, org):
    # org lấy từ ROW đã xác thực (machine_key), KHÔNG từ body — máy gửi
    # org "../../x" vào đây thì open() đọc file JSON ngoài packs/ và lộ
    # version/sha256 qua response. body.get('org') chỉ là lời máy khai.
    try:
        p = json.load(open(os.path.join(
            PACK_DIR, f"latest-{org}.json"),
            encoding="utf-8"))
    except Exception:
        return None
    try:
        if int(p.get("version") or 0) > int(body.get("pack_version") or 0):
            return {"version": p["version"],
                    "url": f"/packs/{org}/{p['version']}.json",
                    "sha256": p.get("sha256")}
    except (TypeError, ValueError, KeyError):
        pass
    return None

# ---------- mirror: collector tự kéo release từ vendor upstream -------

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None

_MIRROR = urllib.request.build_opener(_NoRedirect)

def mirror_loop():
    """config "upstream": {"url": "…/releases/latest.json"} → cứ 6h
    kéo manifest; bản mới hơn local thì tải zip về. Mirror trung lập —
    máy NV verify sig nên mirror kéo nhầm file xấu cũng bị loại ở tầng
    verify của máy; worst case chỉ là stale."""
    url = (CFG.get("upstream") or {}).get("url")
    if not url:
        return
    while True:
        try:
            with _MIRROR.open(urllib.request.Request(url),
                              timeout=10) as r:
                man = json.loads(r.read())
            cur = {}
            try:
                cur = json.load(open(
                    os.path.join(REL_DIR, "latest.json")))
            except Exception:
                pass
            if all(man.get(k) for k in ("version", "url", "sha256",
                                        "sig")) and \
                    _ver_tuple(man["version"]) > \
                    _ver_tuple(cur.get("version")):
                zurl = urllib.parse.urljoin(url, man["url"])
                if urllib.parse.urlparse(zurl).netloc == \
                        urllib.parse.urlparse(url).netloc:
                    with _MIRROR.open(urllib.request.Request(zurl),
                                      timeout=300) as r:
                        data = r.read(REL_CAP)
                    if hashlib.sha256(data).hexdigest() == \
                            man["sha256"]:
                        os.makedirs(REL_DIR, exist_ok=True)
                        fn = os.path.basename(
                            urllib.parse.urlparse(zurl).path)
                        with open(os.path.join(REL_DIR, fn), "wb") as f:
                            f.write(data)
                        man["url"] = fn
                        _write_rel_manifest(man)
        except Exception:
            pass                            # mirror là phụ — lỗi thôi
        time.sleep(6 * 3600)

# ---------- meta-telemetry lên vendor (org-level rollup, 1/ngày) ----------

def telemetry_loop():
    """Collector → vendor: {org, machines_active, version_dist,
    license_expiry, ts}. Chỉ org-level — vendor thấy khách sống/khoẻ để
    support + nhắc gia hạn; KHÔNG gửi machine-level. Tắt bằng
    COLLECTOR_NO_TELEMETRY=1 hoặc bỏ mục telemetry trong config."""
    url, key = TELE.get("url"), TELE.get("key")
    if not url or not key or os.environ.get("COLLECTOR_NO_TELEMETRY"):
        return
    while True:
        try:
            for name in ORGS:
                rows = q("SELECT version,license_json FROM machines "
                         "WHERE org=? AND approved=1 AND revoked=0 "
                         "AND last_seen>?", (name,
                            int(time.time()) - 7 * 86400))
                vdist, expiry = {}, None
                for v, lj in rows:
                    vdist[v or "?"] = vdist.get(v or "?", 0) + 1
                    try:
                        expiry = expiry or json.loads(lj)["expiry"]
                    except Exception:
                        pass
                payload = {"org": name, "machines_active": len(rows),
                           "version_dist": vdist,
                           "license_expiry": expiry,
                           "ts": int(time.time())}
                req = urllib.request.Request(
                    url, data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json",
                             "X-Admin-Key": key}, method="POST")
                urllib.request.urlopen(req, timeout=8).read()
        except Exception:
            pass                    # telemetry là phụ — lỗi thì thôi
        time.sleep(86400)

# ---------- server ----------

class BoundedServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    _slots = threading.BoundedSemaphore(64)
    def process_request(self, request, client_address):
        self._slots.acquire()
        try:
            super().process_request(request, client_address)
        except Exception:
            self._slots.release()
            raise
    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()

if __name__ == "__main__":
    db()                                     # chạy migration ngay khi boot
    threading.Thread(target=telemetry_loop, daemon=True).start()
    threading.Thread(target=mirror_loop, daemon=True).start()
    print(f"collector: http://{BIND}:{PORT}  orgs={list(ORGS)}")
    # không in ?key= vào URL — key rơi vào browser history/proxy log/
    # Referer; dashboard có tab "Dán key" gửi X-Admin-Key header
    print(f"  dashboard: http://<ip>:{PORT}/  (mở → tab 'Dán key', "
          f"nhập admin_key)")
    print(f"  data: {DATA}")
    BoundedServer((BIND, PORT), Handler).serve_forever()
