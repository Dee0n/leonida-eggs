// Счётчик голосов для опросов на сайте LEONIDA-CHEATS.
// GET  /results           -> { "best-gta": [1, 0, 2, ...], "site": [...] }
// POST /vote {poll, option} -> { ok, already, results: [...] }
// POST /marks {create: true, marks} -> { code, marks }   новый код листка
// POST /marks {code, marks}         -> { code, marks }   слить отметки и вернуть общие
// Хранилище: Cloudflare D1. Один голос в опросе на браузер+IP (хэш, сами IP не храним).
import polls from "../../data/polls.json";

const ALLOWED_ORIGINS = ["https://dee0n.github.io"];

function cors(req) {
  const origin = req.headers.get("Origin") || "";
  return {
    "Access-Control-Allow-Origin": ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0],
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Vary": "Origin",
  };
}

function json(req, data, status = 200, extra = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...cors(req), ...extra },
  });
}

async function counts(env, pollId) {
  const poll = polls.find((p) => p.id === pollId);
  const arr = new Array(poll.options.length).fill(0);
  const { results } = await env.DB.prepare("SELECT opt, n FROM counts WHERE poll = ?").bind(pollId).all();
  for (const r of results) if (r.opt >= 0 && r.opt < arr.length) arr[r.opt] = r.n;
  return arr;
}

async function allCounts(env) {
  const out = {};
  for (const p of polls) out[p.id] = new Array(p.options.length).fill(0);
  const { results } = await env.DB.prepare("SELECT poll, opt, n FROM counts").all();
  for (const r of results) if (out[r.poll] && r.opt < out[r.poll].length) out[r.poll][r.opt] = r.n;
  return out;
}

async function sha256(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// отметки: { "id-записи": [0|1, время] }; при слиянии побеждает более позднее
const CODE_ABC = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
const MAX_MARKS = 600;

function cleanMarks(m) {
  const out = {};
  if (!m || typeof m !== "object") return out;
  const limit = Date.now() + 86400000;
  for (const [id, v] of Object.entries(m).slice(0, MAX_MARKS)) {
    if (!/^[a-z0-9-]{1,64}$/.test(id) || !Array.isArray(v) || !Number.isFinite(v[1])) continue;
    out[id] = [v[0] ? 1 : 0, Math.min(Math.max(0, Math.floor(v[1])), limit)];
  }
  return out;
}

function mergeMarks(a, b) {
  const out = { ...a };
  for (const [id, v] of Object.entries(b)) if (!out[id] || v[1] > out[id][1]) out[id] = v;
  return Object.fromEntries(Object.entries(out).slice(0, MAX_MARKS));
}

async function marks(req, env) {
  const text = await req.text();
  if (text.length > 40000) return json(req, { error: "too big" }, 413);
  let body;
  try { body = JSON.parse(text); } catch { return json(req, { error: "bad json" }, 400); }
  const incoming = cleanMarks(body && body.marks);

  if (body && body.create === true) {
    const ip = req.headers.get("CF-Connecting-IP") || "";
    const who = await sha256(`${env.SALT || "leonida"}|marks|${ip}`);
    const row = await env.DB.prepare("SELECT COUNT(*) AS n FROM marks WHERE creator = ? AND at > datetime('now', '-1 day')")
      .bind(who).first();
    if (row.n >= 20) return json(req, { error: "too many" }, 429);
    const code = [...crypto.getRandomValues(new Uint8Array(10))].map((b) => CODE_ABC[b % 32]).join("");
    await env.DB.prepare("INSERT INTO marks (code, data, creator, at) VALUES (?, ?, ?, datetime('now'))")
      .bind(code, JSON.stringify(incoming), who).run();
    return json(req, { code, marks: incoming });
  }

  const code = String((body && body.code) || "");
  if (!/^[A-Z0-9]{10}$/.test(code)) return json(req, { error: "bad code" }, 400);
  const row = await env.DB.prepare("SELECT data FROM marks WHERE code = ?").bind(code).first();
  if (!row) return json(req, { error: "no such code" }, 404);
  const merged = mergeMarks(JSON.parse(row.data), incoming);
  const data = JSON.stringify(merged);
  if (data !== row.data) await env.DB.prepare("UPDATE marks SET data = ? WHERE code = ?").bind(data, code).run();
  return json(req, { code, marks: merged });
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (req.method === "OPTIONS") return new Response(null, { headers: cors(req) });

    if (url.pathname === "/results" && req.method === "GET") {
      return json(req, await allCounts(env), 200, { "Cache-Control": "public, max-age=10" });
    }

    if (url.pathname === "/vote" && req.method === "POST") {
      let body;
      try { body = await req.json(); } catch { return json(req, { error: "bad json" }, 400); }
      const poll = polls.find((p) => p.id === body.poll);
      const opt = Number(body.option);
      if (!poll || !Number.isInteger(opt) || opt < 0 || opt >= poll.options.length) {
        return json(req, { error: "bad vote" }, 400);
      }
      const ip = req.headers.get("CF-Connecting-IP") || "";
      const ua = req.headers.get("User-Agent") || "";
      const h = await sha256(`${env.SALT || "leonida"}|${poll.id}|${ip}|${ua}`);
      const ins = await env.DB.prepare("INSERT OR IGNORE INTO voters (h, poll, at) VALUES (?, ?, datetime('now'))")
        .bind(h, poll.id).run();
      const already = ins.meta.changes === 0;
      if (!already) {
        await env.DB.prepare(
          "INSERT INTO counts (poll, opt, n) VALUES (?, ?, 1) ON CONFLICT(poll, opt) DO UPDATE SET n = n + 1",
        ).bind(poll.id, opt).run();
      }
      return json(req, { ok: true, already, results: await counts(env, poll.id) });
    }

    if (url.pathname === "/marks" && req.method === "POST") return marks(req, env);

    return json(req, { error: "not found" }, 404);
  },
};
