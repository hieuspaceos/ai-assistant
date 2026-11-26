// index.js — troly-fleet worker: port của tools/collector.py sang
// Cloudflare Workers + D1 + R2, cho tier vendor-hosted
// (troly.hieuspace.com/fleet). collector.py vẫn là canonical cho
// self-host — file này giữ nguyên semantics endpoint/key/scope;
// chỗ nào môi trường buộc khác ghi chú ngay chỗ đó:
//   SQLite → D1          (env.DB)
//   DATA/releases|packs  → R2 bucket (env.BUCKET), cùng key layout
//   collector-web/*      → Workers Static Assets (env.ASSETS)
//   mirror/telemetry     → Cron Triggers (scheduled handler)
//   prefix /fleet        → suy từ request path thực tế (xem normPath)

const BODY_CAP = 1_000_000;
const REL_CAP = 200_000_000;             // upload zip tối đa (như py)
const DAY_TZ = 7 * 3600e3;               // "hôm nay" theo giờ VN (UTC+7)
const RATE_GET = 240, RATE_POST = 60;    // req/phút/IP — per isolate,
                                         // best-effort như py (_rate)

const enc = new TextEncoder();
const j = (o, code = 200) => new Response(JSON.stringify(o), {
  status: code,
  headers: { "Content-Type": "application/json; charset=utf-8",
             "Cache-Control": "no-store" } });

function hex(buf) {
  return [...new Uint8Array(buf)]
    .map(b => b.toString(16).padStart(2, "0")).join("");
}
function randHex(n) {
  const a = new Uint8Array(n);
  crypto.getRandomValues(a);
  return hex(a.buffer);
}
// hmac.compare_digest: check độ dài trước (lộ length — y hệt Python),
// rồi XOR từng byte
function eq(a, b) {
  const x = enc.encode(a || ""), y = enc.encode(b || "");
  if (x.length !== y.length) return false;
  let d = 0;
  for (let i = 0; i < x.length; i++) d |= x[i] ^ y[i];
  return d === 0;
}
// "{}".format(v) của Python: None→"None", True→"True" — payload license
// do make-license.py ký theo semantics này, JS phải bắt chước đúng
function py(v) {
  return v == null ? "None" : typeof v === "boolean"
    ? (v ? "True" : "False") : String(v);
}
const basename = s => String(s).split("/").pop();
const dayVN = () =>
  new Date(Date.now() + DAY_TZ).toISOString().slice(0, 10);
const nowSec = () => Math.floor(Date.now() / 1000);

// ---------- rate limit (per isolate — Cloudflare edge chặn DDoS lớn,
// đây chỉ chống một máy hỏng/spam kéo worker, giống _rate trong py) ---
const _rate = new Map();
function rateOk(ip, post) {
  const lim = post ? RATE_POST : RATE_GET, now = Date.now() / 1000;
  let e = _rate.get(ip);
  if (!e || now - e.w > 60) e = { w: now, n: 0 };
  e.n++;
  _rate.set(ip, e);
  if (_rate.size > 10000)
    for (const [k, v] of _rate) if (now - v.w > 300) _rate.delete(k);
  return e.n <= lim;
}
// login riêng: 10 lần/phút/IP — chống brute-force mật khẩu
const _lr = new Map();
function loginOk(ip) {
  const now = Date.now() / 1000;
  let e = _lr.get(ip);
  if (!e || now - e.w > 60) e = { w: now, n: 0 };
  e.n++;
  _lr.set(ip, e);
  return e.n <= 10;
}

// ---------- D1 helpers ----------
const one = (env, s, ...a) => env.DB.prepare(s).bind(...a).first();
const allq = async (env, s, ...a) =>
  (await env.DB.prepare(s).bind(...a).all()).results || [];
const run = (env, s, ...a) => env.DB.prepare(s).bind(...a).run();

// MIGRATIONS[2] của py — repair flow. DB tạo từ schema.sql mới đã có
// cột; DB cũ thì ALTER lazy một lần/isolate (PRAGMA rẻ, fail thì để
// request kế thử lại — query đụng cột thiếu vẫn throw như cũ)
let _v2done = false;
async function ensureV2(env) {
  if (_v2done) return;
  try {
    const cols = await allq(env, "PRAGMA table_info(machines)");
    const names = new Set(cols.map(c => c.name));
    // từng cột một cờ — ALTER 1 thành công rồi ALTER 2 lỗi (hoặc
    // migrate tay thiếu) mà gate chung thì cột thiếu không bao giờ
    // được thêm → query đụng pending_key throw mãi
    if (!names.has("repair"))
      await run(env, "ALTER TABLE machines ADD COLUMN repair "
                     + "INTEGER DEFAULT 0");
    if (!names.has("pending_key"))
      await run(env, "ALTER TABLE machines ADD COLUMN pending_key TEXT");
    // MIGRATIONS[3] của py — admin gán tên nhân viên vào máy
    if (!names.has("label"))
      await run(env, "ALTER TABLE machines ADD COLUMN label TEXT");
    _v2done = true;
  } catch {}
}

// ---------- license (HMAC-SHA256 — đúng format payload của
// make-license.py: "org|seats|expiry|issued") ----------
async function hmacHex(sec, payload) {
  const k = await crypto.subtle.importKey(
    "raw", enc.encode(sec), { name: "HMAC", hash: "SHA-256" },
    false, ["sign"]);
  return hex(await crypto.subtle.sign("HMAC", k, enc.encode(payload)));
}
async function licenseStatus(lic, orgName, orgs) {
  if (typeof lic !== "object" || lic === null) return "missing";
  const sec = (orgs[lic.org || orgName] || {}).license_secret;
  if (!sec) return "invalid";
  const payload =
    `${py(lic.org)}|${py(lic.seats)}|${py(lic.expiry)}|${py(lic.issued)}`;
  if (!eq(await hmacHex(sec, payload), lic.sig || "")) return "invalid";
  const exp = String(lic.expiry || "");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(exp) || isNaN(Date.parse(exp)))
    return "invalid";
  const today = dayVN();
  if (exp < today) return "expired";
  if (Math.round((Date.parse(exp) - Date.parse(today)) / 864e5) <= 30)
    return "expiring";
  return "ok";
}

