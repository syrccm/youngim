// HTTP 단계 진단: node:https 직접 요청과 fetch 원인(cause)까지 기록
import https from "node:https";
export const config = { regions: ["icn1"], maxDuration: 60 };
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36";
function get(path, headers, ms = 15000) {
  return new Promise((res) => {
    const t0 = Date.now(); let bytes = 0;
    const req = https.request({ host: "www.nursejob.co.kr", port: 443, path, method: "GET", headers, servername: "www.nursejob.co.kr" }, (r) => {
      r.on("data", (c) => bytes += c.length);
      r.on("end", () => res({ ok: true, status: r.statusCode, bytes, ms: Date.now() - t0, hdr: r.headers["content-type"], server: r.headers["server"] }));
    });
    req.setTimeout(ms, () => { req.destroy(new Error("timeout")); });
    req.on("error", (e) => res({ ok: false, err: e.code || e.message, ms: Date.now() - t0 }));
    req.end();
  });
}
export default async function handler(req, res) {
  if ((req.query.key || "") !== process.env.PROXY_KEY) return res.status(403).send("forbidden");
  const path = "/recruit/list.php?m=jikjong&smode=search&keyword_search=%EC%88%98%EA%B0%84%ED%98%B8%EC%82%AC&w_area1=73&num=1";
  const out = {};
  out.plain = await get("/", { "User-Agent": UA });
  out.plainNoUA = await get("/", {});
  out.full = await get(path, { "User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8", "Accept-Encoding": "gzip, deflate, br", "Connection": "keep-alive", "Upgrade-Insecure-Requests": "1", "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Site": "none", "Cache-Control": "max-age=0" });
  out.http80 = await new Promise((r2) => { import("node:http").then(({ default: http }) => { const t0 = Date.now(); const rq = http.request({ host: "www.nursejob.co.kr", port: 80, path: "/", headers: { "User-Agent": UA } }, (r) => { let b = 0; r.on("data", c => b += c.length); r.on("end", () => r2({ ok: true, status: r.statusCode, bytes: b, loc: r.headers.location, ms: Date.now() - t0 })); }); rq.setTimeout(15000, () => rq.destroy(new Error("timeout"))); rq.on("error", e => r2({ ok: false, err: e.code || e.message, ms: Date.now() - t0 })); rq.end(); }); });
  try { const t0 = Date.now(); const r = await fetch("https://www.nursejob.co.kr/", { headers: { "User-Agent": UA }, signal: AbortSignal.timeout(15000) }); out.fetch = { status: r.status, len: (await r.text()).length, ms: Date.now() - t0 }; }
  catch (e) { out.fetch = { err: e.message, cause: e.cause && (e.cause.code || e.cause.message), causeStr: e.cause && String(e.cause) }; }
  res.status(200).json(out);
}
