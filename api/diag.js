// 널스잡 접속 진단 — 어느 단계(DNS/TCP/TLS/HTTP)에서 막히는지 확인
import net from "node:net";
import tls from "node:tls";
import dns from "node:dns/promises";
export const config = { regions: ["icn1"], maxDuration: 30 };

function tcp(host, port, ms = 8000) {
  return new Promise((res) => {
    const t0 = Date.now(); const s = net.connect({ host, port });
    const done = (r) => { try { s.destroy(); } catch {} res({ ...r, ms: Date.now() - t0 }); };
    s.setTimeout(ms, () => done({ ok: false, err: "timeout" }));
    s.on("connect", () => done({ ok: true }));
    s.on("error", (e) => done({ ok: false, err: e.code || e.message }));
  });
}
function tlsc(host, ms = 8000) {
  return new Promise((res) => {
    const t0 = Date.now(); const s = tls.connect({ host, port: 443, servername: host, rejectUnauthorized: false });
    const done = (r) => { try { s.destroy(); } catch {} res({ ...r, ms: Date.now() - t0 }); };
    s.setTimeout(ms, () => done({ ok: false, err: "timeout" }));
    s.on("secureConnect", () => done({ ok: true, proto: s.getProtocol(), authorized: s.authorized, authErr: s.authorizationError && String(s.authorizationError) }));
    s.on("error", (e) => done({ ok: false, err: e.code || e.message }));
  });
}
export default async function handler(req, res) {
  if ((req.query.key || "") !== process.env.PROXY_KEY) return res.status(403).send("forbidden");
  const out = { region: process.env.VERCEL_REGION };
  for (const host of ["www.nursejob.co.kr", "m.nursejob.co.kr", "nursejob.co.kr"]) {
    const o = {};
    try { o.dns = (await dns.lookup(host, { all: true })).map(a => a.address); } catch (e) { o.dns = "ERR " + (e.code || e.message); }
    o.tcp443 = await tcp(host, 443); o.tcp80 = await tcp(host, 80); o.tls = await tlsc(host);
    out[host] = o;
  }
  try { const r = await fetch("https://www.saramin.co.kr/", { signal: AbortSignal.timeout(8000) }); out.saramin = r.status; } catch (e) { out.saramin = "ERR " + e.message; }
  try { const r = await fetch("https://api.ipify.org?format=json", { signal: AbortSignal.timeout(8000) }); out.egress_ip = (await r.json()).ip; } catch (e) { out.egress_ip = "ERR"; }
  res.status(200).json(out);
}
