// Счётчик голосов для опросов на сайте LEONIDA-CHEATS.
// GET  /results           -> { "best-gta": [1, 0, 2, ...], "site": [...] }
// POST /vote {poll, option} -> { ok, already, results: [...] }
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

    return json(req, { error: "not found" }, 404);
  },
};
