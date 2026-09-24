import https from "node:https";
import net from "node:net";
export const config = { regions: ["icn1"], maxDuration: 30 };
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36";
function tcp(ms = 4000) { return new Promise((res) => { const t0 = Date.now(); const s = net.connect({ host: "www.nursejob.co.kr", port: 443 }); const d = (r) => { try { s.destroy(); } catch {} res({ ...r, ms: Date.now() - t0 }); }; s.setTimeout(ms, () => d({ ok: false, err: "timeout" })); s.on("connect", () => d({ ok: true })); s.on("error", (e) => d({ ok: false, err: e.code })); }); }
function get(ms = 8000) { return new Promise((res) => { const t0 = Date.now(); let b = 0; const rq = https.request({ host: "www.nursejob.co.kr", port: 443, path: "/", headers: { "User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9" } }, (r) => { r.on("data", c => b += c.length); r.on("end", () => res({ ok: true, status: r.statusCode, bytes: b, ms: Date.now() - t0 })); }); rq.setTimeout(ms, () => rq.destroy(new Error("timeout"))); rq.on("error", e => res({ ok: false, err: e.code || e.message, ms: Date.now() - t0 })); rq.end(); }); }
export default async function handler(req, res) {
  if ((req.query.key || "") !== process.env.PROXY_KEY) return res.status(403).send("forbidden");
  let ip = "?"; try { ip = (await (await fetch("https://api.ipify.org?format=json", { signal: AbortSignal.timeout(5000) })).json()).ip; } catch {}
  const t = await tcp(); const g = t.ok ? await get() : null;
  res.status(200).json({ ip, tcp: t, get: g, at: new Date().toISOString() });
}
