# SPEC — Phase 2: 교육 블록 분리, 논문 연결, 체험실, 학습 진도

- 작성: Claude(총감독), 2026-11-27
- 계획: `docs/plans/streamlit_ux_master_plan.md` 3장·6장 Phase 2
- 브랜치: `feat/phase-2` (Claude가 만들어 둠. Phase 1 명세는 커밋 3050db7의 SPEC.md)
- **작업 방식: Cursor는 코드만 쓴다.** 터미널 명령(python, pytest, ruff, git, pip)을 실행하지 않는다. 테스트·벤치마크·커밋은 Claude가 한다.
- 목표
  1. `question.py`의 화면 블록을 `components/edu_blocks.py` 함수로 옮긴다. 기존 블록의 화면은 그대로다.
  2. 새 블록 세 가지: 개념 팝오버 줄, 논문·사례 연결, "같이 볼 질문" 한 줄 해설.
  3. `@st.fragment` 체험 두 가지(작은 분모, 보고 편향)를 문항 화면과 새 "체험실" 페이지에 넣는다.
  4. 사이드바에 학습 진도를 보여 준다.

## 파일 담당

| 파일 | 담당 | 작업 |
|---|---|---|
| `SPEC.md`, `CLAUDE.md`, `.cursorrules`, `docs/` | Claude | Cursor는 고치지 않음 |
| `questions/meta/papers.toml` | Claude | 작성 완료(12편). Cursor는 읽기만 |
| `questions/content/q###.toml`의 `papers`, `lab`, `related_why` 키 | Claude | 25개 문항에 넣어 둠. Cursor는 읽기만 |
| `questions/qlib.py` | Cursor | 읽기 함수 2개 추가(아래 1장). 기존 함수는 바꾸지 않음 |
| `questions/components/__init__.py` | Cursor | 신규(빈 파일) |
| `questions/components/edu_blocks.py` | Cursor | 신규 |
| `questions/components/labs.py` | Cursor | 신규 |
| `questions/state.py` | Cursor | 신규 |
| `questions/app.py` | Cursor | 체험실 페이지 등록, 사이드바 진도 |
| `questions/app_pages/question.py` | Cursor | 블록 호출로 정리 + 새 블록 |
| `questions/app_pages/labs.py` | Cursor | 신규 |
| `questions/tests/test_app_render.py` | Cursor | 신규 |
| `questions/tests/test_numbers.py` | Cursor | 테스트 함수 1개 추가(기존 6개는 그대로) |
| `questions/tools/benchmark_app.py` | Cursor | `--labs` 옵션 추가 |
| 그 밖의 모든 파일 | 없음 | 고치지 않음(특히 `data/`, `calc/`, `content/` 본문, `concepts.toml`) |

## 0. 새로 생긴 자료 (Claude가 넣음)

`questions/meta/papers.toml` — 키 12개. 각 표의 필드: `title, who, track(1~4), question, data, method, finding, differs` (모두 문자열, track만 정수).

`questions/content/q###.toml`의 새 키(있는 문항만):
```toml
related_why = { 16 = "이 결합으로 임차율과 민원을 비교한다", 33 = "..." }  # 키는 문항 번호(파싱하면 문자열 "16")
papers = ["kontokosta_heat", "urban_2025"]                              # papers.toml 키
lab = "small_denominator"                                              # "small_denominator" | "reporting_bias"
```
- `papers`가 있는 문항: 7, 8, 9, 10, 16, 31, 37, 39, 41, 46, 66, 67, 72, 75, 76, 78, 93, 94, 97, 100
- `lab`: 74·95 → small_denominator, 37·39 → reporting_bias
- `related_why`: 39, 74, 95, 96, 97, 98, 99, 100

## 1. `qlib.py`에 추가

```python
@st.cache_data(ttl="1h")
def _papers(mtime: int) -> dict: ...          # meta/papers.toml을 tomllib로 읽음
def papers() -> dict: ...                     # _papers(_mtime(...)) — concepts()와 같은 모양

@st.cache_data(ttl="1h", max_entries=10)
def _lab(name: str, mtime: int) -> dict: ...  # data/labs/{name}.json
def lab(name: str) -> dict: ...
```
- `small_denominator.json`의 구조는 Phase 1 SPEC과 같다: `default_min_pop, totals{tracts, complaints}, example{GEOID, pop, n, per_1k}, rows[{GEOID, boro, pop, n}]`.
- `reporting_bias`는 JSON 파일이 없다(가상 자료를 코드 안에서 계산).

