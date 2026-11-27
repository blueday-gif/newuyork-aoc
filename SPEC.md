# SPEC — Phase 3B: 쓰레기통 의무화 이중차분 체험 + 선거구 개표 결합(17·99번)

- 작성: Claude(총감독), 2026-11-27
- 계획: `docs/plans/streamlit_ux_master_plan.md` 6장 Phase 3(3B). Phase 3A 명세는 git 기록(`ec608ec`, `4c2eea6`)에 있다.
- 브랜치: `feat/phase-3b` (Claude가 만들어 둠). Cursor는 Claude가 따로 만든 작업 폴더에서 작업한다.
- **작업 방식: Cursor는 코드만 쓴다.** 터미널 명령(python, pytest, ruff, git, pip, curl)을 실행하지 않는다. 내려받기·계산·테스트·커밋은 Claude가 한다.
- 목표:
  1. 이중차분(DiD) 체험실 `did_containerization`. 실제 311 쥐 목격 신고(2021~2025)로 만든다.
  2. 17·99번의 "결합 결과". 2025 시장 선거 선거구(ED)별 개표를 Census Tract로 옮겨 민원과 비교한다.
- 기존 `questions/data/q###.json`, `data/joined/` 8개 파일, `data/labs/small_denominator.json`은 **바꾸지 않는다.**
- 3A 규칙은 그대로 따른다.
  - 배율·비율은 반올림하기 전의 값으로 계산한다.
  - 마크다운으로 보내는 문자열은 `md_safe`를 거친다.
  - `cache_data`에는 `ttl`과 `max_entries`를 둔다.

## 자료 조사 결과 (Claude, 2026-11-27 확인)

### 쓰레기통 의무화 정책 시점 (DSNY 공식 페이지)
| 날짜 | 내용 | 출처 |
|---|---|---|
| 2024-03-01 | 모든 사업장은 뚜껑 있는 통에 쓰레기를 내놓는다 | DSNY 사업장 배출 안내 |
| **2024-11-12** | **1~9세대 주거 건물 전체(도시 전역)**: 55갤런 이하, 뚜껑 있는 통 | DSNY 주거 의무화·M9 페이지 |
| 2025-06-01 | 맨해튼 9구역(웨스트 할렘, `cd=109`)은 **모든 주거 건물**이 통이나 Empire Bin을 쓴다 | M9 페이지, 시범 사업 규칙 |
| 2026-06-01 | 1~9세대 건물은 공식 NYC Bin만 쓴다(경고 기간 뒤 2026-09-08부터 단속) | DSNY 주거 의무화 페이지 |
| 2026년 가을 | 브루클린 2구역(`cd=302`)의 모든 주거 건물 | BK2 페이지 |
| 2032년까지 | 10세대 이상 건물 전역 확대 계획 | DSNY 주거 의무화 페이지 |

→ **처치군** = 1~9세대 건물(2024-11-12 처치). **대조군** = 10세대 이상 건물(같은 기간에 의무가 없었음).
→ 두 집단 모두에서 `cd`가 109·302인 필지는 뺀다(10세대 이상도 일찍 처치됨).
→ 사업장 의무화(2024-03-01)는 두 집단에 똑같이 걸리는 공통 변화로 본다.

### 자료 함정 (Claude가 확인)
- 311 `Rodent` 유형 중 `Signs of Rodents`·`Mouse Sighting`은 **2025-09부터 갑자기 약 1/4로** 줄었다. 분류 변경으로 보인다. 그래서 결과값은 **`Rat Sighting`만** 쓰고, 기간은 **2025-08에서 끊는다**.
- 선관위 CSV의 한 행은 머리글 11칸과 값 11칸이 한 줄에 붙어 있다(22칸). **마지막 11칸이 값이다.**
- 선관위 CSV의 `Tally`에는 **천 단위 쉼표("2,116")**가 있다. 쉼표를 지우지 않고 `to_numeric(errors="coerce")`를 쓰면 큰 선거구 표가 조용히 빠진다(실제로 쿠오모 5,361표가 빠졌다).
- `EDAD Status`가 `COMBINED INTO …`인 선거구 221개는 표가 0이다. 다른 선거구에 합쳐 집계되었다.
- 경계 25c와 25d는 선거구 번호가 같고, 배분 결과도 같았다. **25c**(선거 전 판)를 쓴다.
- 주거 세대(PLUTO 필지 좌표)가 하나도 없는 선거구가 75개 있다. 이 선거구들의 표는 36,109표(1.65%)다. 이 선거구들은 **면적 비율**로 배분한다.

