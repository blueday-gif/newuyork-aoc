"""8부. 이색 민원 — 통계 계산.
문항 77–84. 실행: python questions/calc/part08.py  (일부만: python questions/calc/part08.py 82 83)
84번은 식당 위생 등급(DOHMH)을 아직 붙이지 않아 311 쪽만 계산한다.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import BORO_KO, borough_pop, load_311, records, save  # noqa: E402

BOROS = list(BORO_KO)
AGENCY_KO = {"EDC": "경제개발공사(EDC)", "TLC": "택시리무진위원회(TLC)", "DPR": "공원국(DPR)", "OOS": "시장실 특별사업(OOS)",
             "DOHMH": "보건국(DOHMH)", "OTI": "기술혁신국(OTI)", "DOT": "교통국(DOT)", "DSNY": "위생국(DSNY)",
             "HPD": "주택보존개발국(HPD)", "NYPD": "경찰(NYPD)", "DEP": "환경보호국(DEP)", "DOB": "건축국(DOB)",
             "DHS": "노숙인서비스국(DHS)", "DCWP": "소비자노동자보호국(DCWP)"}


def q077(df):
    vc = df.problem.astype(str).value_counts()
    rank = pd.DataFrame({"순위": np.arange(1, len(vc) + 1), "민원": vc.values})
    tail = vc.tail(15).rename_axis("유형").reset_index(name="민원").sort_values("민원")
    save(77,
         metrics=[
             {"label": "민원 유형", "value": f"{len(vc)}가지"},
             {"label": "상위 10개 유형의 몫", "value": f"{vc.head(10).sum() / vc.sum() * 100:.0f}%"},
             {"label": "1년에 100건 미만", "value": f"{(vc < 100).sum()}가지"},
             {"label": "딱 1건", "value": f"{(vc == 1).sum()}가지", "help": ", ".join(vc[vc == 1].index)},
         ],
         charts=[
             {"title": "유형 순위와 건수(세로축 로그)", "kind": "scatter", "x": "순위", "y": "민원", "log_y": True, "rows": records(rank),
              "caption": "왼쪽 몇 개 유형이 대부분을 차지하고, 오른쪽으로 긴 꼬리가 이어진다. 세로축이 로그라서 한 칸이 10배다."},
         ],
         tables=[{"title": "가장 드문 유형 15", "rows": records(tail)}])


def q078(df):
    sq = df[df.problem.astype(str) == "Squeegee"]
    t = sq[["created", "borough", "loc_type"]].copy()
    t["접수일"] = t.created.dt.strftime("%Y-%m-%d %H시")
    t["자치구"] = t.borough.astype(str).map(BORO_KO).fillna(t.borough.astype(str))
    t["장소 유형"] = t.loc_type.astype(str)
    comp = pd.DataFrame([{"유형": k, "민원": int((df.problem.astype(str) == k).sum())}
                         for k in ["Squeegee", "Panhandling", "Graffiti", "Encampment"]])
    comp["유형"] = comp.유형.map({"Squeegee": "스퀴지(차창 닦이)", "Panhandling": "구걸", "Graffiti": "낙서", "Encampment": "노숙인 야영지"})
    save(78,
         metrics=[
             {"label": "스퀴지 민원(12개월)", "value": f"{len(sq)}건"},
             {"label": "같은 기간 구걸", "value": f"{int(comp.민원.iat[1]):,}건"},
         ],
         charts=[
             {"title": "'질서' 민원과 비교", "kind": "bar", "x": "유형", "y": "민원", "rows": records(comp),
              "caption": "1990년대의 상징이었던 스퀴지는 이제 1년에 다섯 건이다."},
         ],
         tables=[{"title": "스퀴지 민원 5건", "rows": records(t[["접수일", "자치구", "장소 유형"]])}])


ANIMALS = [("Dead Animal", "Raccoon", "죽은 너구리"), ("Dead Animal", "Squirrel", "죽은 다람쥐"), ("Dead Animal", "Cat", "죽은 고양이"),
           ("Dead Animal", "Dog", "죽은 개"), ("Dead Animal", "Bird", "죽은 새"), ("Illegal Animal Kept as Pet", "Rooster", "수탉(기르면 불법)")]


def q079(df, bp):
    p, d = df.problem.astype(str), df.detail.astype(str)
    rows = [{"동물": lab, "민원": int(((p == pr) & (d == de)).sum())} for pr, de, lab in ANIMALS]
    rows = pd.DataFrame(rows).sort_values("민원", ascending=False)
    pet_ko = {"Rooster": "수탉", "Other": "기타", "Farm Animal": "가축", "Snake": "뱀", "Ferret": "페럿", "Monkey": "원숭이",
              "Iguana": "이구아나", "Turtle Under 4 inches Long": "10cm 미만 거북"}
    ill = df[p == "Illegal Animal Kept as Pet"].detail.astype(str).value_counts().head(8).rename_axis("불법으로 기르는 동물").reset_index(name="민원")
    ill["불법으로 기르는 동물"] = ill["불법으로 기르는 동물"].map(pet_ko).fillna(ill["불법으로 기르는 동물"])
    roo = df[(p == "Illegal Animal Kept as Pet") & (d == "Rooster")].borough.astype(str).value_counts().reindex(BOROS).fillna(0).astype(int)
    save(79,
         metrics=[
             {"label": "죽은 너구리", "value": f"{int(rows.set_index('동물').loc['죽은 너구리', '민원']):,}건", "help": "위생국(DSNY)이 수거"},
             {"label": "죽은 다람쥐", "value": f"{int(rows.set_index('동물').loc['죽은 다람쥐', '민원']):,}건"},
             {"label": "기르는 수탉", "value": f"{int(rows.set_index('동물').loc['수탉(기르면 불법)', '민원']):,}건",
              "help": "자치구: " + ", ".join(f"{BORO_KO[b]} {roo[b]}" for b in BOROS)},
         ],
         charts=[
             {"title": "동물 민원", "kind": "barh", "x": "민원", "y": "동물", "rows": records(rows),
              "caption": "너구리·다람쥐는 '살아 있는 동물을 봤다'가 아니라 '죽은 동물을 치워 달라'는 민원이다."},
             {"title": "불법으로 기르는 동물 신고", "kind": "barh", "x": "민원", "y": "불법으로 기르는 동물", "rows": records(ill)},
         ])


def q080(df, bp):
    s = df[(df.problem.astype(str) == "Smoking or Vaping")]
    by = (s.borough.value_counts().reindex(BOROS) / bp.reindex(BOROS) * 1e5).round(1)
    rows = pd.DataFrame({"자치구": [BORO_KO[b] for b in BOROS], "10만 명당": by.values})
    lt = s.loc_type.astype(str).value_counts().head(8).rename_axis("장소 유형").reset_index(name="민원")
    det = s.detail.astype(str).value_counts()
    save(80,
         metrics=[
             {"label": "흡연·전자담배 민원", "value": f"{len(s):,}건", "help": " · ".join(f"{k} {v:,}" for k, v in det.head(3).items())},
             {"label": "금연구역 흡연", "value": f"{int(det.get('Allowed in Smoke Free Area', 0)):,}건"},
             {"label": "가장 많은 자치구", "value": rows.sort_values("10만 명당").자치구.iat[-1], "help": "10만 명당"},
         ],
         charts=[
             {"title": "흡연 민원이 들어온 장소 유형", "kind": "barh", "x": "민원", "y": "장소 유형", "rows": records(lt)},
             {"title": "자치구별 10만 명당", "kind": "bar", "x": "자치구", "y": "10만 명당", "rows": records(rows), "sort": "-y"},
         ])


def q081(df):
    p, d = df.problem.astype(str), df.detail.astype(str)
    es = df[p == "E-Scooter"]
    rows = pd.DataFrame([
        {"민원": "전동킥보드 부적절 주차·방치", "건수": int((es.detail.astype(str) == "Improperly Parked or Abandoned").sum())},
        {"민원": "전동킥보드 전체", "건수": len(es)},
        {"민원": "자전거도로 막은 차(불법주차)", "건수": int(((p == "Illegal Parking") & (d == "Blocked Bike Lane")).sum())},
        {"민원": "보도 막은 차(불법주차)", "건수": int(((p == "Illegal Parking") & (d == "Blocked Sidewalk")).sum())},
    ])
    save(81,
         metrics=[
             {"label": "전동킥보드 부적절 주차", "value": f"{int(rows.건수.iat[0]):,}건", "help": "교통국(DOT) 'E-Scooter' 유형"},
             {"label": "전동킥보드 유형 전체", "value": f"{len(es):,}건"},
             {"label": "'전기자전거' 유형", "value": "없음", "help": "세부 유형에도 없다"},
         ],
         charts=[
             {"title": "킥보드·자전거 관련 민원", "kind": "barh", "x": "건수", "y": "민원", "rows": records(rows),
              "caption": ("킥보드 유형은 공유 킥보드 사업 구역 안의 기기를 위한 칸이다. "
                          "개인 전기자전거가 보도를 막는 문제는 들어갈 칸이 마땅치 않다.")},
         ])


TYPES82 = ["Illegal Parking", "Noise - Residential", "HEAT/HOT WATER", "Dead Animal", "Rodent", "Street Light Condition", "Damaged Tree",
           "Pothole" if False else "Street Condition"]
KO82 = {"Illegal Parking": "불법주차", "Noise - Residential": "주거 소음", "HEAT/HOT WATER": "난방·온수", "Dead Animal": "죽은 동물",
        "Rodent": "쥐", "Street Light Condition": "가로등 고장", "Damaged Tree": "손상된 나무", "Street Condition": "도로 상태"}


def q082(df):
    rows = []
    for t in TYPES82:
        s = df[df.problem.astype(str) == t]
        h = s.hours.dropna()
        rows.append({"유형": KO82[t], "민원": len(s), "중앙값(시간)": round(float(h.median()), 1), "평균(시간)": round(float(h.mean()), 1),
                     "90% 경계(시간)": round(float(h.quantile(0.9)), 0), "미종결(%)": round(float(s.closed.isna().mean() * 100), 1)})
    rows = pd.DataFrame(rows).sort_values("중앙값(시간)", ascending=False)
    sl = rows.set_index("유형").loc["가로등 고장"]
    save(82,
         metrics=[
             {"label": "가로등 고장 중앙값", "value": f"{sl['중앙값(시간)']:.0f}시간", "help": f"약 {sl['중앙값(시간)'] / 24:.0f}일"},
             {"label": "가로등 미종결", "value": f"{sl['미종결(%)']:.1f}%"},
             {"label": "불법주차 중앙값", "value": f"{rows.set_index('유형').loc['불법주차', '중앙값(시간)']:.1f}시간"},
             {"label": "전체 처리시간", "value": f"중앙값 {df.hours.median():.1f} · 평균 {df.hours.mean():.0f}시간"},
         ],
         charts=[
             {"title": "유형별 처리시간 중앙값", "kind": "barh", "x": "중앙값(시간)", "y": "유형", "rows": records(rows),
              "caption": ("기관과 일의 성격이 속도를 정한다. 경찰이 지나가며 닫는 주차·소음은 몇 시간, "
                          "수리·점검이 필요한 가로등·쥐는 일주일이 넘는다. "
                          "나무는 중앙값은 3일이지만 평균은 2주로, 오래 걸리는 꼬리가 길다.")},
         ],
         tables=[{"title": "유형별 처리시간", "rows": records(rows)}])


def q083(df):
    g = df.groupby(df.agency.astype(str)).agg(민원=("key", "size"), 미종결=("closed", lambda s: s.isna().mean() * 100))
    g = g[g.민원 >= 1000].sort_values("미종결", ascending=False).head(10)
    g["미종결"] = g.미종결.round(1)
    g = g.reset_index().rename(columns={"agency": "기관", "미종결": "미종결(%)"})
    g["기관"] = g.기관.map(AGENCY_KO).fillna(g.기관)
    edc = df[df.agency.astype(str) == "EDC"].problem.astype(str).value_counts()
    tlc = df[df.agency.astype(str) == "TLC"]
    tlc_open = tlc.groupby(tlc.problem.astype(str)).closed.apply(lambda s: s.isna().mean() * 100).round(0)
    save(83,
         metrics=[
             {"label": "EDC 미종결", "value": "100%", "help": f"EDC 민원은 전부 '{edc.index[0]}'({edc.iat[0]:,}건)"},
             {"label": "TLC 미종결", "value": f"{tlc.closed.isna().mean() * 100:.1f}%",
              "help": f"택시 민원 {tlc_open.get('Taxi Complaint', 0):.0f}% 미종결"},
             {"label": "전체 미종결", "value": f"{df.closed.isna().mean() * 100:.1f}%"},
         ],
         charts=[
             {"title": "미종결 비율이 높은 기관(1년 1,000건 이상)", "kind": "barh", "x": "미종결(%)", "y": "기관", "rows": records(g),
              "caption": "'닫히지 않는 민원'은 처리가 늦다는 뜻만은 아니다. 헬리콥터 소음처럼 기관이 '기록만' 하는 민원도 있다."},
         ],
         tables=[{"title": "기관별 미종결", "rows": records(g)}])


def q084(df):
    p = df.problem.astype(str)
    fe = df[p == "Food Establishment"].detail.astype(str).value_counts().head(8).rename_axis("식당 민원 세부").reset_index(name="민원")
    rod = df[p == "Rodent"]
    lt = rod.loc_type.astype(str).value_counts()
    apt = lt.get("3+ Family Apt. Building", 0) / len(rod) * 100
    ltr = lt.head(8).rename_axis("쥐 민원 장소 유형").reset_index(name="민원")
    fp = df[p == "Food Poisoning"]
    m = fp.groupby(fp.created.dt.to_period("M").dt.start_time).size().rename_axis("월").reset_index(name="식중독 신고")
    save(84,
         metrics=[
             {"label": "식당 위생 등급 자료", "value": "아직 없음", "help": "DOHMH Restaurant Inspection Results"},
             {"label": "식당 민원", "value": f"{int((p == 'Food Establishment').sum()):,}건",
              "help": f"그중 쥐·벌레·쓰레기 {int(fe.민원.iat[0]):,}건"},
             {"label": "식중독 신고", "value": f"{len(fp):,}건", "help": f"3명 이상 {int((fp.detail.astype(str) == '3 or More').sum()):,}건"},
             {"label": "쥐 민원 중 3세대 이상 아파트", "value": f"{apt:.0f}%", "help": "'Rodent' 유형에는 식당 장소가 없다"},
         ],
         charts=[
             {"title": "식당 민원 세부 유형", "kind": "barh", "x": "민원", "y": "식당 민원 세부", "rows": records(fe),
              "caption": "식당의 쥐는 'Food Establishment' 유형으로 따로 들어간다. 'Rodent' 유형은 집과 길의 쥐다."},
             {"title": "'Rodent' 민원의 장소 유형", "kind": "barh", "x": "민원", "y": "쥐 민원 장소 유형", "rows": records(ltr)},
             {"title": "월별 식중독 신고", "kind": "bar", "x": "월", "y": "식중독 신고", "rows": records(m)},
         ])


if __name__ == "__main__":
    want = {int(a) for a in sys.argv[1:]} or set(range(77, 85))
    df = load_311()
    bp = borough_pop()
    jobs = {77: lambda: q077(df), 78: lambda: q078(df), 79: lambda: q079(df, bp), 80: lambda: q080(df, bp), 81: lambda: q081(df),
            82: lambda: q082(df), 83: lambda: q083(df), 84: lambda: q084(df)}
    for k in sorted(want):
        jobs[k]()
