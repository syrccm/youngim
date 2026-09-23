/**
 * 널스잡(nursejob.co.kr) 프록시 워커.
 *
 * 널스잡은 해외 IP를 막는다. 워커 자체는 "요청한 쪽에서 가장 가까운" Cloudflare 데이터센터에서 실행되므로
 * GitHub(미국)에서 부르면 미국에서 널스잡에 접속하게 되어 막힌다. 그래서 실제 접속은
 * 아시아·태평양(apac)에 고정 배치되는 Durable Object 안에서 수행한다.
 *
 * 사용:  GET https://<worker>/?url=<nursejob.co.kr 주소>   헤더 X-Proxy-Key 또는 ?key=
 * 설정:  Settings → Variables and Secrets → PROXY_KEY (Secret)
 *        Settings → Bindings → Durable Object → 변수명 PROXY_DO, 클래스 KrFetcher
 */
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36";

async function fetchUpstream(target) {
  const r = await fetch(target, {
    headers: { "User-Agent": UA, "Accept-Language": "ko-KR,ko;q=0.9", "Accept": "text/html,application/xhtml+xml" },
    redirect: "follow",
    cf: { cacheTtl: 0 },
    signal: AbortSignal.timeout(25000),
  });
  const body = await r.arrayBuffer();
  return new Response(body, {
    status: r.status,
    headers: { "content-type": r.headers.get("content-type") || "text/html; charset=utf-8", "x-upstream-status": String(r.status) },
  });
}

export class KrFetcher {
  constructor(state, env) { this.state = state; this.env = env; }
  async fetch(request) {
    const target = new URL(request.url).searchParams.get("url");
    try { return await fetchUpstream(target); }
    catch (e) { return new Response("upstream error (do): " + (e && e.message), { status: 502 }); }
  }
}

export default {
  async fetch(request, env) {
    const u = new URL(request.url);
    if (u.pathname === "/health") return new Response("ok " + (request.cf && request.cf.colo || ""));
    const key = request.headers.get("X-Proxy-Key") || u.searchParams.get("key");
    if (!env.PROXY_KEY || key !== env.PROXY_KEY) return new Response("forbidden", { status: 403 });
    const target = u.searchParams.get("url");
    let t;
    try { t = new URL(target); } catch { return new Response("bad url", { status: 400 }); }
    if (!/(^|\.)nursejob\.co\.kr$/.test(t.hostname)) return new Response("host not allowed", { status: 400 });
    // Durable Object 바인딩이 있으면 아시아 배치 DO에서, 없으면 이 자리에서 접속
    if (env.PROXY_DO) {
      const id = env.PROXY_DO.idFromName("kr-fetcher");
      const stub = env.PROXY_DO.get(id, { locationHint: "apac" });
      return stub.fetch("https://do/?url=" + encodeURIComponent(t.toString()));
    }
    try { return await fetchUpstream(t.toString()); }
    catch (e) { return new Response("upstream error: " + (e && e.message), { status: 502 }); }
  },
};