### Claude가 이미 계산해 둔 기준값 (테스트에 쓴다)
| 항목 | 값 |
|---|---|
| 시장 후보 득표 합계(Scattered 제외) | 2,187,998 |
| 맘다니(민주+노동가족) | 1,114,184 (50.9%) |
| 쿠오모 / 슬리와 | 906,614 / 153,749 |
| 개표 CSV의 선거구 수 / 경계 선거구 수 | 4,338 / 4,264 (경계에 없는 74개는 모두 0표) |
| DiD 세대 수(109·302 제외) | 1~9세대 1,380,054세대(719,337동), 10세대 이상 2,233,905세대(39,450동) |

DiD 세대 1,000개당 `Rat Sighting`(12월~8월, 9개월 창):

| 창 | 1~9세대(T) | 10세대 이상(C) | T÷C |
|---|---|---|---|
| 2022 (2021-12-01 ~ 2022-08-31) | 6.468 | 3.650 | 1.772 |
| 2023 (2022-12-01 ~ 2023-08-31) | 6.229 | 3.290 | 1.893 |
| 2024 (2023-12-01 ~ 2024-08-31) | 6.056 | 3.511 | 1.725 |
| 2025 (2024-12-01 ~ 2025-08-31) | 4.577 | 3.263 | 1.403 |

- 2024→2025: DiD **−1.23**, T÷C 변화 **−18.7%**.
- 가짜 정책(정책이 없던 해끼리) 비교: 2022→2023은 +6.8%, 2023→2024는 −8.9%.

## 파일 담당

| 파일 | 담당 | 작업 |
|---|---|---|
| `SPEC.md`, `CLAUDE.md`, `.cursorrules`, `docs/` | Claude | Cursor는 고치지 않음 |
| `questions/content/q###.toml` (`join_status`, `method`, `lab`), `meta/concepts.toml` | Claude | 결과를 본 뒤 Claude가 고침 |
| `questions/calc/fetch_ext.py` | Cursor | `pluto_xy` 자료와 `fetch_files` 추가 (1장) |
| `questions/calc/elections.py` | Cursor | 신규: 개표 읽기, ED→Tract 배분 (2장) |
| `questions/calc/joined.py` | Cursor | `q017`, `q099` 추가 (3장) |
| `questions/calc/labs.py` | Cursor | `did_containerization` JSON 만들기 추가 (4장) |
| `questions/components/labs.py` | Cursor | `did_containerization` fragment 추가 (5장) |
| `questions/tests/test_phase3b.py` | Cursor | 신규 (6장) |
| `questions/tests/test_app_render.py` | Cursor | 테스트 2개 추가 (6장) |
| `questions/data/joined/q017.json`, `q099.json`, `data/labs/did_containerization.json` | Claude | 실행 결과 |
| 그 밖의 모든 파일 | 없음 | 고치지 않음 (`calc/part*.py`, `calc/common.py`, `edu_blocks.py`, `question.py`, `app_pages/labs.py` 포함) |

`app_pages/labs.py`는 `labs.LABS`를 돌며 그리므로, `LABS`에 넣기만 하면 체험실 페이지에 나온다.

## 1. `questions/calc/fetch_ext.py` — 추가

