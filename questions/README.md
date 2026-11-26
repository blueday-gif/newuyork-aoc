# 100가지 질문 — 문항별 Streamlit 앱

```
streamlit run questions/app.py      # 저장소 루트에서
```

## 폴더
| 위치 | 내용 | 만드는 법 |
|---|---|---|
| `meta/questions.json` | 질문·한 줄 답 100개 | `python questions/build_meta.py` (원문 md에서 자동) |
| `meta/concepts.toml` | 공통 개념 카드 | 손으로 쓴다 |
| `content/q###.toml` | 문항 해설: background, method, caveats, sources, concepts, related, (결합) join_status | 손으로 쓴다 |
| `calc/partNN.py` | 부별 통계 계산 → `data/q###.json` | `python questions/calc/part01.py` |
| `data/q###.json` | metrics, charts(kind: bar·barh·line·stack·stackh·group·scatter), tables | 계산 스크립트가 만든다 |

진행: 1–10부(1–100) 모두 채웠다. 97문항은 통계+해설, 21·22·48번은 해설만 있다. 개념 카드 58장.
하수도·상수도·유해 물질 유형은 2026년 7월에 이름이 바뀌었다(94번). 이 유형을 셀 때는 옛 이름과 새 이름을 함께 센다.
11번의 이상치 주소(655 E 230th St, 4.7만 건)는 흑인 다수·소득 최하위·임차율 최상위 Tract에 있다. 집단별 비율을 낼 때 이 주소를 뺀 값도 확인한다.
차트 필드 이름의 따옴표·대괄호·점·콜론은 qlib가 자동으로 바꾼다(Vega-Lite가 경로 문법으로 읽어 조용히 실패하기 때문).
[결합] 문항은 95번(ACS)을 빼고 외부 자료(NOAA, HPD 위반, RGB 목록, 선거구 경계·개표, GTFS, PLUTO, FloodNet 등)를 아직 붙이지 않았다. 각 문항의 '계산 방법'에 결합 순서를 적었다.
계산 예: `python questions/calc/part02.py 16 20` (번호를 빼면 그 부 전체)

311 원본 경로는 `calc/common.py`의 `RAW`(환경 변수 `NY311_RAW`로 바꿀 수 있음). 첫 실행 때 필요한 열만 `questions/.cache/`에 저장한다.

## 문항 하나 추가하기
1. `calc/partNN.py`에 `q0NN(df)` 함수를 만들고 `save()`로 저장한다.
2. `content/q0NN.toml`을 쓴다. 개념은 `concepts.toml`의 키로 건다.
3. 앱 목차에서 "완성" 배지가 붙는지 본다.
