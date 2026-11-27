"""질문 페이지 렌더링 시간·예외·메모리를 AppTest로 잰다.
실행(저장소 루트에서):
  py -3 questions/tools/benchmark_app.py                         # 1~100번
  py -3 questions/tools/benchmark_app.py --ids 1 95 100          # 일부
  py -3 questions/tools/benchmark_app.py --labs                  # 체험 위젯 반응 포함
  py -3 questions/tools/benchmark_app.py --out questions/reports/perf.md
문항마다 새 AppTest로 목차를 한 번 실행한 뒤 질문 페이지로 옮겨 두 번째 run()의 시간을 잰다.
맨 처음 한 번(모듈 import 포함)은 콜드 스타트로 따로 적는다.
"""
import argparse
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import altair
import psutil
import streamlit
from streamlit.testing.v1 import AppTest

QDIR = Path(__file__).resolve().parents[1]
APP = QDIR / "app.py"
LIMIT_SEC, LIMIT_MB, LAB_LIMIT_SEC = 2.0, 500, 0.5


def rss_mb() -> float:
    return psutil.Process().memory_info().rss / 1e6


def joined_qids() -> set[int]:
    return {int(p.stem[1:]) for p in (QDIR / "data" / "joined").glob("q*.json")}


def render(qid: int) -> dict:
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    at.switch_page("app_pages/question.py")
    at.query_params["q"] = str(qid)
    t = time.perf_counter()
    at.run()
    sec = time.perf_counter() - t
    head = at.header[0].value if at.header else ""
    return {"qid": qid, "sec": sec, "exceptions": len(at.exception), "header_ok": head.startswith(f"{qid}. "), "rss": rss_mb()}


def _slider(at: AppTest, key: str):
    for s in at.slider:
        if s.key == key:
            return s
    raise KeyError(key)


def _select_slider(at: AppTest, key: str):
    for s in at.select_slider:
        if s.key == key:
            return s
    raise KeyError(key)


def _toggle(at: AppTest, key: str):
    for s in at.toggle:
        if s.key == key:
            return s
    raise KeyError(key)


def measure_labs() -> list[dict]:
    """체험 위젯 조작 뒤 run() 한 번의 시간을 잰다."""
    rows = []

    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    at.switch_page("app_pages/question.py")
    at.query_params["q"] = "74"
    at.run()
    _slider(at, "q74_min").set_value(500)
    t = time.perf_counter()
    at.run()
    rows.append({"name": "작은 분모", "action": "최소 인구 → 500", "sec": time.perf_counter() - t, "rss": rss_mb()})
    _slider(at, "q74_min").set_value(2000)
    t = time.perf_counter()
    at.run()
    rows.append({"name": "작은 분모", "action": "최소 인구 → 2000", "sec": time.perf_counter() - t, "rss": rss_mb()})

    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    at.switch_page("app_pages/question.py")
    at.query_params["q"] = "39"
    at.run()
    _slider(at, "q39_a_rate").set_value(40)
    t = time.perf_counter()
    at.run()
    rows.append({"name": "보고 편향", "action": "A 신고율 → 40", "sec": time.perf_counter() - t, "rss": rss_mb()})

    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    at.switch_page("app_pages/question.py")
    at.query_params["q"] = "15"
    at.run()
    _select_slider(at, "q15_pre").set_value("2022")
    t = time.perf_counter()
    at.run()
    rows.append({"name": "이중차분", "action": "앞 기간 → 2022", "sec": time.perf_counter() - t, "rss": rss_mb()})
    _select_slider(at, "q15_post").set_value("2023")
    t = time.perf_counter()
    at.run()
    rows.append({"name": "이중차분", "action": "뒤 기간 → 2023", "sec": time.perf_counter() - t, "rss": rss_mb()})
    _toggle(at, "q15_naive").set_value(True)
    t = time.perf_counter()
    at.run()
    rows.append({"name": "이중차분", "action": "전후만 비교 켜기", "sec": time.perf_counter() - t, "rss": rss_mb()})
    return rows


def measure_labs_page() -> dict:
    """체험실 페이지 렌더링 한 번."""
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    at.switch_page("app_pages/labs.py")
    t = time.perf_counter()
    at.run()
    return {"sec": time.perf_counter() - t, "exceptions": len(at.exception), "rss": rss_mb()}


def ruff_count() -> str:
    try:
        r = subprocess.run([sys.executable, "-m", "ruff", "check", str(QDIR), "--statistics", "--quiet"],
                           capture_output=True, text=True, encoding="utf-8")
    except OSError as e:
        return f"실행 못 함({e})"
    lines = [x for x in r.stdout.splitlines() if x.strip()]
    if r.returncode == 0:
        return "0건"
    return f"{sum(int(x.split()[0]) for x in lines if x.split()[0].isdigit())}건 (" + ", ".join(x.split()[1] for x in lines) + ")"