## 2. `components/edu_blocks.py`

모든 함수는 화면에 그리기만 하고 반환값이 없다. 아래 "그대로"는 지금 `question.py`의 코드·문구·위젯 key를 바꾸지 않는다는 뜻이다.

| 함수 | 내용 |
|---|---|
| `render_header(qid: int, q: dict, part: dict, c: dict) -> None` | 그대로: 태그 배지, 부 제목 caption, `st.header`, 한 줄 답 카드, `join_status` info |
| `render_concept_chips(keys: list[str], concepts: dict) -> None` | **새 블록.** 한 줄 답 카드 바로 아래. `st.container(horizontal=True, gap="small")` 안에 개념마다 `st.popover(card["title"], icon=":material/lightbulb:")`. 팝오버 안: `card["summary"]`(굵게 아님), 그 아래 `st.page_link("app_pages/concepts.py", label="개념 사전에서 보기", icon=":material/menu_book:")`. 키가 개념 사전에 없으면 건너뜀. 개념이 없으면 아무것도 그리지 않음 |
| `render_stats(qid: int, part_no: int, s: dict) -> None` | 그대로: "통계" 소제목, 지표, 차트(세로축 전환 key `y_{qid}_{i}`), 표 expander, 계산 출처 caption |
| `render_lab(qid: int, lab_key: str) -> None` | **새 블록.** 소제목 "직접 해 보기"(divider="gray") 뒤 `components.labs.render(lab_key, key=f"q{qid}")` |
| `render_markdown_section(title: str, md: str) -> None` | 그대로: 소제목(divider="gray") + `st.markdown(md)`. 배경 지식, 계산 방법에 씀 |
| `render_concepts(keys: list[str], concepts: dict) -> None` | 그대로: "이 질문에 쓰인 개념" 소제목 + 개념 expander + 개념 사전 링크 |
| `render_caveats(md: str) -> None` | 소제목 "주의할 점"(divider="gray") 뒤 `st.warning(md, icon=":material/warning:")`. **문구는 그대로**, 감싸는 상자만 바뀜 |
| `render_sources(sources: list[dict]) -> None` | 그대로: "출처" 소제목 + 목록 |
| `render_paper_bridge(keys: list[str], papers: dict) -> None` | **새 블록.** 아래 형식 |
| `render_next(qid: int, related: list[int], why: dict, qs: dict) -> None` | 그대로: "같이 볼 질문" 소제목, 배지 + tertiary 버튼(key `rel_{r}`, on_click으로 `st.session_state["q"]=str(r)`). **추가**: `why.get(str(r))`가 있으면 버튼 바로 아래 `st.caption(why)` |

`render_paper_bridge` 형식:
```
with st.expander("학술 논문·시정 사례와 연결하기", icon=":material/school:"):
    논문마다:
      **{title}**
      st.caption(who)
      - **물은 것**: {question}
      - **합친 자료**: {data}
      - **방법**: {method}
      - **결과**: {finding}      ← 여러 줄 문자열이면 줄바꿈을 공백 하나로 합친다
      - **이 프로젝트와 다른 점**: {differs}
      논문 사이에 st.divider()
    맨 아래 st.caption("요약 출처: 뉴욕시_311_민원데이터_해외연구사례_종합.docx(2026-11-26). 원문 수치는 다시 확인하지 않았다.")
```
`papers.toml`에 없는 키는 건너뛴다. 남는 논문이 없으면 expander도 그리지 않는다.

## 3. `app_pages/question.py` 정리

맨 위의 문항 선택 부분(URL ↔ 선택 상자 동기화, 이전/다음 버튼)은 **그대로 둔다**. 그 아래를 이 순서로 바꾼다.

```
render_header(qid, q, part, c)
render_concept_chips(c.get("concepts", []), CONCEPTS)        # c가 없으면 []
state.mark_visited(qid, c.get("concepts", []))
if s: render_stats(qid, q["part"], s)
if c.get("lab"): render_lab(qid, c["lab"])
if not c: (지금의 "아직 해설을 만들지 않았다" info) + st.stop()   ← 그대로
background → render_markdown_section("배경 지식", ...)
concepts   → render_concepts(...)
method     → render_markdown_section("계산 방법", ...)
caveats    → render_caveats(...)
sources    → render_sources(...)
papers     → render_paper_bridge(c["papers"], PAPERS)          # PAPERS = qlib.papers()
related    → render_next(qid, c["related"], c.get("related_why", {}), QS)
```
- 각 블록은 지금처럼 해당 키가 있을 때만 그린다.
- `c`가 없는 문항(21·22·48번은 통계 없이 해설만 있고, 해설·통계가 모두 없는 문항은 현재 없음)에서도 예외가 나지 않아야 한다.

