"""100문 100답용 수치 계산. 기존 분석 파일은 읽기만 한다.
출력: reports/stories/story_01_numbers.txt
"""
import sys, io
import pandas as pd, numpy as np
from scipy.stats import spearmanr

RAW = r"D:/ny311/data/processed/311_requests_2020_present.parquet"
PROJ = r"G:/내 드라이브/newyork"
OUT = PROJ + "/reports/stories/story_01_numbers.txt"
buf = io.StringIO()
def p(*a):
    print(*a); print(*a, file=buf)
def sec(t): p("\n### " + t)

cols = {"Unique Key":"key","Created Date":"created","Closed Date":"closed","Agency":"agency",
        "Problem (formerly Complaint Type)":"problem","Problem Detail (formerly Descriptor)":"detail",
        "Incident Address":"addr","Borough":"borough","Open Data Channel Type":"channel",
        "Resolution Description":"resolution","BBL":"bbl","Location Type":"loc_type"}
df = pd.read_parquet(RAW, columns=list(cols)).rename(columns=cols)
pg = pd.read_parquet(PROJ + "/data/processed/nyc311_point_geoid.parquet").rename(columns={"unique_key":"key"})
df = df.merge(pg, on="key", how="left")
cm = pd.read_csv(PROJ + "/data/processed/category_map.csv")
df["cat"] = df.problem.map(dict(zip(cm.problem, cm.category))).fillna("기타")
df["hours"] = (df.closed - df.created).dt.total_seconds() / 3600
df.loc[df.hours < 0, "hours"] = np.nan
df["date"] = df.created.dt.normalize()
df["addr_n"] = df.addr.fillna("").str.upper().str.replace(r"\s+", " ", regex=True).str.strip()

acs = pd.read_csv(PROJ + "/data/processed/nyc_acs_2024_5yr.csv", dtype={"GEOID": str})
acs["renter_hh"] = acs.renter_occupied
stable = acs[acs.total_pop >= 1000].copy()
race = ["white_rate","black_rate","hispanic_rate","asian_rate"]
stable["major"] = stable[race].idxmax(axis=1).where(stable[race].max(axis=1) >= 0.5, "no_majority")
stable["inc_q"] = pd.qcut(stable.median_income, 5, labels=["Q1(최저)","Q2","Q3","Q4","Q5(최고)"])
stable["his_q"] = pd.qcut(stable.hispanic_rate, 5, labels=False) + 1
stable["renter_q"] = pd.qcut(stable.renter_rate, 5, labels=False) + 1
d = df.merge(stable[["GEOID","borough","major","inc_q","his_q","renter_q","total_pop","renter_hh","median_income","hispanic_rate"]]
             .rename(columns={"borough":"boro_acs"}), on="GEOID", how="inner")
p(f"stable-tract rows: {len(d):,}")
boro_pop = acs.groupby("borough").total_pop.sum()
p("borough pop:", boro_pop.to_dict())

def per_k(sub, by, denom="total_pop", scale=1000):
    num = sub.groupby(by).size()
    den = stable.groupby(by)[denom].sum()
    return (num / den * scale).round(1)

# ---------- A. 뉴스 검증 ----------
sec("A1 Vital City: 2026-02-23 폭설 날 자치구별 Snow or Ice")
for day in ["2026-02-23","2026-02-24"]:
    s = df[(df.date == day)]
    snow = s[s.problem == "Snow or Ice"].borough.value_counts()
    p(day, "전체", len(s), "| 눈 민원", snow.sum(), snow.to_dict())
    bp = boro_pop.rename(index=lambda x: x.split(" (")[0].upper())
    p("  눈 민원 10만명당:", (snow / bp * 1e5).round(1).dropna().sort_values(ascending=False).to_dict())
