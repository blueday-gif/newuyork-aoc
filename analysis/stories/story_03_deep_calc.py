"""심화 페이지 20개(질문 1 제외)용 차트 데이터. 기존 분석 파일은 읽기만 한다.
출력: reports/stories/story_03_deep.json
"""
import json
import pandas as pd, numpy as np
from scipy.stats import spearmanr, chisquare, norm

RAW = r"D:/ny311/data/processed/311_requests_2020_present.parquet"
PROJ = r"G:/내 드라이브/newyork"
OUT = PROJ + "/reports/stories/story_03_deep.json"
R = lambda v, k=1: None if pd.isna(v) else round(float(v), k)

cols = {"Unique Key": "key", "Created Date": "created", "Closed Date": "closed", "Agency": "agency",
        "Problem (formerly Complaint Type)": "problem", "Problem Detail (formerly Descriptor)": "detail",
        "Incident Address": "addr", "Borough": "borough", "Open Data Channel Type": "channel",
        "Resolution Description": "resolution", "BBL": "bbl", "Council District": "cd"}
df = pd.read_parquet(RAW, columns=list(cols)).rename(columns=cols)
pg = pd.read_parquet(PROJ + "/data/processed/nyc311_point_geoid.parquet").rename(columns={"unique_key": "key"})
df = df.merge(pg, on="key", how="left")
cm = pd.read_csv(PROJ + "/data/processed/category_map.csv")
df["cat"] = df.problem.map(dict(zip(cm.problem, cm.category))).fillna("기타")
df["hours"] = (df.closed - df.created).dt.total_seconds() / 3600
df.loc[df.hours < 0, "hours"] = np.nan
df["date"] = df.created.dt.normalize()
df["addr_n"] = df.addr.fillna("").str.upper().str.replace(r"\s+", " ", regex=True).str.strip()
df["noise"] = df.problem.str.startswith("Noise")

acs = pd.read_csv(PROJ + "/data/processed/nyc_acs_2024_5yr.csv", dtype={"GEOID": str})
acs["boro"] = acs.borough.str.split(" (", regex=False).str[0]
bpop = acs.groupby("boro").total_pop.sum()
st = acs[acs.total_pop >= 1000].copy()
race = ["white_rate", "black_rate", "hispanic_rate", "asian_rate"]
st["major"] = st[race].idxmax(axis=1).where(st[race].max(axis=1) >= 0.5, "no_majority")
Q5 = ["Q1", "Q2", "Q3", "Q4", "Q5"]
st["inc_q"] = pd.qcut(st.median_income, 5, labels=Q5)
st["his_q"] = pd.qcut(st.hispanic_rate, 5, labels=Q5)
st["ren_q"] = pd.qcut(st.renter_rate, 5, labels=Q5)
st["old_q"] = pd.qcut(st.pre1950_share.rank(method="first"), 5, labels=Q5)
d = df.merge(st[["GEOID", "boro", "major", "inc_q", "his_q", "ren_q", "old_q"]], on="GEOID", how="inner")
cnt = d.groupby("GEOID").size().rename("n")
T = st.set_index("GEOID").join(cnt).fillna({"n": 0})
T["rate"] = T.n / T.total_pop * 1000
O = {}

def perk(sub, by, denom="total_pop"):
    return (sub.groupby(by, observed=True).size() / st.groupby(by, observed=True)[denom].sum() * 1000)

# ---- Q4 난방 중복 ----
heat = df[df.problem == "HEAT/HOT WATER"].copy()
heat["dup"] = heat.resolution.fillna("").str.lower().str.contains("duplicate")
hs = heat[heat.created < "2026-06-01"]
wk = hs.groupby(hs.created.dt.to_period("W-SUN")).agg(n=("dup", "size"), dup=("dup", "sum"))
wk = wk[wk.n > 300]
O["q04"] = {"weeks": [str(p.start_time.date())[5:] for p in wk.index], "n": wk.n.astype(int).tolist(),
            "dup_pct": (wk.dup / wk.n * 100).round(1).tolist(),
            "total": int(len(heat)), "dup_all": R(heat.dup.mean() * 100),
            "res_top": [[k[:90], int(v)] for k, v in heat.resolution.fillna("(없음)").value_counts().head(5).items()]}

