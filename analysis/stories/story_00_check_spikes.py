import pandas as pd, numpy as np
pd.set_option("display.width", 220)
RAW = r"D:/ny311/data/processed/311_requests_2020_present.parquet"
PROJ = r"G:/내 드라이브/newyork"
df = pd.read_parquet(RAW, columns=["Unique Key","Created Date","Closed Date","Agency","Status",
     "Problem (formerly Complaint Type)","Problem Detail (formerly Descriptor)","Borough","Incident Address"])
df.columns = ["key","created","closed","agency","status","problem","detail","borough","addr"]
d = df.created.dt.date.value_counts().sort_index()
print("first 3 days", d.head(3).to_dict()); print("last 3 days", d.tail(3).to_dict())
print("median day", d.median())
print("hour of created on 2025-11-01:", df[df.created.dt.date==pd.Timestamp("2025-11-01").date()].created.dt.hour.value_counts().sort_index().to_dict())
dur = (df.closed - df.created).dt.total_seconds()/3600
neg = dur < 0
print("\nnegative duration by agency:", df[neg].agency.value_counts().head(6).to_dict())
print("status vs closed missing:"); print(pd.crosstab(df.status, df.closed.isna()).to_string())
print("\nmedian hours to close by agency:")
print(dur[dur>=0].groupby(df.agency).median().round(1).sort_values().to_string())
print("\nborough values:", df.borough.value_counts(dropna=False).to_dict())
# storm days
for day in ["2026-02-24","2026-01-27","2025-12-15"]:
    s = df[df.created.dt.date==pd.Timestamp(day).date()]
    print(day, s.problem.value_counts().head(5).to_dict())
# holiday spikes for noise
noise = df[df.problem.str.startswith("Noise")]
nd = noise.created.dt.date.value_counts()
print("\nnoise top days:", nd.sort_values(ascending=False).head(6).to_dict())
fw = df[df.detail.fillna("").str.contains("Firework", case=False)]
print("fireworks rows", len(fw), "top days", fw.created.dt.date.value_counts().head(4).to_dict())
# detail field richness
print("\ndistinct problem", df.problem.nunique(), "distinct detail", df.detail.nunique())
print("'기타' detail top:")
cm = pd.read_csv(PROJ + "/data/processed/category_map.csv")
other = set(cm[cm.category=="기타"].problem)
print(df[df.problem.isin(other)].problem.value_counts().head(10).to_dict())
# 655 E 230
a = df.addr.fillna("").str.upper().str.replace(r"\s+"," ",regex=True).str.strip()
x = df[a=="655 EAST 230 STREET"]
print("\n655 E 230: n", len(x), "| problems", x.problem.value_counts().head(3).to_dict())
print(" detail", x.detail.value_counts().head(4).to_dict())
print(" by month", x.created.dt.to_period("M").value_counts().sort_index().to_dict())
print(" median close hrs", round(((x.closed-x.created).dt.total_seconds()/3600).median(),2))
