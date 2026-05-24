import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import os
import xml.etree.ElementTree as ET

# ==========================================
# [사용자 입력] API 선택 및 키
# ==========================================
API_SOURCE = "ICN"
API_KEY = os.environ.get("API_KEY_ICN")  # ✅ 하드코딩 제거 - Secret에서만 읽음
API_KEY_KAC = ""

CSV_FILENAME = "japan_flight_api_raw.csv"
MAP_FILENAME = "japan_flight_for_map.csv"
DAYS_AHEAD = 0
DAYS_BACK = 0
UPDATE_MODE = True
DEBUG_MODE = True
TEST_REALTIME_MODE = False

# ==========================================
# [공항 정보 및 매핑 데이터]
# ==========================================
JAPAN_AIRPORTS = {
    # 홋카이도
    "AKJ": {"name": "Asahikawa", "lat": 43.6708, "lon": 142.4475},
    "CTS": {"name": "Sapporo (Chitose)", "lat": 42.7752, "lon": 141.6923},
    "OBO": {"name": "Obihiro", "lat": 42.7333, "lon": 143.2175},
    "HKD": {"name": "Hakodate", "lat": 41.7700, "lon": 140.8220},
    # 도호쿠
    "AOJ": {"name": "Aomori", "lat": 40.7347, "lon": 140.6908},
    "SDJ": {"name": "Sendai", "lat": 38.1397, "lon": 140.9169},
    "FKS": {"name": "Fukushima", "lat": 37.2274, "lon": 140.4350},
    # 간토
    "IBR": {"name": "Ibaraki", "lat": 36.1811, "lon": 140.4147},
    "NRT": {"name": "Narita (Tokyo)", "lat": 35.7719, "lon": 140.3929},
    "HND": {"name": "Haneda (Tokyo)", "lat": 35.5494, "lon": 139.7798},
    # 주부
    "KIJ": {"name": "Niigata", "lat": 37.9558, "lon": 139.1208},
    "FSZ": {"name": "Shizuoka (Mt.Fuji)", "lat": 34.7961, "lon": 138.1797},
    "NGO": {"name": "Nagoya (Chubu)", "lat": 34.8584, "lon": 136.8048},
    "KMQ": {"name": "Komatsu", "lat": 36.3938, "lon": 136.4075},
    "TOY": {"name": "Toyama", "lat": 36.6483, "lon": 137.1875},  # 추가
    # 관서
    "KIX": {"name": "Kansai (Osaka)", "lat": 34.4320, "lon": 135.2304},
    "UKB": {"name": "Kobe", "lat": 34.6329, "lon": 135.2237},
    # 주고쿠
    "OKJ": {"name": "Okayama", "lat": 34.7569, "lon": 133.8550},
    "HIJ": {"name": "Hiroshima", "lat": 34.4361, "lon": 132.9194},
    "YGJ": {"name": "Yonago", "lat": 35.4963, "lon": 133.2635},
    "UBJ": {"name": "Yamaguchi Ube", "lat": 33.9303, "lon": 131.2792},  # 추가
    # 시코쿠
    "TKS": {"name": "Tokushima", "lat": 34.1308, "lon": 134.6064},
    "TAK": {"name": "Takamatsu", "lat": 34.2141, "lon": 134.0156},
    "MYJ": {"name": "Matsuyama", "lat": 33.8272, "lon": 132.6997},
    "KCZ": {"name": "Kochi", "lat": 33.5461, "lon": 133.6694},  # 추가
    # 규슈
    "KKJ": {"name": "Kitakyushu", "lat": 33.8458, "lon": 131.0350},
    "FUK": {"name": "Fukuoka", "lat": 33.5859, "lon": 130.4507},
    "HSG": {"name": "Saga", "lat": 33.1497, "lon": 130.3022},
    "NGS": {"name": "Nagasaki", "lat": 32.9169, "lon": 129.9136},
    "KMJ": {"name": "Kumamoto", "lat": 32.8372, "lon": 130.8550},
    "OIT": {"name": "Oita", "lat": 33.4794, "lon": 131.7378},
    "KMI": {"name": "Miyazaki", "lat": 31.8772, "lon": 131.4486},
    "KOJ": {"name": "Kagoshima", "lat": 31.8039, "lon": 130.7194},
    # 오키나와
    "OKA": {"name": "Okinawa (Naha)", "lat": 26.1958, "lon": 127.6458},
    "SHI": {"name": "Shimojishima (Miyako)", "lat": 24.8267, "lon": 125.1447},  # MMY 교체
    "ISG": {"name": "Ishigaki", "lat": 24.3964, "lon": 124.1864},
}