# ---- Q5 건물 쏠림 (감사관 정의 vs 우리 정의) ----
b = hs[hs.bbl.notna() & (hs.bbl.astype(str).str.strip() != "")].groupby("bbl").size()
bins = [(1, 1, "1회"), (2, 5, "2–5회"), (6, 20, "6–20회"), (21, 100, "21–100회"), (101, 10**7, "100회 넘음")]
O["q05"] = {"bins": [{"label": l, "bld": int(((b >= a) & (b <= z)).sum()), "cmp": int(b[(b >= a) & (b <= z)].sum())} for a, z, l in bins],
            "n_bld": int(len(b)), "n_cmp": int(b.sum()), "over5": int((b > 5).sum()),
            "over5_pct": R((b > 5).mean() * 100), "over5_cmp_pct": R(b[b > 5].sum() / b.sum() * 100),
            "max": [[str(k), int(v)] for k, v in b.sort_values(ascending=False).head(3).items()]}

# ---- Q8 야영지 처리시간 × 소득 ----
enc = d[d.problem.str.contains("Encampment", case=False)]
rows = []
for q, g in enc.groupby("inc_q", observed=True):
    h = g.hours.dropna()
    rows.append({"q": q, "n": int(len(g)), "per1k": R(len(g) / st[st.inc_q == q].total_pop.sum() * 1000, 2),
                 "p25": R(h.quantile(.25), 2), "med": R(h.median(), 2), "p75": R(h.quantile(.75), 2), "mean": R(h.mean(), 1)})
O["q08"] = {"rows": rows, "income_cut": [R(x, 0) for x in st.groupby("inc_q", observed=True).median_income.median()]}

# ---- Q11 소음 이상치 ----
nz = df[df.noise]
ADDR = "655 EAST 230 STREET"
m_all = nz.groupby(nz.created.dt.strftime("%y-%m")).size()
m_ex = nz[nz.addr_n != ADDR].groupby(nz.created.dt.strftime("%y-%m")).size()
bx = (nz.borough.str.title().value_counts() / bpop * 1000).dropna()
bx_ex = (nz[nz.addr_n != ADDR].borough.str.title().value_counts() / bpop * 1000).dropna()
O["q11"] = {"months": list(m_all.index), "all": m_all.astype(int).tolist(), "ex": m_ex.reindex(m_all.index).astype(int).tolist(),
            "total": int(len(nz)), "addr_n": int((nz.addr_n == ADDR).sum()),
            "boro": [{"b": k, "all": R(bx[k]), "ex": R(bx_ex[k])} for k in bx.sort_values(ascending=False).index]}

# ---- Q13 10월 난방: 계절 ----
mh = heat.groupby(heat.created.dt.strftime("%y-%m")).size()
oct_ = heat[heat.created >= "2026-09-01"]
dd = oct_.groupby(oct_.date.dt.strftime("%m-%d")).size()
O["q13"] = {"months": list(mh.index), "heat": mh.astype(int).tolist(),
            "days": list(dd.index), "daily": dd.astype(int).tolist(), "oct": int(mh.get("26-10", 0)), "nov25": int(mh.get("25-11", 0))}

# ---- Q16 임차율 ----
cats = ["주거환경", "소음", "위생", "도로·교통", "해충·동물"]
O["q16"] = {"quint": [R(v) for v in perk(d, "ren_q").values],
            "ren_cut": [R(x * 100, 0) for x in st.groupby("ren_q", observed=True).renter_rate.median()],
            "rho_cat": []}
for c in cats:
    cc = d[d.cat == c].groupby("GEOID").size()
    t = T.join(cc.rename("c")).fillna({"c": 0}); t["cr"] = t.c / t.total_pop * 1000
    O["q16"]["rho_cat"].append([c, R(spearmanr(t.renter_rate, t.cr, nan_policy="omit")[0], 2)])
tt = T.dropna(subset=["renter_rate"])
O["q16"]["rho_all"] = R(spearmanr(tt.renter_rate, tt.rate)[0], 2)
O["q16"]["pearson_all"] = R(np.corrcoef(tt.renter_rate, tt.rate.clip(upper=tt.rate.quantile(.99)))[0, 1], 2)
O["q16"]["pts"] = [[R(a * 100), R(b_)] for a, b_ in zip(tt.renter_rate, tt.rate)]

# ---- Q20 노후 주택 ----
hou = d[d.cat == "주거환경"]
O["q20"] = {"quint": [R(v) for v in perk(hou, "old_q").values],
            "old_cut": [R(x * 100, 0) for x in st.groupby("old_q", observed=True).pre1950_share.median()]}