```python
DATASETS["pluto_xy"] = dict(
    id="64uk-42ks", select="bbl,cd,latitude,longitude,unitsres",
    where="unitsres > 0", order="bbl", period="최신판")

ELECTION_DIR = EXT_DIR / "elections"
BOE = "https://www.vote.nyc/sites/default/files/pdf/election_results/2025/20251104General%20Election/{code}%20Mayor%20Citywide%20EDLevel.csv"
BOE_BOROS = {"manhattan": "00100100000New%20York", "bronx": "00200100000Bronx", "brooklyn": "00300100000Kings",
             "queens": "00400100000Queens", "staten_island": "00500100000Richmond"}
DCP_ED = "https://s-media.nyc.gov/agencies/dcp/assets/files/zip/data-tools/bytes/election-districts/nyed_{v}.zip"
ED_VERSION = "25c"

def fetch_files(refresh: bool = False) -> Path: ...   # 이름은 "elections"
```
- `cd`, `unitsres`, `latitude`, `longitude`는 숫자 열(`_coerce`의 숫자 목록에 `cd`를 더한다).
- `fetch_files`는 다음을 받는다. 요청마다 `headers={"User-Agent": "Mozilla/5.0"}`를 붙이고, `_get`과 같은 재시도를 쓴다(`_get`에 headers 인자를 더해도 된다).
  - `ELECTION_DIR/mayor_2025_{boro}.csv` 5개
  - `ELECTION_DIR/nyed_{ED_VERSION}.zip`. 받은 뒤 `ELECTION_DIR/nyed_{ED_VERSION}/`에 푼다(`zipfile`). shp는 그 아래 `nyed_25c/nyed.shp`에 있다. 경로를 고정하지 말고 `glob("**/nyed.shp")`로 찾는다.
- 파일이 모두 있고 `refresh`가 아니면 내려받기는 건너뛴다. meta가 없으면 meta만 쓴다.
- 메타는 `EXT_DIR/elections.meta.json`에 쓴다: `{"name": "elections", "dataset": "NYC BOE 2025 General ED-level Mayor + DCP nyed_25c", "url": 첫 CSV URL, "period": "2025-11-04", "rows": 개표 CSV 전체 행 수, "fetched_at"}`. `meta("elections")`로 읽힌다.
- CLI: 이름이 없으면 전부(NOAA·`elections` 포함). `py -3 questions/calc/fetch_ext.py elections`도 된다.

## 2. `questions/calc/elections.py` — 신규

```python
from fetch_ext import ELECTION_DIR, load_ext, meta, norm_bbl

BOE_COLS = ["AD", "ED", "County", "EDAD Status", "Event", "Party/Independent Body",
            "Office/Position Title", "District Key", "VoteFor", "Unit Name", "Tally"]
CRS_NY = 2263   # 면적 계산용(피트)

def parse_tally(s: pd.Series) -> pd.Series: ...        # 쉼표 제거 → to_numeric(errors="raise"), 빈 값은 0, int
def load_results() -> pd.DataFrame: ...                # 열: ed(int), candidate(str), votes(int)
def ed_votes() -> pd.DataFrame: ...                    # ED별: ed, mamdani, cuomo, sliwa, other, total
def load_ed_shapes() -> gpd.GeoDataFrame: ...          # 열: ed(int), geometry (EPSG:2263)
def ed_tract_weights() -> pd.DataFrame: ...            # 열: ed, GEOID, w, method("units"|"area")
def tract_votes(method: str = "units") -> pd.DataFrame: ...
    # 열: GEOID, mamdani, cuomo, sliwa, other, total, area_share
    # method="units": 아래 규칙(세대 배분 + 세대 없는 ED만 면적), "area": 모든 ED를 면적으로(99번 비교용)
```
- 순환 import를 피하려고 `TRACT_GEO`와 `points_to_geoid`는 **함수 안에서** `from joined import TRACT_GEO, points_to_geoid`로 가져온다. `joined.py`도 `q017`·`q099` 함수 안에서 `import elections`를 한다.
- `load_results`:
  - `ELECTION_DIR/mayor_2025_*.csv`를 `csv.reader`로 읽는다(`encoding="utf-8-sig"`). 행마다 **마지막 11칸**을 `BOE_COLS`로 쓴다.
  - `ed = int(AD + ED.zfill(3))`. 경계의 `ElectDist`와 같은 꼴이다(예: AD 77, ED 1 → 77001).
  - `Unit Name`에 `" ("`가 들어간 행만 후보 행으로 본다. 그 밖의 `Public Counter`, `Absentee / Military`, `Affidavit`, `Manually Counted Emergency`, `Scattered`는 빠진다.
  - `candidate`는 `" ("` 앞부분이다. 같은 후보의 여러 정당 줄은 합친다.
  - `votes = parse_tally(Tally)`.
