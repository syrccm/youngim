#!/usr/bin/env python3
"""사람인 간호 관리직 검색 결과(부산·경남)를 수집해 data/jobs.json 을 갱신한다.

- 검색어: KEYWORDS 목록 각각 검색 후 합침(공고 번호 기준 중복 제거, 어떤 검색어에 걸렸는지 기록)
- 지역: loc_mcd=106000(부산),110000(경남), 페이지당 100건
- 기존 jobs.json 과 병합해 first_seen / last_seen 을 유지하고 신규 여부를 판단
- data/commute.json(기관별 통근 판정)과 지역 규칙으로 각 공고의 통근 가능성을 채움
"""
import json, re, sys, html, datetime, zoneinfo, pathlib, time
import urllib.request, urllib.parse
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import geo
import nursejob

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
JOBS = DATA / "jobs.json"
COMMUTE = DATA / "commute.json"

KEYWORDS = ["수간호사", "인공신장실", "간호부장", "간호과장", "신장실", "간호부"]
SEARCH_URL = ("https://www.saramin.co.kr/zf_user/search/recruit?searchType=search"
              "&searchword={kw}&loc_mcd=106000%2C110000"
              "&recruitPageCount=100&recruitSort=reg_dt&recruitPage={page}")


def search_url(kw, page=1):
    return SEARCH_URL.format(kw=urllib.parse.quote(kw), page=page)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}

# 직행 4개 노선 + 반여3동 경유 노선(115·144·44·52·해운대구1)이 모두 가지 않는 구·지역 → 자동 '불가'
# (52번이 부산진구·동구까지 가므로 두 구는 제외하고 지도 판정에 맡김)
NO_GO = ["사하구", "서구", "북구", "사상구", "강서구", "영도구", "중구", "경남", "울산", "경북"]


def fetch(url, retries=6):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # noqa
            print(f"fetch failed ({i+1}/{retries}): {e}", file=sys.stderr)
            time.sleep(15 * (i + 1))
    raise SystemExit("사람인 페이지를 가져오지 못했습니다.")


def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


def parse(page_html):
    """item_recruit 블록 단위로 파싱. 사람인 마크업이 바뀌면 이 함수만 손보면 된다."""
    items = []
    blocks = re.split(r'<div class="item_recruit"', page_html)[1:]
    for b in blocks:
        b = b.split('<div class="item_recruit"')[0]
        rec = re.search(r'value="(\d+)"', b[:200])
        rec_idx = rec.group(1) if rec else ""
        tit = re.search(r'<h2 class="job_tit">(.*?)</h2>', b, re.S)
        tb = tit.group(1) if tit else b
        t = re.search(r'title="([^"]*)"', tb)
        title = clean(html.unescape(t.group(1))) if t else clean(re.search(r"<a[^>]*>(.*?)</a>", tb, re.S).group(1)) if re.search(r"<a[^>]*>(.*?)</a>", tb, re.S) else ""
        hm = re.search(r'href="([^"]*rec_idx=(\d+)[^"]*)"', tb)
        if hm:
            rec_idx = rec_idx or hm.group(2)
            url = "https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=" + rec_idx + "&view_type=search"
        else:
            url = ""
        corp = re.search(r'<strong class="corp_name">(.*?)</strong>', b, re.S)
        company = clean(corp.group(1)) if corp else ""
        cond = re.search(r'<div class="job_condition">(.*?)</div>', b, re.S)
        conds = [clean(x) for x in re.findall(r"<span[^>]*>(.*?)</span>", cond.group(1), re.S)] if cond else []
        location = conds[0] if conds else ""
        career = conds[1] if len(conds) > 1 else ""
        edu = conds[2] if len(conds) > 2 else ""
        emp_type = conds[3] if len(conds) > 3 else ""
        dl = re.search(r'class="date">(.*?)</span>', b, re.S)
        deadline = clean(dl.group(1)) if dl else ""
        deadline = deadline.replace("~", "").strip()
        day = re.search(r'class="job_day">(.*?)</span>', b, re.S)
        posted = clean(day.group(1)) if day else ""
        sector = re.search(r'<div class="job_sector">(.*?)</div>', b, re.S)
        sectors = ", ".join(t for t in (clean(x) for x in re.findall(r"<a[^>]*>(.*?)</a>", sector.group(1), re.S)) if t) if sector else ""
        if not (title or company):
            continue
        items.append({
            "id": rec_idx or re.sub(r"\s+", "", company + "|" + title),
            "company": company, "title": title, "location": location,
            "career": career, "education": edu, "type": emp_type,
            "deadline": deadline, "posted": posted, "sector": sectors, "url": url,
        })
    return items


def total_count(page_html):
    m = re.search(r'class="cnt_result">\s*총\s*([\d,]+)\s*건', page_html) or re.search(r'총\s*([\d,]+)\s*건의 검색결과', page_html)
    return int(m.group(1).replace(",", "")) if m else None


