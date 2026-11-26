"""2부. 맘다니·임대료 동결·집주인의 저항 — 통계 계산.
문항 13–24. 실행: python questions/calc/part02.py  (일부만: python questions/calc/part02.py 16 20)
21·22번은 311로 계산할 것이 없어 해설만 둔다.
"""
import sys
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (BORO_KO, Q5, category, load_311, records, save,  # noqa: E402
                    tract_rates, with_tract)

BOROS = list(BORO_KO)
CATS = ["주거환경", "소음", "위생", "도로·교통", "해충·동물"]


def rho(a, b) -> float:
    return round(float(spearmanr(a, b, nan_policy="omit")[0]), 2)


def heat(df):
    return df[df.problem == "HEAT/HOT WATER"]


def per_k(dt, t, by, sub=None) -> pd.Series:
    """분위별 1,000명당. 분자는 dt(또는 sub) 건수, 분모는 그 분위 Tract 인구 합."""
    s = sub if sub is not None else dt
    return (s.groupby(by, observed=True).size() / t.groupby(by, observed=True).total_pop.sum() * 1000).reindex(Q5)


def q013(df):
    h = heat(df)
    sep_oct = h[h.created >= "2026-09-01"]
    daily = sep_oct.groupby("date").size().rename_axis("날짜").reset_index(name="난방 민원")
    octo = h[h.created >= "2026-10-01"]
    wk = octo.groupby(octo.created.dt.isocalendar().week).agg(n=("key", "size"), 시작=("date", "min"), 끝=("date", "max"))
    wk["주"] = wk.시작.dt.strftime("%m/%d") + "–" + wk.끝.dt.strftime("%m/%d")
    wk = wk.rename(columns={"n": "난방 민원"})[["주", "난방 민원"]]
    nov25 = int((h.created < "2025-12-01").sum())
    save(13,
         metrics=[
             {"label": "2026년 10월 난방 민원", "value": f"{len(octo):,}건", "help": f"하루 평균 {len(octo) / 31:,.0f}건"},
             {"label": "10월 첫 주 → 넷째 주", "value": f"{wk['난방 민원'].iat[0]:,} → {wk['난방 민원'].iat[3]:,}건",
              "help": "ISO 주 기준. 첫 주는 10/1(목)부터 4일"},
             {"label": "참고: 2025년 11월", "value": f"{nov25:,}건", "help": f"하루 평균 {nov25 / 30:,.0f}건"},
         ],
         charts=[
             {"title": "9–10월 하루 난방 민원", "kind": "line", "x": "날짜", "y": "난방 민원", "rows": records(daily),
              "caption": "10월 1일 당일은 229건으로 9월 말과 같다. 크게 오르는 날은 10월 6–7일과 17일 이후다. 날짜가 아니라 날씨를 따라 움직이는 모양이다."},
             {"title": "10월 주별 난방 민원", "kind": "bar", "x": "주", "y": "난방 민원", "rows": records(wk)},
         ],
         tables=[{"title": "10월 주별", "rows": records(wk)}])


def q014(df):
    h = heat(df)
    m = h.groupby(h.created.dt.to_period("M").dt.start_time).size().rename_axis("월").reset_index(name="난방 민원")
    first30 = []
    for label, start in [("2025년 시즌(11/1부터)", "2025-11-01"), ("2026년 시즌(10/1부터)", "2026-10-01")]:
        s = h[(h.created >= start) & (h.created < pd.Timestamp(start) + pd.Timedelta(days=31))]
        d = s.groupby("date").size().reset_index(name="난방 민원")
        d["경과일"] = (d.date - pd.Timestamp(start)).dt.days + 1
        d["구분"] = label
        first30.append(d[["경과일", "난방 민원", "구분"]])
    f = pd.concat(first30)
    save(14,
         metrics=[
             {"label": "2026년 10월", "value": f"{int(m['난방 민원'].iat[-1]):,}건"},
             {"label": "2025년 10월", "value": "자료 없음", "help": "이 데이터는 2025-11-01부터다"},
             {"label": "난방 시즌 시작", "value": "매년 10월 1일", "help": "동결 적용일과 같은 날"},
         ],
         charts=[
             {"title": "월별 난방 민원(12개월)", "kind": "bar", "x": "월", "y": "난방 민원", "rows": records(m),
              "caption": "양 끝(2025-11, 2026-10)이 모두 시즌 초입이다. 같은 달을 1년 차이로 비교할 수 있는 달이 없다."},
             {"title": "우리가 가진 두 시즌 초입 31일", "kind": "line", "x": "경과일", "y": "난방 민원", "color": "구분",
              "rows": records(f), "caption": "시작 달이 다르다(11월 대 10월). 기온이 다르므로 이 둘을 비교해도 동결 효과를 말할 수 없다."},
         ])