t = T.join(hou.groupby("GEOID").size().rename("h")).fillna({"h": 0}); t["hr"] = t.h / t.total_pop * 1000
t = t.dropna(subset=["pre1950_share"])
sl = np.polyfit(t.pre1950_share * 100, t.hr, 1)
O["q20"]["lin"] = [R(sl[1], 2), R(sl[0], 3)]
O["q20"]["rho"] = R(spearmanr(t.pre1950_share, t.hr)[0], 2)
O["q20"]["pts"] = [[R(a * 100), R(b_)] for a, b_ in zip(t.pre1950_share, t.hr)]

# ---- Q27 시의회 선거구 ----
cdf = df[df.cd.notna()].copy()
cdf["cd"] = pd.to_numeric(cdf.cd, errors="coerce")
cdf = cdf[cdf.cd.between(1, 51)]
g = cdf.groupby("cd")
rows = []
for k, gg in g:
    top = gg.problem.value_counts()
    rows.append({"cd": int(k), "boro": gg.borough.mode().iat[0].title(), "n": int(len(gg)),
                 "top": top.index[0], "top_n": int(top.iat[0]), "top_share": R(top.iat[0] / len(gg) * 100)})
O["q27"] = {"rows": sorted(rows, key=lambda r: -r["n"]), "missing": int(df.cd.isna().sum())}
O["q27"]["top_types"] = pd.Series([r["top"] for r in rows]).value_counts().to_dict()

# ---- Q33 인종 × 소득 층화 ----
O["q33"] = {"major": {k: R(v) for k, v in perk(d, "major").items()},
            "major_n": st.major.value_counts().to_dict(),
            "major_housing": {k: R(v) for k, v in perk(d[d.cat == "주거환경"], "major").items()}}
hh = d[d.problem == "HEAT/HOT WATER"]
grid = (hh.groupby(["inc_q", "his_q"], observed=True).size() /
        st.groupby(["inc_q", "his_q"], observed=True).renter_occupied.sum() * 1000)
ntr = st.groupby(["inc_q", "his_q"], observed=True).size()
O["q33"]["grid"] = [[R(grid.get((i, h), np.nan)) for h in Q5] for i in Q5]
O["q33"]["grid_n"] = [[int(ntr.get((i, h), 0)) for h in Q5] for i in Q5]
O["q33"]["his_cut"] = [R(x * 100, 0) for x in st.groupby("his_q", observed=True).hispanic_rate.median()]
O["q33"]["rho"] = {"his_renter": R(spearmanr(st.hispanic_rate, st.renter_rate, nan_policy="omit")[0], 2),
                   "his_pov": R(spearmanr(st.hispanic_rate, st.poverty_rate, nan_policy="omit")[0], 2)}

# ---- Q38 쥐 ----
rod = d[d.problem == "Rodent"]
O["q38"] = {"inc": [R(v, 2) for v in perk(rod, "inc_q").values],
            "boro": {k: R(v) for k, v in (df[df.problem == "Rodent"].borough.str.title().value_counts() / bpop * 1e5).dropna().sort_values(ascending=False).items()},
            "n": int((df.problem == "Rodent").sum())}
t = T.join(rod.groupby("GEOID").size().rename("r")).fillna({"r": 0})
O["q38"]["rho_pov"] = R(spearmanr(t.poverty_rate, t.r / t.total_pop, nan_policy="omit")[0], 2)

# ---- Q41 전화 비율 ----
ch = d[d.channel != "UNKNOWN"]
rows = []
for q, gg in ch.groupby("inc_q", observed=True):
    n = len(gg); k = int((gg.channel == "PHONE").sum()); p_ = k / n; se = np.sqrt(p_ * (1 - p_) / n)
    rows.append({"q": q, "n": n, "phone": k, "pct": R(p_ * 100), "lo": R((p_ - 1.96 * se) * 100, 2), "hi": R((p_ + 1.96 * se) * 100, 2)})
O["q41"] = {"inc": rows,
            "major": {k: R(v * 100) for k, v in ch.groupby("major").channel.apply(lambda s: (s == "PHONE").mean()).items()},
            "mix": ch.groupby("inc_q", observed=True).channel.value_counts(normalize=True).unstack().mul(100).round(1).reset_index().to_dict("records")}
# 작은 표본이었다면: 1/1000 표본의 신뢰구간
rng = np.random.default_rng(7)
small = []
for q, gg in ch.groupby("inc_q", observed=True):
    s_ = gg.sample(n=400, random_state=int(rng.integers(1e6)))
    p_ = (s_.channel == "PHONE").mean(); se = np.sqrt(p_ * (1 - p_) / 400)
    small.append({"q": q, "pct": R(p_ * 100), "lo": R((p_ - 1.96 * se) * 100), "hi": R((p_ + 1.96 * se) * 100)})
O["q41"]["small"] = small

