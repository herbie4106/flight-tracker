import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import os
import xml.etree.ElementTree as ET

# ==========================================
# [사용자 입력] API 선택 및 키
# ==========================================
# 목적: 구글 내지도(My Maps)에 "인천→일본 공항별·요일별·항공사별 운항" 메모
# - ICN API: "오늘 비행기 뜨나?" 실시간 현황 → 당일만 제공, 요일 채우려면 7일 매일 실행
# - KAC API: "월/수/금 운항" 같은 고정 스케줄 → 스케줄 파악 목적이면 KAC 권장
API_SOURCE = "ICN"  # "ICN" = 인천공항(당일 운항현황), "KAC" = 한국공항공사(국제선 스케줄)

# 인천공항공사 API 키 (여객편 운항현황 다국어 - 15095093 활용신청 후 발급)
# [수정됨] GitHub Secrets에서 API 키를 가져옵니다.
# 만약 Secrets가 없으면(내 컴퓨터에서 돌릴 때), 뒤에 적힌 기본 키를 사용합니다.
API_KEY = os.environ.get("API_KEY_ICN", "9e77ad58a11ddf5ae8c4aaea81e4495ffe2db8da1ab6bacbbb4442f5f39a0e95")

# 한국공항공사 API 키 (항공기 운항정보 - 국제선 스케줄) ※ 별도 활용신청 후 발급
# 공공데이터포털 → 한국공항공사_항공기 운항정보 → 활용신청
API_KEY_KAC = ""  # 예: "your-kac-service-key"

CSV_FILENAME = "japan_flight_api_raw.csv"   # 원본 수집 데이터 (로그/병합용)
MAP_FILENAME = "japan_flight_for_map.csv"  # 구글 내지도 업로드용 (공항당 핀 1개 요약)
# ICN(실시간) API 사용 시: 당일만 의미 있음. 미래 날짜는 데이터 없음 → 0 권장.
# KAC(스케줄) API 사용 시: 미래 스케줄 조회 가능하면 7 등으로 늘려서 사용.
DAYS_AHEAD = 0  # 오늘부터 며칠 후까지 조회 (0=오늘만)
DAYS_BACK = 0   # 오늘부터 며칠 전까지 조회 (0=과거 미조회)
UPDATE_MODE = True  # True: 기존 파일과 병합, False: 새로 생성
DEBUG_MODE = True  # True: 첫 요청 시 API 응답 확인 (데이터 없을 때 원인 파악용)
TEST_REALTIME_MODE = False  # True: 현재 시간 기준으로도 테스트 (실시간 운항 상태 확인)

# ⚠️ ICN API는 당일 실시간 운항 현황만 제공합니다. 미래 날짜 조회는 의미 없음(데이터 없음).
# - 오늘만 조회(DAYS_AHEAD=0)하고, 요일별로 모으려면 일주일 동안 매일 실행 후 병합(UPDATE_MODE=True)하세요.

# 조회할 일본 주요 공항 목록 (정기편 위주)
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

# 한국공항공사 API: 국제선 운항 스케줄 (XML 반환)
# 활용가이드 문서에 기재된 정확한 서비스 URL·파라미터로 교체 필요
KAC_BASE_URL = "http://openapi.airport.co.kr/service/rest"
KAC_INTERNATIONAL_SCHEDULE_PATH = "FlightScheduleList/getInternationalFlightSchedule"  # 가이드 확인 후 수정