def q015(df):
    hpd = df[df.agency == "HPD"]
    m = hpd.groupby([hpd.created.dt.to_period("M").dt.start_time, hpd.problem.astype(str) == "HEAT/HOT WATER"]).size()
    m = m.rename("민원").reset_index()
    m.columns = ["월", "난방", "민원"]
    m["구분"] = m.난방.map({True: "난방·온수", False: "그 밖의 HPD 주거 민원"})
    has_bbl = hpd.bbl.notna() & (hpd.bbl.astype(str).str.strip() != "")
    did = pd.DataFrame([
        {"": "안정화 건물", "동결 전(2025-11 ~ 2026-09)": "A", "동결 후(2026-10 ~)": "B", "변화": "B − A"},
        {"": "비안정화 건물", "동결 전(2025-11 ~ 2026-09)": "C", "동결 후(2026-10 ~)": "D", "변화": "D − C"},
        {"": "동결 효과(추정)", "동결 전(2025-11 ~ 2026-09)": "", "동결 후(2026-10 ~)": "", "변화": "(B − A) − (D − C)"},
    ])
    save(15,
         metrics=[
             {"label": "HPD 주거 민원(12개월)", "value": f"{len(hpd):,}건"},
             {"label": "BBL이 있는 비율", "value": f"{has_bbl.mean() * 100:.1f}%", "help": "RGB 건물 목록과 붙일 수 있는 몫"},
             {"label": "동결 뒤 쌓인 기간", "value": "1개월", "help": "2026-10 한 달. 한 시즌은 2027년 봄"},
         ],
         charts=[
             {"title": "HPD 주거 민원 월별: 동결 전 기준선", "kind": "stack", "x": "월", "y": "민원", "color": "구분",
              "colors": {"그 밖의 HPD 주거 민원": "#9fb3d1", "난방·온수": "#e07b39"}, "rows": records(m[["월", "구분", "민원"]]),
              "caption": "이중차분에는 이 기준선을 안정화·비안정화 두 집단으로 나눈 선 두 개가 필요하다."},
         ],
         tables=[{"title": "이중차분 표의 뼈대", "rows": records(did)}])


def q016(dt, t):
    rate = per_k(dt, t, "ren_q")
    cut = t.groupby("ren_q", observed=True).renter_rate.median().reindex(Q5) * 100
    rows = pd.DataFrame({"임차율 5분위": Q5, "1,000명당 민원": rate.round(0).values, "임차율 중앙값(%)": cut.round(0).values})
    tt = t.dropna(subset=["renter_rate"])
    within = [{"자치구": BORO_KO[b], "Spearman 상관": rho(g.renter_rate, g.rate), "Tract 수": len(g)}
              for b, g in tt.groupby("boro_acs")]
    pts = tt.assign(**{"임차율(%)": (tt.renter_rate * 100).round(1), "1,000명당 민원": tt.rate.round(0)})
    pts = pts[pts["1,000명당 민원"] <= pts["1,000명당 민원"].quantile(0.99)]
    w = [r["Spearman 상관"] for r in within]
    save(16,
         metrics=[
             {"label": "임차율 최하위 분위", "value": f"{rate.iat[0]:,.0f}건", "help": "1,000명당"},
             {"label": "임차율 최상위 분위", "value": f"{rate.iat[-1]:,.0f}건", "help": "1,000명당"},
             {"label": "차이", "value": f"{rate.iat[-1] / rate.iat[0]:.1f}배"},
             {"label": "자치구 안 상관", "value": f"{min(w):.2f} ~ {max(w):.2f}", "help": f"시 전체 {rho(tt.renter_rate, tt.rate):.2f}"},
         ],
         charts=[
             {"title": "임차율 5분위별 1,000명당 민원", "kind": "bar", "x": "임차율 5분위", "y": "1,000명당 민원", "rows": records(rows),
              "caption": "분위마다 고르게 오른다. 같은 '세입자 동네' 안에서도 임차율이 높을수록 민원이 많다."},
             {"title": "Tract마다 본 임차율과 민원율", "kind": "scatter", "x": "임차율(%)", "y": "1,000명당 민원", "trend": True,
              "rows": records(pts[["GEOID", "임차율(%)", "1,000명당 민원"]]),
              "caption": "점 하나가 Tract 하나. 주황 선은 국소 추세(LOESS). 위쪽 1%는 그림에서만 뺐다."},
             {"title": "자치구 안에서도 같은 방향인가", "kind": "bar", "x": "자치구", "y": "Spearman 상관", "rows": within, "sort": "-y"},
         ],
         tables=[{"title": "임차율 5분위", "rows": records(rows)}, {"title": "자치구별 상관", "rows": within}])