w = df[(df.created >= "2026-02-22 18:00") & (df.created < "2026-03-03") & (df.problem == "Snow or Ice")]
p("2/22 18시~3/2 눈 민원:", len(w), w.borough.value_counts().to_dict())
p("  10만명당:", (w.borough.value_counts() / bp * 1e5).round(0).dropna().sort_values(ascending=False).to_dict())
p("  처리시간 중앙값(시간) 자치구별:", w.groupby("borough").hours.median().round(1).to_dict())
winter = df[(df.created >= "2025-12-01") & (df.created < "2026-03-01")]
p("겨울(12~2월) 하루 평균 접수:", round(winter.groupby("date").size().mean()))

sec("A2 감사관 Turn Up the Heat: 한 시즌에 난방 민원 5회 초과 건물")
heat = df[df.problem == "HEAT/HOT WATER"]
hs = heat[(heat.created < "2026-06-01")]
b = hs[hs.bbl.notna() & (hs.bbl.str.strip() != "")].groupby("bbl").size()
p("2025-11~2026-05 난방 민원", len(hs), "| BBL 있는 건물 수", len(b),
  "| 5회 초과 건물", (b > 5).sum(), f"({(b>5).mean()*100:.1f}%)",
  "| 이 건물들의 민원 비율", f"{b[b>5].sum()/b.sum()*100:.1f}%")
p("  건물당 최다:", b.sort_values(ascending=False).head(3).to_dict())

sec("A3 City Limits: 난방 민원 중 '중복' 처리 비율")
res = heat.resolution.fillna("").str.lower()
dup = res.str.contains("duplicate")
p("난방 민원 중 결과문에 duplicate:", f"{dup.mean()*100:.1f}%")
cold = heat[(heat.date >= "2026-01-24") & (heat.date <= "2026-02-01")]
p("1/24~2/1 한파 기간 duplicate:", f"{cold.resolution.fillna('').str.lower().str.contains('duplicate').mean()*100:.1f}%")
p("결과문 상위:", heat.resolution.fillna("(없음)").str[:70].value_counts().head(4).to_dict())

sec("A4 AEI: 노숙인 야영지(Encampment) 처리시간 × 소득 5분위")
enc = d[d.problem == "Encampment"]
p(enc.groupby("inc_q", observed=True).hours.agg(["size","median"]).round(2).to_string())
hh = d[d.problem == "HEAT/HOT WATER"]
p("참고 난방 처리시간 중앙값 × 소득:", hh.groupby("inc_q", observed=True).hours.median().round(1).to_dict())
ip = d[d.problem == "Illegal Parking"]
p("참고 불법주차 처리시간 중앙값 × 소득:", ip.groupby("inc_q", observed=True).hours.median().round(2).to_dict())

sec("A5 DCJ: '사회적 무질서' 민원 비중")
soc = ["Encampment","Homeless Person Assistance","Graffiti","Panhandling","Drug Activity","Drinking","Urinating in Public","Disorderly Youth"]
x = df.problem.isin(soc)
p("해당 유형 합계", int(x.sum()), f"{x.mean()*100:.2f}%", df[x].problem.value_counts().to_dict())

sec("A6 Kontokosta: 히스패닉 비율과 난방 민원 (임차가구 1,000가구당)")
p("히스패닉 5분위별:", per_k(hh, "his_q", "renter_hh").to_dict())
t = hh.groupby(["inc_q","his_q"], observed=True).size() / stable.groupby(["inc_q","his_q"], observed=True).renter_hh.sum() * 1000
p("소득 5분위 안에서 히스패닉 5분위:\n" + t.unstack().round(0).to_string())

sec("A7 임대료 동결(2026-10-01 시행) 뒤 10월 난방 민원")
oct26 = heat[(heat.created >= "2026-10-01")]
nov25 = heat[(heat.created < "2025-12-01")]
p("2026-10 난방 민원", len(oct26), "| 2025-11 난방 민원", len(nov25), "| 하루 평균", round(len(oct26)/31), "vs", round(len(nov25)/30))
p("2026-10 주별:", oct26.groupby(oct26.created.dt.isocalendar().week).size().to_dict())

