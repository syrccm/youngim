"""카카오 로컬 API로 기관·정류장 좌표를 찾고, 정류장까지 거리로 통근 가능성을 자동 판정한다.

- 환경변수 KAKAO_REST_KEY 가 없으면 모든 함수가 None/unknown 을 돌려주고 조용히 넘어간다.
- data/stops.json  : 4개 노선 정류장 좌표 (없거나 빠진 정류장이 있으면 채운다)
- data/geo_cache.json : 기관명 → 좌표 캐시 (API 호출 절약)
"""
import json, math, os, re, sys, time, pathlib, urllib.request, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
STOPS = DATA / "stops.json"
CACHE = DATA / "geo_cache.json"
KEY = os.environ.get("KAKAO_REST_KEY", "").strip()

# 부산·경남 동부 대략 범위 (검색 결과를 이 안으로 제한)
RECT = "128.7,34.9,129.4,35.5"

WALK_OK_MIN, WALK_FAR_MIN = 10, 20     # 도보 분
WALK_M_PER_MIN, DETOUR = 75, 1.3       # 분당 75m, 직선거리 대비 실제 경로 1.3배


def _get(url):
    req = urllib.request.Request(url, headers={"Authorization": "KakaoAK " + KEY})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def search(query, near=None, size=5):
    """키워드 검색. near=(x,y) 주면 그 근처 우선 정렬."""
    if not KEY:
        return []
    q = {"query": query, "rect": RECT, "size": size}
    if near:
        q.update({"x": near[0], "y": near[1], "sort": "distance"})
    url = "https://dapi.kakao.com/v2/local/search/keyword.json?" + urllib.parse.urlencode(q)
    for i in range(3):
        try:
            return _get(url).get("documents", [])
        except Exception as e:  # noqa
            print(f"kakao search failed ({i+1}/3) [{query}]: {e}", file=sys.stderr)
            time.sleep(2)
    return []


def dist_m(x1, y1, x2, y2):
    R = 6371000.0
    p1, p2 = math.radians(y1), math.radians(y2)
    dp, dl = math.radians(y2 - y1), math.radians(x2 - x1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ---------- 정류장 좌표 ----------
def _stop_query_variants(name):
    base = name.replace(".", " ").replace("·", " ")
    return [base + " 버스정류장", base + " 정류장", base]


def build_stops(routes):
    """routes.json 의 정류장 이름을 좌표로. 이미 있는 것은 건너뛴다."""
    stops = json.loads(STOPS.read_text(encoding="utf-8")) if STOPS.exists() else {}
    changed = False
    for rno, r in routes["routes"].items():
        have = {s["name"]: s for s in stops.get(rno, [])}
        out, prev = [], None
        for name in r["stops"]:
            if name in have and have[name].get("x"):
                out.append(have[name]); prev = (have[name]["x"], have[name]["y"]); continue
            found = None
            if KEY:
                for q in _stop_query_variants(name):
                    docs = search(q, near=prev, size=5)
                    # 정류장 카테고리 우선, 없으면 이름이 들어간 결과, 이전 정류장에서 3km 이내
                    cands = []
                    for d in docs:
                        x, y = float(d["x"]), float(d["y"])
                        if prev and dist_m(prev[0], prev[1], x, y) > 3000:
                            continue
                        score = 0
                        if "버스정류장" in d.get("category_name", "") or "정류" in d.get("place_name", ""):
                            score += 2
                        if name.split(".")[0][:3] in d.get("place_name", ""):
                            score += 1
                        cands.append((score, -dist_m(prev[0], prev[1], x, y) if prev else 0, x, y, d["place_name"]))
                    if cands:
                        cands.sort(reverse=True)
                        s = cands[0]
                        found = {"name": name, "x": s[2], "y": s[3], "matched": s[4]}
                        break
                    time.sleep(0.1)
            if found:
                out.append(found); prev = (found["x"], found["y"]); changed = True
            else:
                out.append({"name": name, "x": None, "y": None})
                if name not in have:
                    changed = True
        stops[rno] = out
    if changed:
        STOPS.write_text(json.dumps(stops, ensure_ascii=False, indent=1), encoding="utf-8")
    located = sum(1 for r in stops.values() for s in r if s.get("x"))
    total = sum(len(r) for r in stops.values())
    print(f"stops located {located}/{total}")
    return stops


# ---------- 기관 좌표 ----------
def _clean_company(name):
    n = re.sub(r"[\(\[（].*?[\)\]）]", " ", name)                    # 괄호 내용 제거
    n = re.sub(r"(의료법인|사회복지법인|재단법인|사단법인|학교법인|주식회사|\(의\)|의\)|\(재\)|\(주\)|\(사\)|의료재단|복지재단|재단)", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n or name


def _gu(location):
    m = re.search(r"(부산|경남|울산)\s*([가-힣]+[구군시])", location or "")
    return m.group(2) if m else ""


def geocode_company(company, location, cache):
    key = re.sub(r"\s+", "", company)
    if key in cache:
        return cache[key]
    result = None
    if KEY:
        clean = _clean_company(company)
        gu = _gu(location)
        queries = [f"{clean} {gu}".strip(), clean]
        # 괄호 안 병원명이 있으면 그것도 시도 (예: 의료법인 xx재단(yy병원))
        m = re.search(r"[\(（]([^\)）]*(병원|의원|센터|클리닉)[^\)）]*)[\)）]", company)
        if m:
            queries.insert(0, f"{m.group(1)} {gu}".strip())
        for q in queries:
            docs = search(q, size=5)
            docs = [d for d in docs if any(k in d.get("category_name", "") for k in ("병원", "의원", "의료", "보건", "요양", "치과", "한의", "약국", "센터"))] or docs
            if docs:
                d = docs[0]
                result = {"x": float(d["x"]), "y": float(d["y"]), "place": d["place_name"],
                          "address": d.get("road_address_name") or d.get("address_name", ""), "query": q}
                break
            time.sleep(0.1)
    cache[key] = result
    return result


def nearest_stop(x, y, stops):
    best = None
    for rno, lst in stops.items():
        for s in lst:
            if not s.get("x"):
                continue
            d = dist_m(x, y, s["x"], s["y"])
            if best is None or d < best[0]:
                best = (d, rno, s["name"])
    return best


def auto_verdict(company, location, stops, cache):
    """카카오 좌표 기반 자동 판정. 실패하면 None."""
    g = geocode_company(company, location, cache)
    if not g or not stops:
        return None
    best = nearest_stop(g["x"], g["y"], stops)
    if not best:
        return None
    d, rno, sname = best
    walk = round(d * DETOUR / WALK_M_PER_MIN)
    verdict = "ok" if walk <= WALK_OK_MIN else "far" if walk <= WALK_FAR_MIN else "no"
    return {"verdict": verdict, "route": rno if verdict != "no" else "", "stop": sname if verdict != "no" else "",
            "walk_min": walk if verdict != "no" else None,
            "note": ("자동 판정 · 지도 기준 가장 가까운 정류장 " + rno + "번 " + sname + f" 직선 {int(d)}m")
                    if verdict != "no" else f"자동 판정 · 가장 가까운 정류장({rno}번 {sname})까지 직선 {int(d)}m",
            "address": g.get("address", ""), "auto": True}


def load_cache():
    return json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}


def save_cache(cache):
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
