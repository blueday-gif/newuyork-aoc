# SPEC — Phase 3A: 외부 자료 수집과 10부 결합 (8개 문항)

- 작성: Claude(총감독), 2026-11-27
- 계획: `docs/plans/streamlit_ux_master_plan.md` 5장·6장 Phase 3
- 브랜치: `feat/phase-3` (Claude가 만들어 둠). Cursor는 Claude가 따로 만든 작업 폴더에서 작업한다.
- **작업 방식: Cursor는 코드만 쓴다.** 터미널 명령(python, pytest, ruff, git, pip, curl)을 실행하지 않는다. 내려받기·계산·테스트·커밋은 Claude가 한다.
- 목표: 공개 외부 자료 6종을 내려받는 코드와, 311과 결합해 8개 문항(7·57·58·72·75·96·97·100번)의 "결합 결과"를 만드는 코드, 그리고 그 결과를 문항 화면에 보여 주는 블록.
- 기존 `questions/data/q###.json`(311만으로 낸 통계)은 **바꾸지 않는다.** 결합 결과는 별도 파일 `questions/data/joined/q###.json`에 둔다.

## 자료 조사 결과 (Claude, 2026-11-27 API로 확인)

| 자료 | 출처 · ID | 기간 내 행 수 | 채택 |
|---|---|---|---|
| NOAA 센트럴파크 일별 기상 | NCEI daily-summaries, 관측소 `USW00094728` | 365일 | 채택 |
| HPD 주택 유지관리 위반 | NYC Open Data `wvxf-dwi5` | 2025-11~2026-10: 950,039 / 2024-11~: 1,865,451 | 채택 |
| DOHMH 쥐 점검 | `p937-wjvj` | 206,388 (Initial 147,961 · Compliance 36,912 · Treatments 28,953 …) | 채택 |
| PLUTO 필지 | `64uk-42ks` | 약 85만 필지(주거 세대 있는 필지만 받음) | 채택 |
| FloodNet 침수 이벤트·센서 | `aq7i-eu5q`, `kb2e-tjy3` | 이벤트 1,752 | 채택 |
| 311 쥐 민원 2020~ (DiD 준비) | `erm2-nwe9`, `complaint_type='Rodent'` | 연 약 3.9만(2021: 38,809, 2024: 39,726) | 수집만(계산은 Phase 3B) |
| 임대료 안정화 건물 목록(RGB) | 공개 데이터 없음(DHCR 목록은 PDF) | — | 보류(13·14·15·21·24·98번) |
| 선거구(ED)별 개표 결과 | 경계는 `wwxk-38u4`에 있으나 개표는 선관위 사이트 | — | 보류(17·99번), Claude가 Phase 3B에서 조사 |
| 쓰레기통 의무화 구역 | 공개 데이터 없음 | — | DiD 보류, Claude가 정책 시점 조사 |
| SONYC 소음 센서, ACS 2015–2019 | NYC Open Data에 없음 / Census API 키 필요 | — | 보류(66·46번) |

## 파일 담당

| 파일 | 담당 | 작업 |
|---|---|---|
| `SPEC.md`, `CLAUDE.md`, `.cursorrules`, `docs/` | Claude | Cursor는 고치지 않음 |
| `questions/content/q###.toml`(`join_status`, `method` 문구) | Claude | 결과를 본 뒤 Claude가 고침 |
| `questions/calc/fetch_ext.py` | Cursor | 신규 (1장) |
| `questions/calc/joined.py` | Cursor | 신규 (2·3장) |
| `questions/qlib.py` | Cursor | `joined(qid)` 추가 (4장) |
| `questions/components/edu_blocks.py` | Cursor | `render_joined` 추가 (4장) |
| `questions/app_pages/question.py` | Cursor | `render_joined` 호출 한 줄 (4장) |
| `questions/tests/test_joined.py` | Cursor | 신규 (5장) |
| `questions/tests/test_app_render.py` | Cursor | 테스트 1개 추가 (5장) |
| `questions/data/joined/*.json` | Claude | `joined.py` 실행 결과 |
| 그 밖의 모든 파일 | 없음 | 고치지 않음(`calc/part*.py`, `calc/common.py`, `data/q###.json` 포함) |

## 1. `questions/calc/fetch_ext.py` — 내려받기

내려받은 원자료는 저장소 밖에 둔다.

