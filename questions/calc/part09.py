"""9부. 통계 초보 교실: 이렇게 하면 틀린다 — 통계 계산.
문항 85–94. 실행: python questions/calc/part09.py  (일부만: python questions/calc/part09.py 90 94)
90번은 plan02의 LISA 결과표(outputs/tables/plan02_lisa.csv)를 읽는다.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (BORO_KO, INC_Q, Q5, ROOT, borough_pop, category, load_311, records,  # noqa: E402
                    save, tract_rates, tracts, with_tract)

BOROS = list(BORO_KO)
HOT = "655 EAST 230 STREET"


def rho(a, b) -> float:
    return round(float(spearmanr(a, b, nan_policy="omit")[0]), 2)


def q085(df):
    h = df.hours.dropna()
    bins = [0, 1, 6, 24, 72, 168, 720, 2160, np.inf]
    labs = ["1시간 미만", "1–6시간", "6–24시간", "1–3일", "3–7일", "1–4주", "1–3개월", "3개월 넘게"]
    c = pd.cut(h, bins, labels=labs, right=False).value_counts().reindex(labs)
    rows = pd.DataFrame({"처리시간": labs, "민원": c.values, "비율(%)": (c / c.sum() * 100).round(1).values})
    top1 = h.sort_values(ascending=False)
    k = int(len(h) * 0.01)
    save(85,
         metrics=[
             {"label": "평균", "value": f"{h.mean():.1f}시간", "help": f"약 {h.mean() / 24:.1f}일"},
             {"label": "중앙값", "value": f"{h.median():.1f}시간"},
             {"label": "평균 ÷ 중앙값", "value": f"{h.mean() / h.median():.0f}배"},
             {"label": "가장 긴 1%를 빼면 평균", "value": f"{top1.iloc[k:].mean():.1f}시간", "help": "중앙값은 거의 그대로"},
         ],
         charts=[
             {"title": "처리시간 분포", "kind": "bar", "x": "처리시간", "y": "민원", "alt_y": "비율(%)", "rows": records(rows),
              "caption": "절반 넘게 하루 안에 닫힌다. 오른쪽 몇 칸의 긴 꼬리가 평균을 일주일 가까이 끌어올린다."},
         ],
         tables=[{"title": "처리시간 구간", "rows": records(rows)}])


def q086(df, bp):
    n = df.borough.value_counts().reindex(BOROS)
    n_ex = df[df.addr_n != HOT].borough.value_counts().reindex(BOROS)
    # 원문(eda01)은 위치를 Tract에 붙인 민원을 Tract의 자치구로 셌다. 비교용으로 같이 계산한다.
    pg = pd.read_parquet(ROOT / "data" / "processed" / "nyc311_point_geoid.parquet").rename(columns={"unique_key": "key"})
    from common import acs, BORO_ACS
    geo = df[["key"]].merge(pg, on="key").merge(acs()[["GEOID", "borough"]], on="GEOID")
    n_geo = geo.borough.map(BORO_ACS).value_counts().reindex(BOROS)
    rows = pd.DataFrame({"자치구": [BORO_KO[b] for b in BOROS], "민원 건수": n.values,
                         "1,000명당": (n / bp.reindex(BOROS) * 1000).round(1).values,
                         "1,000명당(한 주소 제외)": (n_ex / bp.reindex(BOROS) * 1000).round(1).values,
                         "1,000명당(위치 기준, 원문 방식)": (n_geo / bp.reindex(BOROS) * 1000).round(1).values})
    r = rows.set_index("자치구")
    save(86,
         metrics=[
             {"label": "건수 1위", "value": r["민원 건수"].idxmax(), "help": f"{int(r['민원 건수'].max()):,}건"},
             {"label": "1,000명당 1위", "value": r["1,000명당"].idxmax(), "help": f"{r['1,000명당'].max():.1f}건"},
             {"label": "한 주소를 빼도", "value": r["1,000명당(한 주소 제외)"].idxmax(),
              "help": f"{r['1,000명당(한 주소 제외)'].max():.1f}건"},
             {"label": "위치 기준(원문 방식)", "value": f"{r.loc['브롱크스', '1,000명당(위치 기준, 원문 방식)']:.1f}건",
              "help": "자치구 열 대신 좌표로 Tract에 붙여 셌다. 좌표 없는 민원이 빠진다"},
         ],
         charts=[
             {"title": "자치구별 민원: 건수와 1,000명당", "kind": "bar", "x": "자치구", "y": "민원 건수", "alt_y": "1,000명당",
              "rows": records(rows), "sort": "-y", "caption": "세로축을 바꿔 보자. 순위가 바뀐다."},
         ],
         tables=[{"title": "자치구별", "rows": records(rows)}])


def q087(t):
    tt = t.dropna(subset=["renter_rate"])
    import geopandas as gpd
    g = gpd.read_file(ROOT / "data" / "processed" / "nyc_acs_2024_5yr.geojson").to_crs(2263)
    g["km2"] = g.geometry.area * 0.09290304 / 1e6
    tt = tt.merge(g[["GEOID", "km2"]], on="GEOID", how="left")
    tt["density"] = tt.total_pop / tt.km2
    vars_ = {"인구 밀도": "density", "빈곤율": "poverty_rate", "1950년 이전 주택 비율": "pre1950_share", "중위 가구소득": "median_income"}
    a = [{"변수": k, "임차율과의 상관": rho(tt.renter_rate, tt[v]), "민원율과의 상관": rho(tt[v], tt.rate)} for k, v in vars_.items()]
    long = pd.DataFrame(a).melt(id_vars="변수", var_name="구분", value_name="Spearman 상관")
    tt["dens_q"] = pd.qcut(tt.density, 5, labels=Q5)
    within = [{"인구 밀도 5분위": str(q), "임차율 × 민원율 상관": rho(s.renter_rate, s.rate), "Tract 수": len(s)}
              for q, s in tt.groupby("dens_q", observed=True)]
    save(87,
         metrics=[
             {"label": "임차율 × 민원율", "value": f"{rho(tt.renter_rate, tt.rate):.2f}", "help": "시 전체 Tract"},
             {"label": "임차율 × 인구 밀도", "value": f"{rho(tt.renter_rate, tt.density):.2f}"},
             {"label": "밀도를 맞춘 뒤(5분위 안)", "value": f"{min(w['임차율 × 민원율 상관'] for w in within):.2f} ~ {max(w['임차율 × 민원율 상관'] for w in within):.2f}"},
         ],
         charts=[
             {"title": "공통 원인 후보: 임차율·민원율과 함께 움직이는 변수", "kind": "group", "x": "변수", "y": "Spearman 상관", "color": "구분",
              "colors": {"임차율과의 상관": "#9fb3d1", "민원율과의 상관": "#2457a7"}, "rows": records(long),
              "caption": "두 막대가 같은 방향으로 크면, 그 변수가 임차율과 민원율을 함께 움직였을 수 있다."},
             {"title": "인구 밀도를 맞춘 뒤 임차율과 민원율의 상관", "kind": "bar", "x": "인구 밀도 5분위", "y": "임차율 × 민원율 상관",
              "rows": within, "caption": "밀도가 비슷한 동네끼리만 봐도 관계가 남는지 확인한다."},
         ],
         tables=[{"title": "밀도 5분위 안의 상관", "rows": within}])


def q088(df):
    p, d = df.problem.astype(str), df.detail.astype(str)
    series = {"아이스크림 트럭 소음": d.str.contains("Ice Cream", case=False), "불법 불꽃놀이": p == "Illegal Fireworks",
              "난방·온수": p == "HEAT/HOT WATER"}
    mon = df.created.dt.to_period("M").dt.start_time
    m = pd.DataFrame({k: df[v].groupby(mon[v]).size() for k, v in series.items()}).fillna(0)
    idx = (m / m.max() * 100).round(1)
    long = idx.rename_axis("월").reset_index().melt(id_vars="월", var_name="민원", value_name="최대 달=100")
    r = m.corr(method="pearson").round(2)
    save(88,
         metrics=[
             {"label": "아이스크림 × 불꽃놀이", "value": f"{r.loc['아이스크림 트럭 소음', '불법 불꽃놀이']:+.2f}", "help": "월별 12개 점의 상관"},
             {"label": "아이스크림 × 난방", "value": f"{r.loc['아이스크림 트럭 소음', '난방·온수']:+.2f}"},
             {"label": "점의 수", "value": "12개", "help": "12개월. 계절 하나가 상관을 만든다"},
         ],
         charts=[
             {"title": "월별 민원(각자 가장 많은 달 = 100)", "kind": "line", "x": "월", "y": "최대 달=100", "color": "민원",
              "colors": {"아이스크림 트럭 소음": "#e07b39", "불법 불꽃놀이": "#c94f6d", "난방·온수": "#2457a7"}, "rows": records(long),
              "point": True, "caption": "아이스크림은 4–6월, 불꽃놀이는 7월 한 달에 솟아 '둘 다 여름'인데도 상관이 약하다. 반대로 아이스크림과 난방은 서로 아무 관계도 없지만 계절 때문에 강하게 반대로 움직인다(−0.86)."},
         ],
         tables=[{"title": "월별 건수", "rows": records(m.rename_axis("월").reset_index())}])


def q089(df):
    first, last = df.created.min(), df.created.max()
    d = df.groupby("date").size()
    edge = pd.DataFrame({"날": ["첫날 " + first.strftime("%m/%d"), "둘째 날", "하루 평균", "마지막 전날", "마지막 날 " + last.strftime("%m/%d")],
                         "민원": [int(d.iloc[0]), int(d.iloc[1]), round(d.iloc[1:-1].mean()), int(d.iloc[-2]), int(d.iloc[-1])]})
    f = df[df.date == d.index[0]].created.dt.hour.value_counts().sort_index()
    save(89,
         metrics=[
             {"label": "자료 시작", "value": first.strftime("%Y-%m-%d %H:%M")},
             {"label": "자료 끝", "value": last.strftime("%Y-%m-%d %H:%M")},
             {"label": "첫날 민원", "value": f"{int(d.iloc[0]):,}건", "help": f"{f.index.min()}시 이후만. 하루 평균 {d.iloc[1:-1].mean():,.0f}건"},
             {"label": "마지막 날", "value": f"{int(d.iloc[-1]):,}건", "help": f"{last.hour}시까지만"},
         ],
         charts=[
             {"title": "양 끝 날은 잘려 있다", "kind": "bar", "x": "날", "y": "민원", "rows": records(edge),
              "caption": "첫날은 저녁 9시부터, 마지막 날은 저녁 9시까지만 들어 있다. 하루 단위 순위에서 두 날은 빼야 한다."},
         ])


def q090():
    l = pd.read_csv(ROOT / "outputs" / "tables" / "plan02_lisa.csv", dtype={"GEOID": str})
    n = len(l)
    raw = (l.lisa_p < 0.05).sum()
    fdr = (l.lisa_p_fdr < 0.05).sum()
    exp = n * 0.05
    rows = pd.DataFrame([{"기준": "우연히 '유의'할 것으로 기대되는 수(5%)", "Tract 수": round(exp)},
                         {"기준": "보정 전 p < 0.05", "Tract 수": int(raw)},
                         {"기준": "FDR 보정 후 q < 0.05", "Tract 수": int(fdr)}])
    hist = pd.cut(l.lisa_p, np.arange(0, 1.05, 0.05), right=False).value_counts().sort_index()
    hrows = pd.DataFrame({"p값 구간": [f"{iv.left:.2f}–{iv.right:.2f}" for iv in hist.index], "Tract 수": hist.values})
    save(90,
         metrics=[
             {"label": "검정한 Tract", "value": f"{n:,}개"},
             {"label": "보정 전 '유의'", "value": f"{raw}개", "help": f"우연만으로도 약 {exp:.0f}개"},
             {"label": "FDR 보정 후", "value": f"{fdr}개"},
         ],
         charts=[
             {"title": "보정 전후 '유의'한 Tract 수", "kind": "barh", "x": "Tract 수", "y": "기준", "rows": records(rows),
              "caption": "보정 전 278개는 우연 기대치(약 110개)의 2.5배라 무언가 있어 보인다. 하지만 2,195번 검정을 했으니 개별 Tract 하나하나를 '유의'하다고 말할 근거는 약하다. FDR로 보정하면 0개가 남는다."},
             {"title": "Tract별 LISA p값 분포", "kind": "bar", "x": "p값 구간", "y": "Tract 수", "rows": records(hrows),
              "caption": "진짜 효과가 많다면 맨 왼쪽(0–0.05)에 크게 몰린다. 여기서는 크게 몰리지 않는다."},
         ])


def q091(dt, t):
    tt = t.dropna(subset=["hispanic_rate"])
    lv = [{"집계 단위": "Tract", "Spearman 상관": rho(tt.hispanic_rate, tt.rate), "점 수": len(tt)}]
    q = tt.groupby("his_q", observed=True).agg(h=("hispanic_rate", "mean"), n=("n", "sum"), p=("total_pop", "sum"))
    lv.append({"집계 단위": "히스패닉 비율 5분위", "Spearman 상관": rho(q.h, q.n / q.p), "점 수": len(q)})
    pts = tt.assign(**{"히스패닉 비율(%)": (tt.hispanic_rate * 100).round(1), "1,000명당 민원": tt.rate.round(0)})
    pts = pts[pts["1,000명당 민원"] <= pts["1,000명당 민원"].quantile(0.99)]
    save(91,
         metrics=[{"label": f"{r['집계 단위']} 단위", "value": f"{r['Spearman 상관']:.2f}", "help": f"점 {r['점 수']:,}개"} for r in lv],
         charts=[
             {"title": "Tract마다 본 히스패닉 비율과 민원율", "kind": "scatter", "x": "히스패닉 비율(%)", "y": "1,000명당 민원", "trend": True,
              "rows": records(pts[["GEOID", "히스패닉 비율(%)", "1,000명당 민원"]]),
              "caption": "점은 동네다. 이 그림에는 '누가' 신고했는지가 들어 있지 않다. 위쪽 1%는 그림에서만 뺐다."},
         ])


def q092(t):
    r = t.rate.dropna()
    r = r[r <= r.quantile(0.995)]
    q_edges = r.quantile([0, .2, .4, .6, .8, 1]).values
    e_edges = np.linspace(r.min(), r.max(), 6)
    lab = ["1(낮음)", "2", "3", "4", "5(높음)"]
    qc = pd.cut(r, q_edges, labels=lab, include_lowest=True).value_counts().reindex(lab)
    ec = pd.cut(r, e_edges, labels=lab, include_lowest=True).value_counts().reindex(lab)
    rows = []
    for l in lab:
        rows.append({"색 칸": l, "구간 나누기": "5분위(같은 개수)", "Tract 수": int(qc[l])})
        rows.append({"색 칸": l, "구간 나누기": "같은 간격", "Tract 수": int(ec[l])})
    save(92,
         metrics=[
             {"label": "가장 진한 칸: 5분위", "value": f"{int(qc[lab[-1]])}개 Tract", "help": f"{q_edges[4]:,.0f}건 이상"},
             {"label": "가장 진한 칸: 같은 간격", "value": f"{int(ec[lab[-1]])}개 Tract", "help": f"{e_edges[4]:,.0f}건 이상"},
             {"label": "같은 자료", "value": f"Tract {len(r):,}개", "help": "1,000명당 민원(상위 0.5%는 범위 계산에서 뺌)"},
         ],
         charts=[
             {"title": "구간 나누기 방식에 따라 칸마다 들어가는 Tract 수", "kind": "group", "x": "색 칸", "y": "Tract 수", "color": "구간 나누기",
              "colors": {"5분위(같은 개수)": "#2457a7", "같은 간격": "#e07b39"}, "rows": rows,
              "caption": "5분위는 칸마다 같은 수의 동네를 칠한다. 같은 간격은 대부분을 연한 칸에 넣고 소수만 진하게 칠한다. 같은 자료로 '빨간 동네' 지도가 전혀 달라진다."},
         ])


def q093(dt):
    rod = dt[dt.problem == "Rodent"]
    res = rod.resolution.fillna("").str.lower()
    found = res.str.contains("found violations|minor violations")
    insp = found | res.str.contains("did not find any violations")
    g = rod.assign(f=found, i=insp).groupby("GEOID").agg(신고=("key", "size"), 점검=("i", "sum"), 위반발견=("f", "sum"))
    pts = g.reset_index().rename(columns={"신고": "쥐 신고", "위반발견": "점검에서 위반 발견"})
    save(93,
         metrics=[
             {"label": "Tract 쥐 신고 × 위반 발견", "value": f"{rho(g.신고, g.위반발견):.2f}", "help": f"Tract {len(g):,}개"},
             {"label": "위반 발견이 신고에서 출발", "value": "100%", "help": "이 자료의 '점검'은 모두 311 신고에 대한 점검이다"},
             {"label": "점검까지 간 신고", "value": f"{insp.mean() * 100:.0f}%"},
         ],
         charts=[
             {"title": "Tract마다 본 쥐 신고와 점검에서 발견된 위반", "kind": "scatter", "x": "쥐 신고", "y": "점검에서 위반 발견",
              "rows": records(pts[["GEOID", "쥐 신고", "점검에서 위반 발견"]]),
              "caption": "거의 직선이다. 위반은 신고가 있는 곳에서만 찾아지기 때문이다. 두 숫자는 독립된 증거가 아니다."},
         ])


RENAMES = [("Sewer", "Sewer Maintenance", "하수도"), ("Water System", "Water Maintenance", "상수도"),
           ("Hazardous Materials", "Hazardous Material", "유해 물질")]


def q094(df):
    p = df.problem.astype(str)
    mon = df.created.dt.to_period("M").dt.start_time
    rows = []
    for old, new, lab in RENAMES:
        for name, tag in [(old, "옛 이름"), (new, "새 이름")]:
            s = mon[p == name].value_counts()
            for m_, v in s.items():
                rows.append({"월": m_, "유형": f"{lab} · {tag}({name})", "민원": int(v)})
    r = pd.DataFrame(rows)
    full = pd.MultiIndex.from_product([sorted(mon.unique()), r.유형.unique()], names=["월", "유형"])
    r = r.set_index(["월", "유형"]).reindex(full, fill_value=0).reset_index()
    sew = r[r.유형.str.startswith("하수도")]
    sw = df[p.isin(["Sewer", "Sewer Maintenance"])]
    old_last = df[p == "Sewer"].created.max()
    save(94,
         metrics=[
             {"label": "하수도 옛 이름 마지막", "value": old_last.strftime("%Y-%m-%d")},
             {"label": "옛 이름만 세면", "value": f"{int((p == 'Sewer').sum()):,}건", "help": "그 뒤로는 0"},
             {"label": "두 이름 합", "value": f"{len(sw):,}건", "help": "실제 하수도 민원"},
         ],
         charts=[
             {"title": "같은 해 안에서 바뀐 유형 이름(하수도)", "kind": "line", "x": "월", "y": "민원", "color": "유형", "rows": records(sew),
              "point": True, "caption": "옛 이름의 선이 갑자기 끊기고 새 이름의 선이 이어받는다. 옛 이름만 세면 '하수도 민원이 사라졌다'는 오보가 된다."},
         ],
         tables=[{"title": "옛 이름과 새 이름의 월별 건수", "rows": records(r.pivot(index="월", columns="유형", values="민원").reset_index())}])


if __name__ == "__main__":
    want = {int(a) for a in sys.argv[1:]} or set(range(85, 95))
    df = load_311() if want - {90} else None
    if want & {87, 91, 93}:
        dt = with_tract(df)
        dt["cat"] = category(dt.problem)
        t = tract_rates(dt)
    elif want & {92}:
        dt = with_tract(df[["key"]])
        t = tract_rates(dt)
    jobs = {85: lambda: q085(df), 86: lambda: q086(df, borough_pop()), 87: lambda: q087(t), 88: lambda: q088(df),
            89: lambda: q089(df), 90: q090, 91: lambda: q091(dt, t), 92: lambda: q092(t), 93: lambda: q093(dt), 94: lambda: q094(df)}
    for k in sorted(want):
        jobs[k]()
