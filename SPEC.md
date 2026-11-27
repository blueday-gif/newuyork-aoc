# SPEC — Phase 4: 코드 위생(ruff 0건), 성능 보고 최종본, 배포 점검

- 작성: Claude(총감독), 2026-11-27
- 계획: `docs/plans/streamlit_ux_master_plan.md` 6장 Phase 4, 7장 체크리스트. 앞 단계 명세는 git 기록에 있다(3A `ec608ec`, 3B `560c8ea`).
- 브랜치: `feat/phase-4` (Claude가 만들어 둠). Cursor는 Claude가 따로 만든 작업 폴더에서 작업한다.
- **작업 방식: Cursor는 코드만 쓴다.** 터미널 명령(python, pytest, ruff, git, pip, curl)을 실행하지 않는다. 계산·테스트·커밋은 Claude가 한다.
- 목표:
  1. `ruff check questions`를 0건으로 만든다. 계산 결과는 **한 글자도 바뀌면 안 된다.**
  2. `reports/perf.md` 최종본을 만든다. 체험 3종 반응과 피크 메모리를 넣는다.
  3. Streamlit Community Cloud 배포 준비를 자동 테스트로 묶는다.
- 실제 배포(share.streamlit.io 로그인과 앱 만들기)는 사용자 계정이 필요하다. Claude가 준비 상태를 확인한 뒤 사용자에게 절차를 안내한다.

## 현재 상태 (Claude, 2026-11-27 확인)

- `ruff check questions`: 46건, 모두 `calc/part01~10.py`에 있다.
  - E501(150자 초과) 36건, F401(안 쓰는 import) 6건, E741(`l` 변수) 2건, F541 1건, E731(lambda 대입) 1건
  - 새로 만든 `elections.py`, `joined.py`, `labs.py`, `fetch_ext.py`, `components/`, `tests/`는 이미 0건이다.
- 앱이 import하는 외부 패키지는 `streamlit`, `pandas`, `altair`뿐이다. `questions/requirements.txt`와 일치한다.
- 앱 자료(`data/`, `content/`, `meta/`)는 약 4MB이고, 모두 git에 들어 있다(`.gitignore`에 걸리지 않음).
- 이 PC에는 Python 3.14만 있다. `ruff.toml`의 `target-version = "py311"`로 3.11 문법만 쓰는지 본다.

## 파일 담당

| 파일 | 담당 | 작업 |
|---|---|---|
| `SPEC.md`, `CLAUDE.md`, `.cursorrules`, `docs/`, `questions/README.md` | Claude | Cursor는 고치지 않음 |
| `questions/calc/part01.py` ~ `part10.py` | Cursor | ruff 오류만 고친다 (1장) |
| `questions/tools/benchmark_app.py` | Cursor | DiD 체험·체험실 페이지 측정 추가 (2장) |
| `questions/tests/test_deploy.py` | Cursor | 신규 (3장) |
| `questions/reports/perf.md` | Claude | 벤치마크 실행 결과 + 배포 점검 절 |
| `questions/data/*.json` | Claude | 1장 검증용으로 다시 만들되, 결과가 같으면 커밋하지 않는다 |
| 그 밖의 모든 파일 | 없음 | 고치지 않음 |

## 1. `calc/part01.py` ~ `part10.py` — ruff 0건, 동작은 그대로

규칙:
- **E501:** 긴 문자열은 괄호 안 **암묵적 문자열 이어 붙이기**로 나눈다(`"앞부분 " "뒷부분"`). 글자, 공백, 문장 부호는 하나도 바꾸지 않는다. 이어 붙인 결과가 원래 문자열과 **정확히 같아야** 한다. 긴 식은 중간 변수로 나누거나 줄을 바꾼다.
- **F401:** 안 쓰는 import를 지운다. 단, 지우기 전에 그 이름을 **다른 모듈이 이 part 모듈에서 가져다 쓰는지** 저장소 전체에서 찾아본다(`from part07 import HPD_KO, has_bbl`, `from part10 import WEATHER, flood` 같은 경우가 있다). 쓰이면 지우지 말고 `# noqa: F401`과 이유를 단다.
- **E741:** `l`을 뜻 있는 이름으로 바꾼다(예: `lisa`, `label`). 그 함수 안의 모든 사용처를 함께 바꾼다.
- **E731:** `name = lambda ...`를 같은 이름의 `def`로 바꾼다. 인자와 반환값은 그대로 둔다.
- **F541:** 자리표시자 없는 f-string의 `f`만 지운다.
- `# noqa`로 덮는 것은 F401(다른 모듈이 쓰는 경우)에만 허용한다. E501을 `noqa`로 덮지 않는다.
- 계산 순서, 열 이름, 반올림, 문구는 바꾸지 않는다. 리팩터링하지 않는다.

