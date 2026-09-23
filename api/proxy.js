// 널스잡(nursejob.co.kr) 프록시 — Vercel 서버리스 함수. 서울(icn1) 리전에서 실행되어 널스잡의 해외 IP 차단을 피한다.
// 사용: GET /api/proxy?url=<nursejob 주소>   헤더 X-Proxy-Key 또는 ?key=   (환경변수 PROXY_KEY 필요)
export const config = { regions: ["icn1"], maxDuration: 30 };

const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36";

export default async function handler(req, res) {
  const { url, key } = req.query;
  if (req.url && req.url.startsWith("/api/proxy/health")) return res.status(200).send("ok");
  const k = req.headers["x-proxy-key"] || key;
  if (!process.env.PROXY_KEY || k !== process.env.PROXY_KEY) return res.status(403).send("forbidden");
  let t;
  try { t = new URL(url); } catch { return res.status(400).send("bad url"); }
  if (!/(^|\.)nursejob\.co\.kr$/.test(t.hostname)) return res.status(400).send("host not allowed");
  try {
    const r = await fetch(t.toString(), {
      headers: { "User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9", "Accept": "text/html,application/xhtml+xml" },
      redirect: "follow",
      signal: AbortSignal.timeout(25000),
    });
    const buf = Buffer.from(await r.arrayBuffer());
    res.status(r.status);
    res.setHeader("content-type", r.headers.get("content-type") || "text/html; charset=utf-8");
    res.setHeader("x-upstream-status", String(r.status));
    return res.send(buf);
  } catch (e) {
    return res.status(502).send("upstream error: " + (e && e.message));
  }
}
