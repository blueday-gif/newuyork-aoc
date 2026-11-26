import sys, re
import pandas as pd, numpy as np
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 40)
RAW = r"D:/ny311/data/processed/311_requests_2020_present.parquet"
PROJ = r"G:/내 드라이브/newyork"

cols = ["Unique Key","Created Date","Closed Date","Agency","Problem (formerly Complaint Type)",
        "Problem Detail (formerly Descriptor)","Incident Address","Status","Open Data Channel Type",
        "Borough","Latitude","Longitude","Resolution Description","Location Type","BBL","Incident Zip"]
df = pd.read_parquet(RAW, columns=cols)
df.columns = ["key","created","closed","agency","problem","detail","addr","status","channel",
              "borough","lat","lon","resolution","loc_type","bbl","zip"]
print("== RAW", len(df), "unique keys", df.key.nunique())
print("created", df.created.min(), df.created.max())
print("closed ", df.closed.min(), df.closed.max())

# match with project point->GEOID
pg = pd.read_parquet(PROJ + "/data/processed/nyc311_point_geoid.parquet")
m = df.key.isin(pg.unique_key)
print("keys in point_geoid:", m.sum(), "of", len(pg), "| raw keys not in pg:", (~m).sum())
print("lat missing", df.lat.isna().sum())

print("\n== column missing %")
miss = (df.isna() | (df.astype(str).apply(lambda s: s.str.strip()) == "")).mean().mul(100).round(2)
print(miss.to_string())

print("\n== status"); print(df.status.value_counts(dropna=False).head(10).to_string())
print("\n== channel"); print(df.channel.value_counts(dropna=False).to_string())
print("\n== agency top"); print(df.agency.value_counts().head(12).to_string())

# response time
dur = (df.closed - df.created).dt.total_seconds() / 3600
print("\n== duration hours")
print("closed missing", df.closed.isna().sum(), "| negative", (dur < 0).sum(), "| zero", (dur == 0).sum(),
      "| >365d", (dur > 24*365).sum())
print(dur[dur >= 0].describe(percentiles=[.1,.5,.9,.99]).round(2).to_string())
print("closed after extract date 2026-11-12:", (df.closed > "2026-11-12").sum())

# created time artifacts (midnight stamps)
t = df.created
print("\n== created exactly 00:00:00 share", round(((t.dt.hour==0)&(t.dt.minute==0)&(t.dt.second==0)).mean()*100,2), "%")
print("by agency (midnight %):")
mid = (t.dt.hour==0)&(t.dt.minute==0)&(t.dt.second==0)
print(mid.groupby(df.agency).mean().mul(100).round(1).sort_values(ascending=False).head(8).to_string())

# daily counts
daily = t.dt.date.value_counts().sort_index()
print("\n== days", len(daily), "min", daily.min(), "max", daily.max())
print("top 8 days:"); print(daily.sort_values(ascending=False).head(8).to_string())

# address normalization
a = df.addr.fillna("").str.upper().str.strip()
an = a.str.replace(r"\s+", " ", regex=True)
print("\n== address: distinct raw", a.nunique(), "normalized", an.nunique(),
      "| rows whose addr has double spaces", a.str.contains("  ").sum())
top = an[an != ""].value_counts().head(10)
print(top.to_string())
c = an[an != ""].value_counts()
print("address concentration: top 0.1% addrs share", round(c.head(int(len(c)*0.001)).sum()/c.sum()*100,2),
      "% | top 1%", round(c.head(int(len(c)*0.01)).sum()/c.sum()*100,2), "%")

# duplicate-like: same addr+problem+created minute
dupe = df.assign(an=an, m=t.dt.floor("min")).duplicated(["an","problem","m"]) & (an != "")
print("same addr+problem+minute repeated rows:", dupe.sum(), round(dupe.mean()*100,2), "%")

# ACS race
acs = pd.read_csv(PROJ + "/data/processed/nyc_acs_2024_5yr.csv", dtype={"GEOID": str})
print("\n== ACS rows", len(acs))
rc = ["white_rate","black_rate","hispanic_rate","asian_rate"]
print(acs[rc + ["median_income","poverty_rate","renter_rate"]].describe().round(3).to_string())
print("race_total == total_pop:", (acs.race_total == acs.total_pop).mean().round(3))
s = acs[rc].sum(axis=1)
print("sum of 4 race shares: describe"); print(s.describe().round(3).to_string())
big = acs[acs.total_pop >= 1000].copy()
print("pop>=1000:", len(big), "race missing:", big[rc].isna().any(axis=1).sum())
big["major"] = big[rc].idxmax(axis=1).where(big[rc].max(axis=1) >= 0.5, "no_majority")
print("majority group (>=50%) tract counts:"); print(big.major.value_counts().to_string())
print("by borough:"); print(pd.crosstab(big.borough, big.major).to_string())
print("\nSpearman among race / SES (pop>=1000):")
print(big[rc + ["median_income","poverty_rate","renter_rate"]].corr("spearman").round(2).to_string())
print("\nlang_total non-null:", acs.lang_total.notna().sum(), "describe:", acs.lang_total.describe().round(0).to_dict())

# tract table join
tr = pd.read_csv(PROJ + "/outputs/tables/plan02_tracts.csv", dtype={"GEOID": str})
j = tr.merge(acs[["GEOID"] + rc], on="GEOID", how="left")
print("\n== plan02_tracts", len(tr), "race joined:", j[rc].notna().all(axis=1).sum())
cats = ["소음","주거환경","위생","도로·교통","해충·동물","건축·안전","기타"]
print("category sum == complaint_count:", (tr[cats].sum(axis=1) == tr.complaint_count).mean().round(4))
print("tract complaint total:", tr.complaint_count.sum())