```python
EXT_DIR = Path(os.environ.get("NY311_EXT", "D:/ny311/external"))
SODA = "https://data.cityofnewyork.us/resource/{id}.csv"
PAGE = 50_000

DATASETS: dict[str, dict] = {
    "hpd_violations": dict(
        id="wvxf-dwi5",
        select="violationid,bbl,bin,class,inspectiondate,novissueddate,novdescription,rentimpairing,latitude,longitude",
        where="inspectiondate between '2024-11-01T00:00:00' and '2026-10-31T23:59:59'",
        order="violationid", period="2024-11-01~2026-10-31"),
    "rodent_inspections": dict(
        id="p937-wjvj",
        select="job_id,inspection_date,inspection_type,result,bbl,borough,latitude,longitude",
        where="inspection_date between '2025-11-01T00:00:00' and '2026-10-31T23:59:59'",
        order=":id", period="2025-11-01~2026-10-31"),
    "pluto": dict(
        id="64uk-42ks",
        select="bbl,borocode,bldgclass,landuse,unitsres,unitstotal,yearbuilt,numfloors,bct2020",
        where="unitsres > 0", order="bbl", period="최신판"),
    "floodnet_events": dict(
        id="aq7i-eu5q",
        select="sensor_id,flood_start_time,flood_end_time,max_depth_inches,duration_mins",
        where="flood_start_time between '2025-11-01T00:00:00' and '2026-10-31T23:59:59'",
        order="sensor_id,flood_start_time", period="2025-11-01~2026-10-31"),
    "floodnet_sensors": dict(
        id="kb2e-tjy3",
        select="sensor_id,sensor_name,date_installed,date_removed,tidally_influenced,borough,latitude,longitude",
        where=None, order="sensor_id", period="전체"),
    "rodent_311_history": dict(
        id="erm2-nwe9",
        select="unique_key,created_date,descriptor,bbl,incident_zip,borough,latitude,longitude",
        where="complaint_type='Rodent' and created_date between '2020-01-01T00:00:00' and '2026-10-31T23:59:59'",
        order="unique_key", period="2020-01-01~2026-10-31"),
}
NOAA = dict(
    url="https://www.ncei.noaa.gov/access/services/data/v1",
    params=dict(dataset="daily-summaries", stations="USW00094728", startDate="2025-11-01", endDate="2026-10-31",
                dataTypes="TMIN,TMAX,PRCP,SNOW", units="metric", format="csv"),
    period="2025-11-01~2026-10-31")
```

함수:
```python
def fetch_soda(name: str, refresh: bool = False) -> Path: ...
def fetch_noaa(refresh: bool = False) -> Path: ...        # 이름은 "noaa_centralpark"
def load_ext(name: str) -> pd.DataFrame: ...              # 없으면 FileNotFoundError("... py -3 questions/calc/fetch_ext.py {name}")
def meta(name: str) -> dict: ...                          # {name}.meta.json 내용
def norm_bbl(s: pd.Series) -> pd.Series: ...              # 아래 규칙
```
- SoQL 쿼리: `$select`, `$where`(있을 때), `$order`, `$limit=PAGE`, `$offset`을 `requests.get(..., params=..., timeout=120)`으로 보낸다. 받은 행이 `PAGE`보다 적으면 끝.
- HTTP 오류나 503이면 10초, 30초, 90초 기다렸다 다시 시도(최대 3번). 그래도 실패하면 예외. **진행 표시**: 페이지마다 `print(f"{name}: {누적:,}행")`.
- CSV는 `pd.read_csv(io.StringIO(text), dtype=str)`로 읽고 마지막에 한 번 이어 붙인다. 날짜 열(이름에 대소문자 무시로 `date`가 들어가거나 `_time`으로 끝나는 열. NOAA는 `DATE`)은 `pd.to_datetime(errors="coerce")`, 숫자 열(`unitsres, unitstotal, yearbuilt, numfloors, max_depth_inches, duration_mins, latitude, longitude, TMIN, TMAX, PRCP, SNOW`)은 `pd.to_numeric(errors="coerce")`. `bbl`은 `norm_bbl`.
- 저장: `EXT_DIR/{name}.parquet`와 `EXT_DIR/{name}.meta.json` = `{"name", "dataset"(ID 또는 "NCEI daily-summaries USW00094728"), "url"(쿼리 붙은 첫 요청 URL), "period", "rows", "fetched_at"("YYYY-MM-DD HH:MM")}`.
- 파일이 이미 있으면 `refresh`가 아닐 때 건너뛰고 경로만 반환.
- `norm_bbl`: 문자열로 바꾸고 공백 제거 → `.` 앞부분만(PLUTO는 `1000010010.00000000` 꼴) → 숫자 10자리이고 첫 글자가 1~5이며 `"0000000000"`이 아닐 때만 남기고 나머지는 `pd.NA`.
- CLI: `py -3 questions/calc/fetch_ext.py [이름 ...] [--refresh]` — 이름이 없으면 전부(NOAA 포함).

