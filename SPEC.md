# SPEC — Phase 1: 기준선·테스트·환경 정리

- 작성: Claude(총감독), 2026-11-27
- 계획: `docs/plans/streamlit_ux_master_plan.md` 6장 Phase 1
- 브랜치: `questions-app`에서 `feat/phase-1`
- 목표: 지금의 기준 수치와 성능을 테스트·보고서로 고정해 둔다. 그래야 Phase 2 리팩토링이 숫자를 바꿨는지 바로 알 수 있다. 체험 1(작은 분모)의 자료도 만든다.
- 이 단계에서는 앱 화면(`app.py`, `app_pages/`, `qlib.py`)을 바꾸지 않는다.

## 파일 담당

| 파일 | 담당 | 작업 |
|---|---|---|
| `questions/requirements-dev.txt` | Cursor | 신규 |
| `questions/ruff.toml` | Cursor | 신규 |
| `questions/calc/common.py` | Cursor | `RAW` 기본 경로 한 줄만 수정 |
| `data/external/SOURCE.txt` | Cursor | 경로·설명 수정 |
| `questions/calc/labs.py` | Cursor | 신규 |
| `questions/data/labs/small_denominator.json` | Cursor | `calc/labs.py` 실행 결과 |
| `questions/tests/conftest.py`, `test_numbers.py`, `test_recompute.py` | Cursor | 신규 |
| `questions/tools/benchmark_app.py` | Cursor | 신규 |
| `questions/reports/perf.md` | Cursor | `benchmark_app.py` 실행 결과 |
| `SPEC.md`, `CLAUDE.md`, `.cursorrules`, `docs/` | Claude | Cursor는 고치지 않음 |
| 그 밖의 모든 파일 | 없음 | 고치지 않음 |

## 1. 개발 환경

`questions/requirements-dev.txt`
```
-r requirements.txt
-r ../requirements.txt
pytest>=8
ruff>=0.8
psutil>=5.9
```

`questions/ruff.toml`
```toml
line-length = 150
target-version = "py311"
extend-exclude = [".cache"]

[lint]
select = ["E", "F", "W"]
```
- 기존 코드의 ruff 오류는 이 단계에서 고치지 않는다. 건수만 `reports/perf.md`에 적는다(0건 만들기는 Phase 4).

## 2. 원본 경로 수정

- `questions/calc/common.py`의 `RAW` 기본값을 `D:/ny311/data/processed/311_requests_2020_present.parquet`로 바꾼다. 환경 변수 `NY311_RAW`가 우선하는 방식은 그대로 둔다. 다른 줄은 바꾸지 않는다.
- `data/external/SOURCE.txt`의 경로를 위와 같게 고치고 한 줄을 추가한다: "파일 이름은 2020_present지만 내용은 2025-11-01~2026-10-31, 3,963,959행이다."

## 3. 체험 1 자료: `questions/calc/labs.py`

입력: `ROOT / "data" / "processed" / "nyc311_tract_complaints.csv"` (Tract 2,327행. `common.ROOT`를 쓴다)

```python
def small_denominator() -> dict: ...   # 아래 JSON을 만들어 반환
def save_lab(name: str, doc: dict) -> Path: ...   # questions/data/labs/{name}.json 저장(ensure_ascii=False)
if __name__ == "__main__": save_lab("small_denominator", small_denominator())
```

출력 `questions/data/labs/small_denominator.json`:
```json
{
  "id": "small_denominator",
  "computed_at": "YYYY-MM-DD HH:MM",
  "source": "data/processed/nyc311_tract_complaints.csv",
  "default_min_pop": 1000,
  "totals": {"tracts": 2327, "complaints": 3880604},
  "example": {"GEOID": "36081056100", "pop": 12, "n": 679, "per_1k": 56583.3},
  "rows": [{"GEOID": "36081056100", "boro": "퀸스", "pop": 12, "n": 679}, ...]
}
```
- `rows`는 2,327개 전부. `pop`, `n`은 정수. 자치구는 `common.BORO_ACS` → `common.BORO_KO`로 한글로 바꾼다.
- 인구 0명 Tract가 84개 있다. 행은 그대로 두고 1,000명당 값은 JSON에 넣지 않는다(체험 화면이 계산하며, 0명은 순위에서 뺀다. Phase 2에서 처리).
- `json.dumps(..., ensure_ascii=False, separators=(",", ":"))`로 줄여 저장한다(목표 200KB 이하).

## 4. 테스트