// ---------- orgs: env ORGS_JSON là fallback/seed, D1 là nguồn chính
// (org tạo trong UI master nằm trong bảng orgs — D1 ghi đè env cùng tên)
// Cache 30s/isolate — SELECT orgs mỗi request là N+1 vô ích; write
// path (org-create/rotate) bust ngay nên secret mới có hiệu lực tức thì.
// NHƯNG bust chỉ dọn isolate hiện tại: secret đã rotate còn sống ≤30s
// trên isolate khác → đường SO SECRET (pair, admin_key) phải gọi
// fresh=true đọc thẳng D1; cache chỉ cho consumer không-nhạy
// (licenseStatus, danh sách org dashboard).
let _orgs = { ts: 0, val: {} };
async function loadOrgs(env, fresh = false) {
  if (!fresh && Date.now() - _orgs.ts < 30e3) return _orgs.val;
  const out = {};
  try { Object.assign(out, JSON.parse(env.ORGS_JSON || "{}")); } catch {}
  try {
    for (const r of await allq(env, "SELECT * FROM orgs"))
      out[r.name] = { beacon_secret: r.beacon_secret,
                      license_secret: r.license_secret,
                      admin_key: r.admin_key || undefined };
  } catch {}                          // bảng chưa migrate → chỉ env
  _orgs = { ts: Date.now(), val: out };
  return out;
}
const bustOrgs = () => { _orgs.ts = 0; };

// ---------- admin accounts (PBKDF2-HMAC-SHA256) + sessions ----------
async function passHash(pass, salt) {
  const key = await crypto.subtle.importKey(
    "raw", enc.encode(pass), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", salt: enc.encode(salt), iterations: 100000,
      hash: "SHA-256" }, key, 256);
  return hex(bits);
}
const SESSION_TTL = 7 * 86400;         // 7 ngày — đóng tab vẫn giữ,
                                       // logout/expire mới mất

// trả {role:'master'|'admin', org:'*'|<org>, name, id?} | null
// ưu tiên Bearer session (tài khoản thật), fallback X-Admin-Key cũ
// (vendor_key → master "*"; admin_key của org → admin org đó)
async function authAdmin(req, env, orgs) {
  const auth = req.headers.get("Authorization") || "";
  if (auth.startsWith("Bearer ")) {
    const row = await one(env,
      `SELECT a.id,a.username,a.role,a.org FROM sessions s
       JOIN admins a ON a.id=s.admin_id
       WHERE s.token=? AND s.expires_ts>? AND a.disabled=0`,
      auth.slice(7), nowSec());
    if (row) return { role: row.role, name: row.username, id: row.id,
                      via: "session",
                      org: row.role === "master" ? "*" : row.org };
  }
  const k = req.headers.get("X-Admin-Key") || "";
  if (env.VENDOR_KEY && eq(k, env.VENDOR_KEY))
    return { role: "master", org: "*", name: "vendor", via: "key" };
  // fresh: admin_key vừa rotate phải đúng/sai NGAY — cache 30s trên
  // isolate khác chưa bust được (key cũ sống thêm 30s)
  for (const [n, o] of Object.entries(await loadOrgs(env, true)))
    if (o.admin_key && eq(k, o.admin_key))
      return { role: "admin", org: n, name: "key:" + n, via: "key" };
  return null;
}

// audit trail — ai vừa làm gì trên org nào (dashboard master xem lại)
function audit(env, actor, action, org, target, detail) {
  return run(env,
    "INSERT INTO audit(actor,action,org,target,detail,ts) "
    + "VALUES(?,?,?,?,?,?)",
    actor.name || "?", action, org || "", target || "",
    String(detail || "").slice(0, 500), nowSec()).catch(() => {});
}
const machineRow = (env, req) => one(env,
  "SELECT * FROM machines WHERE machine_key=? "
  + "AND approved=1 AND revoked=0",
  req.headers.get("X-Beacon-Key") || "");

async function body(req) {
  const t = await req.text();
  if (t.length > BODY_CAP) return [null, j({ err: "body quá lớn" }, 413)];
  try { return [t ? JSON.parse(t) : {}, null]; }
  catch { return [null, j({ err: "json không hợp lệ" }, 400)]; }
}

// _path() của py: bỏ prefix /fleet; TRẢ KÈM prefix để hint URL trả về
// đúng mount — máy urljoin với absolute-path nên URL phải chứa prefix
// ("/fleet/releases/x"), không thì request bay sang Pages 404
function normPath(url) {
  const p = url.pathname;
  if (p === "/fleet") return ["/", "/fleet"];
  if (p.startsWith("/fleet/")) return [p.slice(6), "/fleet"];
  return [p, ""];
}

// ---------- version compare (_ver_tuple) ----------
function verTuple(s) {
  const t = String(s).split(".").map(x => {
    const n = parseInt(x);
    return isNaN(n) ? undefined : n;
  });
  return t.includes(undefined) ? [] : t;
}
function verGt(a, b) {                    // tuple > tuple của Python
  const n = Math.max(a.length, b.length);
  for (let i = 0; i < n; i++) {
    const x = a[i] || 0, y = b[i] || 0;
    if (x !== y) return x > y;
  }
  return false;
}

// ---------- hints (R2 thay filesystem; url KÈM prefix mount) ----------
async function releaseHint(env, b, prefix) {
  const r = await env.BUCKET.get("releases/latest.json");
  if (!r) return null;
  let man;
  try { man = await r.json(); } catch { return null; }
  if (verGt(verTuple(man.version), verTuple(b.version)))
    return { ...man,
             url: `${prefix}/releases/${basename(man.url || "")}` };
  return null;
}
async function packHint(env, b, org, prefix) {
  // org từ ROW đã xác thực (machine_key) — fix vòng 3 audit của py:
  // không bao giờ tin body.get("org") do máy tự khai
  const r = await env.BUCKET.get(`packs/latest-${org}.json`);
  if (!r) return null;
  let p;
  try { p = await r.json(); } catch { return null; }
  const pv = parseInt(p.version) || 0, bv = parseInt(b.pack_version) || 0;
  if (pv > bv)
    return { version: p.version,
             url: `${prefix}/packs/${org}/${p.version}.json`,
             sha256: p.sha256 };
  return null;
}