## 2. `questions/calc/joined.py` — 공통 도구

```python
from common import BORO_KO, INC_Q, ROOT, category, load_311, records, tracts, with_tract
from fetch_ext import load_ext, meta, norm_bbl
from part07 import HPD_KO, has_bbl          # part07 모듈은 import해도 계산하지 않는다(__main__ 보호)
from part10 import WEATHER, flood

JOINED_OUT = Path(__file__).resolve().parents[1] / "data" / "joined"
TRACT_GEO = ROOT / "data" / "processed" / "nyc_acs_2024_5yr.geojson"
RAT_FOUND = ["Failed for Rat Activity", "Failed for Rat Activity and Other Reason"]
HEAT_VIOL = r"27-2029|27-2031"          # novdescription에 들어 있으면 난방·온수 위반

def points_to_geoid(df, lat="latitude", lon="longitude") -> pd.Series: ...
def heat_violations(v: pd.DataFrame) -> pd.DataFrame: ...   # novdescription.str.contains(HEAT_VIOL)
def source(name: str) -> dict: ...                          # meta(name)에서 name, dataset, url, period, rows, fetched_at
def save_joined(qid, sources, metrics, charts, tables=None, numbers=None) -> Path: ...
```
- `points_to_geoid`: 좌표가 있는 행만 geopandas `points_from_xy(lon, lat, crs="EPSG:4326")`로 만들고, `TRACT_GEO`(EPSG:4326으로 맞춤, `GEOID` 열만)와 `sjoin(predicate="within")`. 반환은 `df.index`에 맞춘 `GEOID` 시리즈(못 찾으면 NA). `scripts/join_311_acs.py`와 같은 방식.
- `save_joined`: `JOINED_OUT/q{qid:03d}.json`, 키는 정확히 `id, computed_at, sources, metrics, charts, tables, numbers`. 형식은 `common.save`와 같다(`ensure_ascii=False, indent=1`).
- 차트 `kind`는 기존 `qlib.chart`가 아는 것만 쓴다: `bar, barh, line, stack, stackh, group, scatter`.
- CLI: `py -3 questions/calc/joined.py [번호 ...]` — 없으면 8개 전부. `load_311()`과 `with_tract()`는 필요할 때 한 번만 부른다.
- 모든 기간은 `PERIOD = ("2025-11-01", "2026-10-31")`. 날짜 비교는 날짜 단위(`.dt.normalize()`).

## 3. 문항별 계산

모든 비율·중앙값은 소수 첫째 자리(배율·상관은 둘째 자리)로 반올림해 저장한다. **배율·비율은 반올림하기 전의 값으로 계산한다**(2026-11-27 검토에서 추가: 반올림한 0.7 ÷ 0.1 = 7.0이 실제 5.0을 가린 사례). q072의 "세대당 이전 위반"은 값이 작아 소수 둘째 자리로 보인다. 차트 `caption`과 지표 `help`의 문구는 아래 그대로 쓴다.

### q057 — 기온과 난방 민원 (NOAA)
- 난방 민원: `problem == "HEAT/HOT WATER"`, 2025-11-01~2026-03-31(기존 q057과 같은 기간). 날짜별 건수, 빠진 날은 0.
- NOAA `TMIN`(°C)을 날짜로 붙인다.
- 구간: `[-inf,-10)`, `[-10,-5)`, `[-5,0)`, `[0,5)`, `[5,10)`, `[10,inf)` → 이름 `"-10 미만"`, `"-10~-5"`, `"-5~0"`, `"0~5"`, `"5~10"`, `"10 이상"`.
- metrics:
  - `"0°C 미만 날의 하루 중앙값"` = TMIN<0인 날 건수 중앙값(`f"{x:,.0f}건"`), help `f"{n}일"`
  - `"0~10°C 날의 하루 중앙값"` = 0≤TMIN<10, help `f"{n}일"`
  - `"배율"` = 앞 ÷ 뒤 (`f"{x:.1f}배"`), help `"BuildingHealthX는 0°C 아래에서 약 2배라고 보고했다"`
  - `"순위 상관(최저기온 vs 민원)"` = scipy `spearmanr`의 ρ (`f"{x:.2f}"`)