- `ed_votes`:
  - 후보를 열로 펼친다. `Zohran Kwame Mamdani` → `mamdani`, `Andrew M. Cuomo` → `cuomo`, `Curtis A. Sliwa` → `sliwa`, 나머지 후보의 합 → `other`.
  - `total`은 네 열의 합이다. `total == 0`인 ED는 뺀다.
- `load_ed_shapes`: `gpd.read_file(glob 결과)`, `ElectDist`를 `ed`(int)로 바꾸고 `to_crs(CRS_NY)`.
- `ed_tract_weights`:
  1. `load_ext("pluto_xy")`에서 좌표와 `unitsres > 0`이 있는 필지를 고른다. `points_to_geoid`로 GEOID를 붙이고, 점을 `CRS_NY`로 바꿔 ED와 `sjoin(predicate="within")`한다. GEOID를 못 찾은 필지는 뺀다.
  2. `(ed, GEOID)`별 `unitsres` 합을 ED 안에서 나눠 `w`로 한다(ED마다 합이 1). `method="units"`.
  3. 세대가 0인 ED(`ed_votes`에는 있는데 1에서 빠진 ED)는 면적 비율로 `w`를 구한다. `method="area"`.
     - 면적: ED ∩ Tract 겹친 면적(`gpd.overlay(..., how="intersection")`, `CRS_NY`). Tract 경계는 `TRACT_GEO`를 `CRS_NY`로 바꿔 쓴다.
     - 분모: 그 ED의 **전체 면적**. 그래서 물 위처럼 Tract가 없는 부분의 표는 버려진다.
- `tract_votes`:
  - `ed_votes × w`를 GEOID별로 더한다. 소수 표를 그대로 둔다(반올림은 화면에서만).
  - `area_share`는 그 Tract가 받은 `total` 중 `method="area"`로 받은 비율이다.

## 3. `questions/calc/joined.py` — `q017`, `q099` 추가

공통으로 쓰는 값:
- Tract 민원율: `with_tract(load_311())`의 GEOID별 건수 ÷ `total_pop` × 1,000. 3A와 같은 방식이고 분석 대상 2,195개 Tract만 쓴다.
- Tract 선거값: `tract_votes()`를 `tracts()`에 inner merge한다.
  - `mamdani_share = mamdani / total`
  - `votes_per_1k = total / total_pop × 1000`. 이것은 **투표율이 아니다**(분모가 유권자가 아니라 전체 인구다). 화면에도 "주민 1,000명당 표"라고 쓴다.
- `total < 100`인 Tract는 득표율 계산에서 뺀다. 작은 분모 규칙이다. 뺀 Tract 수를 `numbers`에 남긴다.
- 상관은 `scipy.stats.spearmanr`(ρ)로 구한다. 소수 둘째 자리로 보인다.

### q017 — 맘다니 득표율 × 민원율, 임차율 통제
- 지표:
  1. `"맘다니 득표율(시 전체)"` = 1,114,184 ÷ 2,187,998 → `"50.9%"`. ED 원자료 합으로 구한다.
  2. `"ρ: 득표율 × 1,000명당 민원(통제 없음)"`.
  3. `"ρ: 득표율 × 임차율"`.
  4. `"ρ: 임차율 5분위 안에서(중앙값)"`. 아래 표 5개 ρ의 중앙값이다.
- 차트 1 `group`: x = `"임차율 5분위"`(`ren_q`), color = `"지표"`, y = `"값"`. 행은 두 지표다.
  - `"맘다니 득표율(%)"` = 분위 안 Tract들의 `mamdani` 합 ÷ `total` 합 × 100
  - `"1,000명당 민원(÷10)"` = 분위 안 민원 합 ÷ 인구 합 × 1000 ÷ 10
  - 캡션: "두 지표 모두 임차율을 따라 오른다. 공통 원인을 통제하지 않은 상관은 믿기 어렵다."
