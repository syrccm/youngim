"""널스잡(nursejob.co.kr) 검색 결과 수집 (Cloudflare 프록시 경유).

널스잡은 해외 IP를 막으므로 Cloudflare 워커(cloudflare/worker.js)를 프록시로 거친다.
환경변수 NJ_PROXY_URL / NJ_PROXY_KEY 가 없으면 직접 접속을 시도하고, 실패하면 빈 목록을 돌려준다.
반환 항목 형식은 사람인(fetch_jobs.parse)과 같다. 마감된 공고는 제외.
"""
import html, os, re, sys, time, urllib.parse, urllib.request

PROXY_URL = os.environ.get("NJ_PROXY_URL", "").strip().rstrip("/")
PROXY_KEY = os.environ.get("NJ_PROXY_KEY", "").strip()
BASE = "https://www.nursejob.co.kr"
AREAS = {"73": "부산", "71": "경남"}          # w_area1 코드
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
           "Accept-Language": "ko-KR,ko;q=0.9"}


def _get(url, retries=2):
    if not PROXY_URL:
        return ""
    for i in range(retries):
        try:
            if PROXY_URL:
                sep = "&" if "?" in PROXY_URL else "?"
                req = urllib.request.Request(PROXY_URL + sep + "url=" + urllib.parse.quote(url, safe=""),
                                             headers={"X-Proxy-Key": PROXY_KEY})
            else:
                req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                b = r.read()
            try:
                return b.decode("utf-8")
            except UnicodeDecodeError:
                return b.decode("euc-kr", "replace")
        except Exception as e:  # noqa
            print(f"nursejob fetch failed ({i+1}/{retries}): {e}", file=sys.stderr)
            time.sleep(5 * (i + 1))
    return ""


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def parse(page):
    items = []
    for m in re.finditer(r'<tr id="l_(\d+)"(.*?)</tr>', page, re.S):
        rid, b = m.group(1), m.group(2)
        name = re.search(r'<p class="name">(.*?)</p>', b, re.S)
        title = re.search(r'<p class="title"[^>]*>(.*?)</p>', b, re.S)
        stxts = [clean(x) for x in re.findall(r'<p class="stxt(?: [^"]*)?">(.*?)</p>', b, re.S)]
        loc = stxts[0] if stxts else ""
        loc = re.sub(r"\|\s*(부산|수도권|대구|서울|인천|광주|대전)?\s*\d*호선[^|]*$", "", loc).strip()  # 지하철 정보 제거
        loc = re.sub(r"\|.*$", "", loc).strip() if loc.count("|") else loc
        cond = stxts[1] if len(stxts) > 1 else ""
        dm = re.search(r'<td class="date"[^>]*>(.*?)</td>', b, re.S)
        date = clean(dm.group(1)) if dm else ""
        if "마감됨" in date:
            continue
        # "6시간전 등록 11-07 (토) D-45" / "1일전 등록 채용시"
        posted = re.search(r"(.+?등록)", date)
        dl = re.search(r"(\d{2}-\d{2})\s*\(([^)]+)\)", date)
        deadline = f"{dl.group(1).replace('-', '/')}({dl.group(2)})" if dl else ("" if "채용시" in date else "")
        parts = [x.strip() for x in cond.split(">")]
        career = parts[1] if len(parts) > 1 else ""
        pay = next((x for x in parts if "만원" in x), "")
        items.append({
            "id": "nj" + rid,
            "company": clean(name.group(1)) if name else "",
            "title": clean(title.group(1)) if title else "",
            "location": loc,
            "career": career, "education": (parts[2] if len(parts) > 2 else ""), "type": pay,
            "deadline": deadline,
            "posted": (posted.group(1).strip() if posted else date),
            "sector": cond,
            "url": f"{BASE}/recruit/recruit_view.php?r_idx={rid}",
            "source": "널스잡",
        })
    return items


def search(keyword, area, page=1):
    q = {"m": "jikjong", "smode": "search", "keyword_search": keyword, "w_area1": area, "num": 1, "page": page}
    return f"{BASE}/recruit/list.php?" + urllib.parse.urlencode(q)


def collect(keywords, max_pages=5):
    """키워드 × 지역별로 검색해 합친다. {id: item} 와 id→키워드 목록을 돌려준다."""
    by_id, kws = {}, {}
    if not PROXY_URL:
        print("NJ_PROXY_URL 없음: 널스잡 수집 생략", file=sys.stderr)
        return []
    for kw in keywords:
        for area in AREAS:
            for page in range(1, max_pages + 1):
                h = _get(search(kw, area, page))
                if not h:
                    break
                got = parse(h)
                if not got:
                    break
                for it in got:
                    by_id.setdefault(it["id"], it)
                    kws.setdefault(it["id"], [])
                    if kw not in kws[it["id"]]:
                        kws[it["id"]].append(kw)
                if len(got) < 20:
                    break
                time.sleep(0.5)
        print(f"[널스잡 {kw}] 누적 {len(by_id)}건")
    for i, it in by_id.items():
        it["keywords"] = kws[i]
    return list(by_id.values())


if __name__ == "__main__":
    for it in collect(["수간호사"], max_pages=1)[:5]:
        print(it)
