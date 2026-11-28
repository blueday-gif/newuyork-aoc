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
    assert titles == [
        "작은 분모의 함정",
        "보고 편향 시뮬레이터",
        "이중차분: 쓰레기통 의무화와 쥐 신고",
    ]


def test_talks_page():
    """발표후보: Ramphal 재현. 기준 수치(7월÷겨울 Q1 1.68, Q4 1.29, 격차 1.30)와 그림 2개."""
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    at.switch_page("app_pages/talks.py")
    at.run()
    assert not at.exception
    assert _metric(at, "7월 ÷ 겨울: 저소득(Q1)").value == "1.68배"
    assert _metric(at, "7월 ÷ 겨울: 고소득(Q4)").value == "1.29배"
    assert _metric(at, "격차(Q1 ÷ Q4)").value == "1.30배"
    assert _metric(at, "자치구별 계절 허용 시 격차").value == "1.07배"
    assert len(at.get("image")) == 2
    assert [s.value for s in at.main.subheader][0].startswith("소음 불평등과 계절성")


def _select_slider(at: AppTest, key: str):
    for s in at.select_slider:
        if s.key == key:
            return s
    raise AssertionError(f"select_slider not found: {key}")


def test_did_lab_default():
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    at.switch_page("app_pages/labs.py")
    at.run()
    assert not at.exception
    assert len(at.metric) >= 3
    assert _metric(at, "이중차분").value == "-1.23"


def test_did_lab_placebo():
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    at.switch_page("app_pages/labs.py")
    at.run()
    _select_slider(at, "page_did_containerization_pre").set_value("2022")
    _select_slider(at, "page_did_containerization_post").set_value("2023")
    at.run()
    assert not at.exception
    assert any("가짜 정책" in (c.value or "") for c in at.caption)

    _select_slider(at, "page_did_containerization_pre").set_value("2025")
    _select_slider(at, "page_did_containerization_post").set_value("2024")
    at.run()
    assert not at.exception
    assert len(at.info) >= 1
    assert any("뒤 기간을 앞 기간보다 나중으로 고르세요." in (i.value or "") for i in at.info)


def test_joined_section():
    at = open_question(97)
    assert not at.exception
    titles = [s.value for s in at.main.subheader]
    assert "결합 결과" in titles
    at1 = open_question(1)
    assert not at1.exception
    titles1 = [s.value for s in at1.main.subheader]
    assert "결합 결과" not in titles1