- 차트 2 `scatter`: x = `"맘다니 득표율(%)"`, y = `"1,000명당 민원"`, color = `"임차율 5분위"`. Tract마다 한 점이다. 점이 2천 개 남짓이어서 그대로 둔다.
- 표: 임차율 5분위별 `Tract 수`, `득표율(%)`, `1,000명당 민원`, `ρ(분위 안)`.
- `numbers`: `rho_raw`, `rho_rent`, `rho_within`(5개 리스트), `n_tracts`, `dropped_small_total`, `votes_total`, `votes_mamdani`.
- sources: `source("elections")`, `source("pluto_xy")`.

### q099 — 공간 보간이 결과를 얼마나 바꾸나
- 지표:
  1. `"Tract로 옮긴 표"` = 분석 대상 Tract가 받은 `total` 합 ÷ ED 원자료 합 → `"%"` 한 자리
  2. `"면적으로 옮긴 표"` = `method="area"` 몫의 비율(%)
  3. `"ρ: 세대 배분 × 면적 배분 득표율"`. `tract_votes("area")`로 구한 득표율과 Tract끼리 상관을 본다.
  4. `"두 방법 득표율 차이(중앙값, %p)"`
- 차트 1 `barh`: 두 방법의 차이(|%p|)가 큰 Tract 상위 10곳. y = `"Tract"`(`GEOID` + 자치구), x = `"차이(%p)"`. 캡션: "공원·공항·대단지처럼 사람이 고르게 살지 않는 곳에서 면적 배분이 크게 틀린다."
- 차트 2 `group`: x = 소득 5분위(`inc_q`), color = `"지표"`. 행은 `"주민 1,000명당 표(÷2)"`와 `"1,000명당 민원(÷2)"`다. 31번과 이어지는 "참여" 비교다.
- `numbers`: `share_allocated`, `share_area`, `rho_methods`, `median_abs_diff_pp`, `n_ed`, `n_ed_area`.
- sources는 q017과 같다.

`main()`의 문항 목록에 17·99를 더한다. 인자가 없으면 10개 전부다. `py -3 questions/calc/joined.py 17 99`도 된다.

## 4. `questions/calc/labs.py` — `did_containerization` 추가

```python
DID_POLICY = "2024-11-12"
DID_EXCLUDE_CD = [109, 302]
DID_WINDOWS = {"2022": ("2021-12-01", "2022-09-01"), "2023": ("2022-12-01", "2023-09-01"),
               "2024": ("2023-12-01", "2024-09-01"), "2025": ("2024-12-01", "2025-09-01")}   # [시작, 끝)
DID_MONTHS = ("2021-01", "2025-08")

def did_containerization() -> Path: ...   # data/labs/did_containerization.json
```
- 세대:
  - `load_ext("pluto_xy")`, `bbl = norm_bbl`, bbl이 없는 행은 빼고, 중복 bbl은 첫 행만 남긴다.
  - `unitsres > 0`이고 `cd`가 `DID_EXCLUDE_CD`에 없는 필지만 쓴다.
  - 집단은 `T` = `unitsres` 1~9, `C` = 10 이상이다.
- 신고: `load_ext("rodent_311_history")`에서 `descriptor == "Rat Sighting"`만 고르고, `bbl`(`norm_bbl`)로 위 필지와 inner merge한다.
- 비율: 집단별 신고 수 ÷ 집단 세대 합 × 1000. 반올림하지 않고 저장한 뒤 JSON 쓸 때 소수 넷째 자리로 한다.
- JSON 키:
  - `id`, `computed_at`, `policy_date`, `excluded_cd`
  - `sources`: `meta("rodent_311_history")`, `meta("pluto_xy")`
  - `groups`: `{"T": {"label": "1~9세대(의무화)", "units", "buildings"}, "C": {"label": "10세대 이상(아직 아님)", "units", "buildings"}}`
  - `monthly`: `[{"month": "2021-01", "T": …, "C": …}, …]`, `DID_MONTHS` 범위
  - `windows`: `[{"label": "2022", "start", "end", "T", "C"}, …]`
  - `notes`: 위 "자료 함정" 첫 항목을 한국어 한 문장으로