- charts: ① bar `"최저기온 구간별 하루 난방 민원(중앙값)"`, x `"최저기온 구간"`, y `"하루 난방 민원"`, caption `"같은 겨울 안에서 추운 날일수록 신고가 많다. 요일·연휴 효과는 빼지 않았다."` ② scatter `"최저기온과 하루 난방 민원"`, x `"최저기온(°C)"`, y `"난방 민원"`, `trend=True`.
- numbers: `{"days_below0", "days_0_10", "median_below0", "median_0_10", "ratio", "spearman"}`

### q058 — 열대야와 정전·소화전 민원 (NOAA)
- 2026-06-01~2026-08-31. 정전: `problem == "ELECTRIC"`이고 `detail == "POWER OUTAGE"`. 소화전: `problem in ["Water System","Water Maintenance"]`이고 `detail`에 `"Hydrant Running"`(대소문자 무시). 기존 q058과 같은 정의.
- 열대야 = `TMIN > 20`.
- 하루 평균 민원을 열대야 / 그 밖의 날로 나눈다.
- metrics: `"열대야 일수"`(`f"{n}일"`, help `"최저기온 20°C 초과, 6~8월"`), `"정전 민원 배율"`(열대야 평균 ÷ 그 밖 평균, `f"{x:.1f}배"`), `"소화전 민원 배율"`.
- chart: group `"여름 하루 평균 민원: 열대야 vs 그 밖의 날"`, x `"민원"`(값 `"정전"`, `"소화전 열림"`), color `"날"`(값 `"열대야"`, `"그 밖의 날"`, colors `{"열대야": "#c94f6d", "그 밖의 날": "#9fb3d1"}`), y `"하루 평균"`. caption `"열대야에는 냉방 부하로 정전이, 더위를 피하려 소화전을 여는 일이 늘어난다는 가설을 확인한다."`

### q096 — 날씨 민원 4종과 기상 변수 (NOAA)
- `part10.WEATHER`의 4개 정의를 그대로 쓴다. 1년 전체 날짜별 건수(빠진 날 0).
- 짝: `눈·얼음`–`SNOW`, `난방·온수`–`TMIN`, `빗물받이 막힘·도로 침수`–`PRCP`, `소화전 열림`–`TMAX`.
- 각 짝의 spearman ρ를 두 번: 같은 날(t의 민원 vs t의 날씨), 다음 날(t+1의 민원 vs t의 날씨).
- table `"날씨 민원과 기상 변수의 순위 상관"`: 열 `"민원", "기상 변수", "같은 날 ρ", "다음 날 ρ"`.
- metrics: 4개, label = 민원 이름, value = 두 ρ 중 절댓값이 큰 것(`f"{x:.2f}"`), help = `f"{변수} · {'같은 날' or '다음 날'}"`.
- chart: scatter `"강수량과 하루 침수 관련 민원"`, x `"강수량(mm)"`, y `"민원"`, `trend=True`, caption `"비가 많이 온 날 신고가 솟는다. 같은 강수량에도 날마다 차이가 크다."`