def get_flight_data_kac(airport_code, search_date, debug=False):
    """한국공항공사 API: 국제선 운항 스케줄 조회 (스케줄 데이터 = 요일별 누락 없음)"""
    if not API_KEY_KAC:
        if debug:
            print("  [KAC] API_KEY_KAC가 비어 있습니다. 공공데이터포털에서 활용신청 후 키를 넣으세요.")
        return []
    url = f"{KAC_BASE_URL}/{KAC_INTERNATIONAL_SCHEDULE_PATH}"
    params = {
        "ServiceKey": API_KEY_KAC,
        "depAirportId": "ICN",  # 인천
        "arrAirportId": airport_code,
        "depPlandTime": search_date,  # YYYYMMDD (가이드 확인)
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        # XML 구조는 활용가이드 참고. 예: body > items > item
        items = []
        for item in root.findall(".//item"):
            d = {c.tag: (c.text or "").strip() for c in item}
            items.append(d)
        if debug and items:
            print(f"  [KAC] 샘플 필드: {list(items[0].keys())}")
        return items
    except ET.ParseError as e:
        if debug:
            print(f"  [KAC] XML 파싱 오류: {e}")
        return []
    except requests.RequestException as e:
        if debug:
            print(f"  [KAC] 요청 오류: {e}")
        return []


def get_flight_data(airport_code, search_date, debug=False, use_current_time=False):
    """특정 날짜의 항공편 데이터 조회
    
    Args:
        airport_code: 도착 공항 코드
        search_date: 조회 날짜 (YYYYMMDD)
        debug: 디버그 모드
        use_current_time: True면 현재 시간 기준 ±2시간으로 조회 (실시간 운항 상태 확인용)
    """
    url = "http://apis.data.go.kr/B551177/StatusOfPassengerFlightsOdp/getPassengerDeparturesOdp"
    
    # 시간 범위 설정
    if use_current_time:
        # 현재 시간 기준 ±2시간 (실시간 운항 상태 확인용)
        now = datetime.now()
        from_time_obj = now - timedelta(hours=2)
        to_time_obj = now + timedelta(hours=2)
        from_time = from_time_obj.strftime("%H%M")
        to_time = to_time_obj.strftime("%H%M")
        search_date = now.strftime("%Y%m%d")
        if debug:
            print(f"  [시간 범위] 현재 시간 기준: {from_time} ~ {to_time}")
    else:
        from_time = "0000"
        to_time = "2359"  # 00:00~23:59 전체 (2400은 미지원일 수 있음)
    
    # 출발 API이므로 출발지는 인천(ICN) 고정. airport 파라미터는 '목적지(도착 공항)' 의미.
    params = {
        "serviceKey": API_KEY,
        "numOfRows": 1000,
        "pageNo": 1,
        "from_time": from_time,
        "to_time": to_time,
        "airport": airport_code,  # 목적지 공항 (예: NRT, KIX). arrived 파라미터 아님.
        "flight_date": search_date,
        "lang": "K",  # 다국어 API: 국문=K, 영문=E, 중문=C, 일문=J
        "type": "json"
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()  # HTTP 에러 체크
        
        # 응답 상태 확인
        if debug:
            print(f"  [HTTP 응답] 상태코드: {response.status_code}")
            print(f"  [요청 URL] {response.url}")
        
        data = response.json()
        
        if debug:
            print(f"  [JSON 응답] {data}")
        
        # 디버그 모드: API 응답 구조 확인
        if debug:
            print(f"\n  [디버그] API 응답 구조:")
            print(f"  - 응답 키: {list(data.keys())}")
            if 'response' in data:
                print(f"  - response 키: {list(data['response'].keys())}")
                if 'body' in data['response']:
                    print(f"  - body 키: {list(data['response']['body'].keys())}")
                    if 'items' in data['response']['body']:
                        items = data['response']['body']['items']
                        if items and len(items) > 0:
                            print(f"  - 첫 번째 항공편 필드: {list(items[0].keys())}")
                            print(f"  - 샘플 데이터: {items[0]}")
        
        if 'response' in data:
            # 헤더 정보 확인 (에러 코드 및 메시지)
            if 'header' in data['response']:
                result_code = data['response']['header'].get('resultCode', '')
                result_msg = data['response']['header'].get('resultMsg', '')
                total_count = data['response']['header'].get('totalCount', 0)
                
                # 항상 API 응답 정보 출력 (첫 번째 호출 시에만 상세히)
                if debug:
                    print(f"  [API 응답] 결과코드: {result_code}, 메시지: {result_msg}, 총건수: {total_count}")
                    print(f"  [전체 응답] {data}")
                
                # 에러 코드 체크 (03/총건수0은 믿지 않음 → 아래에서 body.items 기준으로 판단)
                if result_code not in ('00', '', '03'):
                    print(f"  [에러] API 결과 코드: {result_code}, 메시지: {result_msg}")
                    return []
                if result_code == '03' and debug:
                    print(f"  [정보] 헤더는 데이터 없음(03)이지만, body.items 기준으로 재확인합니다.")
                # totalCount는 사용하지 않음. 실제 데이터 유무는 body.items만으로 판단.
            
            # 본문 데이터 확인
            if 'body' in data['response']:
                body = data['response']['body']
                
                # body가 None이거나 비어있는 경우
                if body is None:
                    if debug:
                        print(f"  [정보] body가 None입니다.")
                    return []
                
                if 'items' in body:
                    items = body['items']
                    
                    # items가 None이거나 빈 리스트인 경우
                    if items is None:
                        if debug:
                            print(f"  [정보] items가 None입니다.")
                        return []
                    
                    # items가 리스트가 아닌 단일 딕셔너리인 경우 처리
                    if isinstance(items, dict):
                        items = [items]
                    
                    # 빈 리스트인 경우
                    if not items:
                        if debug:
                            print(f"  [정보] items가 비어있습니다.")
                        return []
                    
                    # 페이지네이션 처리: totalCount 확인하여 더 많은 데이터가 있으면 추가 조회
                    total_count = data['response']['header'].get('totalCount', len(items))
                    if total_count > len(items) and not debug:  # 디버그 모드가 아닐 때만
                        # 여러 페이지가 있는 경우 처리 (필요시)
                        pass
                    
                    return items
                else:
                    if debug:
                        print(f"  [정보] body에 'items' 키가 없습니다. body 키: {list(body.keys())}")
                    return []
            else:
                if debug:
                    print(f"  [정보] response에 'body' 키가 없습니다.")
                return []
    except requests.exceptions.RequestException as e:
        error_msg = f"API 호출 실패: {e}"
        if not debug:
            print(f"  [에러] {error_msg}")
        else:
            print(f"  [에러] {error_msg}")
            print(f"  [요청 URL] {url}")
            print(f"  [파라미터] {params}")
        return []
    except ValueError as e:
        error_msg = f"JSON 파싱 실패: {e}"
        if debug:
            print(f"  [에러] {error_msg}")
            print(f"  [응답 텍스트] {response.text[:500]}")
        else:
            print(f"  [에러] {error_msg}")
        return []
    except Exception as e:
        error_msg = f"예상치 못한 에러: {e}"
        if debug:
            print(f"  [에러] {error_msg}")
            import traceback
            traceback.print_exc()
        else:
            print(f"  [에러] {error_msg}")
        return []

def load_existing_data():
    """기존 CSV 파일이 있으면 로드"""
    if os.path.exists(CSV_FILENAME) and UPDATE_MODE:
        try:
            df = pd.read_csv(CSV_FILENAME, encoding='utf-8-sig')
            print(f"[기존 데이터] {len(df)}개 항공편 로드됨")
            return df
        except Exception as e:
            print(f"[경고] 기존 파일 로드 실패: {e}")
    return pd.DataFrame()

def create_unique_key(row):
    """항공편 고유 키 생성 (중복 체크용)"""
    return f"{row.get('Flight_ID', '')}_{row.get('Flight_Date', '')}_{row.get('Destination_Code', '')}"


def process_and_save_summary(df):
    """
    [지도 가독성 핵심] 수집된 원본을 공항별로 요약하여,
    구글 내지도에 올릴 때 공항당 핀 1개만 찍히도록 CSV 생성.
    - 변경 전: 나리타에 KE703 월/화/수/… 7개 핀 겹침
    - 변경 후: 나리타 1개 핀, Description에 "[대한항공] KE703(Daily), [아시아나] OZ101(월,수,금)"
    """
    if df.empty:
        print("데이터가 없어 지도용 요약 파일을 생성하지 못했습니다.")
        return
    if 'Weekday' not in df.columns or 'Destination_Code' not in df.columns:
        print("Weekday 또는 Destination_Code 컬럼이 없어 요약을 건너뜁니다.")
        return

    summary_list = []
    weekday_order = ['월', '화', '수', '목', '금', '토', '일']

    for dest_code, group in df.groupby("Destination_Code"):
        airport_info = JAPAN_AIRPORTS.get(dest_code, {})
        dest_name = airport_info.get("name", dest_code)
        lat = airport_info.get("lat", 0)
        lon = airport_info.get("lon", 0)

        # 항공사 → 편명 → 요일 집합
        flight_summary = {}
        for _, row in group.iterrows():
            airline = row.get('Airline', 'N/A')
            flight_id = row.get('Flight_ID', '')
            weekday = row.get('Weekday', '')
            if not airline or not flight_id:
                continue
            if airline not in flight_summary:
                flight_summary[airline] = {}
            if flight_id not in flight_summary[airline]:
                flight_summary[airline][flight_id] = set()
            flight_summary[airline][flight_id].add(weekday)

        desc_lines = []
        for airline, flights in sorted(flight_summary.items()):
            line_parts = []
            for fid, days_set in sorted(flights.items()):
                sorted_days = sorted(
                    [d for d in days_set if d in weekday_order],
                    key=lambda x: weekday_order.index(x)
                )
                if len(sorted_days) == 7:
                    day_str = "매일"
                else:
                    day_str = ",".join(sorted_days)
                line_parts.append(f"{fid}({day_str})")
            desc_lines.append(f"[{airline}] {', '.join(line_parts)}")

        summary_list.append({
            "Name": f"{dest_name} ({dest_code})",
            "Description": "\n".join(desc_lines) if desc_lines else "(운항 정보 없음)",
            "Latitude": lat,
            "Longitude": lon,
            "Total_Flights_Weekly": len(group),
        })

    summary_df = pd.DataFrame(summary_list)
    summary_df.to_csv(MAP_FILENAME, index=False, encoding='utf-8-sig')
    print(f"\n✅ [지도용 파일 생성] '{MAP_FILENAME}' (공항당 핀 1개)")
    print("   → 구글 내지도(My Maps)에서 이 CSV를 가져오기 하면, 핀을 눌렀을 때 해당 공항의 항공사·요일 요약이 표시됩니다.")


def main():
    # 날짜 범위 생성
    today = datetime.now()
    date_range = []
    
    # 과거 날짜 추가 (DAYS_BACK > 0인 경우)
    if DAYS_BACK > 0:
        for i in range(DAYS_BACK, 0, -1):
            date_range.append(today - timedelta(days=i))
    
    # 오늘부터 미래 날짜 추가
    for i in range(DAYS_AHEAD + 1):
        date_range.append(today + timedelta(days=i))
    
    print(f"[{today.strftime('%Y-%m-%d')}] API 데이터 수집 시작...")
    print(f"API 소스: {API_SOURCE} ({'한국공항공사(국제선 스케줄)' if API_SOURCE == 'KAC' else '인천공항공사(실시간 운항상태)'})")
    if API_SOURCE == "KAC" and not API_KEY_KAC:
        print("⚠️ API_KEY_KAC가 비어 있습니다. 공공데이터포털 → 한국공항공사_항공기 운항정보 → 활용신청 후 키를 입력하세요.")
    if DAYS_BACK > 0:
        print(f"조회 기간: {date_range[0].strftime('%Y-%m-%d')} ~ {date_range[-1].strftime('%Y-%m-%d')} (과거 {DAYS_BACK}일 + 오늘 + 미래 {DAYS_AHEAD}일 = 총 {len(date_range)}일)")
    else:
        print(f"조회 기간: {date_range[0].strftime('%Y-%m-%d')} ~ {date_range[-1].strftime('%Y-%m-%d')} (오늘 + 미래 {DAYS_AHEAD}일 = 총 {len(date_range)}일)")
    print(f"업데이트 모드: {'병합' if UPDATE_MODE else '새로 생성'}")
    print(f"디버그 모드: {'ON' if DEBUG_MODE else 'OFF'}")
    
    # 실시간 모드 테스트 (현재 시간 기준 ±2시간)
    if TEST_REALTIME_MODE:
        print(f"\n🔍 [실시간 운항 상태 테스트] 현재 시간 기준 ±2시간 조회 테스트...")
        test_airport = list(JAPAN_AIRPORTS.keys())[0]  # 첫 번째 공항으로 테스트
        test_flights = get_flight_data(test_airport, today.strftime("%Y%m%d"), debug=True, use_current_time=True)
        if test_flights:
            print(f"  ✅ 실시간 모드에서 {len(test_flights)}개 항공편 발견!")
            print(f"  → 이 API는 실시간 운항 상태만 제공하는 것으로 보입니다.")
        else:
            print(f"  ⚠️ 실시간 모드에서도 데이터 없음")
            print(f"  → 이 API는 현재 시간에 운항 중인 항공편이 없거나,")
            print(f"    API가 다른 방식으로 작동할 수 있습니다.\n")
    print()
    
    # 기존 데이터 로드
    existing_df = load_existing_data()
    existing_keys = set()
    if not existing_df.empty:
        existing_df['_unique_key'] = existing_df.apply(create_unique_key, axis=1)
        existing_keys = set(existing_df['_unique_key'].values)
    
    all_data = []
    collection_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_flights = 0
    new_flights = 0
    
    # 각 날짜별로 조회
    date_stats = {}  # 날짜별 통계 저장
    
    for search_date in date_range:
        date_str = search_date.strftime("%Y%m%d")
        date_display = search_date.strftime('%Y-%m-%d (%a)')
        is_past = search_date < today
        is_future = search_date > today
        date_type = "과거" if is_past else ("미래" if is_future else "오늘")
        
        print(f"\n📅 날짜: {date_display} [{date_type}]")
        date_stats[date_str] = {"total": 0, "airports": {}}
        
        for code, info in JAPAN_AIRPORTS.items():
            print(f"  Scanning {code} ({info['name']})...", end=" ")
            is_first = code == list(JAPAN_AIRPORTS.keys())[0] and search_date == date_range[0]
            debug_this = DEBUG_MODE and is_first

            if API_SOURCE == "KAC":
                flights = get_flight_data_kac(code, date_str, debug=debug_this)
            else:
                flights = get_flight_data(code, date_str, debug=debug_this, use_current_time=False)
            
            if flights:
                print(f"✓ Found {len(flights)}")
                total_flights += len(flights)
                date_stats[date_str]["total"] += len(flights)
                date_stats[date_str]["airports"][code] = len(flights)
                
                for f in flights:
                    if API_SOURCE == "KAC":
                        flight_id = f.get("flightId") or f.get("flightNo") or f.get("varmodel") or ""
                        sch = f.get("scheduleDateTime") or f.get("depPlandTime") or f.get("scheduleTime") or "0000"
                        sch = str(sch)[-4:] if len(str(sch)) >= 4 else "0000"
                        time_str = sch[:2] + ":" + sch[2:] if len(sch) == 4 else "00:00"
                        airline = f.get("airline") or f.get("airlineNm") or "N/A"
                    else:
                        flight_id = f.get('flightId', '')
                        sch_time = f.get('scheduleDateTime', '0000')
                        time_str = sch_time[-4:-2] + ":" + sch_time[-2:] if len(sch_time) >= 4 else "00:00"
                        airline = f.get('airline', 'N/A')
                    
                    unique_key = f"{flight_id}_{date_str}_{code}"
                    if UPDATE_MODE and unique_key in existing_keys:
                        continue
                    new_flights += 1
                    # 요일: 지도에서 "이 공항은 월/수/금 운항" 등 메모용
                    weekday_kr = ['월','화','수','목','금','토','일'][search_date.weekday()]
                    all_data.append({
                        "Name": f"{flight_id} ({airline})",
                        "Description": f"인천→{info['name']}\n항공사: {airline}\n요일: {weekday_kr}\n출발: {time_str}\n날짜: {search_date.strftime('%Y-%m-%d')}",
                        "Latitude": info['lat'],
                        "Longitude": info['lon'],
                        "Destination_Code": code,
                        "Destination_Name": info['name'],
                        "Flight_ID": flight_id,
                        "Flight_Date": date_str,
                        "Flight_Time": time_str,
                        "Weekday": weekday_kr,
                        "Airline": airline,
                        "Collected_At": collection_timestamp
                    })
            else:
                print("No data")
            
            time.sleep(0.1)  # 서버 부하 방지
    
    # 새 데이터가 있으면 기존 데이터와 병합
    if all_data:
        new_df = pd.DataFrame(all_data)
        
        if UPDATE_MODE and not existing_df.empty:
            # 기존 데이터에서 _unique_key 컬럼 제거 후 병합
            if '_unique_key' in existing_df.columns:
                existing_df = existing_df.drop(columns=['_unique_key'])
            df = pd.concat([existing_df, new_df], ignore_index=True)
            print(f"\n[병합 완료] 기존 {len(existing_df)}개 + 신규 {len(new_df)}개 = 총 {len(df)}개")
        else:
            df = new_df
            print(f"\n[신규 생성] {len(df)}개 항공편")
        
        # 중복 제거 (혹시 모를 중복 방지)
        df = df.drop_duplicates(subset=['Flight_ID', 'Flight_Date', 'Destination_Code'], keep='last')
        
        # 기존 데이터에 요일/도착지명이 없으면 채우기 (이전 버전 CSV 호환)
        if 'Weekday' not in df.columns:
            df['Weekday'] = pd.to_datetime(df['Flight_Date'], format='%Y%m%d', errors='coerce').dt.weekday.apply(lambda x: ['월','화','수','목','금','토','일'][x] if 0 <= x <= 6 else '')
        if 'Destination_Name' not in df.columns:
            df['Destination_Name'] = df['Destination_Code'].map(lambda c: JAPAN_AIRPORTS.get(c, {}).get('name', c))
        
        # 날짜순으로 정렬
        if 'Flight_Date' in df.columns:
            df = df.sort_values(['Flight_Date', 'Flight_Time', 'Destination_Code'])
        
        df.to_csv(CSV_FILENAME, index=False, encoding='utf-8-sig')
        print(f"\n✅ [성공] '{CSV_FILENAME}' (원본) 업데이트 완료.")
        print(f"   - 총 항공편: {len(df)}개 / 이번 수집: {total_flights}건 조회, {new_flights}건 추가")
        print(f"   - 수집 시각: {collection_timestamp}")

        # 지도 업로드용: 공항당 핀 1개 요약 CSV 생성 (핀 겹침 방지)
        process_and_save_summary(df)

        # 지도 메모용: 공항별·항공사별 운항 요일 요약 (인천→일본, 어느 요일에 누가 뜨는지)
        if 'Weekday' in df.columns and 'Destination_Name' in df.columns:
            print(f"\n📌 [지도 메모용] 공항별 · 항공사별 운항 요일:")
            for (code, name), grp in df.groupby(['Destination_Code', 'Destination_Name']):
                by_airline = grp.groupby('Airline')['Weekday'].apply(lambda s: ','.join(sorted(s.unique(), key=lambda w: '월화수목금토일'.index(w)))).to_dict()
                summary = " / ".join(f"{al}({days})" for al, days in sorted(by_airline.items()))
                print(f"   {code} {name}: {summary or '-'}")
        
        # 날짜별 통계 출력
        print(f"\n📊 날짜별 데이터 수집 현황:")
        weekday_count = {}  # 요일별 통계
        for date_str, stats in date_stats.items():
            date_obj = datetime.strptime(date_str, "%Y%m%d")
            weekday_name = date_obj.strftime('%A')  # 요일 이름
            weekday_kr = {'Monday': '월', 'Tuesday': '화', 'Wednesday': '수', 'Thursday': '목', 
                          'Friday': '금', 'Saturday': '토', 'Sunday': '일'}.get(weekday_name, weekday_name)
            
            date_label = date_obj.strftime('%Y-%m-%d')
            if date_obj < today:
                date_label += " (과거)"
            elif date_obj > today:
                date_label += " (미래)"
            else:
                date_label += " (오늘)"
            
            if stats["total"] > 0:
                print(f"   ✓ {date_label} ({weekday_kr}): {stats['total']}개 항공편")
                weekday_count[weekday_kr] = weekday_count.get(weekday_kr, 0) + stats["total"]
            else:
                print(f"   ✗ {date_label} ({weekday_kr}): 데이터 없음")
        
        # 요일별 통계 요약
        if weekday_count:
            print(f"\n📅 요일별 수집된 항공편 수:")
            for weekday in ['월', '화', '수', '목', '금', '토', '일']:
                count = weekday_count.get(weekday, 0)
                if count > 0:
                    print(f"   {weekday}요일: {count}개")
                else:
                    print(f"   {weekday}요일: 없음 ⚠️")
        
        # 중요 안내 메시지
        if API_SOURCE == "ICN":
            print(f"\n⚠️ [중요 안내]")
            print(f"이 API가 실시간 운항 상태만 제공한다면,")
            print(f"모든 요일의 정기편을 수집하려면 일주일 동안 매일 실행해야 합니다!")
            print(f"한국공항공사 API(국제선 스케줄) 사용 시: API_SOURCE = 'KAC', API_KEY_KAC 설정 후 활용.")
            print(f"\n현재 수집된 요일: {', '.join(weekday_count.keys()) if weekday_count else '없음'}")
            print(f"누락된 요일: {', '.join([w for w in ['월', '화', '수', '목', '금', '토', '일'] if w not in weekday_count])}")
        else:
            print(f"\n✅ 한국공항공사 API(국제선 스케줄) 사용 중 — 요일별 누락 없이 스케줄 반영됩니다.")
        
        print("\n📌 구글 내지도 업로드: '가져오기' → 위에서 생성된 '" + MAP_FILENAME + "' 선택")
        print("   장소 열: Latitude, Longitude / 제목 열: Name")
    else:
        if UPDATE_MODE and not existing_df.empty:
            print(f"\n[정보] 새로운 항공편이 없습니다. 기존 데이터 유지: {len(existing_df)}개")
        else:
            print("\n❌ [실패] 데이터가 수집되지 않았습니다.")
            print("   가능한 원인:")
            print("   1) API가 당일 운항만 제공 → 오늘 실제 운항 시간대(예: 오전 8시~저녁 8시)에 실행해 보세요.")
            print("   2) 일반인증키(서비스키)가 맞는지, 해당 API(15095093) 활용신청이 승인되었는지 확인하세요.")
            print("   3) 디버그 모드(DEBUG_MODE=True)로 다시 실행해 첫 번째 API 응답 내용을 확인해 보세요.")

if __name__ == "__main__":
    main()