def q017(dt, t):
    g = (dt.groupby(["boro_acs", "ren_q"], observed=True).size()
         / t.groupby(["boro_acs", "ren_q"], observed=True).total_pop.sum() * 1000).rename("1,000명당 민원").reset_index()
    g["자치구"] = g.boro_acs.map(BORO_KO)
    g["임차율 5분위"] = g.ren_q.astype(str)
    g["1,000명당 민원"] = g["1,000명당 민원"].round(0)
    save(17,
         metrics=[
             {"label": "선거 자료", "value": "아직 없음", "help": "선거구(ED) 개표 결과를 Tract에 붙여야 한다"},
             {"label": "임차율과 민원율 상관(Tract)", "value": f"{rho(t.renter_rate, t.rate):.2f}", "help": "통제해야 할 공통 원인 후보"},
         ],
         charts=[
             {"title": "자치구 × 임차율 5분위, 1,000명당 민원", "kind": "group", "x": "자치구", "y": "1,000명당 민원",
              "color": "임차율 5분위", "colors": dict(zip(Q5, ["#c9d6ea", "#9fb3d1", "#6f8fbf", "#3f6aa9", "#1d3f7a"])),
              "rows": records(g[["자치구", "임차율 5분위", "1,000명당 민원"]]),
              "caption": "맘다니 표와 민원이 함께 높게 나와도, 둘 다 임차율을 따라 움직인 것일 수 있다. 이 차트는 그 '공통 원인' 쪽만 보여 준다."},
         ])


def q018(dt, t):
    tt = t.dropna(subset=["renter_rate"])
    lv = [{"집계 단위": "Tract (2,195개 안팎)", "Spearman 상관": rho(tt.renter_rate, tt.rate), "점 수": len(tt)}]
    q = tt.groupby("ren_q", observed=True).agg(r=("renter_rate", "mean"), n=("n", "sum"), p=("total_pop", "sum"))
    lv.append({"집계 단위": "임차율 5분위 묶음(5개)", "Spearman 상관": rho(q.r, q.n / q.p), "점 수": len(q)})
    b = tt.groupby("boro_acs").agg(ro=("renter_occupied", "sum"), n=("n", "sum"), p=("total_pop", "sum"))
    br = tt.groupby("boro_acs").apply(lambda g: (g.renter_rate * g.total_pop).sum() / g.total_pop.sum())
    lv.append({"집계 단위": "자치구(5개)", "Spearman 상관": rho(br, b.n / b.p), "점 수": len(b)})
    save(18,
         metrics=[{"label": f"{lab} 단위 상관", "value": f"{r['Spearman 상관']:.2f}", "help": f"점 {r['점 수']:,}개"}
                  for lab, r in zip(["Tract", "5분위 묶음", "자치구"], lv)],
         charts=[
             {"title": "같은 관계, 집계 단위만 바꾼 상관", "kind": "barh", "x": "Spearman 상관", "y": "집계 단위", "rows": lv,
              "caption": "임차율과 민원율. 동네를 크게 묶을수록 개인 차이가 지워져 상관이 커지거나 뒤집힌다. 어느 단위의 상관도 '개인'에 대해서는 말하지 않는다."},
         ],
         tables=[{"title": "집계 단위별 상관", "rows": lv}])


