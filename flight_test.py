import requests
import json
import math
import os
from datetime import datetime, timedelta, timezone

API_KEY = os.environ.get("OPENAPI_KEY")
ICN_URL = "http://apis.data.go.kr/B551177/StatusOfPassengerFlightsOdp/getPassengerDeparturesOdp" 
KAC_URL = "http://apis.data.go.kr/1610000/IflightInfoService/getFlightInfo" 

AIRCRAFT_CAPACITY = {
    "B738": 189, "B737": 189, "B38M": 189,
    "A320": 180, "A321": 230, "A21N": 240,
    "A333": 300, "A330": 300,
    "B77W": 350, "B772": 300,
    "B789": 290, "B788": 250,
    "DEFAULT": 180
}

# ✈️ 일본 전역 20개 공항으로 타겟 대폭 확장!
TARGET_AIRPORTS = {
    "NRT": "도쿄", "HND": "도쿄", "KIX": "오사카", "FUK": "후쿠오카",
    "CTS": "삿포로", "OKA": "오키나와", "NGO": "나고야",
    "KMJ": "구마모토", "KOJ": "가고시마", "OIT": "오이타",
    "NGS": "나가사키", "HSG": "사가", "KKJ": "기타큐슈",
    "MYJ": "마쓰야마", "TAK": "다카마쓰", "HIJ": "히로시마",
    "OKJ": "오카야마", "FSZ": "시즈오카", "KIJ": "니이가타",
    "SDJ": "센다이", "AOJ": "아오모리"
}

def get_estimated_pax(aircraft_code):
    max_seats = AIRCRAFT_CAPACITY.get(aircraft_code, AIRCRAFT_CAPACITY["DEFAULT"])
    return math.floor(max_seats * 0.9) 

def fetch_and_process_flights():
    KST = timezone(timedelta(hours=9))
    now = datetime.now(KST)
    
    from_time_str = now.strftime("%H%M")
    to_time_str = (now + timedelta(hours=3)).strftime("%H%M")
    
    # 20개 도시를 기본값(0대)으로 자동 세팅
    result_data = {}
    for city in set(TARGET_AIRPORTS.values()):
        result_data[city] = {"1h": {"flights": 0, "pax": 0}, "2h": {"flights": 0, "pax": 0}, "3h": {"flights": 0, "pax": 0}}

    # 1. 인천공항
    try:
        icn_request_url = f"{ICN_URL}?serviceKey={API_KEY}&from_time={from_time_str}&to_time={to_time_str}&type=json"
        icn_response = requests.get(icn_request_url, timeout=10)
        icn_data = icn_response.json()
        icn_items = icn_data.get("response", {}).get("body", {}).get("items", [])
        
        if icn_items:
            if isinstance(icn_items, dict): icn_items = [icn_items]
            for item in icn_items:
                dest_code = item.get("airportCode") 
                if dest_code in TARGET_AIRPORTS:
                    city = TARGET_AIRPORTS[dest_code]
                    pax = get_estimated_pax(item.get("typeOfFlight", "DEFAULT"))
                    
                    flight_time_str = str(item.get("scheduleDateTime", "")).zfill(4)
                    if not flight_time_str or flight_time_str == "0000": continue
                        
                    flight_hour = int(flight_time_str[:2])
                    flight_minute = int(flight_time_str[2:])
                    flight_dt = now.replace(hour=flight_hour, minute=flight_minute, second=0, microsecond=0)
                    time_diff_minutes = (flight_dt - now).total_seconds() / 60
                    
                    if 0 <= time_diff_minutes <= 60:
                        result_data[city]["1h"]["flights"] += 1; result_data[city]["1h"]["pax"] += pax
                    elif 60 < time_diff_minutes <= 120:
                        result_data[city]["2h"]["flights"] += 1; result_data[city]["2h"]["pax"] += pax
                    elif 120 < time_diff_minutes <= 180:
                        result_data[city]["3h"]["flights"] += 1; result_data[city]["3h"]["pax"] += pax
    except Exception as e:
        print(f"❌ 인천공항 에러: {e}")

    # 2. 전국 14개 공항
    try:
        kac_request_url = f"{KAC_URL}?serviceKey={API_KEY}&_type=json"
        kac_response = requests.get(kac_request_url, timeout=10)
        if kac_response.status_code == 200:
            kac_data = kac_response.json()
            kac_items = kac_data.get("response", {}).get("body", {}).get("items", [])
            
            if isinstance(kac_items, dict) and "item" in kac_items: kac_items = kac_items["item"]
            if isinstance(kac_items, dict): kac_items = [kac_items]

            for item in kac_items:
                dest_code = item.get("arrivedEng") or item.get("airportCode")
                if dest_code in TARGET_AIRPORTS:
                    city = TARGET_AIRPORTS[dest_code]
                    pax = 162 
                    
                    flight_time_str = str(item.get("std", item.get("scheduledDateTime", ""))).zfill(4)
                    if not flight_time_str or flight_time_str == "0000": continue
                        
                    flight_hour = int(flight_time_str[:2])
                    flight_minute = int(flight_time_str[2:])
                    flight_dt = now.replace(hour=flight_hour, minute=flight_minute, second=0, microsecond=0)
                    time_diff_minutes = (flight_dt - now).total_seconds() / 60
                    
                    if 0 <= time_diff_minutes <= 60:
                        result_data[city]["1h"]["flights"] += 1; result_data[city]["1h"]["pax"] += pax
                    elif 60 < time_diff_minutes <= 120:
                        result_data[city]["2h"]["flights"] += 1; result_data[city]["2h"]["pax"] += pax
                    elif 120 < time_diff_minutes <= 180:
                        result_data[city]["3h"]["flights"] += 1; result_data[city]["3h"]["pax"] += pax
    except Exception as e:
        print(f"❌ 전국공항 에러: {e}")

    # 3. 저장
    try:
        with open("flight_data.json", "w", encoding="utf-8") as f:
            json.dump(result_data, f, ensure_ascii=False, indent=4)
        print("✅ 성공적으로 20개 공항 데이터 업데이트 완료!")
    except Exception as e:
        print(f"❌ 저장 에러: {e}")

if __name__ == "__main__":
    fetch_and_process_flights()
