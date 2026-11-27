"""311 원본에서 기준 수치를 다시 계산해 대조한다(느림, 메모리 수 GB).
실행: py -3 -m pytest questions/tests -q --runslow
JSON을 덮어쓰지 않도록 save()는 부르지 않는다."""
import pandas as pd
import pytest

import common

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def raw():
    return common.load_311()


@pytest.fixture(scope="module")
def joined(raw):
    dt = common.with_tract(raw)
    dt["cat"] = common.category(dt.problem)
    return dt


def test_raw_rows(raw):
    assert len(raw) == 3_963_959


def test_point_geoid_rows():
    pg = pd.read_parquet(common.ROOT / "data" / "processed" / "nyc311_point_geoid.parquet", columns=["GEOID"])
    assert len(pg) == 3_880_604


def test_tracts_and_joined(joined):
    assert len(common.tracts()) == 2195
    assert len(joined) == 3_803_874


def test_q095_bronx_recomputed(joined):
    # part10.q095와 같은 식: 분석 대상 Tract의 분야별 민원 ÷ 자치구(분석 대상 Tract) 인구 × 1,000
    pop = common.tracts().groupby("boro_acs").total_pop.sum()
    rate = lambda cat: round(float((joined.cat == cat)[joined.boro_acs == "BRONX"].sum() / pop["BRONX"] * 1000), 1)  # noqa: E731
    assert rate("주거환경") == 183.0
    assert rate("소음") == 152.8