### `questions/tests/conftest.py`
- `questions/`와 `questions/calc/`를 `sys.path` 앞에 넣는다(`Path(__file__)` 기준).
- 픽스처: `qdir`(questions 폴더 Path), `stats(qid) -> dict`(data/q###.json 읽기).
- 옵션 `--runslow`를 추가한다. `@pytest.mark.slow` 테스트는 이 옵션이 없거나 `common.RAW`가 없으면 건너뛴다(건너뛴 이유를 표시).

### `questions/tests/test_numbers.py` (빠름, 원본 불필요)

| 테스트 | 확인 내용 |
|---|---|
| `test_q095_metrics` | q095 metrics의 value가 순서대로 `"97.9%"`, `"2,195개"`, `"3,803,874건"`. 첫 지표 help가 `"3,880,604 / 3,963,959건"` |
| `test_q095_bronx` | q095 차트 rows에서 브롱크스 주거환경 = 183.0, 소음 = 152.8 (`pytest.approx(rel=1e-4)`) |
| `test_tract_table` | `nyc311_tract_complaints.csv`: 2,327행, 인구 1,000명 이상 2,195개, 그 민원 합 3,803,874, 전체 합 3,880,604, GEOID 36081056100은 인구 12·민원 679·1,000명당 56,583(반올림) |
| `test_small_denominator_lab` | labs JSON의 rows로 인구 ≥ 1,000을 골라 다시 세면 2,195개·3,803,874건. `totals`, `example`이 위 값과 같다 |
| `test_stats_schema` | `data/q*.json` 97개. 키가 정확히 `id, computed_at, source, metrics, charts, tables, numbers`. `id`가 파일 이름 번호와 같다 |
| `test_content_links` | `content/q001~q100.toml` 100개가 모두 있다. `concepts`의 키가 모두 `meta/concepts.toml`에 있다. `related` 번호는 1~100이고 자기 자신이 아니다 |

### `questions/tests/test_recompute.py` (느림, `@pytest.mark.slow`)
- `common.load_311()` 행 수 3,963,959.
- `nyc311_point_geoid.parquet` 행 수 3,880,604.
- `common.tracts()` 2,195행, `common.with_tract(df)` 3,803,874행.
- 95번 브롱크스 주거환경·소음 1,000명당 값을 `part10.q095`와 같은 식으로 다시 계산해 183.0, 152.8과 비교(소수 첫째 자리 반올림 후 일치). `save()`는 부르지 않는다(JSON을 덮어쓰지 않게).

## 5. 성능 기준선: `questions/tools/benchmark_app.py`

```
py -3 questions/tools/benchmark_app.py                 # 1~100번 전체
py -3 questions/tools/benchmark_app.py --ids 1 95 100  # 일부
py -3 questions/tools/benchmark_app.py --out questions/reports/perf.md
```
- `streamlit.testing.v1.AppTest`로 `questions/app.py`를 연다(경로는 `Path(__file__)` 기준). 문항마다: 새 AppTest → `run()` → `switch_page("app_pages/question.py")` → `query_params["q"] = str(qid)` → `run()`. **두 번째 `run()`의 시간**을 그 문항의 렌더링 시간으로 잰다.
- 맨 처음 한 번(import 포함)은 "콜드 스타트"로 따로 적는다.
- 문항마다 기록: 렌더링 시간(초), `at.exception` 개수, 첫 헤더가 `"{qid}. "`로 시작하는지.
- 메모리: 시작과 끝, 그리고 문항마다 `psutil.Process().memory_info().rss`를 재서 최대값을 적는다.
- `--out`이 있으면 마크다운으로 저장한다. 내용:
  - 측정 날짜, Python·streamlit·altair 버전
  - 요약: 문항 수, 예외가 난 문항 수, 렌더링 시간 중앙값·p95·최대, 콜드 스타트, 최대 RSS(MB)
  - 기준 판정: 2초 이내 문항 수 / 100, RSS 500MB 이하 여부
  - 가장 느린 10문항 표
  - 예외가 난 문항 목록(없으면 "없음")
  - `ruff check questions` 오류 건수(스크립트가 아니라 사람이 실행해 적어도 된다)
- 참고(Claude 사전 측정, 2026-11-27): 95·1·74·100번 렌더링 1.2~2.1초(목차 실행 포함), 콜드 5.3초, 예외 0, Python 힙 최대 75MB.

## 완료 조건

1. `py -3 -m pytest questions/tests -q` → 빠른 테스트 6개 통과, slow는 건너뜀 표시.
2. `py -3 -m pytest questions/tests -q --runslow` → 모두 통과(원본이 있는 이 PC에서).
3. `py -3 questions/tools/benchmark_app.py --out questions/reports/perf.md` → 100문항 예외 0, 보고서 생성.
4. `git diff questions-app --stat`에 위 "파일 담당" 표의 Cursor 파일만 나온다. `questions/data/q###.json`은 바뀌지 않았다.
5. 보고: 위 세 명령 출력 원문, `ruff check questions` 건수, 바꾼 파일 목록.

---

## Cursor CLI 실행 프롬프트

```text
저장소 루트의 SPEC.md(Phase 1)와 .cursorrules를 먼저 읽어 줘.
questions-app 브랜치에서 feat/phase-1 브랜치를 만들고, SPEC.md "파일 담당" 표에서 Cursor 담당인 파일만 만들거나 고쳐.
순서: 1) requirements-dev.txt·ruff.toml 2) common.py RAW 경로·SOURCE.txt 3) calc/labs.py 작성 후 실행해 data/labs/small_denominator.json 생성
4) tests/ 세 파일 5) tools/benchmark_app.py 작성 후 실행해 reports/perf.md 생성.
끝나면 아래를 실행하고 출력을 그대로 보여 줘(요약하지 말 것):
py -3 -m pytest questions/tests -q
py -3 -m pytest questions/tests -q --runslow
py -3 questions/tools/benchmark_app.py --out questions/reports/perf.md
py -3 -m ruff check questions --statistics
git diff questions-app --stat
기준 수치(2,195개, 3,803,874건, 183.0, 152.8 등)가 맞지 않거나 표에 없는 파일을 고쳐야 하면, 고치지 말고 멈춘 뒤 보고해.
커밋은 feat/phase-1에만 하고 푸시하지 마.
```