# ---- Q44 심슨 ----
tt = T.dropna(subset=["median_income"])
O["q44"] = {"rho_all": R(spearmanr(tt.median_income, tt.rate)[0], 2),
            "rho_boro": {k: [R(spearmanr(gg.median_income, gg.rate)[0], 2), int(len(gg))] for k, gg in tt.groupby("boro")},
            "pts": [[R(a / 1000), R(min(b_, 3000)), c] for a, b_, c in zip(tt.median_income, tt.rate, tt.boro)],
            "boro_med": {k: [R(gg.median_income.median() / 1000), R(gg.rate.median())] for k, gg in tt.groupby("boro")}}

# ---- Q49 소음 시계 ----
hr = nz.created.dt.hour.value_counts().sort_index()
dw = nz.created.dt.dayofweek.value_counts().sort_index()
chi_h = chisquare(hr.values); chi_d = chisquare(dw.values)
O["q49"] = {"hour": hr.astype(int).tolist(), "dow": dw.astype(int).tolist(), "total": int(len(nz)),
            "night_share": R(hr.loc[[22, 23, 0, 1, 2, 3, 4, 5]].sum() / hr.sum() * 100),
            "wkend_share": R(dw.loc[[5, 6]].sum() / dw.sum() * 100),
            "chi_h": R(chi_h.statistic, 0), "chi_d": R(chi_d.statistic, 0)}
# 작은 예: 1개 건물 1주일 70건이라면
O["q49"]["toy"] = {"obs": [6, 7, 8, 9, 12, 15, 13], "exp": 10}
O["q49"]["toy_chi"] = R(chisquare([6, 7, 8, 9, 12, 15, 13]).statistic, 2)
O["q49"]["toy_p"] = R(chisquare([6, 7, 8, 9, 12, 15, 13]).pvalue, 3)

# ---- Q53 불꽃놀이 ----
fw = df[df.detail.fillna("").str.contains("firework|fire work", case=False) | df.problem.str.contains("Firework", case=False)]
fs = fw[(fw.created >= "2026-05-15") & (fw.created < "2026-08-16")].groupby(fw.date.dt.strftime("%m-%d")).size()
idx = pd.date_range("2026-05-15", "2026-08-15").strftime("%m-%d")
fs = fs.reindex(idx, fill_value=0)
O["q53"] = {"days": list(fs.index), "n": fs.astype(int).tolist(), "total": int(len(fw)),
            "base_med": R(fs[(fs.index < "06-15")].median()), "jul4": int(fs.get("07-04", 0)),
            "jul3_5": int(fs.loc[["07-03", "07-04", "07-05"]].sum()),
            "top_days": fw.date.dt.strftime("%m-%d").value_counts().head(5).to_dict(),
            "boro": {k: R(v) for k, v in (fw.borough.str.title().value_counts() / bpop * 1e5).dropna().sort_values(ascending=False).items()}}

# ---- Q59 평균으로의 회귀 ----
d["half"] = np.where(d.created < "2026-05-01", "H1", "H2")
r = d.groupby(["GEOID", "half"]).size().unstack().fillna(0).join(st.set_index("GEOID").total_pop)
r["r1"] = r.H1 / r.total_pop * 1000; r["r2"] = r.H2 / r.total_pop * 1000
r["dec1"] = pd.qcut(r.r1.rank(method="first"), 10, labels=False) + 1
dec = r.groupby("dec1").agg(r1=("r1", "median"), r2=("r2", "median"))
O["q59"] = {"dec": [[int(k), R(a, 1), R(b_, 1)] for k, (a, b_) in dec.iterrows()],
            "med1": R(r.r1.median()), "med2": R(r.r2.median()),
            "keep_top": R((r[r.dec1 == 10].r2 >= r.r2.quantile(.9)).mean() * 100, 0),
            "rho": R(spearmanr(r.r1, r.r2)[0], 2),
            "pts": [[R(a), R(b_)] for a, b_ in zip(r.r1.clip(upper=1500), r.r2.clip(upper=1500))]}