sec("A8 맘다니 취임(2026-01-01) 전후 단순 비교 함정")
m = df.groupby(df.created.dt.to_period("M")).size()
p("월별 총 민원:", m.to_dict())
p("월별 난방:", heat.groupby(heat.created.dt.to_period("M")).size().to_dict())

sec("A9 2024 뉴스 '소음 1위 73.8만' 대비 이번 12개월")
p("Noise 계열 problem 합계:", int(df.problem.str.startswith("Noise").sum()), "| 불법주차", int((df.problem=="Illegal Parking").sum()))

# ---------- B. 동네·인종·계층 ----------
sec("B1 과반 집단별 1,000명당 민원과 유형")
p("전체:", per_k(d, "major").to_dict())
for c in ["소음","주거환경","도로·교통","위생","해충·동물"]:
    p(f"  {c}:", per_k(d[d.cat == c], "major").to_dict())
sec("B2 소득 5분위별 1,000명당")
p("전체:", per_k(d, "inc_q").to_dict())
for c in ["소음","주거환경","도로·교통","위생","해충·동물"]:
    p(f"  {c}:", per_k(d[d.cat == c], "inc_q").to_dict())
sec("B3 채널(온라인·모바일 vs 전화) × 소득")
ch = d[d.channel != "UNKNOWN"]
share = ch.groupby("inc_q", observed=True).channel.value_counts(normalize=True).unstack().mul(100).round(1)
p(share.to_string())
share2 = ch.groupby("major").channel.value_counts(normalize=True).unstack().mul(100).round(1)
p(share2.to_string())
sec("B4 쥐(Rodent) 1,000명당 × 소득 · 자치구")
rod = d[d.problem == "Rodent"]
p("소득:", per_k(rod, "inc_q").to_dict())
p("자치구:", (df[df.problem=="Rodent"].borough.value_counts() / bp * 1e5).round(1).dropna().to_dict(), "(10만명당)")
sec("B5 심슨의 역설: 소득과 민원율 Spearman, 전체 vs 자치구 안")
tr = pd.read_csv(PROJ + "/outputs/tables/plan02_tracts.csv", dtype={"GEOID": str})
tr = tr[tr.stable == True].dropna(subset=["median_income"])
p("전체 rho", round(spearmanr(tr.median_income, tr.complaints_per_1k)[0], 2))
for bname, g in tr.groupby("borough"):
    p(f"  {bname} rho", round(spearmanr(g.median_income, g.complaints_per_1k)[0], 2), "n", len(g))
sec("B6 생태학적 오류 예: 히스패닉 비율과 소음 민원율 (Tract)")
tr2 = tr.merge(acs[["GEOID","hispanic_rate","black_rate","white_rate"]], on="GEOID")
for r in ["hispanic_rate","black_rate","white_rate"]:
    p(r, "vs 소음율 rho", round(spearmanr(tr2[r], tr2.noise_rate, nan_policy="omit")[0], 2),
      "| vs 주거율", round(spearmanr(tr2[r], tr2.housing_rate, nan_policy="omit")[0], 2),
      "| vs 도로율", round(spearmanr(tr2[r], tr2.road_rate, nan_policy="omit")[0], 2))

# ---------- C. 시간 ----------
sec("C1 소음: 시간대·요일·특별한 날")
nz = df[df.problem.str.startswith("Noise")]
p("시간대 1위:", nz.created.dt.hour.value_counts().head(3).to_dict())
p("요일(0=월):", nz.created.dt.dayofweek.value_counts().sort_index().to_dict())
for day in ["2025-12-31","2026-01-01","2026-07-04","2026-07-05","2026-02-08","2026-06-21","2026-03-17"]:
    p(day, "소음", int((nz.date == day).sum()))
