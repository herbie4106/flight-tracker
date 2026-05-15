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
API_KEY = os.environ.get("API_KEY_ICN", "9e77ad58a11ddf5ae8c4aaea81e4495ffe2db8da1ab6bacbbb4442f5f39a0e95")
API_KEY_KAC = ""  

CSV_FILENAME = "japan_flight_api_raw.csv"   
MAP_FILENAME = "japan_flight_for_map.csv"  

DAYS_AHEAD = 0  
DAYS_BACK = 0   
UPDATE_MODE = True  
DEBUG_MODE = True  
TEST_REALTIME_MODE = False  

# 조회할 일본 주요 공항 목록
JAPAN_AIRPORTS = {
    "NRT": {"name": "Narita (Tokyo)", "lat": 35.7719, "lon": 140.3929},
    "HND": {"name": "Haneda (Tokyo)", "lat": 35.5494, "lon": 139.7798},
    "KIX": {"name": "Kansai (Osaka)", "lat": 34.4320, "lon": 135.2304},
    "FUK": {"name": "Fukuoka", "lat": 33.5859, "lon": 130.4507},
    "CTS": {"name": "Sapporo (Chitose)", "lat": 42.7752, "lon": 141.6923},
    "NGO": {"name": "Nagoya (Chubu)", "lat": 34.8584, "lon": 136.8048},
    "OKA": {"name": "Okinawa (Naha)", "lat": 26.1958, "lon": 127.6458},
    "HIJ": {"name": "Hiroshima", "lat": 34.4361, "lon": 132.9194},
    "MYJ": {"name": "Matsuyama", "lat": 33.8272, "lon": 132.6997},
    "TAK": {"name": "Takamatsu", "lat": 34.2141, "lon": 134.0156},
    "KMJ": {"name": "Kumamoto", "lat": 32.8372, "lon": 130.8550},
    "KOJ": {"name": "Kagoshima", "lat": 31.8039, "lon": 130.7194},
    "FKS": {"name": "Fukushima", "lat": 37.2274, "lon": 140.4350},
    "OITA": {"name": "Oita", "lat": 33.4794, "lon": 131.7378},
    "SHM": {"name": "Shizuoka", "lat": 34.7963, "lon": 138.1796},
    "KKJ": {"name": "Kitakyushu", "lat": 33.8458, "lon": 131.0350},
    "FSZ": {"name": "Shizuoka (Mt.Fuji)", "lat": 34.7961, "lon": 138.1797},
    "SDJ": {"name": "Sendai", "lat": 38.1397, "lon": 140.9169},
    "KOM": {"name": "Komatsu", "lat": 36.3938, "lon": 136.4075},
    "YGJ": {"name": "Yonago", "lat": 35.4963, "lon": 133.2635}
}

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
    except Exception:
        return []

def get_flight_data(airport_code, search_date, debug=False, use_current_time=False):
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
    except Exception:
        return []

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
    """
    [과거 양식 복구] WKT, Group, 주요_항공사 컬럼 추가 및 항공사별 요일 요약
    """
    if df.empty or 'Weekday' not in df.columns or 'Destination_Code' not in df.columns:
        return

    REGION_MAP = {
        "NRT": "간토", "HND": "간토", "KIX": "관서",
        "FUK": "규슈", "KMJ": "규슈", "KOJ": "규슈", "OITA": "규슈", "KKJ": "규슈",
        "CTS": "홋카이도", "NGO": "주부", "SHM": "주부", "FSZ": "주부", "KOM": "주부",
        "OKA": "오키나와", "HIJ": "주고쿠", "YGJ": "주고쿠",
        "MYJ": "시코쿠", "TAK": "시코쿠", "SDJ": "도호쿠", "FKS": "도호쿠"
    }
    
    KOR_NAME_MAP = {
        "NRT": "도쿄(나리타)", "HND": "도쿄(하네다)", "KIX": "오사카(간사이)", 
        "FUK": "후쿠오카", "CTS": "삿포로(신치토세)", "NGO": "나고야(주부)", 
        "OKA": "오키나와(나하)", "HIJ": "히로시마", "MYJ": "마쓰야마", 
        "TAK": "다카마쓰", "KMJ": "구마모토", "KOJ": "가고시마", 
        "FKS": "후쿠시마", "OITA": "오이타", "SHM": "시즈오카", 
        "KKJ": "기타큐슈", "FSZ": "시즈오카", "SDJ": "센다이", 
        "KOM": "고마쓰", "YGJ": "요나고"
    }

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
    date_range = [today - timedelta(days=i) for i in range(DAYS_BACK, 0, -1)] + [today + timedelta(days=i) for i in range(DAYS_AHEAD + 1)]
    
    existing_df = load_existing_data()
    existing_keys = set(existing_df.apply(create_unique_key, axis=1).values) if not existing_df.empty else set()
    
    all_data = []
    collection_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for search_date in date_range:
        date_str = search_date.strftime("%Y%m%d")
        for code, info in JAPAN_AIRPORTS.items():
            flights = get_flight_data_kac(code, date_str) if API_SOURCE == "KAC" else get_flight_data(code, date_str)
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
            df['Weekday'] = pd.to_datetime(df['Flight_Date'], format='%Y%m%d', errors='coerce').dt.weekday.apply(lambda x: ['월','화','수','목','금','토','일'][x] if 0 <= x <= 6 else '')
        if 'Destination_Name' not in df.columns:
            df['Destination_Name'] = df['Destination_Code'].map(lambda c: JAPAN_AIRPORTS.get(c, {}).get('name', c))
        if 'Flight_Date' in df.columns:
            df = df.sort_values(['Flight_Date', 'Flight_Time', 'Destination_Code'])
        
        df.to_csv(CSV_FILENAME, index=False, encoding='utf-8-sig')
        process_and_save_summary(df)

if __name__ == "__main__":
    main()
