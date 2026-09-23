/**
 * 널스잡(nursejob.co.kr) 페이지를 한국 근처 Cloudflare 엣지에서 대신 가져다 주는 작은 프록시.
 * GitHub Actions(해외 IP)는 널스잡에 직접 접속이 막혀 있어 이 워커를 거친다.
 *
 * 사용:  GET https://<worker>/?url=<nursejob.co.kr 주소>   헤더 X-Proxy-Key: <PROXY_KEY>
 * 설정:  Cloudflare 대시보드 → 이 워커 → Settings → Variables and Secrets → PROXY_KEY (Secret)
 */
export default {
  async fetch(request, env) {
    const u = new URL(request.url);
    if (u.pathname === "/health") return new Response("ok");
    const key = request.headers.get("X-Proxy-Key") || u.searchParams.get("key");
    if (!env.PROXY_KEY || key !== env.PROXY_KEY) return new Response("forbidden", { status: 403 });
    const target = u.searchParams.get("url");
    let t;
    try { t = new URL(target); } catch { return new Response("bad url", { status: 400 }); }
    if (!/(^|\.)nursejob\.co\.kr$/.test(t.hostname)) return new Response("host not allowed", { status: 400 });
    try {
      const r = await fetch(t.toString(), {
        headers: {
          "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
          "Accept-Language": "ko-KR,ko;q=0.9",
          "Accept": "text/html,application/xhtml+xml",
        },
        redirect: "follow",
        cf: { cacheTtl: 0 },
      });
      const body = await r.arrayBuffer();
      return new Response(body, {
        status: r.status,
        headers: { "content-type": r.headers.get("content-type") || "text/html; charset=utf-8", "x-upstream-status": String(r.status) },
      });
    } catch (e) {
      return new Response("upstream error: " + (e && e.message), { status: 502 });
    }
  },
};
