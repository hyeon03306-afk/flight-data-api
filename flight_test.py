import requests
import json
import math
import os
from datetime import datetime, timedelta

# 1. 환경 설정 (API 키와 엔드포인트)
API_KEY = os.environ.get("OPENAPI_KEY") 
URL = "http://apis.data.go.kr/B551177/StatusOfPassengerFlightsOdp/getPassengerDeparturesOdp"

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
    
    # 파이썬 인코딩 에러 방지용 수동 URL 조립
    request_url = f"{URL}?serviceKey={API_KEY}&from_time={from_time_str}&to_time={to_time_str}&type=json"

    try:
        response = requests.get(request_url)
        
        # 터미널이 지저분해지지 않게 원본 텍스트 출력 부분은 가려두었습니다 (주석 처리)
        # print("=== 정부 서버 응답 원본 ===")
        # print(response.text)
        # print("===========================\n")
        
        data = response.json()
        
        # 3. 결과 데이터를 담을 그릇 (JSON 구조)
        result_data = {
            "도쿄": {"1h": {"flights": 0, "pax": 0}, "2h": {"flights": 0, "pax": 0}, "3h": {"flights": 0, "pax": 0}},
            "오사카": {"1h": {"flights": 0, "pax": 0}, "2h": {"flights": 0, "pax": 0}, "3h": {"flights": 0, "pax": 0}},
            "후쿠오카": {"1h": {"flights": 0, "pax": 0}, "2h": {"flights": 0, "pax": 0}, "3h": {"flights": 0, "pax": 0}}
        }

        items = data.get("response", {}).get("body", {}).get("items", [])
        
        # 데이터가 아예 없을 경우 방어
        if not items:
            print("조회된 데이터가 없습니다. (API 승인 대기 중이거나 비행기가 없음)")
            return

        if isinstance(items, dict): 
            items = [items]

        for item in items:
            dest_code = item.get("airportCode") # 목적지 공항 코드
            
            # 여기서 도쿄, 오사카, 후쿠오카 노선만 통과시킵니다. 나머지는 버려집니다.
            if dest_code in TARGET_AIRPORTS:
                city = TARGET_AIRPORTS[dest_code]
                
                # 탑승객 계산 (공공데이터에 기종 정보가 없으면 DEFAULT 값인 162명으로 자동 계산됨)
                aircraft_type = item.get("typeOfFlight", "DEFAULT") 
                pax = get_estimated_pax(aircraft_type)
                
                # ---------------- [핵심: 시간 분류 로직 수정 완료 (scheduleDateTime으로 매칭)] ----------------
                flight_time_str = str(item.get("scheduleDateTime", "")).zfill(4)
                if not flight_time_str or flight_time_str == "0000":
                    continue
                    
                # 비행 시간을 datetime 객체로 변환
                flight_hour = int(flight_time_str[:2])
                flight_minute = int(flight_time_str[2:])
                flight_dt = now.replace(hour=flight_hour, minute=flight_minute, second=0, microsecond=0)
                
                # 현재 시간과 비행 시간의 차이를 '분(Minute)'으로 계산
                time_diff_minutes = (flight_dt - now).total_seconds() / 60
                
                # 조건에 맞춰 1시간, 2시간, 3시간 슬롯에 데이터 분배
                if 0 <= time_diff_minutes <= 60:
                    time_key = "1h"
                elif 60 < time_diff_minutes <= 120:
                    time_key = "2h"
                elif 120 < time_diff_minutes <= 180:
                    time_key = "3h"
                else:
                    continue # 3시간 밖이거나 이미 지나간 비행기는 패스
                
                # 분배된 슬롯에 비행기 대수와 인원 누적
                result_data[city][time_key]["flights"] += 1
                result_data[city][time_key]["pax"] += pax

        # 4. 최종 JSON 파일로 저장
        with open("flight_data.json", "w", encoding="utf-8") as f:
            json.dump(result_data, f, ensure_ascii=False, indent=4)
            
        print("✅ flight_data.json 파일 생성 완료!")
        print(json.dumps(result_data, ensure_ascii=False, indent=2))

    except Exception as e:
        print(f"❌ 에러 발생: {e}")

if __name__ == "__main__":
    fetch_and_process_flights()