Claude 검증:
1. 고치기 전에 커밋된 `data/q001~q100.json`을 따로 보관한다.
2. 고친 뒤 작업 폴더에서 `part01~10.py`를 모두 다시 돌린다.
3. 새 JSON과 보관본을 `computed_at`을 뺀 내용으로 비교한다. 100개 모두 같아야 한다.
4. 다른 파일이 있으면, 고치기 전 코드로도 다시 돌려 원래부터 달랐는지 가린다. 고친 코드 때문이면 Cursor가 되돌린다.

## 2. `tools/benchmark_app.py` — 측정 추가

- `measure_labs()`에 DiD 체험을 더한다. 15번 질문 페이지에서 키 `q15_pre`, `q15_post`, `q15_naive`를 쓴다(키 이름은 `components/labs.py`의 `f"{key}_pre"` 규칙을 따른다).
  - `"이중차분"`, `"앞 기간 → 2022"`: pre를 `"2022"`로 바꾼 뒤 `run()` 한 번
  - `"이중차분"`, `"뒤 기간 → 2023"`: post를 `"2023"`으로 바꾼 뒤 `run()` 한 번
  - `"이중차분"`, `"전후만 비교 켜기"`: toggle을 `True`로 바꾼 뒤 `run()` 한 번
  - select_slider와 toggle을 키로 찾는 도우미를 `_slider`와 같은 꼴로 만든다(`_select_slider`, `_toggle`).
- 체험실 페이지 렌더링을 더한다: 목차 실행 → `switch_page("app_pages/labs.py")` → `run()` 한 번의 시간과 예외 수. 보고서 요약 표에 `| 체험실 페이지 렌더링 | x.xx초 | 2초 이내 |` 한 줄을 넣는다.
- 결합 결과가 있는 문항(`data/joined/`에 파일이 있는 번호)의 렌더링 최대값을 요약 표에 한 줄 넣는다: `| 결합 결과 문항 렌더링 최대 | x.xx초 (n개) | 2초 이내 |`.
- 피크 메모리: 지금처럼 측정 중 `rss_mb()` 최대값을 쓴다. 체험 측정과 체험실 페이지 측정 중 RSS도 최대값에 넣는다.
- 보고서 맨 끝에 `## 배포 점검` 절 자리를 둔다: `"(Claude가 배포 점검 뒤 채운다)"` 한 줄만. Claude가 실행 뒤 손으로 채운다.
- 나머지 출력 형식은 그대로 둔다.

## 3. `tests/test_deploy.py` — 배포 준비 테스트 (신규)

앱이 Streamlit Cloud(리눅스, 원본 자료 없음)에서 돌 수 있는지 정적으로 본다. 외부 파일이나 네트워크를 쓰지 않는다.

```python
QDIR = Path(__file__).resolve().parents[1]
APP_FILES = [QDIR / "app.py", QDIR / "qlib.py", QDIR / "state.py",
             *sorted((QDIR / "components").glob("*.py")), *sorted((QDIR / "app_pages").glob("*.py"))]
LOCAL = {"qlib", "state", "components", "app_pages"}
ALLOWED = {"streamlit", "pandas", "altair"}
```

- `test_app_imports_allowed`: `APP_FILES`를 `ast`로 읽어 최상위 패키지 이름을 모은다(`import x.y` → `x`, `from x.y import z` → `x`, 상대 import는 건너뜀).
  - 모은 이름 중 `sys.stdlib_module_names`에도, `LOCAL`에도 없는 이름은 모두 `ALLOWED` 안에 있어야 한다.
  - 함수 안의 import도 포함한다(`ast.walk`).