- `main`에 넣는다. `py -3 questions/calc/labs.py`를 돌리면 small_denominator와 함께 만든다. `py -3 questions/calc/labs.py did`로 이것만 만들 수도 있다.

## 5. `questions/components/labs.py` — `did_containerization` fragment

```python
@st.fragment
def did_containerization(key: str) -> None: ...
LABS["did_containerization"] = ("이중차분: 쓰레기통 의무화와 쥐 신고", did_containerization)
```
- 데이터는 `qlib.lab("did_containerization")`에서 읽는다. DataFrame 변환은 `@st.cache_data(ttl="1h", max_entries=2)`로 캐시한다(`small_denominator`와 같은 방식, mtime 인자).
- 맨 위 설명(`st.markdown`):
  > 2024년 11월 12일부터 1~9세대 건물은 쓰레기를 뚜껑 있는 통에 내놓아야 한다. 10세대 이상 건물은 아직 아니다. 두 집단의 쥐 목격 신고가 **각각 얼마나 변했는지** 빼 보면, 두 집단이 함께 겪은 변화(날씨, 311 이용 습관)를 지울 수 있다. 실제 311 자료다(웨스트 할렘·브루클린 2구역 제외).
- 차트 1: 월별 선 그래프. x = 월, y = 세대 1,000개당 신고, color = 집단 라벨. `DID_POLICY`에 세로 규칙선을 긋는다(Altair `mark_rule`, `strokeDash`). 기존 `qlib.chart`로 세로선을 못 그리면 이 fragment 안에서 Altair를 직접 쓴다(Altair만 쓴다).
- 입력:
  - `st.select_slider("앞 기간", options=창 라벨, value="2024", key=f"{key}_pre")`
  - `st.select_slider("뒤 기간", options=창 라벨, value="2025", key=f"{key}_post")`
  - `st.toggle("대조군 없이 전후만 비교", value=False, key=f"{key}_naive")`
- 계산(반올림 전 값으로):
  - `dT = T_post − T_pre`, `dC = C_post − C_pre`, `did = dT − dC`
  - `ratio_change = (T_post/C_post) / (T_pre/C_pre) − 1`
- 출력:
  - 앞 ≥ 뒤이면 `st.info("뒤 기간을 앞 기간보다 나중으로 고르세요.")`만 보이고 끝낸다.
  - `st.metric` 3개: `"1~9세대 변화"` = `f"{dT:+.2f}"`, `"10세대 이상 변화"` = `f"{dC:+.2f}"`, `"이중차분"` = `f"{did:+.2f}"`(delta = `f"{ratio_change*100:+.1f}%"`, `delta_color="off"`).
  - 토글이 켜지면 이중차분 metric 대신 `"전후 차이(대조군 없음)"` = `f"{dT:+.2f}"`를 보인다. 캡션: "대조군 없이 보면 날씨·습관 변화까지 정책 효과로 잘못 센다."
  - 뒤 기간이 `"2025"`가 아니면(두 기간 모두 정책 전) 캡션: "정책이 없던 해끼리 비교한 '가짜 정책' 시험이다. 0에 가까울수록 평행 추세 가정을 믿을 만하다."
  - 기본값(2024→2025)일 때 캡션: "정책 뒤 1~9세대 건물의 상대 비율이 약 19% 줄었다. 정책 전 해마다 바뀐 폭(+7%, −9%)보다 크지만, 그 흔들림만큼은 오차로 본다."
  - 맨 아래 `st.caption(md_safe(notes))`(`from components.edu_blocks import md_safe`)

## 6. 테스트