// ---------- machine endpoints ----------
async function pair(req, env, orgs, pairOrg) {
  const org = orgs[pairOrg];
  if (!org) return j({ err: "org không tồn tại" }, 401);
  const [b, err] = await body(req);
  if (err) return err;
  const mid = String(b.machine_id || "").slice(0, 200);
  if (!mid) return j({ err: "thiếu machine_id" }, 400);
  const now = nowSec();
  await ensureV2(env);               // repair/pending_key (MIGRATIONS[2])
  const row = await one(env,
    "SELECT * FROM machines WHERE machine_id=?", mid);
  // mid đã đăng ký org khác — secret org này không được đụng vào
  if (row && row.org !== pairOrg) return j({ status: "pending" });
  if (row && row.approved && !row.revoked) {
    if (row.pending_key) {
      // admin đã duyệt (cấp mới hoặc cấp lại) — key LUÔN đi qua
      // pending_key, máy chỉ nhận qua pair: phát key và set machine_key
      // tại đây (rotate nếu key cũ tồn tại — kẻ cầm key cũ mất quyền)
      const mk = row.pending_key;
      await run(env, "UPDATE machines SET machine_key=?, repair=0, "
        + "pending_key=NULL WHERE machine_id=?", mk, mid);
      return j({ status: "approved", machine_key: mk });
    }
    // re-pair máy approved ĐÃ CÓ key (mất machine.key) → KHÔNG trả key
    // chỉ vì biết beacon_secret — shared toàn org (N1). Flag repair →
    // /api/pending hiện cho admin duyệt cấp lại
    if (!row.repair)
      await run(env, "UPDATE machines SET repair=1 "
        + "WHERE machine_id=?", mid);
    return j({ status: "pending" });
  }
  if (row && row.revoked) return j({ status: "revoked" });
  await run(env,
    `INSERT INTO machines(machine_id,org,hostname,os,approved,
       first_seen,last_seen,license_json,license_status)
     VALUES(?,?,?,?,0,?,?,?,?)
     ON CONFLICT(machine_id) DO UPDATE SET
       hostname=excluded.hostname, os=excluded.os,
       last_seen=excluded.last_seen, license_json=excluded.license_json,
       license_status=excluded.license_status`,
    mid, pairOrg, String(b.hostname || "").slice(0, 200),
    String(b.os || "").slice(0, 100), now, now,
    JSON.stringify(b.license ?? null),
    await licenseStatus(b.license, pairOrg, orgs));
  return j({ status: "pending" });
}

async function beacon(req, env, orgs, prefix) {
  const key = req.headers.get("X-Beacon-Key") || "";
  const row = await one(env,
    "SELECT * FROM machines WHERE machine_key=?", key);
  if (!row) return j({ err: "máy chưa pair hoặc key sai" }, 403);
  if (row.revoked || !row.approved) return j({ status: "revoked" }, 403);
  const [b, err] = await body(req);
  if (err) return err;
  const now = nowSec();
  const snap = b.snapshot || {}, cfg = snap.config || {},
        brain = (snap.brain || {}).current || {},
        health = snap.health || {};
  await run(env,
    `UPDATE machines SET hostname=?, os=?, last_seen=?, learner=?,
       brain=?, version=?, ext_version=?, pack_version=?, snapshot_json=?,
       license_json=?, license_status=?, ev_stats=? WHERE machine_id=?`,
    String(b.hostname || row.hostname).slice(0, 200),
    String(b.os || row.os).slice(0, 100), now,
    String(cfg.learner_name || "").slice(0, 100),
    String(brain.label || brain.id || "").slice(0, 100),
    String(b.version || health.version || "").slice(0, 40),
    String(health.extVersion || "").slice(0, 40),
    String(b.pack_version || "").slice(0, 40),
    JSON.stringify(snap), JSON.stringify(b.license ?? null),
    await licenseStatus(b.license, row.org, orgs),
    JSON.stringify(b.counts || {}), row.machine_id);
  const counts = b.counts || {};
  if (Object.keys(counts).length) {
    const day = dayVN();
    const old = await one(env,
      "SELECT counts FROM usage WHERE machine_id=? AND day=?",
      row.machine_id, day);
    const merged = old ? JSON.parse(old.counts) : {};
    for (const [k, v] of Object.entries(counts)) {
      const n = parseInt(v);
      if (!isNaN(n)) merged[k] = (merged[k] || 0) + n;
    }
    await run(env,
      `INSERT INTO usage(machine_id,day,counts) VALUES(?,?,?)
       ON CONFLICT(machine_id,day) DO UPDATE SET counts=excluded.counts`,
      row.machine_id, day, JSON.stringify(merged));
  }
  const resp = { ok: true };
  const rel = await releaseHint(env, b, prefix);
  if (rel) resp.update = rel;
  const pack = await packHint(env, b, row.org, prefix);
  if (pack) resp.pack = pack;
  return j(resp);
}

