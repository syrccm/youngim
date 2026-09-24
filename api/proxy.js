// 널스잡(nursejob.co.kr) 프록시 — Vercel 서버리스 함수, 서울(icn1) 리전.
// undici fetch 는 이 서버에 간헐적으로 연결 실패하므로 node:https 로 요청하고 3회까지 재시도한다.
// 사용: GET /api/proxy?url=<nursejob 주소>   헤더 X-Proxy-Key 또는 ?key=   (환경변수 PROXY_KEY 필요)
import https from "node:https";
export const config = { regions: ["icn1"], maxDuration: 30 };

const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36";

function getOnce(t, ms = 8000) {
  return new Promise((resolve) => {
    const chunks = [];
    const rq = https.request({
      host: t.hostname, port: 443, path: t.pathname + t.search, method: "GET", servername: t.hostname,
      headers: { "User-Agent": UA, "Accept": "text/html,application/xhtml+xml", "Accept-Language": "ko-KR,ko;q=0.9", "Connection": "close" },
    }, (r) => {
      r.on("data", (c) => chunks.push(c));
      r.on("end", () => resolve({ ok: true, status: r.statusCode, type: r.headers["content-type"], body: Buffer.concat(chunks) }));
    });
    rq.setTimeout(ms, () => rq.destroy(new Error("timeout")));
    rq.on("error", (e) => resolve({ ok: false, err: e.code || e.message }));
    rq.end();
  });
}

export default async function handler(req, res) {
  const { url, key } = req.query;
  const k = req.headers["x-proxy-key"] || key;
  if (!process.env.PROXY_KEY || k !== process.env.PROXY_KEY) return res.status(403).send("forbidden");
  let t;
  try { t = new URL(url); } catch { return res.status(400).send("bad url"); }
  if (!/(^|\.)nursejob\.co\.kr$/.test(t.hostname)) return res.status(400).send("host not allowed");
  let last = null;
  for (let i = 0; i < 3; i++) {
    const r = await getOnce(t);
    if (r.ok) {
      res.status(r.status);
      res.setHeader("content-type", r.type || "text/html; charset=utf-8");
      res.setHeader("x-upstream-status", String(r.status));
      res.setHeader("x-attempts", String(i + 1));
      return res.send(r.body);
    }
    last = r.err;
    await new Promise((s) => setTimeout(s, 800));
  }
  return res.status(502).send("upstream error: " + last);
}