### q007 — 난방 민원과 HPD 난방 위반 (BBL)
- 311: `problem == "HEAT/HOT WATER"`, 2025-11-01~2026-05-31, `norm_bbl(bbl)`이 있는 행. 건물(BBL)별 민원 수.
- HPD: `heat_violations`, `inspectiondate` 2025-11-01~2026-05-31, `norm_bbl` 있는 행. 건물별 위반 수.
- 두 표를 BBL로 outer join.
- metrics: `"신고됐고 위반도 있는 건물"`, `"신고됐지만 위반이 없는 건물"`, `"위반은 있는데 신고가 없던 건물"` (모두 `f"{n:,}동"`, help = 전체 건물 중 비율 `f"{p:.1f}%"`), `"10건 이상 신고·위반 0 건물"`(`f"{n:,}동"`).
- chart: bar `"건물당 난방 민원 수와 위반이 확인된 비율"`, x `"건물당 민원"`(구간 `"1건"`, `"2–4건"`, `"5–9건"`, `"10–49건"`, `"50건 이상"`), y `"위반 있는 건물(%)"`, caption `"많이 신고된 건물일수록 위반이 확인되는 비율이 높은지 본다. 위반 없음은 '문제없음'이 아니라 '점검에서 확인 못 함'일 수 있다."`
- table `"10건 이상 신고됐는데 위반이 없는 건물 상위 10"`: 열 `"BBL", "난방 민원", "주소"`(주소는 311 `addr_n`의 최빈값).

### q072 — 건물 증후군과 신고 이전 위반 (HPD 위반 + PLUTO)
- 311 HPD 민원 건물 × 유형: 기존 `part07.q072`와 같은 방법(`agency == "HPD"`, `has_bbl`, `problem in HPD_KO`, 건물별 나온 유형 수 `ntype`). BBL은 `norm_bbl`.
- 묶음: `"1가지"`, `"2–3가지"`, `"4–5가지"`, `"6가지 이상"`.
- **신고 이전 위반**: HPD 위반 중 `inspectiondate`가 2024-11-01~2025-10-31(311 기간 바로 앞 1년)인 것의 건물별 수.
- PLUTO `unitsres`(>0)를 BBL로 붙인다. 세대 수가 없는 건물은 빼고, 붙은 비율을 지표로 적는다.
- 묶음별: 건물 수, 세대 수 합, 이전 위반 합, `"세대당 이전 위반"` = 위반 합 ÷ 세대 합, `"C등급 비율(%)"`(이전 위반 중 `class == "C"`).
- metrics: `"PLUTO 세대 수가 붙은 건물"`(비율 %), `"6가지 이상 건물의 세대당 이전 위반"`, `"1가지 건물의 세대당 이전 위반"`, `"배율"`(6가지 이상 ÷ 1가지, `f"{x:.1f}배"`, help `"ikrar.dev는 12~44배라고 보고했다(기간·정의가 다르다)"`).
- chart: bar `"민원 유형 수별 세대당 신고 이전 1년 위반"`, x `"민원 유형 수"`, y `"세대당 이전 위반"`, caption `"311 기간(2025-11~) 이전 1년의 위반이다. '신고 → 점검 → 위반'의 행정 순환을 피하려고 시간을 앞으로 뺐다."`
- table: 묶음별 표 전체.

### q075 — 건물 규모와 민원 (PLUTO)
- 311 전체 민원 중 `norm_bbl` 있는 것을 PLUTO(`unitsres > 0`)와 BBL로 붙인다. 분야는 `common.category(problem)`.
- 규모: `"1–2세대"`, `"3–9세대"`, `"10–49세대"`, `"50–99세대"`, `"100세대 이상"`.
- 규모별: 건물 수, 세대 수 합, 분야별(`주거환경`, `소음`) 민원, `"100세대당 민원"` = 민원 ÷ 세대 × 100.
- metrics: `"PLUTO 주거 필지와 연결된 민원"`(BBL 있는 민원 중 비율 %), `"연결된 건물"`(`f"{n:,}동"`), `"주거환경: 100세대 이상 ÷ 1–2세대"`(배율).
- chart: group `"건물 규모별 100세대당 민원"`, x `"건물 규모"`, color `"분야"`(colors `{"주거환경": "#2457a7", "소음": "#e07b39"}`), y `"100세대당 민원"`, caption `"같은 동네 안의 비교가 아니라 시 전체 비교다. 대형 건물이 몰린 동네의 특성이 섞여 있다."`
- table: 규모별 표 전체.

### q097 — 신고 vs 점검 (DOHMH 쥐 점검 + HPD 난방 위반)
- 분석 대상 Tract(`tracts()`, 인구 1,000명 이상)와 소득 5분위 `inc_q`만 쓴다.
- 쥐: 311 `problem == "Rodent"`(with_tract 결과). 점검: `rodent_inspections`를 `points_to_geoid`로 Tract에 붙이고, `result in RAT_FOUND`면 "쥐 확인".
- 난방: 311 `HEAT/HOT WATER`(1년 전체, with_tract). 위반: `heat_violations`(inspectiondate 1년 전체)를 좌표로 Tract에 붙인다.
- 분위별: 쥐는 1,000명당(분모 `total_pop`), 난방은 임차 1,000가구당(분모 `renter_occupied`).
  - `"311 쥐 신고"`, `"점검에서 쥐 확인"`, `"쥐: 신고 ÷ 확인"`
  - `"311 난방 신고"`, `"HPD 난방 위반"`, `"난방: 신고 ÷ 위반"`