# ---- Q69 주소 로렌츠 ----
c = df[df.addr_n != ""].addr_n.value_counts()
v = np.sort(c.values)[::-1]; cum = np.cumsum(v) / v.sum()
xs = np.array([0.001, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.43, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
lor = [[0, 0]] + [[R(x * 100, 1), R(cum[max(0, int(np.ceil(x * len(v))) - 1)] * 100)] for x in xs]
asc = np.sort(c.values); n = len(asc)
gini = (2 * np.sum((np.arange(1, n + 1)) * asc) / (n * asc.sum())) - (n + 1) / n
O["q69"] = {"n_addr": int(len(c)), "one": R((c == 1).mean() * 100, 0), "top1": R(c.head(int(len(c) * .01)).sum() / c.sum() * 100),
            "top01": R(c.head(int(len(c) * .001)).sum() / c.sum() * 100), "gini": R(gini, 2), "lorenz": lor,
            "top10": [[k.title(), int(x)] for k, x in c.head(10).items()]}
# 비교: 인구의 Tract별 지니(민원이 사람 따라 고르게 퍼졌다면)
pp = np.sort(st.total_pop.values); n2 = len(pp)
O["q69"]["gini_pop"] = R((2 * np.sum(np.arange(1, n2 + 1) * pp) / (n2 * pp.sum())) - (n2 + 1) / n2, 2)

# ---- Q74 작은 수 ----
cnt_all = df.groupby("GEOID").size().rename("n")
A = acs.set_index("GEOID").join(cnt_all).fillna({"n": 0})
A = A[A.total_pop > 0]
A["rate"] = A.n / A.total_pop * 1000
med = T.rate.median()
O["q74"] = {"pts": [[int(p_), R(min(rt, 20000), 0), int(n_)] for p_, rt, n_ in zip(A.total_pop, A.rate, A.n)],
            "median": R(med), "small_n": int((A.total_pop < 1000).sum()),
            "top5": A.sort_values("rate", ascending=False).head(5)[["boro", "total_pop", "n", "rate"]].round(0).reset_index().values.tolist()}

# ---- Q77 긴 꼬리 ----
vc = df.problem.value_counts()
O["q77"] = {"rank": [[i + 1, int(x)] for i, x in enumerate(vc.values)], "n_types": int(len(vc)),
            "top10_share": R(vc.head(10).sum() / vc.sum() * 100), "under100": int((vc < 100).sum()),
            "head": [[k, int(x)] for k, x in vc.head(8).items()], "tail": [[k, int(x)] for k, x in vc.tail(12).items()]}
for kw in ["Rooster", "Squirrel", "Raccoon", "Ice Cream", "Squeegee"]:
    O["q77"].setdefault("fun", []).append([kw, int((df.detail.fillna("").str.contains(kw, case=False) | df.problem.str.contains(kw, case=False)).sum())])

# ---- Q85 평균 vs 중앙값 ----
h = df.hours.dropna()
edges = [0, 0.25, 0.5, 1, 2, 4, 8, 24, 72, 168, 720, 2160, 1e9]
lab = ["15분", "30분", "1시간", "2시간", "4시간", "8시간", "1일", "3일", "1주", "1달", "3달", "그 이상"]
hist = pd.cut(h, edges, right=False, labels=lab).value_counts().reindex(lab)
O["q85"] = {"hist": hist.astype(int).tolist(), "labels": lab, "mean": R(h.mean()), "median": R(h.median()),
            "p90": R(h.quantile(.9)), "zero": int((h == 0).sum()), "neg": int(((df.closed - df.created).dt.total_seconds() < 0).sum()),
            "types": []}
for prob in ["Illegal Parking", "Noise - Residential", "HEAT/HOT WATER", "Rodent", "Street Light Condition"]:
    s = df[df.problem == prob].hours
    O["q85"]["types"].append([prob, R(s.median()), R(s.mean()), R(df[df.problem == prob].closed.isna().mean() * 100)])
top5 = h.sort_values(ascending=False)
O["q85"]["drop_top1"] = R(h[h < h.quantile(.99)].mean())

# ---- Q90 다중 비교: 가짜 데이터 시뮬레이션 ----
rng = np.random.default_rng(2026)
ntr = len(T)
# 각 Tract: 진짜 차이가 0인 세계에서 z 점수를 뽑는다(순수한 우연)
z = rng.standard_normal(ntr)
pv = 2 * (1 - norm.cdf(np.abs(z)))
order = np.sort(pv); k = np.arange(1, ntr + 1)
bh = (order <= k / ntr * 0.05)
O["q90"] = {"ntr": ntr, "sig": int((pv < .05).sum()), "bonf": int((pv < .05 / ntr).sum()),
            "bh": int(bh.nonzero()[0].max() + 1) if bh.any() else 0,
            "phist": np.histogram(pv, bins=20, range=(0, 1))[0].astype(int).tolist(),
            "expected": R(ntr * 0.05, 0)}

json.dump(O, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, default=lambda o: o.item() if hasattr(o, "item") else str(o))
for k_, v_ in O.items():
    s = json.dumps(v_, ensure_ascii=False, default=str)
    print(k_, s[:600])
