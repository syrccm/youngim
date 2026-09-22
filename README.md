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
- 그 외 지역의 새 기관은 **카카오 지도 API**로 위치를 찾아 4개 노선 정류장(`data/stops.json`)까지의 거리로 자동 판정합니다(도보 10분 이내 가능 / 20분 이내 도보 멀음 / 그 밖 불가). 결과는 `data/geo_cache.json`에 캐시됩니다.
- 지도에서도 찾지 못하면 **확인 필요**로 표시됩니다. 자동 판정이 틀린 기관은 `commute.json`에 적어 두면 그 값이 우선합니다.

### 카카오 지도 API 키 (자동 판정에 필요)

1. https://developers.kakao.com → 내 애플리케이션 → 애플리케이션 추가 (이름 아무거나)
2. 앱 설정 → 앱 키 → **REST API 키** 복사
3. 앱 설정 → 카카오맵 → **사용 설정 ON** (로컬 API 사용에 필요)
4. 이 저장소 Settings → Secrets and variables → Actions → New repository secret → 이름 `KAKAO_REST_KEY`, 값에 REST API 키 붙여넣기
키가 없으면 자동 판정만 건너뛰고 나머지는 정상 동작합니다.

## 검색 조건 바꾸기

`scripts/fetch_jobs.py` 상단의 `KEYWORDS`(검색어 목록)와 `SEARCH_URL`의 `loc_mcd`(지역 코드: 부산 106000, 경남 110000, 울산 107000)를 바꾸면 됩니다.