// ---------- GET ----------
async function doGet(req, env, path, prefix, orgs, url) {
  // download phía máy (X-Beacon-Key = machine_key) — manifest/zip/pack
  // không public, chỉ máy đã pair mới tải được
  if (path === "/api/releases/latest" ||
      path.startsWith("/releases/") || path.startsWith("/packs/")) {
    const row = await machineRow(env, req);
    if (!row) return j({ err: "máy chưa pair" }, 403);
    if (path === "/api/releases/latest") {
      const r = await env.BUCKET.get("releases/latest.json");
      if (!r) return j({ err: "chưa có release" }, 404);
      const man = await r.json();
      man.url = `${prefix}/releases/${basename(man.url || "")}`;
      return j(man);
    }
    if (path.startsWith("/packs/") &&
        !path.startsWith(`/packs/${row.org}/`))
      return j({ err: "pack org khác" }, 403);
    if (path.includes("..")) return j({ err: "not found" }, 404);
    const obj = await env.BUCKET.get(path.slice(1));
    if (!obj) return j({ err: "not found" }, 404);
    return new Response(obj.body, { headers: {
      "Content-Type": "application/octet-stream",
      "Cache-Control": "no-store" } });
  }
  if (!path.startsWith("/api/")) {
    // dashboard tĩnh — data endpoints vẫn đòi X-Admin-Key; path đã bỏ
    // prefix /fleet nên assets (collector-web/) map trực tiếp
    const u = new URL(url);
    u.pathname = path;
    return env.ASSETS.fetch(new Request(u.toString()));
  }
  if (path === "/api/whoami") {
    const a = await authAdmin(req, env, orgs);
    if (!a) return j({ err: "chưa đăng nhập" }, 401);
    return j({ role: a.role, org: a.org, name: a.name, via: a.via });
  }
  const actor = await authAdmin(req, env, orgs);
  if (!actor)
    return j({ err: "thiếu hoặc sai credential" }, 401);
  const org = actor.org;
  if (path === "/api/orgs") {
    // master xem danh sách cty: D1 orgs + org chỉ còn trong env (chưa migrate)
    if (org !== "*") return j({ err: "chỉ master" }, 403);
    const rows = await allq(env,
      `SELECT o.name,o.note,o.created_ts,
         (SELECT COUNT(*) FROM machines m WHERE m.org=o.name
           AND approved=1 AND revoked=0) AS machines,
         (SELECT MAX(m2.license_status) FROM machines m2
           WHERE m2.org=o.name) AS license_worst
       FROM orgs o ORDER BY o.name`);
    const seen = new Set(rows.map(r => r.name));
    for (const n of Object.keys(orgs)) {
      if (seen.has(n)) continue;
      const c = await one(env,
        "SELECT COUNT(*) AS c FROM machines WHERE org=? "
        + "AND approved=1 AND revoked=0", n);
      rows.push({ name: n, machines: c ? c.c : 0, env_only: 1 });
    }
    return j({ orgs: rows });
  }
  if (path === "/api/admins") {
    if (org !== "*") return j({ err: "chỉ master" }, 403);
    const rows = await allq(env,
      "SELECT id,username,role,org,disabled,created_ts FROM admins "
      + "ORDER BY username");
    return j({ admins: rows });
  }
  if (path === "/api/audit") {
    const rows = org === "*"
      ? await allq(env, "SELECT actor,action,org,target,detail,ts FROM audit "
                      + "ORDER BY ts DESC LIMIT 200")
      : await allq(env, "SELECT actor,action,org,target,detail,ts FROM audit "
                      + "WHERE org=? ORDER BY ts DESC LIMIT 200", org);
    return j({ audit: rows });
  }
  if (path === "/api/fleet") {
    const rows = org === "*"
      ? await allq(env, "SELECT * FROM machines WHERE approved=1 "
                        + "AND revoked=0")
      : await allq(env, "SELECT * FROM machines WHERE approved=1 "
                        + "AND revoked=0 AND org=?", org);
    const day = dayVN();
    // usage của CẢ fleet hôm nay trong 1 query — trước là N+1 (một
    // SELECT mỗi máy → fleet 200 máy = 200 roundtrip D1)
    const urows = await allq(env,
      "SELECT machine_id,counts FROM usage WHERE day=?", day);
    const usage = {};
    for (const u of urows) {
      try { usage[u.machine_id] = JSON.parse(u.counts); } catch {}
    }
    const out = [];
    for (const r of rows) {
      let snap = {};
      try { snap = JSON.parse(r.snapshot_json || "{}"); } catch {}
      // conns gọn [{n,s}] — dashboard đếm kết nối/app cho cả fleet
      // mà không phải tải full snapshot từng máy
      const apps = ((snap.conns || {}).apps) || [];
      out.push({
        machine_id: r.machine_id, org: r.org, hostname: r.hostname,
        label: r.label || "",
        os: r.os, learner: r.learner, brain: r.brain,
        version: r.version, ext: r.ext_version,
        pack_version: r.pack_version, last_seen: r.last_seen,
        license_status: r.license_status,
        bot: (snap.bots || {}).active,
        conns: apps.map(a => ({ n: a.name || a.id, s: a.status })),
        today: usage[r.machine_id] || {},
      });
    }
    return j({ machines: out, ts: nowSec() });
  }
  if (path === "/api/pending") {
    // repair=1 = máy approved xin cấp lại key (re-pair sau khi mất
    // machine.key) — admin phải thấy để duyệt, y hệt py
    await ensureV2(env);
    const rows = org === "*"
      ? await allq(env, "SELECT machine_id,org,hostname,os,first_seen,"
                        + "last_seen,license_status,repair FROM machines "
                        + "WHERE (approved=0 OR repair=1) AND revoked=0")
      : await allq(env, "SELECT machine_id,org,hostname,os,first_seen,"
                        + "last_seen,license_status,repair FROM machines "
                        + "WHERE (approved=0 OR repair=1) AND revoked=0 "
                        + "AND org=?",
                   org);
    return j({ pending: rows });
  }
  if (path.startsWith("/api/fleet/")) {
    const mid = path.slice("/api/fleet/".length);
    const r = await one(env,
      "SELECT * FROM machines WHERE machine_id=?", mid);
    if (!r || (org !== "*" && r.org !== org))
      return j({ err: "not found" }, 404);
    const usage = await allq(env,
      "SELECT day,counts FROM usage WHERE machine_id=? "
      + "ORDER BY day DESC LIMIT 14", mid);
    return j({
      machine_id: mid, org: r.org, hostname: r.hostname, os: r.os,
      label: r.label || "",
      approved: !!r.approved, revoked: !!r.revoked,
      first_seen: r.first_seen, last_seen: r.last_seen,
      license: JSON.parse(r.license_json || "null"),
      license_status: r.license_status,
      ev_stats: JSON.parse(r.ev_stats || "{}"),
      snapshot: JSON.parse(r.snapshot_json || "{}"),
      usage: usage.map(u => ({ day: u.day, counts: JSON.parse(u.counts) })),
    });
  }
  if (path === "/api/license") {
    const rows = org === "*"
      ? await allq(env, "SELECT machine_id,org,last_seen,license_json,"
                        + "license_status FROM machines WHERE approved=1 "
                        + "AND revoked=0")
      : await allq(env, "SELECT machine_id,org,last_seen,license_json,"
                        + "license_status FROM machines WHERE approved=1 "
                        + "AND revoked=0 AND org=?", org);
    let active30 = 0, seats = null, expiry = null, worst = "ok";
    const rank = { ok: 0, expiring: 1, expired: 2, invalid: 3,
                   missing: 4 };
    const cutoff = nowSec() - 30 * 86400;
    for (const r of rows) {
      if (r.last_seen && r.last_seen > cutoff) active30++;
      // seats/expiry chỉ tin license SIG HỢP LỆ
      let lic = null;
      try { lic = JSON.parse(r.license_json || "null"); } catch {}
      if (lic && typeof lic === "object" &&
          ["ok", "expiring", "expired"].includes(r.license_status)) {
        if (seats === null) seats = lic.seats;
        expiry = expiry || lic.expiry;
      }
      if ((rank[r.license_status] ?? 0) > rank[worst])
        worst = r.license_status;
    }
    return j({ org, seats, active30, expiry,
               status: seats && active30 > seats ? "exceeded" : worst });
  }
  if (path === "/api/org-pings") {
    if (org !== "*") return j({ err: "chỉ vendor key" }, 403);
    const rows = await allq(env,
      "SELECT org,ts,payload FROM org_pings ORDER BY ts DESC LIMIT 500");
    return j({ pings: rows.map(r => {
      // payload ghi bởi bản cũ có thể bị cắt giữa JSON → parse fail
      // từng row, đừng để một row rác làm 500 cả dashboard
      let data = null;
      try { data = JSON.parse(r.payload); }
      catch { data = { _corrupt: true }; }
      return { org: r.org, ts: r.ts, data };
    }) });
  }
  if (path === "/api/packs") {
    // latest-<org>.json của org mình — admin xem pack đang phát
    const l = await env.BUCKET.list({ prefix: "packs/latest-" });
    const latest = {};
    for (const o of l.objects) {
      const oname = o.key.slice("packs/latest-".length, -5);
      if (org !== "*" && oname !== org) continue;
      const r = await env.BUCKET.get(o.key);
      if (r) { try { latest[oname] = await r.json(); } catch {} }
    }
    return j({ latest });
  }
  if (path === "/api/seats/export") {
    // CSV đếm ghế — chủ cty in báo cáo gia hạn (y py collector)
    await ensureV2(env);
    const rows = org === "*"
      ? await allq(env, "SELECT machine_id,org,hostname,label,learner,"
                        + "version,pack_version,last_seen,license_status "
                        + "FROM machines WHERE approved=1 AND revoked=0")
      : await allq(env, "SELECT machine_id,org,hostname,label,learner,"
                        + "version,pack_version,last_seen,license_status "
                        + "FROM machines WHERE approved=1 AND revoked=0 "
                        + "AND org=?", org);
    const esc = v => {
      const s = String(v ?? "");
      return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    };
    let csv = "org,machine_id,hostname,label,learner,version,"
            + "pack_version,last_seen,license_status\r\n";
    for (const r of rows) {
      csv += [r.org, r.machine_id, r.hostname, r.label || "",
              r.learner || "", r.version || "", r.pack_version || "",
              r.last_seen || "", r.license_status || ""]
             .map(esc).join(",") + "\r\n";
    }
    return new Response("\uFEFF" + csv, {   // BOM — Excel mở đúng dấu
      headers: {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": 'attachment; filename="seats.csv"',
      },
    });
  }
  return j({ err: "not found" }, 404);
}