- metrics: `"쥐 점검(12개월)"`(전체 건수, help `f"쥐 확인 {n:,}건"`), `"좌표로 Tract를 찾은 점검"`(%), `"쥐: 신고 ÷ 확인(최하위 → 최상위 소득)"`(`f"{a:.2f} → {b:.2f}"`), `"난방: 신고 ÷ 위반(최하위 → 최상위 소득)"`.
- charts: ① group `"소득 5분위별 쥐: 신고와 점검 확인(1,000명당)"`, x `"소득 5분위"`, color `"지표"`(`"311 쥐 신고"`, `"점검에서 쥐 확인"`), y `"1,000명당"`. ② bar `"신고 ÷ 확인 배율(쥐)"`, x `"소득 5분위"`, y `"쥐: 신고 ÷ 확인"`, caption `"배율이 크면 확인된 문제에 비해 신고가 많은 동네, 작으면 적은 동네다. 점검은 신고로 시작하기도 하고(행정 순환) 신고 없이 지역 단위로 하기도 해서 두 값은 독립이 아니다."` (2026-11-27 결과 검토 뒤 Claude가 고침)
- tables: 분위별 전체 표, `"점검 종류별 건수"`(inspection_type별 건수와 쥐 확인 비율).

### q100 — FloodNet 센서와 311 침수 민원
- 센서: `floodnet_sensors`에서 `tidally_influenced`가 대소문자 무시 `{"yes","y","true","1"}`이면 뺀다(조수 영향). 좌표로 Tract를 붙인다.
- 이벤트: `floodnet_events`를 그 센서로 거르고, 날짜 = `flood_start_time`의 날짜. 센서-날짜 단위로 중복을 없앤다(그날 최대 깊이를 남김).
- 311 침수 민원: `part10.flood(df)`를 `with_tract`로 Tract에 붙인 것. Tract-날짜별 건수.
- 센서-날짜마다 "같은 Tract에서 같은 날 또는 다음 날 311 침수 민원이 1건 이상 있었나".
- 깊이 구간: `"4인치 미만"`, `"4–12인치"`, `"12인치 이상"`.
- metrics: `"분석한 센서"`(`f"{n}개"`, help `"조수 영향 센서 제외"`), `"센서가 잡은 침수(센서-날짜)"`(`f"{n:,}건"`), `"311 신고가 함께 있었던 비율"`(%), `"12인치 이상 침수의 신고 비율"`(%).
- chart: bar `"침수 깊이별 311 신고가 함께 있었던 비율"`, x `"침수 깊이"`, y `"311 신고 있음(%)"`, caption `"센서가 물을 잡은 날, 같은 Tract에서 아무도 신고하지 않은 경우가 '보이지 않는 침수'다. 센서 위치와 민원 위치가 같은 거리는 아니다."`
- table: 깊이 구간별 센서-날짜 수, 신고 있음 수, 비율.

## 4. 앱에 보여 주기

- `qlib.py`: `_joined(qid, mtime)` + `joined(qid) -> dict | None` (`data/joined/q###.json`, 없으면 None). `@st.cache_data(ttl="1h", max_entries=50)`. 기존 `stats()`와 같은 모양.
- `edu_blocks.render_joined(qid: int, j: dict) -> None`:
  - 소제목 `"결합 결과"`(divider="gray"), 그 아래 `st.caption("합친 자료: " + " · ".join(f"{s['name']}({s['dataset']}, {s['period']}, {s['rows']:,}행)" for s in j["sources"]))`
  - 지표·차트·표는 `render_stats`와 같은 방식. 세로축 전환 key는 `f"jy_{qid}_{i}"`(기존 `y_{qid}_{i}`와 겹치지 않게).
  - 맨 아래 caption: `f"계산: questions/calc/joined.py · {j['computed_at']}"`