def q019(df):
    df = df.assign(cat=category(df.problem))
    mon = df.groupby(df.created.dt.to_period("M").dt.start_time).size().rename_axis("월").reset_index(name="전체 민원")
    dec = df[(df.created >= "2025-12-01") & (df.created < "2026-01-01")]
    jan = df[(df.created >= "2026-01-01") & (df.created < "2026-02-01")]
    top = (jan.problem.astype(str).value_counts() - dec.problem.astype(str).value_counts()).dropna()
    top = top.sort_values(key=abs, ascending=False).head(8).rename_axis("유형").reset_index(name="1월 − 12월")
    top["1월 − 12월"] = top["1월 − 12월"].astype(int)
    diff = len(jan) - len(dec)
    h_diff = int(top.set_index("유형").loc["HEAT/HOT WATER", "1월 − 12월"])
    save(19,
         metrics=[
             {"label": "2025-12", "value": f"{len(dec):,}건"},
             {"label": "2026-01", "value": f"{len(jan):,}건", "help": f"+{diff:,}건(+{diff / len(dec) * 100:.1f}%)"},
             {"label": "그중 난방 증가분", "value": f"+{h_diff:,}건", "help": f"전체 증가분의 {h_diff / diff * 100:.0f}%"},
         ],
         charts=[
             {"title": "월별 전체 민원", "kind": "bar", "x": "월", "y": "전체 민원", "rows": records(mon),
              "caption": "1월은 원래 높은 달이다. 2월은 폭설에도 1월보다 낮다(일수가 적다)."},
             {"title": "12월 → 1월 변화가 큰 유형", "kind": "barh", "x": "1월 − 12월", "y": "유형", "rows": records(top),
              "caption": "늘어난 몫의 대부분이 난방이다. 계절이 만든 증가다."},
         ],
         tables=[{"title": "12월 → 1월 변화 상위 유형", "rows": records(top)}])


def q020(dt, t):
    hou = dt[dt.cat == "주거환경"]
    rate = per_k(dt, t, "old_q", hou)
    cut = t.groupby("old_q", observed=True).pre1950_share.median().reindex(Q5) * 100
    rows = pd.DataFrame({"1950년 이전 주택 비율 5분위": Q5, "1,000명당 주거 민원": rate.round(0).values,
                         "1950년 이전 비율 중앙값(%)": cut.round(0).values})
    tt = t.dropna(subset=["pre1950_share"])
    pts = tt.assign(**{"1950년 이전 주택 비율(%)": (tt.pre1950_share * 100).round(1), "1,000명당 주거 민원": tt.주거환경.round(0)})
    pts = pts[pts["1,000명당 주거 민원"] <= pts["1,000명당 주거 민원"].quantile(0.99)]
    save(20,
         metrics=[
             {"label": "최하위 분위", "value": f"{rate.iat[0]:,.0f}건", "help": "1,000명당 주거 민원"},
             {"label": "최상위 분위", "value": f"{rate.iat[-1]:,.0f}건"},
             {"label": "Tract 순위 상관", "value": f"{rho(tt.pre1950_share, tt.주거환경):.2f}"},
         ],
         charts=[
             {"title": "노후 주택 비율 5분위별 주거 민원", "kind": "bar", "x": "1950년 이전 주택 비율 5분위", "y": "1,000명당 주거 민원",
              "rows": records(rows), "caption": "올라가다가 Q3부터 멈춘다."},
             {"title": "Tract마다 본 노후 주택 비율과 주거 민원", "kind": "scatter", "x": "1950년 이전 주택 비율(%)",
              "y": "1,000명당 주거 민원", "trend": True, "rows": records(pts[["GEOID", "1950년 이전 주택 비율(%)", "1,000명당 주거 민원"]]),
              "caption": "노후 비율이 높은 쪽에서 점이 넓게 퍼진다. 오래됐다는 것만으로는 민원을 설명하지 못한다."},
         ],
         tables=[{"title": "노후 주택 5분위", "rows": records(rows)}])