REGION_MAP = {
    "AKJ": "홋카이도", "CTS": "홋카이도", "OBO": "홋카이도", "HKD": "홋카이도",
    "AOJ": "도호쿠", "SDJ": "도호쿠", "FKS": "도호쿠",
    "IBR": "간토", "NRT": "간토", "HND": "간토",
    "KIJ": "주부", "FSZ": "주부", "NGO": "주부", "KMQ": "주부", "TOY": "주부",
    "KIX": "관서", "UKB": "관서",
    "OKJ": "주고쿠", "HIJ": "주고쿠", "YGJ": "주고쿠", "UBJ": "주고쿠",
    "TKS": "시코쿠", "TAK": "시코쿠", "MYJ": "시코쿠", "KCZ": "시코쿠",
    "KKJ": "규슈", "FUK": "규슈", "HSG": "규슈", "NGS": "규슈",
    "KMJ": "규슈", "OIT": "규슈", "KMI": "규슈", "KOJ": "규슈",
    "OKA": "오키나와", "SHI": "오키나와", "ISG": "오키나와",
}

KOR_NAME_MAP = {
    "AKJ": "아사히카와", "CTS": "삿포로(신치토세)", "OBO": "오비히로", "HKD": "하코다테",
    "AOJ": "아오모리", "SDJ": "센다이", "FKS": "후쿠시마",
    "IBR": "이바라키", "NRT": "도쿄(나리타)", "HND": "도쿄(하네다)",
    "KIJ": "니가타", "FSZ": "시즈오카(후지산)", "NGO": "나고야(주부)", "KMQ": "고마쓰", "TOY": "도야마",
    "KIX": "오사카(간사이)", "UKB": "고베",
    "OKJ": "오카야마", "HIJ": "히로시마", "YGJ": "요나고", "UBJ": "야마구치(우베)",
    "TKS": "도쿠시마", "TAK": "다카마쓰", "MYJ": "마쓰야마", "KCZ": "고치",
    "KKJ": "기타큐슈", "FUK": "후쿠오카", "HSG": "사가", "NGS": "나가사키",
    "KMJ": "구마모토", "OIT": "오이타", "KMI": "미야자키", "KOJ": "가고시마",
    "OKA": "오키나와(나하)", "SHI": "미야코지마(시모지시마)", "ISG": "이시가키",
}

# ==========================================
# [API 통신 함수]
# ==========================================
KAC_BASE_URL = "http://openapi.airport.co.kr/service/rest"
KAC_INTERNATIONAL_SCHEDULE_PATH = "FlightScheduleList/getInternationalFlightSchedule"

