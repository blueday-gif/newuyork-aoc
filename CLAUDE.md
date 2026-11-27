# CLAUDE.md — 총감독 컨텍스트 (NYC 311 질문 앱)

## 프로젝트
- 뉴욕시 311 민원(2025-11-01~2026-10-31, 3,963,959건)과 ACS 2024 5개년을 Census Tract로 결합한 분석 저장소.
- 지금 진행 중인 작업: 질문 앱 `questions/`(100문항 Streamlit)의 교육 UX·성능 확장.
  - 계획: `docs/plans/streamlit_ux_master_plan.md` (v2)
  - 현재 단계 명세: `SPEC.md`
- 범위 밖(이 계획에서 건드리지 않음): `dashboard/`, `analysis/`, `reports/stories/`, `outputs/`, `scripts/`.

## 역할
- Claude: 설계, 통계 타당성 검증, 교육 UX 기획, `SPEC.md`·해설 문구 작성, Cursor 작업 지시와 Diff 리뷰.
- Cursor CLI: `SPEC.md`에 적힌 파일의 구현·실행·테스트. 규칙은 `.cursorrules`.
- Claude는 100개 파일을 하나씩 고치는 반복 작업을 직접 하지 않고 Cursor에 넘긴다.
- 두 에이전트가 같은 파일을 동시에 고치지 않는다. 각 Phase에서 누가 어떤 파일을 쓰는지는 `SPEC.md`의 "파일 담당" 표를 따른다.

## 앱 구조 (questions/)
- 앱은 원본 311을 읽지 않는다. `calc/partNN.py`가 로컬에서 계산해 `data/q###.json`에 저장하고, 앱은 그 JSON과 `content/q###.toml`(해설), `meta/`(문항·개념)만 읽는다.
- 원본 311: `D:\ny311\data\processed\311_requests_2020_present.parquet` (392MB, 이름과 달리 1년치). 경로는 환경 변수 `NY311_RAW`.
- 문항 화면은 `app_pages/question.py` 하나가 100문항을 그린다. 문항별 페이지 파일을 만들지 않는다.
- 배포: Streamlit Community Cloud, 시작 파일 `questions/app.py`, 의존성 `questions/requirements.txt`.

## 기준 수치 (바뀌면 안 됨)
- 좌표로 Tract를 찾은 민원 97.9% (3,880,604 / 3,963,959)
- 분석 대상 Tract 2,195개 (인구 1,000명 이상, 전체 2,327개)
- 분석에 쓴 민원 3,803,874건
- 95번 브롱크스 1,000명당 주거환경 183.0, 소음 152.8
- 작은 분모 예시: Tract 36081056100, 인구 12명, 민원 679건 → 1,000명당 56,583건

## 리뷰 체크포인트
1. 위 기준 수치가 그대로인가? `py -3 -m pytest questions/tests`가 통과하는가?
2. 질문 페이지 첫 렌더링 2초 이내, 체험 위젯 반응 0.5초 이내, 피크 메모리 500MB 이하인가?
3. 통계 개념(결합, 공간결합, 작은 분모, 보고 편향, DiD)을 비전공자가 이해할 수 있게 설명했는가? 가상 자료에 가상이라고 표시했는가?
4. 해설·주의 문구, 인구 1,000명 기준, 결측 처리가 명세 없이 바뀌지 않았는가?
5. Cursor에 넘길 때는 파일명, 함수 시그니처, 통과해야 할 pytest 조건을 적는다.

## 실행 습관
- Python은 `py -3`(3.14)로 실행하고 `-I`를 붙이지 않는다(붙이면 dateutil을 못 찾는다).
- 앱 실행: 저장소 루트에서 `py -3 -m streamlit run questions/app.py`.
- 작업 브랜치: `questions-app`에서 `feat/phase-N`을 만들고, 검증 뒤 `questions-app`에 합친다.