## 4. `components/labs.py`

```python
LABS: dict[str, tuple[str, Callable[[str], None]]] = {
    "small_denominator": ("작은 분모의 함정", small_denominator),
    "reporting_bias": ("보고 편향 시뮬레이터", reporting_bias),
}
def render(lab_key: str, key: str) -> None: ...   # 없는 키면 아무것도 안 함. 있으면 LABS[lab_key][1](key)

@st.fragment
def small_denominator(key: str) -> None: ...
@st.fragment
def reporting_bias(key: str) -> None: ...
```
- 두 함수 안의 위젯 key는 모두 `f"{key}_..."`로 시작한다(한 화면에 두 번 나와도 겹치지 않게).
- 차트는 `qlib.chart(spec)`로 그린다(Altair). 새 라이브러리 금지.
- 슬라이더를 움직였을 때 fragment만 다시 실행되어야 한다(전체 `st.rerun()` 금지).

### 4.1 작은 분모의 함정

자료: `qlib.lab("small_denominator")`. `rows`를 DataFrame으로 바꾸는 부분은 `@st.cache_data(ttl="1h", max_entries=2)` 함수로 감싼다.

1. 설명(그대로 쓸 문구):
   > 인구가 아주 적은 Tract는 민원 몇백 건만으로 '1,000명당 민원'이 수만 건으로 치솟는다. 최소 인구 기준을 바꿔 가며 순위가 어떻게 흔들리는지 보자. 기본값 1,000명은 이 프로젝트의 분석 기준이다.
2. 슬라이더 `"최소 인구(명)"`: 0~5,000, step 50, 기본값 `default_min_pop`(1000), key `f"{key}_min"`.
3. 계산: `per_1k = n / pop * 1000`. 남는 Tract = `pop >= 최소 인구` **이고** `pop > 0`. 인구 0명 Tract는 항상 비율 계산에서 뺀다.
4. 지표 3개(`st.metric`, border=True, 가로 배치):
   - "남은 Tract": `f"{남은 수:,}개"`, help `f"전체 {totals.tracts:,}개 중"`
   - "남은 민원": `f"{남은 민원 합:,}건"`, help `f"전체의 {비율:.1f}%"` (전체 = `totals.complaints`)
   - "1,000명당 최댓값": `f"{최댓값:,.0f}건"`, help `f"인구 {그 Tract 인구:,}명, 민원 {n:,}건"`
5. 차트 1 — `kind="barh"`, 제목 `"1,000명당 민원 상위 10개 Tract"`, x `"1,000명당"`, y `"Tract"`. y 값은 `f"{boro} {GEOID[-6:]} · {pop:,}명"`. 1,000명당은 소수 첫째 자리 반올림.
6. 차트 2 — `kind="scatter"`, 제목 `"인구와 1,000명당 민원(로그 축)"`, x `"인구"`, y `"1,000명당"`, color `"구분"`(값 `"포함"`/`"제외"`, `colors={"포함": "#2457a7", "제외": "#c94f6d"}`), `log_x=True`, `log_y=True`. 점은 `pop > 0`이고 `n > 0`인 Tract 전부(로그 축이라 0은 뺀다). 캡션: `"제외된 점(빨강)이 왼쪽 위로 치솟는다. 분모가 작을수록 비율이 불안정하다."`
7. 최소 인구가 기본값이면 `st.caption("기본값 1,000명: 95번 분석과 같은 2,195개 Tract, 3,803,874건이다.")`. 숫자는 문자열로 박지 말고 계산 결과로 채운다.
8. 최소 인구가 0이면 `st.caption("인구 0명인 Tract {k}개는 나눌 수 없어 늘 뺀다.")` (k는 계산값, 지금 84).

### 4.2 보고 편향 시뮬레이터 (가상 자료)

1. 맨 위에 `st.info("가상 자료다. 실제 뉴욕 수치가 아니라, '신고가 적다 = 문제가 적다'는 착각이 예산을 어떻게 비트는지 따라가 보는 모형이다.", icon=":material/science:")`
2. 두 열(`st.columns(2)`): "동네 A", "동네 B". 각 열에 슬라이더 2개
   - `"실제 문제(1,000가구당 건)"`: 0~100, step 1, 기본 A 30 / B 20, key `f"{key}_a_true"`, `f"{key}_b_true"`
   - `"신고율(%)"`: 0~100, step 5, 기본 A 20 / B 60, key `f"{key}_a_rate"`, `f"{key}_b_rate"`