- `question.py`: `render_stats` 바로 다음, `render_lab` 앞에
  ```python
  j = qlib.joined(qid)
  if j:
      edu_blocks.render_joined(qid, j)
  ```

## 5. 테스트 (Cursor가 쓰고 Claude가 실행)

`tests/test_joined.py`:
| 테스트 | 확인 |
|---|---|
| `test_norm_bbl` | `["1000010010.00000000", " 3033540029", "0000000000", "", None, "123", "6000000001"]` → `["1000010010", "3033540029", NA, NA, NA, NA, NA]` |
| `test_points_to_geoid` | 타임스스퀘어(40.7580, −73.9855)의 GEOID가 `"36061"`로 시작, 대서양 한가운데(40.0, −70.0)는 NA |
| `test_joined_schema` | `data/joined/q*.json`이 정확히 7·57·58·72·75·96·97·100번 8개. 키가 정확히 `id, computed_at, sources, metrics, charts, tables, numbers`. 모든 source에 `name, dataset, url, period, rows, fetched_at`이 있고 `rows > 0`. 차트 kind는 허용 목록 안 |
| `test_original_stats_untouched` | `data/q007.json`의 metrics 첫 항목이 `{"label": "난방 민원(2025-11 ~ 2026-05)", "value": "308,677건"}`과 같다(결합이 기존 통계를 건드리지 않았는지 확인) |
| `test_q057_numbers` | q057 numbers에 `days_below0, days_0_10, median_below0, median_0_10, ratio, spearman`이 모두 있고, `days_below0 + days_0_10 <= 151`(11~3월 일수), `-1 <= spearman <= 1` (결과의 방향은 검사하지 않는다. 그건 Claude가 해석한다) |

`test_app_render.py`에 추가: `test_joined_section` — 97번에 소제목 `"결합 결과"`가 있고 예외가 없다. 결합 파일이 없는 1번에는 `"결합 결과"`가 없다.
## 완료 조건 (Claude가 확인)

1. `py -3 questions/calc/fetch_ext.py` → 7종 모두 저장, meta의 행 수가 위 조사 결과와 크게 다르지 않다(±5%, 자료가 계속 갱신되므로).
2. `py -3 questions/calc/joined.py` → 8개 JSON 생성.
3. `py -3 -m pytest questions/tests -q` → 모두 통과. `--runslow`도 통과(기준 수치 그대로).
4. 벤치마크: 결합 결과가 붙은 문항도 렌더링 2초 이내.
5. Claude가 결과를 읽고 통계적으로 말이 되는지 검토한 뒤, 8개 문항의 `join_status`·`method` 문구를 고친다.
6. 브라우저로 7·57·97·100번 확인.

## Phase 3B (다음, Claude 조사 먼저)
- 쓰레기통 의무화(Containerization) 정책 시점과 적용 대상을 DSNY 공식 자료로 확인 → 처치·대조 집단을 정의할 수 있으면 `rodent_311_history`로 DiD 체험 설계.
- 선거구(ED)별 개표 자료 확보 방법 조사(17·99번).

---

## Cursor CLI 실행 프롬프트 (Claude가 헤드리스로 실행)

```text
작업 폴더는 Claude가 알려 주는 git worktree다. 그 폴더 안의 파일만 읽고 고쳐.
저장소 루트의 SPEC.md(Phase 3A)와 .cursorrules를 먼저 읽어 줘.
코드만 작성해. 터미널 명령(python, py, pytest, ruff, pip, git, curl)은 하나도 실행하지 마. 내려받기·계산·테스트·커밋은 Claude가 한다.
SPEC.md "파일 담당" 표에서 Cursor 담당인 파일만 만들거나 고쳐. 순서:
1) calc/fetch_ext.py  2) calc/joined.py(공통 도구 → 문항 8개, 문구는 SPEC 그대로)
3) qlib.joined, edu_blocks.render_joined, question.py 한 줄
4) tests/test_joined.py, tests/test_app_render.py에 test_joined_section
calc/part*.py, calc/common.py, data/, content/, meta/는 읽기만 해.
자료의 열 이름과 값(result, novdescription 등)은 SPEC에 적힌 것이 실제 확인한 값이다. 추측해서 바꾸지 마.
끝나면 바꾼 파일 목록과, SPEC과 다르게 한 부분이나 확신이 없는 부분을 정리해서 알려 줘.
```