- `test_requirements_cover_imports`: `requirements.txt`에서 주석·빈 줄을 뺀 패키지 이름(`>=` 앞부분, 소문자)이 `ALLOWED`와 정확히 같다.
- `test_no_absolute_paths`: `APP_FILES`와 `content/*.toml`, `meta/*` 텍스트에 다음이 없어야 한다.
  - 드라이브 경로(정규식 `[A-Za-z]:[\\/]`)
  - `/Users/`, `/home/`
  - 단, URL(`https?://` 뒤)은 제외한다. 줄 단위로 URL을 먼저 지운 뒤 검사한다.
- `test_app_does_not_read_raw`: `APP_FILES` 텍스트에 `parquet`, `NY311_RAW`, `NY311_EXT`, `geopandas`, `D:/ny311`이 없어야 한다.
- `test_data_files_exact_case`: `meta/questions.json`의 문항 id마다 확인한다. 리눅스는 대소문자를 가리므로, `Path.exists`가 아니라 `os.listdir`로 얻은 실제 이름 집합으로 본다.
  - `content/q{id:03d}.toml`과 `data/q{id:03d}.json`이 그 이름 그대로 있어야 한다.
  - `data/joined/`과 `data/labs/`의 파일 이름도 코드에서 부르는 이름(`small_denominator.json`, `did_containerization.json`)과 정확히 같아야 한다.
- `test_app_data_size`: `data/`, `content/`, `meta/` 합계가 20MB 이하다.
- `test_streamlit_config`: 저장소 루트 `.streamlit/config.toml`이 `tomllib`로 읽히고, `[browser] gatherUsageStats = false`가 있다. `.streamlit/secrets.toml`은 없다.

## 완료 조건 (Claude가 확인)

1. `py -3 -m ruff check questions` → 0건(`All checks passed!`).
2. 1장 검증: `data/q001~q100.json` 100개가 `computed_at`을 빼고 모두 같다.
3. `py -3 -m pytest questions/tests -q --runslow` → 모두 통과. 기준 수치도 그대로여야 한다.
4. `py -3 questions/tools/benchmark_app.py --labs --out questions/reports/perf.md` → 모든 문항 2초 이내, 체험 3종 0.5초 이내, 피크 RSS 500MB 이하.
5. 깨끗한 가상 환경 점검(Claude):
   - `py -3 -m venv` 새 환경에 `questions/requirements.txt`만 설치한다.
   - `streamlit run questions/app.py --server.headless true`를 띄운다.
   - `/_stcore/health`가 `ok`를 돌려주는지 본다.
   - 브라우저로 목차, 1·17·95·97번, 체험실을 연다.
6. `perf.md`의 "배포 점검" 절을 채운다: 깨끗한 환경 결과, Python 버전 권장, 배포할 브랜치, 사용자가 할 단계.

## 배포 때 사용자가 할 일 (Claude가 마지막에 안내)
1. share.streamlit.io에 GitHub 계정으로 로그인한다.
2. Create app을 고르고 다음을 지정한다.
   - 저장소 `blueday-gif/newuyork-aoc`
   - 브랜치: Claude가 권하는 브랜치
   - 메인 파일 `questions/app.py`
   - Advanced settings의 Python 버전: 3.12 또는 3.13
3. Deploy를 누르고 주소를 Claude에게 알려 준다. Claude가 그 주소로 확인한다.

---

## Cursor CLI 실행 프롬프트 (Claude가 헤드리스로 실행)

```text
작업 폴더는 Claude가 알려 주는 git worktree다. 그 폴더 안의 파일만 읽고 고쳐.
저장소 루트의 SPEC.md(Phase 4)와 .cursorrules를 먼저 읽어 줘.
코드만 작성해. 터미널 명령(python, py, pytest, ruff, pip, git, curl)은 하나도 실행하지 마. 계산·테스트·커밋은 Claude가 한다.
SPEC.md "파일 담당" 표에서 Cursor 담당인 파일만 고쳐. 순서:
1) calc/part01.py ~ part10.py의 ruff 오류 46건(SPEC 1장 규칙. 문자열은 나눠도 결과가 정확히 같아야 하고, 계산은 바꾸지 마)
2) tools/benchmark_app.py 측정 추가  3) tests/test_deploy.py 신규
ruff 오류 위치는 아래 목록이다(Claude가 실행한 결과).
끝나면 바꾼 파일 목록과, noqa를 단 곳과 이유, 확신이 없는 부분을 정리해서 알려 줘.
```
