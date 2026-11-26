"""샘플 페이지(질문 1: 폭설과 스태튼아일랜드)용 데이터.
출력: reports/stories/story_02_snow_sample.json
"""
import json
import pandas as pd, numpy as np
import statsmodels.formula.api as smf

RAW = r"D:/ny311/data/processed/311_requests_2020_present.parquet"
PROJ = r"G:/내 드라이브/newyork"
df = pd.read_parquet(RAW, columns=["Unique Key","Created Date","Problem (formerly Complaint Type)","Borough"])
df.columns = ["key","created","problem","borough"]
snow = df[df.problem == "Snow or Ice"].copy()
pg = pd.read_parquet(PROJ + "/data/processed/nyc311_point_geoid.parquet").rename(columns={"unique_key":"key"})
acs = pd.read_csv(PROJ + "/data/processed/nyc_acs_2024_5yr.csv", dtype={"GEOID": str})
acs["boro"] = acs.borough.str.split(" (", regex=False).str[0]
bpop = acs.groupby("boro").total_pop.sum()
out = {}

# 1) 일별 자치구 눈 민원 2/15~3/5
win = snow[(snow.created >= "2026-02-15") & (snow.created < "2026-03-06")]
win = win[win.borough != "Unspecified"]
daily = win.groupby([win.created.dt.strftime("%m-%d"), "borough"]).size().unstack(fill_value=0)
out["daily"] = {"dates": list(daily.index), "series": {b.title(): daily[b].tolist() for b in daily.columns}}

# 2) 2/23 자치구별 건수, 10만명당
d23 = snow[snow.created.dt.strftime("%Y-%m-%d") == "2026-02-23"].borough.value_counts()
rows = []
for b, n in d23.items():
    if b == "Unspecified": continue
    name = b.title()
    pop = bpop[name]
    rows.append({"borough": name, "n": int(n), "pop": int(pop), "per100k": round(n / pop * 1e5, 1)})
out["feb23"] = sorted(rows, key=lambda r: -r["per100k"])
out["feb23_total_all"] = int((df.created.dt.strftime("%Y-%m-%d") == "2026-02-23").sum())

# 3) Tract 단위: 폭설 주간 (2/22 18시 ~ 3/2) 눈 민원 → GEOID → ACS
wk = snow[(snow.created >= "2026-02-22 18:00") & (snow.created < "2026-03-03")].merge(pg, on="key", how="inner")
cnt = wk.groupby("GEOID").size().rename("snow_n")
t = acs[acs.total_pop >= 1000].set_index("GEOID").join(cnt).fillna({"snow_n": 0})
t["rate"] = t.snow_n / t.total_pop * 1000
t["owner_rate"] = 1 - t.renter_rate
t = t.dropna(subset=["owner_rate"])
out["join"] = {"snow_week": int(len(snow[(snow.created >= "2026-02-22 18:00") & (snow.created < "2026-03-03")])),
               "with_geoid": int(len(wk)), "tracts": int(len(t)), "tracts_zero": int((t.snow_n == 0).sum())}

m1 = smf.ols("rate ~ owner_rate", data=t).fit(cov_type="HC1")
m2 = smf.ols("rate ~ owner_rate + C(boro, Treatment('Manhattan'))", data=t).fit(cov_type="HC1")
m3 = smf.ols("rate ~ owner_rate", data=t[t.boro != "Staten Island"]).fit(cov_type="HC1")
def summ(m):
    return {"intercept": round(m.params["Intercept"], 2), "slope": round(m.params["owner_rate"], 2),
            "slope_10pp": round(m.params["owner_rate"] * 0.1, 2),
            "ci": [round(x * 0.1, 2) for x in m.conf_int().loc["owner_rate"]],
            "r2": round(m.rsquared, 3), "n": int(m.nobs)}
out["m1"], out["m2"], out["m3"] = summ(m1), summ(m2), summ(m3)
out["m2_boro"] = {k.split("[T.")[1].rstrip("]"): round(v, 1) for k, v in m2.params.items() if "C(boro" in k}
out["boro_owner"] = (t.groupby("boro").owner_rate.median() * 100).round(1).to_dict()
out["boro_rate_median"] = t.groupby("boro").rate.median().round(2).to_dict()
pts = t[["owner_rate","rate","boro"]].copy()
pts["owner_rate"] = (pts.owner_rate * 100).round(1)
pts["rate"] = pts.rate.round(2)
out["points"] = pts.values.tolist()

json.dump(out, open(PROJ + "/reports/stories/story_02_snow_sample.json", "w", encoding="utf-8"), ensure_ascii=False)
for k in ["feb23","feb23_total_all","join","m1","m2","m3","m2_boro","boro_owner","boro_rate_median"]:
    print(k, out[k])
print("daily dates", out["daily"]["dates"][:3], "...", len(out["daily"]["dates"]))