// ---------- POST ----------
async function doPost(req, env, path, prefix, orgs, ip) {
  if (path === "/api/pair") {
    // org suy từ beacon_secret — máy không tự chọn org. FRESH orgs:
    // secret vừa rotate phải chết ngay — cache 30s trên isolate khác
    // vẫn nhận secret cũ. Pair hiếm (máy chỉ pair lúc thiếu key) nên
    // SELECT này không tốn kém.
    const key = req.headers.get("X-Beacon-Key") || "";
    let pairOrg = null;
    const freshOrgs = await loadOrgs(env, true);
    for (const [n, o] of Object.entries(freshOrgs))
      if (eq(key, o.beacon_secret)) pairOrg = n;
    return pair(req, env, freshOrgs, pairOrg);
  }
  if (path === "/api/beacon") return beacon(req, env, orgs, prefix);

  // --- public (chính nó là auth) ---
  if (path === "/api/login") {
    if (!loginOk(ip))
      return j({ err: "quá nhiều lần thử — chờ 1 phút" }, 429);
    const [b, err] = await body(req);
    if (err) return err;
    const u = await one(env,
      "SELECT * FROM admins WHERE username=? AND disabled=0",
      String(b.user || "").toLowerCase().trim());
    if (!u || !u.salt ||
        !eq(await passHash(String(b.pass || ""), u.salt), u.pass_hash))
      return j({ err: "sai tài khoản hoặc mật khẩu" }, 401);
    const tok = randHex(24);
    await run(env, "INSERT INTO sessions(token,admin_id,created_ts,"
                   + "expires_ts) VALUES(?,?,?,?)",
              tok, u.id, nowSec(), nowSec() + SESSION_TTL);
    await run(env, "DELETE FROM sessions WHERE expires_ts<?", nowSec());
    return j({ token: tok, role: u.role, name: u.username,
               org: u.role === "master" ? "*" : u.org });
  }
  if (path === "/api/logout") {
    const a = req.headers.get("Authorization") || "";
    if (a.startsWith("Bearer "))
      await run(env, "DELETE FROM sessions WHERE token=?", a.slice(7));
    return j({ ok: true });
  }
  if (path === "/api/bootstrap") {
    // tạo master đầu tiên — chỉ khi CHƯA có tài khoản nào và cầm
    // vendor_key; sau bootstrap endpoint này khoá vĩnh viễn
    if (!(env.VENDOR_KEY &&
          eq(req.headers.get("X-Admin-Key") || "", env.VENDOR_KEY)))
      return j({ err: "thiếu hoặc sai vendor key" }, 401);
    const n = await one(env, "SELECT COUNT(*) AS c FROM admins");
    if (n && n.c > 0) return j({ err: "đã bootstrap" }, 409);
    const [b, err] = await body(req);
    if (err) return err;
    const user = String(b.user || "").toLowerCase().trim(),
          pass = String(b.pass || "");
    if (!/^[a-z0-9_.@-]{3,64}$/.test(user) || pass.length < 8)
      return j({ err: "user 3-64 ký tự (hoặc email), pass ≥ 8" }, 400);
    const salt = randHex(16);
    await run(env, "INSERT INTO admins(username,pass_hash,salt,role,"
                   + "created_ts) VALUES(?,?,?,?,?)",
              user, await passHash(pass, salt), salt, "master", nowSec());
    await audit(env, { name: "bootstrap" }, "bootstrap", "*", user, "");
    return j({ ok: true });
  }

  // --- admin gate: session hoặc key cũ đều qua đây ---
  const actor = await authAdmin(req, env, orgs);
  if (!actor) return j({ err: "thiếu hoặc sai credential" }, 401);
  const org = actor.org;

  if (path === "/api/password") {
    if (!actor.id)
      return j({ err: "key cũ không đổi pass — tạo tài khoản" }, 403);
    const [b, err] = await body(req);
    if (err) return err;
    const u = await one(env, "SELECT * FROM admins WHERE id=?", actor.id);
    if (!eq(await passHash(String(b.old || ""), u.salt), u.pass_hash))
      return j({ err: "sai mật khẩu cũ" }, 403);
    const pass = String(b.pass || "");
    if (pass.length < 8) return j({ err: "pass ≥ 8 ký tự" }, 400);
    const salt = randHex(16);
    await run(env, "UPDATE admins SET pass_hash=?,salt=? WHERE id=?",
              await passHash(pass, salt), salt, actor.id);
    await run(env, "DELETE FROM sessions WHERE admin_id=?", actor.id);
    await audit(env, actor, "password-change", u.org || "*", u.username, "");
    return j({ ok: true, reauth: true });   // mọi session chết → login lại
  }
  if (path === "/api/orgs") {
    // master tạo cty mới: sinh luôn bộ khoá; trả beacon_secret +
    // admin_key để bàn giao cho IT (license_secret giữ server-side)
    if (actor.role !== "master") return j({ err: "chỉ master" }, 403);
    const [b, err] = await body(req);
    if (err) return err;
    const name = String(b.name || "").trim().toUpperCase();
    if (!/^[A-Z0-9_-]{2,24}$/.test(name))
      return j({ err: "tên org 2-24 ký tự [A-Z0-9_-]" }, 400);
    if (orgs[name]) return j({ err: "org đã tồn tại" }, 409);
    const bs = randHex(24), ls = randHex(24), ak = randHex(24);
    await run(env, "INSERT INTO orgs(name,beacon_secret,license_secret,"
                   + "admin_key,note,created_ts) VALUES(?,?,?,?,?,?)",
              name, bs, ls, ak, String(b.note || "").slice(0, 200),
              nowSec());
    bustOrgs();                   // org mới phải thấy ngay, không chờ TTL
    let acct = null;
    if (b.admin_user && b.admin_pass) {
      const u = String(b.admin_user).toLowerCase().trim(),
            p = String(b.admin_pass);
      if (!/^[a-z0-9_.@-]{3,64}$/.test(u) || p.length < 8)
        return j({ err: "org đã tạo; user/pass admin không hợp lệ — "
                        + "tạo lại trong tab Tài khoản", org: name }, 400);
      const salt = randHex(16);
      await run(env, "INSERT INTO admins(username,pass_hash,salt,role,"
                     + "org,created_ts) VALUES(?,?,?,?,?,?)",
                u, await passHash(p, salt), salt, "admin", name, nowSec());
      acct = { username: u };
    }
    await audit(env, actor, "org-create", name, name, b.note || "");
    return j({ ok: true, org: name, admin: acct, admin_key: ak,
               fleet: { collector: "https://troly.hieuspace.com/fleet",
                        org: name, beacon_secret: bs } });
  }
  if (path.startsWith("/api/orgs/") && path.endsWith("/rotate-secret")) {
    // master xoay beacon_secret + admin_key của org — secret lộ hoặc
    // luân chuyển định kỳ. Org chỉ còn trong env → migrate sang D1 với
    // secret mới (D1 ghi đè env trong loadOrgs). kill_machines=true
    // thì đá toàn bộ máy về pending — máy phải re-pair bằng secret
    // mới (IT phát fleet.json mới), chỉ dùng khi secret thật sự lộ
    if (actor.role !== "master") return j({ err: "chỉ master" }, 403);
    const name = decodeURIComponent(
      path.slice("/api/orgs/".length, -"/rotate-secret".length));
    const cur = orgs[name];
    if (!cur) return j({ err: "org không tồn tại" }, 404);
    const [b, err] = await body(req);
    if (err) return err;
    const bs = randHex(24), ak = randHex(24);
    const inD1 = await one(env, "SELECT name FROM orgs WHERE name=?", name);
    if (inD1)
      await run(env, "UPDATE orgs SET beacon_secret=?, admin_key=? "
                     + "WHERE name=?", bs, ak, name);
    else
      // env-only org: license_secret không đổi — copy sang, máy đang
      // chạy verify license vẫn đúng
      await run(env, "INSERT INTO orgs(name,beacon_secret,license_secret,"
                     + "admin_key,note,created_ts) VALUES(?,?,?,?,?,?)",
                name, bs, cur.license_secret || "", ak,
                "rotate từ env", nowSec());
    bustOrgs();                   // secret mới phải thấy ngay, không chờ TTL
    let killed = 0;
    if (b.kill_machines) {
      // dọn cả pending_key/repair — máy bị đá re-pair như máy mới,
      // key cũ đang chờ phát cũng phải chết theo
      await ensureV2(env);
      const r = await run(env,
        "UPDATE machines SET approved=0, revoked=0, machine_key=NULL, "
        + "repair=0, pending_key=NULL WHERE org=?", name);
      killed = (r.meta && r.meta.changes) || 0;
    }
    await audit(env, actor, "org-rotate-secret", name, name,
                killed ? `đá ${killed} máy` : "chỉ đổi secret");
    return j({ ok: true, org: name, admin_key: ak,
               machines_killed: killed,
               fleet: { collector: "https://troly.hieuspace.com/fleet",
                        org: name, beacon_secret: bs } });
  }
  if (path.startsWith("/api/orgs/") && path.endsWith("/license")) {
    // master ký license cho org — cùng payload HMAC của
    // make-license.py nên máy con verify y hệt
    if (actor.role !== "master") return j({ err: "chỉ master" }, 403);
    const name = decodeURIComponent(
      path.slice("/api/orgs/".length, -"/license".length));
    const o = orgs[name];
    if (!o || !o.license_secret)
      return j({ err: "org không tồn tại" }, 404);
    const [b, err] = await body(req);
    if (err) return err;
    const seats = parseInt(b.seats), expiry = String(b.expiry || "");
    if (!(seats > 0) || !/^\d{4}-\d{2}-\d{2}$/.test(expiry))
      return j({ err: "cần seats > 0 + expiry YYYY-MM-DD" }, 400);
    const issued = dayVN();
    const lic = { org: name, seats, expiry, issued,
      sig: await hmacHex(o.license_secret,
                         `${name}|${seats}|${expiry}|${issued}`) };
    await audit(env, actor, "license-issue", name, name,
                `${seats} ghế, hạn ${expiry}`);
    return j({ license: lic });
  }
  if (path === "/api/admins") {
    if (actor.role !== "master") return j({ err: "chỉ master" }, 403);
    const [b, err] = await body(req);
    if (err) return err;
    const u = String(b.username || "").toLowerCase().trim(),
          p = String(b.password || ""),
          role = b.role === "master" ? "master" : "admin",
          aorg = role === "admin" ? String(b.org || "") : null;
    if (!/^[a-z0-9_.@-]{3,64}$/.test(u) || p.length < 8)
      return j({ err: "username 3-64 ký tự (hoặc email), pass ≥ 8" }, 400);
    if (role === "admin" && !orgs[aorg])
      return j({ err: "org không tồn tại" }, 400);
    if (await one(env, "SELECT id FROM admins WHERE username=?", u))
      return j({ err: "username đã có" }, 409);
    const salt = randHex(16);
    const r = await run(env,
      "INSERT INTO admins(username,pass_hash,salt,role,org,created_ts)"
      + " VALUES(?,?,?,?,?,?)",
      u, await passHash(p, salt), salt, role, aorg, nowSec());
    await audit(env, actor, "admin-create", aorg || "*", u, role);
    return j({ ok: true, id: r.meta && r.meta.last_row_id });
  }
  if (path.startsWith("/api/admins/")) {
    // master đổi pass / disable-enable tài khoản — xoá session để
    // thay đổi có hiệu lực ngay (máy kia phải login lại)
    if (actor.role !== "master") return j({ err: "chỉ master" }, 403);
    const id = parseInt(path.slice("/api/admins/".length));
    const u = await one(env, "SELECT * FROM admins WHERE id=?", id);
    if (!u) return j({ err: "not found" }, 404);
    const [b, err] = await body(req);
    if (err) return err;
    if (b.disabled && u.role === "master") {
      // chặn khoá master CUỐI CÙNG — bootstrap đã tự khoá, mất hết
      // master = lockout vĩnh viễn (chỉ còn vendor_key đọc được)
      const n = await one(env,
        "SELECT COUNT(*) AS c FROM admins WHERE role='master' "
        + "AND disabled=0 AND id!=?", id);
      if (!n || n.c === 0)
        return j({ err: "không thể khoá master cuối cùng" }, 400);
    }
    if (b.disabled !== undefined)
      await run(env, "UPDATE admins SET disabled=? WHERE id=?",
                b.disabled ? 1 : 0, id);
    if (b.password) {
      if (String(b.password).length < 8)
        return j({ err: "pass ≥ 8" }, 400);
      const salt = randHex(16);
      await run(env, "UPDATE admins SET pass_hash=?,salt=? WHERE id=?",
                await passHash(String(b.password), salt), salt, id);
    }
    await run(env, "DELETE FROM sessions WHERE admin_id=?", id);
    await audit(env, actor, "admin-update", u.org || "*", u.username,
                // [^"\\]|\\. — pass chứa " thì JSON.stringify escape
                // thành \"; [^"]* thuần dừng sớm và LỘ phần đuôi pass
                JSON.stringify(b).replace(/"password":"(?:[^"\\]|\\.)*"/g,
                                          '"password":"***"'));
    return j({ ok: true });
  }
  if (path === "/api/pair-approve" || path === "/api/pair-revoke") {
    const [b, err] = await body(req);
    if (err) return err;
    const mid = String(b.machine_id || "").slice(0, 200);
    const r = await one(env,
      "SELECT org FROM machines WHERE machine_id=?", mid);
    if (!r || (org !== "*" && r.org !== org))
      return j({ err: "not found" }, 404);
    if (path.endsWith("approve")) {
      const mk = randHex(24);
      // key LUÔN vào pending_key — máy nhận qua pair lần kế (phát ở
      // pair()). Cấp mới lẫn cấp lại (repair) đều một đường: response
      // cho admin xem, beacon_secret một mình không lấy được key
      await ensureV2(env);
      await run(env, "UPDATE machines SET approved=1, revoked=0, "
                     + "pending_key=? WHERE machine_id=?", mk, mid);
      await audit(env, actor, "pair-approve", r.org, mid, "");
      return j({ ok: true, machine_key: mk });
    }
    // GIỮ machine_key — máy bị revoke vẫn tra ra row → beacon thấy
    // status:"revoked" rõ, xoá key local và re-pair pending.
    // Dọn cờ repair/pending_key cũ — revoke là reset sạch (như py).
    await ensureV2(env);
    await run(env, "UPDATE machines SET approved=0, revoked=1, "
                   + "repair=0, pending_key=NULL WHERE machine_id=?",
              mid);
    await audit(env, actor, "pair-revoke", r.org, mid, "");
    return j({ ok: true });
  }
  if (path.startsWith("/api/machine/") && path.endsWith("/label")) {
    // admin gán tên nhân viên vào máy — scope org y pair-approve
    const [b, err] = await body(req);
    if (err) return err;
    const mid = path.slice("/api/machine/".length, -"/label".length);
    const r = await one(env,
      "SELECT org FROM machines WHERE machine_id=?", mid);
    if (!r || (org !== "*" && r.org !== org))
      return j({ err: "not found" }, 404);
    const label = String(b.label || "").trim().slice(0, 80);
    await ensureV2(env);
    await run(env, "UPDATE machines SET label=? WHERE machine_id=?",
              label, mid);
    await audit(env, actor, "machine-label", r.org, mid, label);
    return j({ ok: true, label });
  }
  if (path === "/api/org-ping") {
    // collector cty tự host ping về vendor — chỉ master cấp
    if (actor.role !== "master")
      return j({ err: "chỉ master" }, 403);
    const [b, err] = await body(req);
    if (err) return err;
    // cắt thẳng .slice(0,8000) phá JSON giữa chừng → /api/org-pings
    // parse rớt. Payload quá dài thì thu về bản tóm tắt hợp lệ (y py)
    let payload = JSON.stringify(b);
    if (payload.length > 8000)
      payload = JSON.stringify(
        { org: String(b.org || "?").slice(0, 80), _truncated: true });
    await run(env,
      "INSERT INTO org_pings(org,ts,payload) VALUES(?,?,?)",
      String(b.org || "?").slice(0, 80), nowSec(), payload);
    // prune như py — rollup gần nhất, giữ 90 ngày
    await run(env, "DELETE FROM org_pings WHERE ts<?",
              nowSec() - 90 * 86400);
    return j({ ok: true });
  }
  // upload 2 bước như py: zip raw trước, manifest sau — chỉ master
  // (release ảnh hưởng mọi org, không cho cty-admin đụng)
  if (path.startsWith("/api/releases/")) {
    if (actor.role !== "master")
      return j({ err: "chỉ master đẩy release" }, 403);
    const fn = basename(path.slice("/api/releases/".length));
    // latest.json là manifest do POST /api/releases quản — upload đè
    // trực tiếp = /api/releases/latest trả rác (py chặn y). Regex bắt
    // đầu alnum cũng chặn dotfile
    if (!fn || fn === "." || fn === ".." ||
        fn.toLowerCase() === "latest.json" ||
        !/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(fn))
      return j({ err: "tên file lạ" }, 400);
    const cl = parseInt(req.headers.get("Content-Length") || "0") || 0;
    if (cl <= 0 || cl > REL_CAP) return j({ err: "kích thước zip lạ" }, 413);
    const data = await req.arrayBuffer();
    if (data.byteLength > REL_CAP) return j({ err: "zip quá lớn" }, 413);
    const sha = hex(await crypto.subtle.digest("SHA-256", data));
    await env.BUCKET.put(`releases/${fn}`, data);
    return j({ ok: true, file: fn, sha256: sha });
  }
  if (path === "/api/releases") {
    if (actor.role !== "master")
      return j({ err: "chỉ master đẩy release" }, 403);
    const [b, err] = await body(req);
    if (err) return err;
    if (!(b.version && b.url && b.sha256 && b.sig))
      return j({ err: "manifest thiếu version/url/sha256/sig" }, 400);
    const fn = basename(b.url);
    if (!(await env.BUCKET.head(`releases/${fn}`)))
      return j({ err: `chưa upload ${fn} (bước 1)` }, 400);
    await env.BUCKET.put("releases/latest.json", JSON.stringify({
      version: String(b.version), url: fn, sha256: b.sha256,
      sig: b.sig, min_ver: String(b.min_ver || "0.0.0") }, null, 2));
    await audit(env, actor, "release", "*", String(b.version), "");
    return j({ ok: true });
  }
  if (path === "/api/packs") {
    const [b, err] = await body(req);
    if (err) return err;
    const porg = String(b.org || "");
    if (!porg || typeof b.pack_version !== "number" ||
        !Number.isInteger(b.pack_version))
      return j({ err: "pack cần org + pack_version int" }, 400);
    if (org !== "*" && porg !== org)
      return j({ err: "chỉ đẩy pack cho org mình" }, 403);
    const raw = JSON.stringify(b);
    await env.BUCKET.put(`packs/${porg}/${b.pack_version}.json`, raw);
    await env.BUCKET.put(`packs/latest-${porg}.json`, JSON.stringify({
      version: b.pack_version,
      sha256: hex(await crypto.subtle.digest("SHA-256", enc.encode(raw))),
    }));
    await audit(env, actor, "pack-push", porg,
                String(b.pack_version), "");
    return j({ ok: true });
  }
  return j({ err: "not found" }, 404);
}

