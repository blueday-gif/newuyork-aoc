"""질문·체험실 페이지 AppTest 렌더링 회귀."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app.py"


def open_question(qid: int) -> AppTest:
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    at.switch_page("app_pages/question.py")
    at.query_params["q"] = str(qid)
    at.run()
    return at


def _metric(at: AppTest, label: str):
    for m in at.metric:
        if m.label == label:
            return m
    raise AssertionError(f"metric not found: {label}")


def _slider(at: AppTest, key: str):
    for s in at.slider:
        if s.key == key:
            return s
    raise AssertionError(f"slider not found: {key}")


@pytest.mark.parametrize("qid", list(range(1, 101)))
def test_all_questions_render(qid):
    at = open_question(qid)
    assert not at.exception
    assert at.header[0].value.startswith(f"{qid}. ")


def test_small_denominator_default():
    at = open_question(74)
    assert _slider(at, "q74_min").value == 1000
    assert _metric(at, "남은 Tract").value == "2,195개"
    assert _metric(at, "남은 민원").value == "3,803,874건"


def test_small_denominator_zero():
    at = open_question(74)
    _slider(at, "q74_min").set_value(0)
    at.run()
    assert not at.exception
    assert _metric(at, "남은 Tract").value == "2,243개"


def test_reporting_bias_default():
    at = open_question(39)
    assert _metric(at, "A가 덜 받는 예산").value == "+26.7"


def test_reporting_bias_zero():
    at = open_question(39)
    for key in ("q39_a_true", "q39_b_true", "q39_a_rate", "q39_b_rate"):
        _slider(at, key).set_value(0)
    at.run()
    assert not at.exception
    assert any("두 동네 모두 실제 문제가 0이라 예산을 나눌 수 없다." in (w.value or "") for w in at.warning)


def test_reporting_bias_no_reports():
    at = open_question(39)
    _slider(at, "q39_a_rate").set_value(0)
    _slider(at, "q39_b_rate").set_value(0)
    at.run()
    assert not at.exception
    assert any("두 동네 모두 신고가 0건이라" in (w.value or "") for w in at.warning)


def test_paper_bridge():
    at = open_question(97)
    bridge = [e for e in at.expander if "학술 논문·시정 사례와 연결하기" in (e.label or "")]
    assert bridge, "논문 연결 expander 없음"
    texts = []
    for e in bridge:
        texts.extend(m.value for m in e.markdown if isinstance(m.value, str))
        texts.extend(c.value for c in e.caption if isinstance(c.value, str))
    if not any("Kontokosta" in t for t in texts):
        texts.extend(m.value for m in at.markdown if isinstance(m.value, str))
    assert any("Kontokosta" in t for t in texts)


def test_related_why():
    at = open_question(95)
    texts = [c.value for c in at.caption]
    assert "이 결합으로 임차율과 민원을 비교한다" in texts


def test_caveats_text_unchanged():
    at = open_question(95)
    assert any("좌표가 없는 2.1%" in (w.value or "") for w in at.warning)


def test_progress_sidebar():
    at = open_question(95)
    at.query_params["q"] = "74"
    at.run()
    texts = [p.text for p in at.sidebar.progress if getattr(p, "text", None)]
    if not texts:
        texts = [p.text for p in at.progress if getattr(p, "text", None)]
    assert "2 / 100 문항" in texts


def test_labs_page():
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    at.switch_page("app_pages/labs.py")
    at.run()
    assert not at.exception
    titles = [s.value for s in at.main.subheader]
    assert titles == ["작은 분모의 함정", "보고 편향 시뮬레이터"]