3. 계산: `신고 = 실제 × 신고율 / 100`. 예산 100을 두 방식으로 나눈다: `신고 기준 = 신고 / 신고 합 × 100`, `실제 기준 = 실제 / 실제 합 × 100`. 합이 0이면 `st.warning("두 동네의 값이 모두 0이라 나눌 수 없다.")`만 보이고 끝.
4. 지표 3개: `"동네 A 신고"`(`f"{x:.1f}건"`), `"동네 B 신고"`, `"A가 덜 받는 예산"` = `실제 기준 A − 신고 기준 A` (`f"{x:+.1f}"`, help `"실제 문제에 맞춰 나눌 때와 비교한 차이. 음수면 A가 더 받는다."`)
5. 차트 — `kind="group"`, 제목 `"예산 100을 나누는 두 방식"`, x `"동네"`, y `"예산"`, color `"기준"`, `colors={"실제 문제에 맞춤": "#3a9d6e", "신고에 맞춤": "#e07b39"}`. 값은 소수 첫째 자리.
6. 캡션: `"기본값에서 A는 문제가 더 많은데(30 > 20) 신고가 적어(6 < 12) 예산의 3분의 1만 받는다. 39번(쥐 점검)과 37번(난방)이 이 문제를 실제 자료로 다룬다."` — 기본값일 때만 보인다.

## 5. `app_pages/labs.py` (새 페이지)

```
st.title("체험실")
st.caption("통계 개념을 직접 움직여 본다. 슬라이더를 바꾸면 이 상자만 다시 그려진다.")
for lab_key, (title, _) in labs.LABS.items():
    st.subheader(title, divider="gray")
    labs.render(lab_key, key=f"page_{lab_key}")
    그 체험을 쓰는 문항 링크: content의 lab 키가 같은 문항을 st.page_link(..., query_params={"q": str(qid)})로 가로 배치
```
- 문항 목록은 `qlib.questions()`와 `qlib.content()`로 만든다(파일 직접 읽기 금지).

## 6. `state.py`와 사이드바 진도

```python
CORE = ["data_join", "boundary_overlay", "per_capita", "small_denominator", "did", "reported_vs_occurred"]
def mark_visited(qid: int, concept_keys: list[str]) -> None: ...  # session_state["visited"](set[int]), ["seen_concepts"](set[str])에 추가
def visited() -> set[int]: ...
def seen_concepts() -> set[str]: ...
def render_sidebar(total: int, concepts: dict) -> None: ...
```
`render_sidebar` (모두 `st.sidebar` 안):
- 소제목 `"나의 진도"`
- `st.progress(len(visited()) / total, text=f"{len(visited())} / {total} 문항")`
- `CORE` 개념마다 한 줄: 본 개념이면 `":material/check_circle:"`, 아니면 `":material/radio_button_unchecked:"` 아이콘 + `concepts[key]["title"]`. `st.markdown`으로 그린다(체크박스 위젯 아님).
- `st.caption("진도는 이 브라우저 탭에서만 기억한다. 새로고침하면 처음부터다.")`

`app.py`:
```python
pages = [ ...기존 3개..., st.Page("app_pages/labs.py", title="체험실", icon=":material/science:", url_path="labs") ]
pg = st.navigation(pages)
pg.run()
state.render_sidebar(len(qlib.questions()), qlib.concepts())   # 페이지 실행 뒤에 그려야 방금 본 문항이 반영된다
```

## 7. 테스트 (Cursor가 쓰고 Claude가 실행)

### `tests/test_numbers.py`에 추가: `test_content_extras(qdir)`
- `meta/papers.toml`의 모든 항목에 8개 필드가 있고, `track`은 1~4 정수다.
- 모든 문항의 `papers` 키는 `papers.toml`에 있다. `papers.toml`의 모든 키는 적어도 한 문항이 쓴다.
- `lab` 값은 `{"small_denominator", "reporting_bias"}` 중 하나다.
- `related_why`의 키(문자열)는 모두 그 문항의 `related`에 있는 번호다.

### `tests/test_app_render.py` (AppTest)
도우미: `open_question(qid) -> AppTest` — Phase 1 `benchmark_app.render`와 같은 순서(run → switch_page → query_params → run).

