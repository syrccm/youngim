# 수간호사 채용 모니터

사람인에서 「수간호사」「인공신장실」「간호부장」「간호과장」「신장실」「간호부」(부산 전체 + 경남 전체) 검색 결과를 합쳐 하루 두 번(06:00, 14:00 KST) 자동으로 모아
GitHub Pages 페이지에 보여줍니다. 반여1동 장산성당 정류장에서 시내버스 한 번(115-1 · 155 · 189-1 · 36)으로
출퇴근 가능한지도 함께 표시합니다.

## 구성

| 경로 | 역할 |
|---|---|
| `index.html` | 대시보드 페이지 (GitHub Pages) |
| `data/jobs.json` | 수집된 공고 + 최초/최근 확인 시각 + 통근 판정 (Actions가 자동 갱신) |
| `data/commute.json` | 기관별 통근 판정표 — 새 기관은 여기에 한 줄 추가 |
| `data/routes.json` | 4개 노선의 정류장 목록 (판정 근거) |
| `scripts/fetch_jobs.py` | 사람인 검색 → 파싱 → 병합 → `jobs.json` 저장 |
| `.github/workflows/update.yml` | 예약 실행 (UTC 21:00 / 05:00 = KST 06:00 / 14:00) 및 수동 실행 |

## 처음 한 번 설정

1. **Settings → Pages** : Source를 `Deploy from a branch`, Branch를 `main` / `/ (root)` 로 저장  
   → 잠시 후 `https://syrccm.github.io/youngim/` 에서 열립니다.
2. **Settings → Actions → General → Workflow permissions** : `Read and write permissions` 선택 후 저장  
   (Actions가 `data/jobs.json`을 커밋할 수 있어야 합니다.)
3. **Actions 탭 → 「사람인 수간호사 공고 갱신」 → Run workflow** 로 첫 실행을 해 보고, 로그에 `fetched N items` 가 찍히는지 확인합니다.

## 통근 판정 규칙

- `commute.json`에 기관명이 있으면 그 판정을 사용합니다 (부분 일치).
- 없으면 지역으로 자동 판정: 사하·서·북·사상·강서·영도·동·부산진·중구와 경남 전체는 4개 노선이 가지 않으므로 **불가**.
- 그 외(해운대·수영·남·연제·동래·금정·기장)는 **확인 필요**로 표시됩니다. 기관 위치를 확인한 뒤 `commute.json`에 추가하면 다음 갱신부터 반영됩니다.

## 검색 조건 바꾸기

`scripts/fetch_jobs.py` 상단의 `KEYWORDS`(검색어 목록)와 `SEARCH_URL`의 `loc_mcd`(지역 코드: 부산 106000, 경남 110000, 울산 107000)를 바꾸면 됩니다.
