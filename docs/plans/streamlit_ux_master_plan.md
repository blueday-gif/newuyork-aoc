# 4. Streamlit UX·교육적 설계 확장 및 성능 최적화 마스터 플랜 (v2: 이 저장소에 맞춤)

- **협업 모델:** Claude (총감독 / 주 에이전트) × Cursor CLI (실행 / 보조 에이전트)
- **대상:** 이 저장소(`newyork`)의 질문 앱 `questions/` (1~10부 100문항) + 10편 핵심 논문 확장
- **최종 목표:** 1년치 311 민원 396만 건(분석 대상 380만 건)에서 뽑은 결과를 2초 안에 보여 주고, 사용자가 변수를 직접 움직이며 통계·인과추론·공간결합을 익히는 교육용 앱 완성

> 원본: Gemini 공유 대화(https://gemini.google.com/share/51327d355e1b785f1714f279d8752aae), 2026-11-27 저장. 원본 사본은 `C:\Users\user\Downloads\streamlit_ux_master_plan.md`.
> v2 수정(2026-11-27, Claude): 원본은 새 프로젝트를 가정했다. 이 판은 실제 코드·데이터를 확인하고 경로, 전제, 일정을 고쳤다. 바뀐 내용은 0장에 모았다.

---

## 0. 원본 대비 바뀐 점 (실측 근거)

| 원본 전제 | 실제 (2026-11-27 확인) | 이 판의 결정 |
|---|---|---|
| 앱이 실행 중에 380만 행을 읽어서 느리다 | 앱은 계산 결과 JSON(`questions/data/q###.json`, 97개, 총 3.2MB)만 읽는다. 311 원본(392MB)은 저장소 밖 `D:\ny311\...`에 있고 Streamlit Cloud에는 올라가지 않는다 | 성능 병목의 원인이 다르다. DuckDB 전면 도입은 **보류**한다(4장) |
| 로딩 속도를 새로 확보해야 한다 | AppTest 측정: 질문 페이지 1.2~2.1초(처음 한 번은 import 포함 5.3초), 예외 0, Python 힙 최대 75MB | Phase 1은 "기준선을 기록하고 테스트로 묶기"로 줄인다 |
| `data/agg/`에 사전 집계 parquet를 만든다 | `questions/calc/partNN.py`가 이미 문항별 사전 집계(JSON)를 만든다 | 사전 집계는 지금 방식을 유지한다. 체험실용 자료만 `questions/data/labs/`에 추가한다 |
| `pages/q95_acs.py`처럼 문항마다 페이지 파일 | `questions/app_pages/question.py` 한 개가 100문항을 그린다. 해설은 `content/q###.toml`, 통계는 `data/q###.json` | 문항별 페이지 파일을 만들지 않는다. 템플릿 1개 + 데이터 방식을 유지한다 |
| 6대 교육 블록을 새로 만든다 | `question.py`에 이미 있다: 한 줄 답, 통계, 배경 지식, 개념, 계산 방법, 주의할 점, 출처, 같이 볼 질문 | 새로 만들지 않고 함수로 **분리**한다. 새 블록은 팝오버·논문 연결·체험실만 |
| `glossary.json` 개념 20종 초안 | `questions/meta/concepts.toml`에 개념 카드 58장 | 이 파일을 개념 사전으로 쓴다. 필요하면 `formula`, `analogy` 키를 추가한다 |
| `questions_graph.json` | 각 toml의 `related = [..]`가 이미 연결 정보다. "왜 이어서 보나" 해설만 없다 | toml에 `related_why`를 추가한다(2장) |
| 위도·경도 float32 변환 | `nyc311_point_geoid.parquet`(388만 행)는 `unique_key`, `GEOID` 두 열뿐이다. 좌표는 원본에만 있다 | 앱 자료에는 해당이 없다. 원본에서 계산할 때만 적용한다 |
| 1단계로 DiD 체험(쓰레기통 의무화) | 311 원본은 2025-11-01~2026-10-31, 12개월뿐이다(파일 이름은 `2020_present`이지만 내용은 1년치). 의무화 구역·시점 자료도 없다 | 체험 3(DiD)은 **자료 확보 전까지 보류**한다. 체험 1·2를 먼저 만든다 |
| 10편 논문 결합(PLUTO, HPD, RGB, DOHMH, FloodNet, FEMA, MTA 등) | 실제로 붙인 외부 자료는 ACS 2024 5개년과 TIGER Tract 경계뿐이다 | Phase 3에 "외부 자료 확보" 단계를 넣고, 자료별로 진행 여부를 결정한다 |
| 테스트는 기존 수치와 100% 일치 | 기준 수치는 확인됨: 97.9%(3,880,604 / 3,963,959), Tract 2,195개, 민원 3,803,874건, 브롱크스 주거 183.0·소음 152.8(원본은 153으로 반올림해 적음) | 테스트는 JSON 수치 검사(빠름)와 원본 재계산 검사(느림, 원본이 있을 때만) 두 층으로 나눈다 |
| 작은 분모 예: 인구 12명, 민원 679건 → 56,583건 | 맞다: Tract 36081056100(퀸스), `data/processed/nyc311_tract_complaints.csv` | 체험 1의 고정 예시로 쓴다 |
| 원본 경로 | `calc/common.py`의 기본값 `D:/project-ny311/...`는 없는 경로다. 실제 파일은 `D:\ny311\data\processed\311_requests_2020_present.parquet`. `data/external/SOURCE.txt`도 틀렸다 | Phase 1에서 고친다 |
| 개발 도구 | Python 3.14, streamlit 1.67, altair 6.3, duckdb 2.0, pydeck 0.9 설치됨. pytest, ruff, plotly, h3 없음 | 차트는 Altair를 계속 쓴다. pytest·ruff는 개발용 requirements에 추가한다 |

---

## 1. 에이전트 역할 분담 및 협업 아키텍처

설계·통계 검증은 Claude가, 구현·반복 실행·테스트는 Cursor CLI가 맡는다.

### 1.1 역할 정의 (R&R)

| 구분 | Claude (총감독 / 주 에이전트) | Cursor CLI (실행 / 보조 에이전트) |
|---|---|---|
| 핵심 미션 | 아키텍처 설계, 교육 UX 기획, 통계 수식·해석 검수, 최종 Diff 리뷰 | 파이썬 코드 작성, 계산·최적화 구현, UI 리팩토링, 일괄 수정 |
| 주요 산출물 | `SPEC.md`, `docs/plans/`, 개념 카드·해설 문구(`concepts.toml`, `content/*.toml`), 리뷰 의견 | `questions/components/`, `questions/calc/`, `questions/tests/`, `questions/tools/` |
| 의사결정 권한 | 캐싱 전략, 라이브러리 채택, 통계적 타당성 승인, 외부 자료 채택 | 스펙 안에서의 구현 방식, 에러 디버깅, 린트·포맷 |
| 금지 사항 | 100개 파일 단순 반복 수정을 직접 하기 | 통계 기준(인구 1,000명 미만 제외 등), 해설·주의 문구를 임의로 바꾸기 |

### 1.2 협업 워크플로우 (Spec → Execute → Verify)

```
[1. 기획 및 명세 (Claude)]
└─ 문제 정의 → SPEC.md 갱신 → Cursor CLI 실행 프롬프트 발급
        ↓
[2. 구현 및 실행 (Cursor CLI)]
└─ questions-app에서 feat/phase-N 브랜치 생성 → 코드 작성 → pytest·벤치마크 실행 → 로그 보고
        ↓
[3. 검증 및 통합 (Claude)]
└─ Git Diff 리뷰 + 성능(로딩 시간·메모리) + 통계 정합성 확인 → questions-app에 병합 또는 수정 지시
```

---

## 2. 목표 디렉토리 및 모듈 아키텍처

앱 루트는 `questions/`다. 저장소 루트에는 에이전트 규칙과 명세만 둔다. `dashboard/`, `analysis/`, `reports/stories/`는 이 계획의 범위 밖이다.

```
newyork/
├── CLAUDE.md                     # [신규] Claude 총감독용 컨텍스트·리뷰 기준
├── .cursorrules                  # [신규] Cursor CLI 실행 규칙
├── SPEC.md                       # [신규] 진행 중인 Phase의 명세
├── docs/plans/                   # 이 문서 (마스터 플랜)
├── data/processed/               # 기존: ACS, Tract 집계, 민원-GEOID 연결 (앱은 직접 읽지 않음)
└── questions/                    # 질문 앱 (Streamlit Cloud 시작 파일: questions/app.py)
    ├── app.py                    # 기존: 진입점·라우팅 → 사이드바 진도 트래커 추가
    ├── qlib.py                   # 기존: 자료 읽기(cache_data), Altair 차트 팩토리
    ├── app_pages/
    │   ├── index.py              # 기존: 목차
    │   ├── question.py           # 기존: 문항 템플릿 → components 함수 호출로 얇게
    │   ├── concepts.py           # 기존: 개념 사전
    │   └── labs.py               # [신규] 체험실 모음 페이지
    ├── components/               # [신규]
    │   ├── edu_blocks.py         # question.py의 블록을 함수로 분리 + 팝오버·논문 연결
    │   └── labs.py               # @st.fragment 체험 위젯 (작은 분모, 보고 편향)
    ├── state.py                  # [신규] 진도·개념 체크리스트 (session_state)
    ├── meta/
    │   ├── questions.json        # 기존: 문항·한 줄 답 (build_meta.py가 생성)
    │   ├── concepts.toml         # 기존: 개념 카드 58장 = 개념 사전
    │   └── papers.toml           # [신규] 10편 논문 요약 (가설, 방법, 이 프로젝트와의 차이)
    ├── content/q###.toml         # 기존: 해설 → related_why, papers 키 추가
    ├── calc/
    │   ├── common.py             # 기존: 공통 도구 (RAW 경로 수정)
    │   ├── part01~10.py          # 기존: 문항별 사전 집계 → data/q###.json
    │   ├── labs.py               # [신규] 체험실 자료 → data/labs/*.json
    │   └── papers_ext.py         # [신규, Phase 3] 논문 미니 재현 (외부 자료 확보 뒤)
    ├── data/
    │   ├── q###.json             # 기존: 문항 통계 97개
    │   └── labs/                 # [신규] 체험실 자료 (수십 KB)
    ├── tools/
    │   └── benchmark_app.py      # [신규] AppTest로 100문항 렌더링 시간·예외 측정
    ├── tests/                    # [신규]
    │   ├── conftest.py
    │   ├── test_numbers.py       # 기준 수치 회귀 (JSON, 빠름)
    │   ├── test_recompute.py     # 원본 재계산 대조 (느림, 원본 있을 때만)
    │   └── test_app_render.py    # 100문항 AppTest 렌더링
    ├── reports/perf.md           # [신규] 성능 기준선·결과
    ├── requirements.txt          # 기존: 배포용
    └── requirements-dev.txt      # [신규] pytest, ruff
```

### 2.1 content toml에 추가할 키 (기존 키는 그대로)

```toml
related = [16, 33, 23]                       # 기존
related_why = { 16 = "결합한 Tract로 임차율을 비교한다", 33 = "..." }   # [신규] 한 줄 해설, 없으면 생략
papers = ["moda_illegal_conversion"]         # [신규] meta/papers.toml 키
lab = "small_denominator"                    # [신규] 이 문항에 붙일 체험실 키
```

---

## 3. Streamlit UX 및 교육적 설계 확장 명세

현재 문항 화면 순서(한 줄 답 → 통계 → 배경 지식 → 개념 → 계산 방법 → 주의할 점 → 출처 → 같이 볼 질문)를 표준 템플릿으로 고정하고, 직접 만져 보는 요소를 더한다.

### 3.1 공통 교육 블록 (`questions/components/edu_blocks.py`)

`question.py`에 있는 블록을 함수로 옮기고, 화면 결과는 바뀌지 않아야 한다(리팩토링). 새 기능은 ★ 표시.

| 함수 | 현재 위치 | 내용 |
|---|---|---|
| `render_header(q, part)` | question.py 배지·제목·한 줄 답 | 태그 배지, 부 제목, 한 줄 답 카드, 결합 상태(`join_status`) |
| `render_stats(qid, s)` | question.py 통계 | 지표 카드, 차트, 표(expander) |
| `render_concepts(keys, concepts)` | question.py 개념 | 개념 카드 expander. ★ 본문 안 용어용 `render_concept_popover(key)` 추가(`st.popover`) |
| `render_text_section(title, md)` | 배경·방법·주의·출처 | 배경 지식, 계산 방법, 출처 |
| `render_caveats(md)` | question.py 주의할 점 | ★ 경고 톤 카드로 강조(문구는 그대로) |
| `render_paper_bridge(keys)` | ★ 없음 | `st.expander("학술 논문·시정 사례와 연결하기")`에 `papers.toml` 요약 |
| `render_next(related, why)` | question.py 같이 볼 질문 | ★ `related_why` 한 줄 해설 표시 |

### 3.2 `@st.fragment` 통계 체험실 (`questions/components/labs.py`)

| 체험 | 자료 | 상태 |
|---|---|---|
| 1. 작은 분모의 함정 (74·95번) | `nyc311_tract_complaints.csv`의 Tract 2,327개 → `data/labs/small_denominator.json`. 최소 인구 슬라이더(0~5,000, 기본 1,000)에 따라 제외 Tract 수, 남은 민원 수, 1,000명당 민원 상위 5개가 바뀐다. 기본값에서 2,195개·3,803,874건이 나와야 한다. 고정 예시: 인구 12명, 679건 → 56,583건 | Phase 2 |
| 2. 보고 편향 시뮬레이터 (39번·논문 5·6) | 가상 자료. 실제 문제 발생률과 신고율 슬라이더를 따로 두고, "신고가 적다 = 문제가 적다"는 착각이 배분을 어떻게 비트는지 보여 준다. 가상 자료라는 표시를 반드시 붙인다 | Phase 2 |
| 3. DiD 정책 효과 (논문 7) | 처치 전 기간이 있는 311 자료(2년 이상)와 의무화 구역·시점 자료가 필요하다. 지금은 없다 | **보류**: Phase 3 자료 확보 결과에 따라 결정 |

### 3.3 사이드바 학습 진도 (`questions/state.py`)

- `st.session_state`에 본 문항 번호와 익힌 개념 키를 기록하고, 사이드바에 "n / 100 문항" 진행 막대를 보여 준다.
- 개념 키는 `concepts.toml`의 실제 키를 쓴다: `data_join`, `boundary_overlay`(공간결합), `per_capita`(비율 정규화), `small_denominator`, `did`, `reported_vs_occurred`(보고 편향).
- 한계: session_state는 새로고침하면 사라진다. 이 사실을 사이드바에 작게 적는다. 영구 저장(로그인, DB)은 이 계획의 범위 밖이다.

---

## 4. 성능 기준과 최적화 원칙

### 4.1 데이터 계층

- **원칙 1 (사전 집계, 유지):** 앱은 원본 311을 읽지 않는다. 계산은 로컬에서 `calc/`가 하고, 앱은 `data/*.json`만 읽는다. 원본은 Streamlit Cloud에 없으므로 이 원칙은 선택이 아니라 필수다.
- **원칙 2 (DuckDB, 보류):** 앱 실행 자료가 3.2MB라 지금은 이점이 없다. 체험실이 민원 1건 단위 필터를 필요로 하게 되면 그때 `calc/` 쪽(로컬 계산)에서 먼저 도입한다. 채택은 Claude가 결정한다.
- **원칙 3 (타입):** `calc/common.py`는 이미 반복 문자열을 `category`로 바꾼다. 좌표를 쓰는 계산을 새로 만들 때만 float32를 쓴다.

### 4.2 캐싱 및 부분 렌더링

| 대상 | 적용 | 현재 |
|---|---|---|
| 문항 JSON·toml | `@st.cache_data(ttl, max_entries)` | qlib.py에 적용됨(meta·concepts는 max_entries 없음, 파일 2개라 무관) |
| 체험실 자료 | `@st.cache_data(ttl="1h", max_entries=10)` | 신규 |
| 슬라이더·선택에 반응하는 체험 영역 | `@st.fragment` | 신규. 응답 0.5초 이내 |
| GeoJSON 경계(지도를 넣을 경우) | `@st.cache_resource` | 지도는 Phase 3에서 필요할 때만 |

### 4.3 시각화

- 차트는 Altair(`qlib.chart`)를 계속 쓴다. Plotly는 설치돼 있지 않고 새로 들일 이유가 없다.
- 지도가 필요하면 Tract 단위 집계만 그린다(점 380만 개 금지). H3는 설치돼 있지 않으므로 쓰지 않는다.
- 무거운 표는 `st.expander` 안에 둔다(현재 그렇게 돼 있음).

### 4.4 기준 수치

| 항목 | 기준 | 현재(2026-11-27) |
|---|---|---|
| 질문 페이지 첫 렌더링 | 2초 이내 | 1.2~2.1초(AppTest, 목차 + 질문 두 번 실행 포함). 첫 import 5.3초 |
| 체험 위젯 반응 | 0.5초 이내 | 아직 없음 |
| 피크 메모리 | 500MB 이하 | Python 힙 75MB(프로세스 RSS는 Phase 1에서 측정) |

---

## 5. 10부 결합 분석 및 10편 논문 매핑

외부 자료는 하나도 확보하지 않은 상태다. 각 트랙은 Phase 3 시작 때 자료를 구할 수 있는지 먼저 확인하고, Claude가 진행 여부를 정한다.

| 트랙 | 연계 문항 / 주제 | 필요한 결합 자료 (키) | 자료 상태 | 핵심 기법 | UX 요소 |
|---|---|---|---|---|---|
| 1. 정제·프로파일링 | 94번 등 + 논문 1·2 | 311 + 부동산 가격 (ZIP / Tract) | 311 있음, 가격 없음 | DST 오류 탐지, K-Means | 음수 처리시간 사례, 동네 지문 레이더 |
| 2. 임대차·주거 | 95·97·98번 + 논문 3·4 | PLUTO, HPD 위반, RGB 목록 (BBL) | ACS만 있음. 311 HPD 민원의 BBL 보유율은 98번에 계산됨 | 부스팅 분류, 과소신고 잔차 | 예측 확률 vs 실제 신고 갭 |
| 3. 보고 편향·인과 | 39·97·99번 + 논문 5·6·7 | DOHMH 쥐 점검, 가로수 센서스, 의무화 구역·시점, 2년 이상 311 | 없음 | 선택 편향, DiD | 보고 편향 슬라이더(가상 자료로 먼저), DiD 차트(보류) |
| 4. 센서·NLP | 96·100번 + 논문 8·9·10 | NOAA, FloodNet, FEMA, MTA (좌표·시간) | 없음 | 시공간 동기화, 텍스트 분류 | 폭우 시점 센서 vs 311 타임랩스 |

---

## 6. 단계별 실행 로드맵

각 Phase: Claude 명세(`SPEC.md`) → Cursor 실행 → Claude 검증.

### Phase 1: 기준선·테스트·환경 정리

- **목표:** 지금 성능과 기준 수치를 테스트로 묶어, 이후 리팩토링이 숫자를 바꾸지 않게 한다. 체험 1의 자료를 만든다.
- **Claude:** `SPEC.md` Phase 1 작성 (완료, 2026-11-27).
- **Cursor 산출물:** `questions/requirements-dev.txt`, `questions/ruff.toml`, `questions/tests/{conftest,test_numbers,test_recompute}.py`, `questions/tools/benchmark_app.py`, `questions/reports/perf.md`, `questions/calc/labs.py`, `questions/data/labs/small_denominator.json`, `calc/common.py`·`data/external/SOURCE.txt` 원본 경로 수정.
- 실행 프롬프트는 `SPEC.md` 맨 끝에 있다.

### Phase 2: 교육 블록 분리와 체험실

- **목표:** `question.py`를 `components/edu_blocks.py` 호출로 얇게 만들고(화면 동일), 팝오버·진도·체험 1·2를 넣는다.
- **Claude:** `meta/papers.toml` 초안, 체험 2의 가상 자료 설계, 체험실을 붙일 문항과 `related_why` 문구.
- **Cursor:** `components/edu_blocks.py`, `components/labs.py`, `app_pages/labs.py`, `state.py`, `question.py` 리팩토링, `tests/test_app_render.py`.

### Phase 3: 10부 확장과 외부 자료

> 2026-11-27 갱신: Phase 2 완료(421a982). 자료 조사 결과 NOAA, HPD 위반, DOHMH 쥐 점검, PLUTO, FloodNet은 공개 API로 받을 수 있고,
> RGB 안정화 목록·ED별 개표·의무화 구역·SONYC는 공개 데이터가 없다. 그래서 Phase 3을 둘로 나눈다.
> - **3A**(SPEC.md): 자료 6종 + NOAA 수집, 7·57·58·72·75·96·97·100번 결합 결과(`questions/data/joined/`)
> - **3B**: Claude가 의무화 정책 시점·ED 개표 자료를 조사한 뒤 DiD 체험과 17·99번 결정
>
> 2026-11-27 갱신(3B 조사): 3A는 `questions-app`에 합쳤다(048383b).
> - 의무화 시점: 2024-11-12, 1~9세대 건물 전역. 10세대 이상은 2032년까지 단계 확대이고 M9·BK2만 먼저 했다.
> - 그래서 건물 크기로 처치군과 대조군을 나눈 DiD 체험을 **진행**한다(311 `Rat Sighting` 2021~2025-08).
> - ED 개표: 선관위 CSV와 DCP 경계 25c를 쓴다. 17·99번을 **진행**한다.
> - 명세: SPEC.md(Phase 3B).

- **목표:** 외부 자료를 확보할 수 있는 트랙부터 결합하고, 95~100번에 논문 연결과 체험실을 붙인다.
- **Claude:** 트랙별 자료 확보 가능성 조사 → 채택 결정, `papers_ext.py`의 통계 설계(분모, 비교 집단), DiD 진행 여부 결정.
- **Cursor:** 채택된 자료의 수집·결합 스크립트, `calc/papers_ext.py`, 회귀 테스트 추가.

### Phase 4: 통합 테스트·성능 보고·배포 점검

- **목표:** 100문항과 체험실 전체 렌더링 테스트, `reports/perf.md` 최종본, `ruff check` 0건, Streamlit Cloud 배포 확인.
- 2026-11-27: 3B까지 `questions-app`에 합침(470f00a). 명세는 SPEC.md(Phase 4).
  - 실제 배포는 사용자 계정으로 한다.
  - ruff 정리는 계산 결과 100개 JSON이 같은지로 검증한다.
- **Claude:** 성능 보고 검수, 배포 승인.

---

## 7. 품질 검증 체크리스트 (Definition of Done)

- [ ] **통계 정합성:** `pytest questions/tests`가 통과하는가? 기준 수치(97.9%, Tract 2,195개, 민원 3,803,874건, 브롱크스 주거 183.0·소음 152.8)가 그대로인가?
- [ ] **응답 속도:** 질문 페이지 첫 렌더링 2초 이내, 체험 위젯 반응 0.5초 이내인가?
- [ ] **메모리:** 피크 500MB 이하인가?
- [ ] **교육적 완결성:** 개념, 주의할 점, 같이 볼 질문이 빠짐없이 연결되는가? 가상 자료에는 가상이라는 표시가 있는가?
- [ ] **코드 위생:** 새 코드에 절대 경로가 없는가(원본 경로는 `NY311_RAW` 환경 변수)? `ruff check questions`와 AppTest가 통과하는가?

---

## 8. 에이전트 운영 규칙

규칙 원문은 저장소 루트의 `CLAUDE.md`, `.cursorrules`에 있다. 이 문서와 다르면 그 두 파일이 우선한다.