| 테스트 | 확인 |
|---|---|
| `test_all_questions_render` | 1~100번 모두 `at.exception`이 비어 있고 첫 헤더가 `"{qid}. "`로 시작 (`pytest.mark.parametrize`) |
| `test_small_denominator_default` | 74번: key `q74_min` 슬라이더 값 1000. 지표 "남은 Tract" 값 `"2,195개"`, "남은 민원" 값 `"3,803,874건"` |
| `test_small_denominator_zero` | 74번: `q74_min`을 0으로 바꾸고 run → 예외 없음, "남은 Tract" 값 `"2,243개"` (2,327 − 인구 0명 84) |
| `test_reporting_bias_default` | 39번: "A가 덜 받는 예산" 값 `"+26.7"` (실제 기준 60.0 − 신고 기준 33.3) |
| `test_reporting_bias_zero` | 39번: 네 슬라이더를 모두 0으로 → 예외 없음, warning 1개 |
| `test_paper_bridge` | 97번: expander 라벨에 "학술 논문·시정 사례와 연결하기"가 있고, 그 안에 "Kontokosta"가 보인다 |
| `test_related_why` | 95번: caption 중에 `"이 결합으로 임차율과 민원을 비교한다"`가 있다 |
| `test_caveats_text_unchanged` | 95번: warning 본문에 `"좌표가 없는 2.1%"`가 있다 |
| `test_progress_sidebar` | 같은 AppTest에서 95번 → 74번을 차례로 열면 사이드바 progress 텍스트가 `"2 / 100 문항"` |
| `test_labs_page` | 체험실 페이지(`switch_page("app_pages/labs.py")`) 예외 없음, 소제목 2개 |

지표 값은 `at.metric`에서 label로 찾아 `.value`로 비교한다.

## 8. `tools/benchmark_app.py`에 `--labs` 옵션

- `--labs`가 있으면 문항 측정 뒤에 추가로: 74번을 열고 `q74_min` 슬라이더를 500 → 2000으로 바꿔 각 `run()` 시간을 잰다. 39번은 `q39_a_rate`를 40으로 바꿔 잰다.
- 보고서에 "체험 위젯 반응" 표(체험, 조작, 시간(초), 기준 0.5초)를 추가한다.
- 기존 출력 형식은 바꾸지 않는다.

## 완료 조건 (Claude가 확인)

1. `py -3 -m pytest questions/tests -q` → 기존 6개 + `test_content_extras` + `test_app_render`(100문항 포함) 모두 통과.
2. `py -3 -m pytest questions/tests -q --runslow` → 통과(수치 그대로).
3. `py -3 questions/tools/benchmark_app.py --labs --out questions/reports/perf.md` → 예외 0, 문항 렌더링 2초 이내, 체험 반응 0.5초 이내, RSS 500MB 이하.
4. `py -3 -m ruff check questions/components questions/state.py questions/app.py questions/app_pages questions/tests questions/tools questions/qlib.py` → 새로 생긴 오류 0건(qlib.py의 기존 오류는 제외).
5. `git diff questions-app --stat`에 "파일 담당" 표의 파일만 나온다. `questions/data/`는 바뀌지 않았다.
6. 브라우저로 95·74·39·97번과 체험실을 열어 눈으로 확인(Claude).

---

## Cursor CLI 실행 프롬프트

```text
저장소 루트의 SPEC.md(Phase 2)와 .cursorrules를 먼저 읽어 줘.
이번에는 코드만 작성해. 터미널 명령(python, pytest, ruff, pip, git)은 하나도 실행하지 마. 테스트와 커밋은 Claude가 한다.
지금 브랜치는 feat/phase-2이고 그대로 두면 돼(브랜치를 바꾸지 마).
SPEC.md "파일 담당" 표에서 Cursor 담당인 파일만 만들거나 고쳐. 순서:
1) qlib.py에 papers(), lab() 추가
2) components/__init__.py, components/edu_blocks.py
3) components/labs.py (작은 분모, 보고 편향 — 문구와 숫자 형식은 SPEC 그대로)
4) state.py, app.py, app_pages/labs.py
5) app_pages/question.py를 SPEC 3장 순서로 정리 (문항 선택 부분과 위젯 key는 그대로)
6) tests/test_numbers.py에 test_content_extras 추가, tests/test_app_render.py 작성
7) tools/benchmark_app.py에 --labs 옵션
content/*.toml, meta/papers.toml, meta/concepts.toml, data/ 아래 파일은 읽기만 해.
끝나면 바꾼 파일 목록과, SPEC과 다르게 한 부분이나 확신이 없는 부분을 정리해서 알려 줘.
```