`questions/tests/test_phase3b.py` (외부 파일이 없으면 `pytest.skip`, 조건은 `EXT_DIR` 파일 존재):
- `test_parse_tally`: `parse_tally(pd.Series(["2,116", "0", "15", ""]))` → `[2116, 0, 15, 0]`. 외부 파일 없이 돈다.
- `test_results_totals`: `ed_votes()` 합계가 total 2,187,998, mamdani 1,114,184, cuomo 906,614, sliwa 153,749다(정확히 같음).
- `test_ed_weights_sum`: `ed_tract_weights()`의 ED별 `w` 합이 모두 1+1e-6 이하이고, 합이 0.99 미만인 ED가 전체의 2% 이하다.
- `test_did_lab_numbers`: `data/labs/did_containerization.json`의 windows를 확인한다(이 테스트는 JSON만 읽으므로 skip하지 않는다).
  - 2024: T 6.056, C 3.511
  - 2025: T 4.577, C 3.263
  - 각각 ±0.01이고, 2024→2025 `ratio_change`가 −18.7% ± 0.2%p다.
  - `excluded_cd == [109, 302]`.
- `test_joined_3b_schema`: `data/joined/q017.json`, `q099.json` 키가 3A의 `test_joined_schema`와 같다(JSON만 읽음).

`questions/tests/test_app_render.py`에 추가:
- `test_did_lab_default`: 체험실 페이지(또는 `did_containerization`을 부르는 작은 스크립트)를 AppTest로 돌린다.
  - 예외가 없어야 한다.
  - metric 3개가 있어야 하고, `"이중차분"` 값이 `"-1.23"`이어야 한다.
- `test_did_lab_placebo`: 앞 `2022`, 뒤 `2023`으로 바꾸면 예외가 없어야 하고 캡션에 `"가짜 정책"`이 있어야 한다. 앞 `2025`, 뒤 `2024`면 `st.info`가 하나 나와야 한다.

## 완료 조건 (Claude가 확인)

1. `py -3 questions/calc/fetch_ext.py pluto_xy elections` → 파일과 meta가 만들어진다. pluto_xy는 767,749행 ±1%다.
2. `py -3 questions/calc/labs.py` → `did_containerization.json`. 위 표의 값과 맞아야 한다.
3. `py -3 questions/calc/joined.py 17 99` → 2개 JSON.
4. `py -3 -m pytest questions/tests -q` → 모두 통과. `--runslow`도 통과해야 한다(기준 수치 그대로).
5. 벤치마크: 17·99번 렌더링 2초 이내, DiD 체험 반응 0.5초 이내.
6. Claude가 결과를 검토한 뒤 다음 문구를 고친다.
   - 17·99번의 `join_status`·`method`
   - 15·97·98번에 `lab = "did_containerization"`
   - `concepts.toml`의 `did` 본문(쓰레기통 예시)
7. 브라우저로 17·99번과 체험실을 확인한다.

---

## Cursor CLI 실행 프롬프트 (Claude가 헤드리스로 실행)

```text
작업 폴더는 Claude가 알려 주는 git worktree다. 그 폴더 안의 파일만 읽고 고쳐.
저장소 루트의 SPEC.md(Phase 3B)와 .cursorrules를 먼저 읽어 줘.
코드만 작성해. 터미널 명령(python, py, pytest, ruff, pip, git, curl)은 하나도 실행하지 마. 내려받기·계산·테스트·커밋은 Claude가 한다.
SPEC.md "파일 담당" 표에서 Cursor 담당인 파일만 만들거나 고쳐. 순서:
1) calc/fetch_ext.py(pluto_xy, fetch_files)  2) calc/elections.py  3) calc/joined.py에 q017·q099
4) calc/labs.py에 did_containerization  5) components/labs.py에 fragment와 LABS 항목
6) tests/test_phase3b.py, tests/test_app_render.py에 테스트 2개
"자료 함정"(마지막 11칸, Tally 쉼표, Rat Sighting만, 2025-08에서 끊기)은 Claude가 실제 자료로 확인한 것이다. 그대로 지켜.
calc/part*.py, calc/common.py, data/, content/, meta/는 읽기만 해.
끝나면 바꾼 파일 목록과, SPEC과 다르게 한 부분이나 확신이 없는 부분을 정리해서 알려 줘.
```
