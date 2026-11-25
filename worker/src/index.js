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

// ---------- D1 helpers ----------
const one = (env, s, ...a) => env.DB.prepare(s).bind(...a).first();
const allq = async (env, s, ...a) =>
  (await env.DB.prepare(s).bind(...a).all()).results || [];
const run = (env, s, ...a) => env.DB.prepare(s).bind(...a).run();

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

// ---------- auth helpers ----------
function adminOrg(req, orgs, vendorKey) {
  const k = req.headers.get("X-Admin-Key") || "";
  if (vendorKey && eq(k, vendorKey)) return "*";
  for (const [n, o] of Object.entries(orgs))
    if (o.admin_key && eq(k, o.admin_key)) return n;
  return null;
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
  const mid = String(b.machine_id || "");
  if (!mid) return j({ err: "thiếu machine_id" }, 400);
  const now = nowSec();
  const row = await one(env,
    "SELECT * FROM machines WHERE machine_id=?", mid);
  // mid đã đăng ký org khác — secret org này không được đụng vào
  if (row && row.org !== pairOrg) return j({ status: "pending" });
  if (row && row.approved && !row.revoked)
    return j({ status: "approved", machine_key: row.machine_key });
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
  const org = adminOrg(req, orgs, env.VENDOR_KEY || "");
  if (org === null)
    return j({ err: "thiếu hoặc sai X-Admin-Key" }, 401);
  if (path === "/api/fleet") {
    const rows = org === "*"
      ? await allq(env, "SELECT * FROM machines WHERE approved=1 "
                        + "AND revoked=0")
      : await allq(env, "SELECT * FROM machines WHERE approved=1 "
                        + "AND revoked=0 AND org=?", org);
    const day = dayVN();
    const out = [];
    for (const r of rows) {
      const snap = JSON.parse(r.snapshot_json || "{}");
      const u = await one(env,
        "SELECT counts FROM usage WHERE machine_id=? AND day=?",
        r.machine_id, day);
      out.push({
        machine_id: r.machine_id, org: r.org, hostname: r.hostname,
        os: r.os, learner: r.learner, brain: r.brain,
        version: r.version, ext: r.ext_version,
        pack_version: r.pack_version, last_seen: r.last_seen,
        license_status: r.license_status,
        bot: (snap.bots || {}).active,
        today: u ? JSON.parse(u.counts) : {},
      });
    }
    return j({ machines: out, ts: nowSec() });
  }
  if (path === "/api/pending") {
    const rows = org === "*"
      ? await allq(env, "SELECT machine_id,org,hostname,os,first_seen,"
                        + "last_seen,license_status FROM machines "
                        + "WHERE approved=0 AND revoked=0")
      : await allq(env, "SELECT machine_id,org,hostname,os,first_seen,"
                        + "last_seen,license_status FROM machines "
                        + "WHERE approved=0 AND revoked=0 AND org=?",
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
    return j({ pings: rows.map(r =>
      ({ org: r.org, ts: r.ts, data: JSON.parse(r.payload) })) });
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
  return j({ err: "not found" }, 404);
}

// ---------- POST ----------
async function doPost(req, env, path, prefix, orgs) {
  if (path === "/api/pair") {
    // org suy từ beacon_secret — máy không tự chọn org
    const key = req.headers.get("X-Beacon-Key") || "";
    let pairOrg = null;
    for (const [n, o] of Object.entries(orgs))
      if (eq(key, o.beacon_secret)) pairOrg = n;
    return pair(req, env, orgs, pairOrg);
  }
  if (path === "/api/beacon") return beacon(req, env, orgs, prefix);
  if (path === "/api/pair-approve" || path === "/api/pair-revoke") {
    const org = adminOrg(req, orgs, env.VENDOR_KEY || "");
    if (org === null)
      return j({ err: "thiếu hoặc sai X-Admin-Key" }, 401);
    const [b, err] = await body(req);
    if (err) return err;
    const mid = String(b.machine_id || "");
    const r = await one(env,
      "SELECT org FROM machines WHERE machine_id=?", mid);
    if (!r || (org !== "*" && r.org !== org))
      return j({ err: "not found" }, 404);
    if (path.endsWith("approve")) {
      const mk = randHex(24);
      await run(env, "UPDATE machines SET approved=1, revoked=0, "
                     + "machine_key=? WHERE machine_id=?", mk, mid);
      return j({ ok: true, machine_key: mk });
    }
    // GIỮ machine_key — máy bị revoke vẫn tra ra row → beacon thấy
    // status:"revoked" rõ, xoá key local và re-pair pending
    await run(env, "UPDATE machines SET approved=0, revoked=1 "
                   + "WHERE machine_id=?", mid);
    return j({ ok: true });
  }
  if (path === "/api/org-ping") {
    if (!(env.VENDOR_KEY &&
          eq(req.headers.get("X-Admin-Key") || "", env.VENDOR_KEY)))
      return j({ err: "thiếu hoặc sai key" }, 401);
    const [b, err] = await body(req);
    if (err) return err;
    await run(env,
      "INSERT INTO org_pings(org,ts,payload) VALUES(?,?,?)",
      String(b.org || "?").slice(0, 80), nowSec(),
      JSON.stringify(b).slice(0, 8000));
    return j({ ok: true });
  }
  // upload 2 bước như py: zip raw trước, manifest sau
  if (path.startsWith("/api/releases/")) {
    const org = adminOrg(req, orgs, env.VENDOR_KEY || "");
    if (org === null)
      return j({ err: "thiếu hoặc sai X-Admin-Key" }, 401);
    const fn = basename(path.slice("/api/releases/".length));
    if (!fn || fn === "." || fn === "..")
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
    const org = adminOrg(req, orgs, env.VENDOR_KEY || "");
    if (org === null)
      return j({ err: "thiếu hoặc sai X-Admin-Key" }, 401);
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
    return j({ ok: true });
  }
  if (path === "/api/packs") {
    const org = adminOrg(req, orgs, env.VENDOR_KEY || "");
    if (org === null)
      return j({ err: "thiếu hoặc sai X-Admin-Key" }, 401);
    const [b, err] = await body(req);
    if (err) return err;
    const porg = String(b.org || "");
    if (!porg || typeof b.pack_version !== "number" ||
        !Number.isInteger(b.pack_version))
      return j({ err: "pack cần org + pack_version int" }, 400);
    if (org !== "*" && porg !== org)
      return j({ err: "admin_key chỉ đẩy pack org mình" }, 403);
    const raw = JSON.stringify(b);
    await env.BUCKET.put(`packs/${porg}/${b.pack_version}.json`, raw);
    await env.BUCKET.put(`packs/latest-${porg}.json`, JSON.stringify({
      version: b.pack_version,
      sha256: hex(await crypto.subtle.digest("SHA-256", enc.encode(raw))),
    }));
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
  const orgs = JSON.parse(env.ORGS_JSON || "{}");
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

export default {
  async fetch(req, env, ctx) {
    let orgs = {};
    try { orgs = JSON.parse(env.ORGS_JSON || "{}"); } catch {}
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
    if (post) return doPost(req, env, path, prefix, orgs);
    return j({ err: "not found" }, 404);
  },
  async scheduled(event, env, ctx) {
    if (event.cron === "7 */6 * * *")
      ctx.waitUntil(mirror(env).catch(() => {}));
    if (event.cron === "30 2 * * *")
      ctx.waitUntil(telemetry(env).catch(() => {}));
  },
};