def q023(dt, t):
    tt = t.dropna(subset=["renter_rate"])
    rc = pd.DataFrame([{"분야": c, "임차율과 Spearman 상관": rho(tt.renter_rate, tt[c])} for c in CATS])
    lines = []
    for c in CATS:
        r = per_k(dt, t, "ren_q", dt[dt.cat == c])
        for q, v in r.items():
            lines.append({"분야": c, "임차율 5분위": q, "1,000명당": round(float(v), 1),
                          "최하위=100": round(float(v / r.iat[0] * 100), 0)})
    save(23,
         metrics=[{"label": r["분야"], "value": f"{r['임차율과 Spearman 상관']:.2f}", "help": "Tract 임차율과의 순위 상관"}
                  for r in rc.to_dict("records")],
         charts=[
             {"title": "분야별 임차율과의 상관", "kind": "barh", "x": "임차율과 Spearman 상관", "y": "분야", "rows": records(rc),
              "caption": "세입자 동네는 '집 안'(주거)과 '이웃'(소음)으로 신고한다. 해충은 임차율과 무관하다."},
             {"title": "임차율 5분위별 분야 민원", "kind": "line", "x": "임차율 5분위", "y": "최하위=100", "alt_y": "1,000명당",
              "color": "분야", "rows": lines, "point": True,
              "caption": "분야마다 최하위 분위를 100으로 맞췄다. 세로축을 바꾸면 절대 크기를 볼 수 있다."},
         ],
         tables=[{"title": "분야별 상관", "rows": records(rc)}])


def q024(dt, t):
    tt = t[t.ren_q == Q5[-1]].dropna(subset=["주거환경"])
    rows = []
    for b, g in tt.groupby("boro_acs"):
        for p, lab in [(0.25, "하위 25%"), (0.5, "중앙값"), (0.75, "상위 25%")]:
            rows.append({"자치구": BORO_KO[b], "분위점": lab, "1,000명당 주거 민원": round(float(g.주거환경.quantile(p)), 0)})
    spread = tt.주거환경.quantile(0.75) / tt.주거환경.quantile(0.25)
    save(24,
         metrics=[
             {"label": "임차율 최상위 분위 Tract", "value": f"{len(tt):,}개",
              "help": f"임차율 {tt.renter_rate.min() * 100:.0f}% 이상"},
             {"label": "그 안의 주거 민원 격차", "value": f"{spread:.1f}배", "help": "상위 25% ÷ 하위 25%"},
             {"label": "안정화 비율 변수", "value": "아직 없음", "help": "RGB 건물 목록 → PLUTO → Tract"},
         ],
         charts=[
             {"title": "임차율이 비슷해도 주거 민원은 크게 다르다(임차율 최상위 분위)", "kind": "group", "x": "자치구",
              "y": "1,000명당 주거 민원", "color": "분위점",
              "colors": {"하위 25%": "#c9d6ea", "중앙값": "#6f8fbf", "상위 25%": "#1d3f7a"}, "rows": rows,
              "caption": "이 차이를 '안정화 비율'이 얼마나 설명하는지가 24번의 질문이다."},
         ],
         tables=[{"title": "자치구별 분위점", "rows": rows}])


if __name__ == "__main__":
    want = {int(a) for a in sys.argv[1:]} or set(range(13, 25))
    df = load_311()
    need_t = want & {16, 17, 18, 20, 23, 24}
    if need_t:
        dt = with_tract(df)
        dt["cat"] = category(dt.problem)
        t = tract_rates(dt, CATS)
    jobs = {13: lambda: q013(df), 14: lambda: q014(df), 15: lambda: q015(df), 16: lambda: q016(dt, t),
            17: lambda: q017(dt, t), 18: lambda: q018(dt, t), 19: lambda: q019(df), 20: lambda: q020(dt, t),
            23: lambda: q023(dt, t), 24: lambda: q024(dt, t)}
    for k in sorted(want & set(jobs)):
        jobs[k]()