// ---------- cron: mirror_loop + telemetry_loop (giống py — thiếu
// config thì return êm) ----------
async function mirror(env) {
  const url = env.UPSTREAM_URL;
  if (!url) return;
  const r = await fetch(url, { redirect: "manual" });
  if (!r.ok) return;                       // kể cả 3xx — no-redirect
  const man = await r.json();
  let cur = {};
  const c = await env.BUCKET.get("releases/latest.json");
  if (c) { try { cur = await c.json(); } catch {} }
  if (!(man.version && man.url && man.sha256 && man.sig)) return;
  if (!verGt(verTuple(man.version), verTuple(cur.version))) return;
  const zurl = new URL(man.url, url).href;
  if (new URL(zurl).host !== new URL(url).host) return;
  const zr = await fetch(zurl, { redirect: "manual" });
  if (!zr.ok) return;
  const data = await zr.arrayBuffer();
  if (data.byteLength > REL_CAP) return;
  if (hex(await crypto.subtle.digest("SHA-256", data)) !== man.sha256)
    return;
  await env.BUCKET.put(`releases/${basename(new URL(zurl).pathname)}`,
                       data);
  man.url = basename(man.url);
  await env.BUCKET.put("releases/latest.json",
                       JSON.stringify(man, null, 2));
}