p("소음 일평균", round(nz.groupby("date").size().mean()))
p("Noise 세부 상위:", nz.detail.value_counts().head(8).to_dict())
fw = df[df.detail.fillna("").str.contains("firework|fire work", case=False) | df.problem.str.contains("Firework", case=False)]
p("불꽃놀이 관련:", len(fw), fw.problem.value_counts().head(3).to_dict(), fw.date.value_counts().head(3).to_dict())
sec("C2 새벽 3시에 들어오는 민원")
p(df[df.created.dt.hour == 3].problem.value_counts().head(5).to_dict())
sec("C3 평균 vs 중앙값: 처리시간")
p("전체 평균", round(df.hours.mean(), 1), "중앙값", round(df.hours.median(), 1))
for prob in ["Illegal Parking","HEAT/HOT WATER","Rodent","Street Light Condition","Dead Animal","Pothole" ]:
    s = df[df.problem == prob].hours
    if len(s): p(f"  {prob}: n {len(s)}, 중앙값 {s.median():.1f}h, 평균 {s.mean():.1f}h, 미종결 {df[(df.problem==prob)].closed.isna().mean()*100:.1f}%")
sec("C4 평균으로의 회귀: 앞 6개월 상위 10% Tract는 뒤 6개월에도?")
d["half"] = np.where(d.created < "2026-05-01", "H1", "H2")
r = d.groupby(["GEOID","half"]).size().unstack().fillna(0)
r = r.join(stable.set_index("GEOID").total_pop)
r["r1"] = r.H1 / r.total_pop * 1000; r["r2"] = r.H2 / r.total_pop * 1000
top = r.r1 >= r.r1.quantile(0.9)
p("앞 상위10%가 뒤에도 상위10%:", f"{(r[top].r2 >= r.r2.quantile(0.9)).mean()*100:.0f}%",
  "| 앞 상위10% 평균 비율(전체 중앙값 대비)", round(r[top].r1.median()/r.r1.median(),2), "→ 뒤", round(r[top].r2.median()/r.r2.median(),2),
  "| 앞뒤 Spearman", round(spearmanr(r.r1, r.r2)[0], 2))

# ---------- D. 건물·주소 ----------
sec("D1 쏠림")
c = df[df.addr_n != ""].addr_n.value_counts()
p("주소 수", len(c), "| 1건만 있는 주소", f"{(c==1).mean()*100:.0f}%", "| 상위 1% 주소의 민원 비율", f"{c.head(int(len(c)*0.01)).sum()/c.sum()*100:.1f}%")
p("상위 10:", c.head(10).to_dict())
sec("D2 655 E 230th St 효과: 브롱크스 소음 순위")
bxn = df[df.problem.str.startswith("Noise")].borough.value_counts() / bp * 1000
p("자치구 소음 1,000명당:", bxn.round(1).dropna().to_dict())
no655 = df[(df.addr_n != "655 EAST 230 STREET") & df.problem.str.startswith("Noise")].borough.value_counts() / bp * 1000
p("655 제외:", no655.round(1).dropna().to_dict())
sec("D3 1인당의 함정: 거주 인구가 적은 Tract")
low = tr.sort_values("complaints_per_1k", ascending=False).head(5)[["GEOID","borough","total_pop","complaint_count","complaints_per_1k"]]
p(low.to_string())

# ---------- E. 희귀·이색 민원 ----------
sec("E1 가장 드문 민원 유형")
vc = df.problem.value_counts()
p(vc.tail(15).to_dict())
sec("E2 이색 세부내용")
for kw in ["Squirrel","Raccoon","Bed Bug","Ice Cream","Helicopter","Barking","Rooster","Drone","Car Horn","Banging","Smoking","E-Bike|E-Scooter|Electric Bike"]:
    s = df[df.detail.fillna("").str.contains(kw, case=False) | df.problem.str.contains(kw, case=False)]
    p(kw, len(s), s.detail.value_counts().head(2).to_dict())
sec("E3 기관별 미종결 비율")
p(df.groupby("agency").closed.apply(lambda s: s.isna().mean()*100).round(1).sort_values(ascending=False).head(6).to_dict())

open(OUT, "w", encoding="utf-8").write(buf.getvalue())