def judge_commute(item, table, stops=None, cache=None):
    """1) commute.json 수동 판정 → 2) 노선이 안 가는 지역 → 3) 카카오 지도 자동 판정 → 4) 확인 필요."""
    comp = re.sub(r"\s+", "", item["company"])
    hits = [(len(k), k) for k in table if not k.startswith("_") and re.sub(r"\s+", "", k) in comp]
    if hits:
        v = table[max(hits)[1]]  # 가장 구체적인(긴) 기관명 우선
        return {"verdict": v.get("verdict", "unknown"), "route": v.get("route", ""),
                "stop": v.get("stop", ""), "walk_min": v.get("walk_min"),
                "note": v.get("note", ""), "address": v.get("address", "")}
    loc = item.get("location", "")
    if any(loc.startswith(g) or ("부산 " + g) in loc for g in NO_GO) or loc.startswith("경남") or loc.startswith("울산"):
        return {"verdict": "no", "route": "", "stop": "", "walk_min": None,
                "note": "이용 가능한 노선이 가지 않는 지역", "address": ""}
    if stops is not None and cache is not None:
        auto = geo.auto_verdict(item["company"], loc, stops, cache)
        if auto:
            return auto
    return {"verdict": "unknown", "route": "", "stop": "", "walk_min": None, "note": "기관 위치 확인 필요", "address": ""}


def main():
    now = datetime.datetime.now(zoneinfo.ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%dT%H:%M")
    state = json.loads(JOBS.read_text(encoding="utf-8")) if JOBS.exists() else {}
    state.setdefault("items", []); state.setdefault("runs", [])
    table = json.loads(COMMUTE.read_text(encoding="utf-8")) if COMMUTE.exists() else {}
    routes = json.loads((DATA / "routes.json").read_text(encoding="utf-8"))
    stops = geo.build_stops(routes) if geo.KEY else (json.loads(geo.STOPS.read_text(encoding="utf-8")) if geo.STOPS.exists() else {})
    cache = geo.load_cache()
    if not geo.KEY:
        print("KAKAO_REST_KEY 없음: 자동 위치 판정 생략", file=sys.stderr)

    fetched, by_id = [], {}
    for kw in KEYWORDS:
        page, expected, got_kw = 1, None, 0
        while page <= 5:
            h = fetch(search_url(kw, page))
            if expected is None:
                expected = total_count(h)
            got = parse(h)
            if not got:
                break
            for it in got:
                got_kw += 1
                if it["id"] in by_id:
                    if kw not in by_id[it["id"]]["keywords"]:
                        by_id[it["id"]]["keywords"].append(kw)
                else:
                    it["keywords"] = [kw]
                    by_id[it["id"]] = it
                    fetched.append(it)
            if expected is not None and got_kw >= expected:
                break
            page += 1
            time.sleep(1)
        print(f"[{kw}] {got_kw} items (site says {expected})")
        time.sleep(1)
    for it in fetched:
        it["source"] = "사람인"
    print(f"[사람인] {len(fetched)} unique items")
    if not fetched:
        raise SystemExit("파싱 결과가 0건입니다. 사람인 마크업 변경 여부를 확인하세요.")

    # 널스잡 (Cloudflare 프록시 경유). 실패해도 사람인 결과는 유지한다.
    try:
        nj = nursejob.collect(KEYWORDS)
    except Exception as e:  # noqa
        print(f"널스잡 수집 실패: {e}", file=sys.stderr); nj = []
    print(f"[널스잡] {len(nj)} unique items")
    fetched += nj

    old = {it["id"]: it for it in state["items"]}
    merged, new_ids = [], []
    seen = set()
    for it in fetched:
        if it["id"] in seen:
            continue
        seen.add(it["id"])
        prev = old.get(it["id"])
        it["first_seen"] = prev["first_seen"] if prev else now
        it["last_seen"] = now
        it["commute"] = judge_commute(it, table, stops, cache)
        if not prev:
            new_ids.append(it["id"])
        merged.append(it)
    for p in state["items"]:
        p.setdefault("keywords", ["수간호사"])

    # 이번 검색에서 사라진 공고는 7일간 '마감/종료' 로 보관 (널스잡 수집이 통째로 실패한 경우는 그대로 유지)
    nj_ok = bool(nj)
    for pid, p in old.items():
        if pid in seen:
            continue
        if not nj_ok and p.get("source") == "널스잡":
            merged.append(p); continue
        last = datetime.datetime.fromisoformat(p["last_seen"])
        if (datetime.datetime.fromisoformat(now) - last).days <= 7:
            p["gone"] = True
            p["commute"] = judge_commute(p, table, stops, cache)
            merged.append(p)

    state["items"] = merged
    state["updated"] = now
    state["search"] = {"keywords": KEYWORDS, "regions": "부산 전체, 경남 전체", "sources": ["사람인", "널스잡"],
                       "urls": {kw: search_url(kw) for kw in KEYWORDS},
                       "nursejob_urls": {kw: nursejob.search(kw, "73") for kw in KEYWORDS}}
    state["runs"] = (state["runs"] + [{"at": now, "total": len(fetched), "new": len(new_ids) if state["runs"] else 0,
                                       "saramin": len(fetched) - len(nj), "nursejob": len(nj)}])[-200:]
    JOBS.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    geo.save_cache(cache)
    print(f"updated {now}: total {len(fetched)}, new {len(new_ids)}")


if __name__ == "__main__":
    main()
