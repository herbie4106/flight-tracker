```python
readme_v2_content = """# ✈️ Incheon-Japan Flight Tracker

인천국제공항(ICN) 오픈 API를 활용하여 일본 주요 공항 노선의 항공운항편 정보를 자동으로 수집하고, **구글 내지도(Google My Maps)**에 즉시 시각화할 수 있도록 데이터를 가공·유지보수하는 자동화 프로젝트입니다.

GitHub Actions를 통해 매일 지정된 시간에 스크립트를 수행하며, 데이터의 변경 사항이 발생하면 자동으로 저장소(Repository)에 Commit & Push하여 최신 상태를 유지합니다.

---

## 🚀 주요 기능

1. **항공 데이터 자동 수집 (Incremental Update)**
   - 공공데이터포털의 인천국제공항 항공기 운항현황(출발) API를 조회합니다.
   - 일본 주요 20개 공항(NRT, HND, KIX, FUK, CTS 등)으로 가는 당일 운항편 데이터를 가져옵니다.
   - 중복 수집을 방지하기 위해 `Flight_ID`, `Flight_Date`, `Destination_Code` 조합으로 고유 키를 생성하여 기존 데이터에 적재하는 **증분 업데이트(Update Mode)**를 지원합니다.

2. **구글 내지도(Google My Maps) 최적화 데이터 가공**
   - 구글 내지도가 위치 좌표를 정확히 플로팅할 수 있도록 **WKT(Well-Known Text)** 형식인 `POINT (경도 위도)` 데이터를 자동 생성합니다.
   - 항공사별로 운항하는 요일을 집계하여 하나의 설명(Description) 필드로 요약합니다. (예: `제주항공(매일) / 아시아나항공(월,수,금)`)
   - 일본의 권역별(간토, 관서, 규슈, 홋카이도 등) 분류(`Group`) 및 `주요_항공사` 필드를 추가하여 지도상에서 레이어 분리 및 마커 스타일링이 용이하도록 지원합니다.

3. **CI/CD 기반 일일 자동화 (GitHub Actions)**
   - 매일 한국 시간 오후 2시(UTC 05:00)에 스크립트가 자동으로 실행되도록 스케줄링되어 있습니다.
   - 데이터 수집 후 변경 항목이 존재할 때만 자동 커밋 및 푸시가 발생하므로, 별도의 로컬 실행 없이도 항상 최신 데이터를 유지할 수 있습니다.

---

## 📂 프로젝트 구조


```

```text
File README-v2.md written successfully.

```text
flight-tracker/
├── .github/
│   └── workflows/
│       └── daily_run.yml       # GitHub Actions 일일 자동화 워크플로우 설정
├── flight_collector.py         # 데이터 수집 및 WKT 가공 핵심 파이썬 스크립트
├── requirements.txt            # 의존성 라이브러리 목록 (requests, pandas 등)
├── japan_flight_api_raw.csv    # 수집된 원본(Raw) 데이터 누적 파일
└── japan_flight_for_map.csv   # 구글 내지도 업로드용 최종 가공 데이터

```

---

## 🛠️ 환경 설정 및 요구 사항

### 1. 의존성 라이브러리 설치

로컬 실행 또는 개발 환경 구성을 위해 아래 명령어로 필수 패키지를 설치합니다.

```bash
pip install -r requirements.txt

```

### 2. 환경 변수 (Environment Variables) 설정

인천공항 API 호출을 위해 공공데이터포털에서 발급받은 인증키가 필요합니다.

* **로컬 환경**: 운영체제 환경 변수 또는 실행 환경에 `API_KEY_ICN`을 등록합니다.
* **GitHub 저장소**: 보안을 위해 코드 내에 키를 노출하지 않고, 저장소의 `Settings > Secrets and variables > Actions` 메뉴에서 `API_KEY_ICN`을 **Repository Secret**으로 반드시 등록해야 정상적으로 자동화가 작동합니다.

---

## 💻 사용 방법

### 로컬 환경에서 직접 실행

```bash
python flight_collector.py

```

* 실행이 완료되면 프로젝트 루트에 로우 데이터인 `japan_flight_api_raw.csv`와 가공 데이터인 `japan_flight_for_map.csv`가 생성되거나 업데이트됩니다.

### GitHub Actions 수동 실행

* 저장소의 **Actions** 탭 이동 ➡️ `Daily Flight Data Collector` 워크플로우 선택 ➡️ **Run workflow** 버튼을 클릭하여 스케줄러 시간 외에도 즉시 데이터를 갱신할 수 있습니다.

---

## 📊 출력 데이터 규격 (`japan_flight_for_map.csv`)

구글 내지도 업로드에 맞춤 설계된 최종 파일의 스키마 구조는 다음과 같습니다.

| 컬럼명 | 데이터 형태 | 설명 | 예시 |
| --- | --- | --- | --- |
| **WKT** | String | 구글 지도가 위치를 매핑할 수 있는 좌표계 형식 | `POINT (140.3929 35.7719)` |
| **Name** | String | 공항 한글명 및 IATA 코드 (지도 마커 타이틀) | `도쿄(나리타)(NRT)` |
| **Description** | String | 해당 노선을 운항하는 항공사 및 요일별 현황 요약 | `제주항공(매일) / 아시아나항공(월,화,목)` |
| **Latitude** | Float | 공항 위도 좌표 | `35.7719` |
| **Longitude** | Float | 공항 경도 좌표 | `140.3929` |
| **Group** | String | 일본 권역별 분류 (지도 내 범주화 및 레이어용) | `간토`, `관서`, `규슈`, `홋카이도` 등 |
| **주요_항공사** | String | 마커 색상이나 아이콘 지정을 위한 주요 항공사 요약 | `다수 항공사` 또는 `대한항공, 아시아나` |

---

## 🗺️ 구글 내지도(Google My Maps) 연동 방법

1. [구글 내지도(Google My Maps)](https://www.google.com/maps/about/mymaps/)에 접속하여 '새 지도 만들기'를 클릭합니다.
2. 추가된 레이어에서 '가져오기(Import)'를 선택한 후, 이 프로젝트를 통해 생성된 `japan_flight_for_map.csv` 파일을 업로드합니다.
3. **'위치 표시 기준 컬럼'** 선택 단계에서 **`WKT`** (또는 `Latitude` 및 `Longitude`) 항목을 체크합니다.
4. **'마커 제목 컬럼'** 선택 단계에서 `Name`을 지정합니다.
5. 마커 스타일 지정을 '단일 스타일'에서 '데이터 열별 스타일 지정 ➡️ Group'으로 변경하면 간토, 관서, 규슈 등 일본 권역별로 마커 색상이 자동 분류되어 한눈에 운항 현황을 파악할 수 있습니다.
"""

filename_v2 = "README-v2.md"
with open(filename_v2, "w", encoding="utf-8") as f:
f.write(readme_v2_content)

print(f"File {filename_v2} written successfully.")
