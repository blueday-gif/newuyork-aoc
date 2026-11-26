# newyork

뉴욕시 Census Tract에 311 민원 건수와 ACS 2024 5개년 지표를 붙여 보는 분석 프로젝트다.

311 기간은 2025-11-01 ~ 2026-10-31이다. 민원 원본은 이 폴더에 두지 않고 `data/external/SOURCE.txt`가 가리키는 parquet를 읽는다.

## 폴더

```
data/raw/          TIGER/Line 2024 뉴욕주 Tract 경계 zip
data/external/     외부 311 파일 위치
data/processed/    ACS, Tract 집계, 민원-GEOID 연결
scripts/           수집과 공간 결합
analysis/          EDA
outputs/tables/    요약 표
outputs/figures/   그림
reports/           해석이 있는 보고서
```

## 실행

```powershell
py -3 -m pip install -r requirements.txt
py -3 scripts/nyc_acs_2024.py
py -3 scripts/join_311_acs.py
py -3 analysis/eda_01_overview.py
py -3 analysis/plan_02_core.py
py -3 -m streamlit run dashboard/app.py
```

ACS 수집은 환경변수 `CENSUS_API_KEY`가 필요하다. 이미 `data/processed`에 결과가 있으면 분석 스크립트부터 다시 실행하면 된다.

`plan_02_core.py`는 분석계획서의 우선 분석(유형, 임차율, 공간 군집, 품질)을 계산하고 `outputs/tables/plan02_*.csv`에 저장한다. 대시보드는 그 표를 읽는다.