def get_flight_data_kac(airport_code, search_date, debug=False):
    if not API_KEY_KAC:
        return []
    url = f"{KAC_BASE_URL}/{KAC_INTERNATIONAL_SCHEDULE_PATH}"
    params = {
        "ServiceKey": API_KEY_KAC, "depAirportId": "ICN",
        "arrAirportId": airport_code, "depPlandTime": search_date,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = [{c.tag: (c.text or "").strip() for c in item} for item in root.findall(".//item")]
        return items
    except Exception as e:
        if debug:
            print(f"  ⚠️ KAC API 오류 [{airport_code}]: {e}")
        return []

def get_flight_data(airport_code, search_date, debug=False, use_current_time=False):
    if not API_KEY:
        print("❌ API_KEY_ICN 환경변수가 설정되지 않았습니다.")
        return []

    url = "http://apis.data.go.kr/B551177/StatusOfPassengerFlightsOdp/getPassengerDeparturesOdp"
    if use_current_time:
        now = datetime.now()
        from_time = (now - timedelta(hours=2)).strftime("%H%M")
        to_time = (now + timedelta(hours=2)).strftime("%H%M")
        search_date = now.strftime("%Y%m%d")
    else:
        from_time, to_time = "0000", "2359"

    params = {
        "serviceKey": API_KEY, "numOfRows": 1000, "pageNo": 1,
        "from_time": from_time, "to_time": to_time,
        "airport": airport_code, "flight_date": search_date,
        "lang": "K", "type": "json"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if 'response' in data and 'body' in data['response']:
            body = data['response']['body']
            if body and 'items' in body and body['items']:
                items = body['items']
                if isinstance(items, dict): items = [items]
                return items
        return []
    except Exception as e:
        if debug:
            print(f"  ⚠️ ICN API 오류 [{airport_code} / {search_date}]: {e}")
        return []

# ==========================================
# [데이터 처리 함수]
# ==========================================
def load_existing_data():
    if os.path.exists(CSV_FILENAME) and UPDATE_MODE:
        try:
            return pd.read_csv(CSV_FILENAME, encoding='utf-8-sig')
        except Exception:
            pass
    return pd.DataFrame()

def create_unique_key(row):
    return f"{row.get('Flight_ID', '')}_{row.get('Flight_Date', '')}_{row.get('Destination_Code', '')}"

def process_and_save_summary(df):
    if df.empty or 'Weekday' not in df.columns or 'Destination_Code' not in df.columns:
        return

    summary_list = []
    weekday_order = ['월', '화', '수', '목', '금', '토', '일']

    for dest_code, group in df.groupby("Destination_Code"):
        lat = JAPAN_AIRPORTS.get(dest_code, {}).get("lat", 0)
        lon = JAPAN_AIRPORTS.get(dest_code, {}).get("lon", 0)
        kor_name = KOR_NAME_MAP.get(dest_code, dest_code)
        airline_days = {}

        for _, row in group.iterrows():
            airline = row.get('Airline', '')
            weekday = row.get('Weekday', '')
            if not airline: continue
            if airline not in airline_days: airline_days[airline] = set()
            airline_days[airline].add(weekday)

        desc_parts = []
        for airline, days_set in sorted(airline_days.items()):
            sorted_days = sorted([d for d in days_set if d in weekday_order], key=lambda x: weekday_order.index(x))
            day_str = "매일" if len(sorted_days) == 7 else ",".join(sorted_days)
            desc_parts.append(f"{airline}({day_str})")

        description = " / ".join(desc_parts)
        airlines = list(airline_days.keys())
        main_airlines = "다수 항공사" if len(airlines) >= 3 else ", ".join(airlines)
        region_group = REGION_MAP.get(dest_code, "기타")

        summary_list.append({
            "WKT": f"POINT ({lon} {lat})",
            "Name": f"{kor_name}({dest_code})",
            "Description": description if description else "(운항 정보 없음)",
            "Latitude": lat,
            "Longitude": lon,
            "Group": region_group,
            "주요_항공사": main_airlines
        })

    summary_df = pd.DataFrame(summary_list)
    cols = ["WKT", "Name", "Description", "Latitude", "Longitude", "Group", "주요_항공사"]
    summary_df = summary_df[[c for c in cols if c in summary_df.columns]]
    summary_df.to_csv(MAP_FILENAME, index=False, encoding='utf-8-sig')
    print(f"\n✅ [지도용 파일 생성] '{MAP_FILENAME}' (과거 양식 복구 완료)")

def main():
    today = datetime.now()
    date_range = [today - timedelta(days=i) for i in range(DAYS_BACK, 0, -1)] + \
                 [today + timedelta(days=i) for i in range(DAYS_AHEAD + 1)]

    existing_df = load_existing_data()
    existing_keys = set(existing_df.apply(create_unique_key, axis=1).values) if not existing_df.empty else set()

    all_data = []
    collection_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for search_date in date_range:
        date_str = search_date.strftime("%Y%m%d")
        for code, info in JAPAN_AIRPORTS.items():
            flights = get_flight_data_kac(code, date_str) if API_SOURCE == "KAC" else get_flight_data(code, date_str, debug=DEBUG_MODE)
            
            if flights:
                for f in flights:
                    if API_SOURCE == "KAC":
                        flight_id = f.get("flightId") or f.get("flightNo") or f.get("varmodel") or ""
                        sch = f.get("scheduleDateTime") or f.get("depPlandTime") or f.get("scheduleTime") or "0000"
                        time_str = str(sch)[-4:-2] + ":" + str(sch)[-2:] if len(str(sch)) >= 4 else "00:00"
                        airline = f.get("airline") or f.get("airlineNm") or "N/A"
                    else:
                        flight_id = f.get('flightId', '')
                        sch_time = f.get('scheduleDateTime', '0000')
                        time_str = sch_time[-4:-2] + ":" + sch_time[-2:] if len(sch_time) >= 4 else "00:00"
                        airline = f.get('airline', 'N/A')

                    unique_key = f"{flight_id}_{date_str}_{code}"
                    if UPDATE_MODE and unique_key in existing_keys: continue

                    weekday_kr = ['월','화','수','목','금','토','일'][search_date.weekday()]
                    all_data.append({
                        "Name": f"{flight_id} ({airline})",
                        "Description": f"인천→{info['name']}\n항공사: {airline}\n요일: {weekday_kr}\n출발: {time_str}\n날짜: {search_date.strftime('%Y-%m-%d')}",
                        "Latitude": info['lat'], "Longitude": info['lon'],
                        "Destination_Code": code, "Destination_Name": info['name'],
                        "Flight_ID": flight_id, "Flight_Date": date_str,
                        "Flight_Time": time_str, "Weekday": weekday_kr,
                        "Airline": airline, "Collected_At": collection_timestamp
                    })
            time.sleep(0.1)

    if all_data:
        new_df = pd.DataFrame(all_data)
        if UPDATE_MODE and not existing_df.empty:
            df = pd.concat([existing_df.drop(columns=['_unique_key'], errors='ignore'), new_df], ignore_index=True)
        else:
            df = new_df

        df = df.drop_duplicates(subset=['Flight_ID', 'Flight_Date', 'Destination_Code'], keep='last')

        if 'Weekday' not in df.columns:
            df['Weekday'] = pd.to_datetime(df['Flight_Date'], format='%Y%m%d', errors='coerce').dt.weekday.apply(
                lambda x: ['월','화','수','목','금','토','일'][int(x)] if pd.notnull(x) and 0 <= x <= 6 else '')
        if 'Destination_Name' not in df.columns:
            df['Destination_Name'] = df['Destination_Code'].map(lambda c: JAPAN_AIRPORTS.get(c, {}).get('name', c))
        if 'Flight_Date' in df.columns:
            df = df.sort_values(['Flight_Date', 'Flight_Time', 'Destination_Code'])

        df.to_csv(CSV_FILENAME, index=False, encoding='utf-8-sig')
        process_and_save_summary(df)
        print(f"✅ 신규 데이터 {len(all_data)}건 추가 완료")

    else:
        print("ℹ️ 신규 데이터 없음 (이미 수집됐거나 API 무응답). 기존 데이터로 map 파일 재생성합니다.")
        if not existing_df.empty:
            process_and_save_summary(existing_df)

if __name__ == "__main__":
    main()