async function telemetry(env) {
  const url = env.TELEMETRY_URL, key = env.TELEMETRY_KEY;
  if (!url || !key) return;
  const orgs = await loadOrgs(env);
  for (const name of Object.keys(orgs)) {
    const rows = await allq(env,
      `SELECT version,license_json FROM machines WHERE org=?
       AND approved=1 AND revoked=0 AND last_seen>?`,
      name, nowSec() - 7 * 86400);
    const vdist = {}; let expiry = null;
    for (const r of rows) {
      const v = r.version || "?";
      vdist[v] = (vdist[v] || 0) + 1;
      if (!expiry) try { expiry = JSON.parse(r.license_json).expiry; }
      catch {}
    }
    await fetch(url, { method: "POST",
      headers: { "Content-Type": "application/json",
                 "X-Admin-Key": key },
      body: JSON.stringify({ org: name, machines_active: rows.length,
        version_dist: vdist, license_expiry: expiry, ts: nowSec() }) });
  }
}

// dọn bảng không giới hạn — py chỉ prune org_pings; worker có thêm
// audit/usage/sessions (bảng riêng của worker) + pending-spam của máy
// không ai duyệt. Chạy ở cron hàng ngày (telemetry slot).
async function pruneDaily(env) {
  const t = nowSec();
  await run(env, "DELETE FROM org_pings WHERE ts<?", t - 90 * 86400);
  await run(env, "DELETE FROM audit WHERE ts<?", t - 180 * 86400);
  await run(env, "DELETE FROM usage WHERE day<?",
            new Date((Date.now() + DAY_TZ) - 180 * 86400e3)
              .toISOString().slice(0, 10));
  await run(env, "DELETE FROM sessions WHERE expires_ts<?", t);
  // pending-spam: máy pair nhưng không ai approve 30 ngày — máy thật
  // sẽ tự pair lại tạo row mới; repair=1 không nằm trong nhóm này
  await run(env, "DELETE FROM machines WHERE approved=0 AND revoked=0 "
            + "AND first_seen<?", t - 30 * 86400);
}

export default {
  async fetch(req, env, ctx) {
    const orgs = await loadOrgs(env);
    const url = new URL(req.url);
    // /fleet (không slash) → 301 về /fleet/ — dashboard fetch api/...
    // tương đối, URL không có trailing slash thì resolve ra /api/* ở
    // root (Pages) thay vì /fleet/api/*
    if (url.pathname === "/fleet")
      return Response.redirect(url.origin + "/fleet/" + url.search, 301);
    const [path, prefix] = normPath(url);
    const ip = req.headers.get("CF-Connecting-IP") || "?";
    const post = req.method === "POST";
    if (!rateOk(ip, post)) return j({ err: "quá nhiều request" }, 429);
    if (req.method === "GET") return doGet(req, env, path, prefix, orgs, url);
    if (post) return doPost(req, env, path, prefix, orgs, ip);
    return j({ err: "not found" }, 404);
  },
  async scheduled(event, env, ctx) {
    if (event.cron === "7 */6 * * *")
      ctx.waitUntil(mirror(env).catch(() => {}));
    if (event.cron === "30 2 * * *") {
      ctx.waitUntil(telemetry(env).catch(() => {}));
      ctx.waitUntil(pruneDaily(env).catch(() => {}));
    }
  },
};