def report(
    rows: list[dict],
    cold: float,
    rss0: float,
    rss_max: float,
    lab_rows: list[dict] | None = None,
    labs_page: dict | None = None,
) -> str:
    secs = sorted(r["sec"] for r in rows)
    p95 = secs[min(len(secs) - 1, round(0.95 * (len(secs) - 1)))]
    bad = [r for r in rows if r["exceptions"] or not r["header_ok"]]
    ok = sum(r["sec"] <= LIMIT_SEC for r in rows)
    slow = sorted(rows, key=lambda r: -r["sec"])[:10]
    jids = joined_qids()
    joined = [r for r in rows if r["qid"] in jids]
    out = [
        "# 질문 앱 성능 측정",
        "",
        f"- 측정: {datetime.now():%Y-%m-%d %H:%M}, `questions/tools/benchmark_app.py` (streamlit AppTest, 로컬 PC)",
        f"- 환경: Python {platform.python_version()}, streamlit {streamlit.__version__}, altair {altair.__version__}, "
        f"{platform.system()} {platform.release()}",
        "",
        "## 요약",
        "",
        "| 항목 | 값 | 기준 |",
        "|---|---|---|",
        f"| 측정 문항 | {len(rows)}개 | |",
        f"| 예외·헤더 오류 문항 | {len(bad)}개 | 0개 |",
        f"| 렌더링 중앙값 | {statistics.median(secs):.2f}초 | |",
        f"| 렌더링 p95 | {p95:.2f}초 | |",
        f"| 렌더링 최대 | {secs[-1]:.2f}초 | {LIMIT_SEC:.0f}초 이내 |",
        f"| {LIMIT_SEC:.0f}초 이내 문항 | {ok} / {len(rows)} | 전부 |",
        f"| 콜드 스타트(첫 실행, import 포함) | {cold:.2f}초 | 참고 |",
        f"| 프로세스 RSS 시작 → 최대 | {rss0:.0f}MB → {rss_max:.0f}MB | {LIMIT_MB}MB 이하 ({'통과' if rss_max <= LIMIT_MB else '초과'}) |",
        f"| `ruff check questions` | {ruff_count()} | Phase 4에서 0건 |",
    ]
    if labs_page is not None:
        out.append(
            f"| 체험실 페이지 렌더링 | {labs_page['sec']:.2f}초 | {LIMIT_SEC:.0f}초 이내 |"
        )
    if joined:
        out.append(
            f"| 결합 결과 문항 렌더링 최대 | {max(r['sec'] for r in joined):.2f}초 ({len(joined)}개) | "
            f"{LIMIT_SEC:.0f}초 이내 |"
        )
    out += [
        "",
        "렌더링 시간은 질문 페이지로 옮긴 뒤의 `run()` 한 번이다(목차 실행 제외). 브라우저 그리기 시간은 들어 있지 않다.",
        "한 프로세스에서 돌아 `st.cache_data`가 문항 사이에 공유된다. 문항별 JSON·toml은 처음 읽는 비용이 들어 있지만, "
        "목차·개념 사전 캐시는 데워진 상태다. 서버를 막 띄운 첫 방문자는 콜드 스타트에 가깝다.",
        "RSS는 측정 스크립트와 AppTest가 한 프로세스에서 돈 값이라 실제 서버보다 약간 크다.",
        "",
        "## 가장 느린 10문항",
        "",
        "| 문항 | 시간(초) |",
        "|---|---|",
        *[f"| {r['qid']} | {r['sec']:.2f} |" for r in slow],
        "",
        "## 예외가 난 문항",
        "",
        *([f"- {r['qid']}번: 예외 {r['exceptions']}개, 헤더 {'정상' if r['header_ok'] else '이상'}" for r in bad] or ["없음"]),
        "",
    ]
    if lab_rows is not None:
        out += [
            "## 체험 위젯 반응",
            "",
            f"| 체험 | 조작 | 시간(초) | 기준 {LAB_LIMIT_SEC}초 |",
            "|---|---|---|---|",
            *[
                f"| {r['name']} | {r['action']} | {r['sec']:.2f} | "
                f"{'통과' if r['sec'] <= LAB_LIMIT_SEC else '초과'} |"
                for r in lab_rows
            ],
            "",
        ]
    out += [
        "## 배포 점검",
        "",
        "(Claude가 배포 점검 뒤 채운다)",
        "",
    ]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", type=int, nargs="*", default=list(range(1, 101)))
    ap.add_argument("--out", type=Path)
    ap.add_argument("--labs", action="store_true", help="체험 위젯 반응 시간도 잰다")
    args = ap.parse_args()

    rss0 = rss_mb()
    t = time.perf_counter()
    render(args.ids[0])  # 콜드 스타트: 결과는 버리고 시간만 쓴다
    cold = time.perf_counter() - t
    rows = []
    for qid in args.ids:
        r = render(qid)
        rows.append(r)
        flag = "" if r["exceptions"] == 0 and r["header_ok"] else "  <-- 확인"
        print(f"q{qid:03d} {r['sec']:.2f}s exc={r['exceptions']} rss={r['rss']:.0f}MB{flag}", flush=True)
    lab_rows = None
    labs_page = None
    rss_extra = []
    if args.labs:
        lab_rows = measure_labs()
        for r in lab_rows:
            flag = "" if r["sec"] <= LAB_LIMIT_SEC else "  <-- 확인"
            print(f"lab {r['name']} {r['action']} {r['sec']:.2f}s{flag}", flush=True)
            rss_extra.append(r["rss"])
        labs_page = measure_labs_page()
        flag = "" if labs_page["exceptions"] == 0 and labs_page["sec"] <= LIMIT_SEC else "  <-- 확인"
        print(f"labs_page {labs_page['sec']:.2f}s exc={labs_page['exceptions']}{flag}", flush=True)
        rss_extra.append(labs_page["rss"])
    rss_max = max([r["rss"] for r in rows] + rss_extra)
    text = report(rows, cold, rss0, rss_max, lab_rows=lab_rows, labs_page=labs_page)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print("saved", args.out)
    else:
        print(text)


if __name__ == "__main__":
    main()
