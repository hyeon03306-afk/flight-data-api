import requests
import json
import math
import os
from datetime import datetime, timedelta

# 1. 환경 설정 (API 키와 엔드포인트)
API_KEY = os.environ.get("OPENAPI_KEY")
ICN_URL = "http://apis.data.go.kr/B551177/StatusOfPassengerFlightsOdp/getPassengerDeparturesOdp" # 기존 인천공항
KAC_URL = "http://apis.data.go.kr/1610000/IflightInfoService/getFlightInfo" # 추가된 전국 14개 공항

# 2. 기종별 최대 좌석수 사전 (API에서 기종이 안 오면 DEFAULT 180석 적용)
AIRCRAFT_CAPACITY = {
    "B738": 189, "B737": 189, "B38M": 189,
    "A320": 180, "A321": 230, "A21N": 240,
    "A333": 300, "A330": 300,
    "B77W": 350, "B772": 300,
    "B789": 290, "B788": 250,
    "DEFAULT": 180
}

# 목적지 공항 코드 맵핑 (이 필터 덕분에 전 세계 비행기 중 일본만 딱 걸러집니다!)
TARGET_AIRPORTS = {
    "NRT": "도쿄", "HND": "도쿄", 
    "KIX": "오사카", 
    "FUK": "후쿠오카"
}

def get_estimated_pax(aircraft_code):
    max_seats = AIRCRAFT_CAPACITY.get(aircraft_code, AIRCRAFT_CAPACITY["DEFAULT"])
    return math.floor(max_seats * 0.9) # 90% 탑승률 적용

def fetch_and_process_flights():
    # 현재 시간 계산
    now = datetime.now()
    from_time_str = now.strftime("%H%M")
    to_time_str = (now + timedelta(hours=3)).strftime("%H%M")
    
    # 3. 결과 데이터를 담을 그릇 (여기에 인천공항 + 전국공항 데이터가 누적 합산됩니다)
    result_data = {
        "도쿄": {"1h": {"flights": 0, "pax": 0}, "2h": {"flights": 0, "pax": 0}, "3h": {"flights": 0, "pax": 0}},
        "오사카": {"1h": {"flights": 0, "pax": 0}, "2h": {"flights": 0, "pax": 0}, "3h": {"flights": 0, "pax": 0}},
        "후쿠오카": {"1h": {"flights": 0, "pax": 0}, "2h": {"flights": 0, "pax": 0}, "3h": {"flights": 0, "pax": 0}}
    }

    # =========================================================================
    # [엔진 1] 사장님이 만드신 기존 로직 (인천공항) - 원본 100% 유지
    # =========================================================================
    try:
        icn_request_url = f"{ICN_URL}?serviceKey={API_KEY}&from_time={from_time_str}&to_time={to_time_str}&type=json"
        icn_response = requests.get(icn_request_url, timeout=10)
        icn_data = icn_response.json()
        
        icn_items = icn_data.get("response", {}).get("body", {}).get("items", [])
        
        if not icn_items:
            print("인천공항: 조회된 데이터가 없습니다.")
        else:
            if isinstance(icn_items, dict): 
                icn_items = [icn_items]

            for item in icn_items:
                dest_code = item.get("airportCode") 
                
                if dest_code in TARGET_AIRPORTS:
                    city = TARGET_AIRPORTS[dest_code]
                    aircraft_type = item.get("typeOfFlight", "DEFAULT") 
                    pax = get_estimated_pax(aircraft_type)
                    
                    flight_time_str = str(item.get("scheduleDateTime", "")).zfill(4)
                    if not flight_time_str or flight_time_str == "0000":
                        continue
                        
                    flight_hour = int(flight_time_str[:2])
                    flight_minute = int(flight_time_str[2:])
                    flight_dt = now.replace(hour=flight_hour, minute=flight_minute, second=0, microsecond=0)
                    
                    time_diff_minutes = (flight_dt - now).total_seconds() / 60
                    
                    if 0 <= time_diff_minutes <= 60:
                        result_data[city]["1h"]["flights"] += 1
                        result_data[city]["1h"]["pax"] += pax
                    elif 60 < time_diff_minutes <= 120:
                        result_data[city]["2h"]["flights"] += 1
                        result_data[city]["2h"]["pax"] += pax
                    elif 120 < time_diff_minutes <= 180:
                        result_data[city]["3h"]["flights"] += 1
                        result_data[city]["3h"]["pax"] += pax
    except Exception as e:
        print(f"❌ 인천공항 데이터 수집 에러: {e}")


    # =========================================================================
    # [엔진 2] 새롭게 추가된 로직 (한국공항공사 - 전국 14개 공항)
    # =========================================================================
    try:
        kac_request_url = f"{KAC_URL}?serviceKey={API_KEY}&_type=json"
        kac_response = requests.get(kac_request_url, timeout=10)
        
        if kac_response.status_code == 200:
            kac_data = kac_response.json()
            kac_body = kac_data.get("response", {}).get("body", {})
            kac_items = kac_body.get("items", [])
            
            # 전국 공항 API는 JSON 구조가 살짝 달라서 item 리스트를 한 번 더 벗겨냅니다
            if isinstance(kac_items, dict) and "item" in kac_items:
                kac_items = kac_items["item"]
            if isinstance(kac_items, dict):
                kac_items = [kac_items]

            for item in kac_items:
                # 전국 공항은 목적지 코드를 'arrivedEng'나 'airportCode'로 줍니다
                dest_code = item.get("arrivedEng") or item.get("airportCode")
                
                if dest_code in TARGET_AIRPORTS:
                    city = TARGET_AIRPORTS[dest_code]
                    pax = 162 # 전국 공항은 기종 정보를 잘 안 주므로 기본 162명 적용
                    
                    # 시간 필드명도 std 또는 scheduledDateTime으로 다를 수 있습니다
                    flight_time_str = str(item.get("std", item.get("scheduledDateTime", ""))).zfill(4)
                    if not flight_time_str or flight_time_str == "0000":
                        continue
                        
                    flight_hour = int(flight_time_str[:2])
                    flight_minute = int(flight_time_str[2:])
                    flight_dt = now.replace(hour=flight_hour, minute=flight_minute, second=0, microsecond=0)
                    
                    time_diff_minutes = (flight_dt - now).total_seconds() / 60
                    
                    if 0 <= time_diff_minutes <= 60:
                        result_data[city]["1h"]["flights"] += 1
                        result_data[city]["1h"]["pax"] += pax
                    elif 60 < time_diff_minutes <= 120:
                        result_data[city]["2h"]["flights"] += 1
                        result_data[city]["2h"]["pax"] += pax
                    elif 120 < time_diff_minutes <= 180:
                        result_data[city]["3h"]["flights"] += 1
                        result_data[city]["3h"]["pax"] += pax
    except Exception as e:
        print(f"❌ 전국 공항 데이터 수집 에러: {e}")


    # =========================================================================
    # 4. 합쳐진 데이터를 최종 JSON 파일로 저장
    # =========================================================================
    try:
        with open("flight_data.json", "w", encoding="utf-8") as f:
            json.dump(result_data, f, ensure_ascii=False, indent=4)
            
        print("✅ flight_data.json 파일 생성 완료! (인천 + 전국 공항 융합 성공)")
        print(json.dumps(result_data, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"❌ JSON 파일 저장 에러: {e}")

if __name__ == "__main__":
    fetch_and_process_flights()
