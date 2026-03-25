import os
import requests
import datetime

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
APP_KEY = os.environ.get('HANWHA_APP_KEY')
APP_SECRET = os.environ.get('HANWHA_APP_SECRET')
API_BASE_URL = "https://openapi.koreainvestment.com:9443"

def run_api_scanner():
    msg = "🕵️‍♂️ **한국투자증권 API 정밀 스캐너 가동**\n\n```text\n"
    
    # 1. 토큰 발급 (성공 확인용)
    res = requests.post(
        f"{API_BASE_URL}/oauth2/tokenP", 
        json={"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET}
    )
    token = res.json().get('access_token')
    if not token:
        msg += f"❌ 토큰 발급 실패\n{res.text[:100]}\n```"
        return msg
    msg += "✅ 1단계: API 접근 토큰 획득 성공!\n"

    # API 공통 헤더
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "custtype": "P"
    }
    url = f"{API_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-investor"

    # 오늘 날짜와 현재 시간 세팅 (KST)
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    today_str = now.strftime("%Y%m%d")
    
    # 💡 찔러볼 4가지 경우의 수 (한 번에 검거하기 위한 덫)
    test_cases = [
        {"name": "테스트1 (날짜만 추가)", 
         "tr_id": "FHPUP02120000", 
         "params": {"FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": "0001", "FID_INPUT_DATE_1": today_str}},
         
        {"name": "테스트2 (날짜+시간 추가)", 
         "tr_id": "FHPUP02120000", 
         "params": {"FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": "0001", "FID_INPUT_DATE_1": today_str, "FID_INPUT_HOUR_1": "153000"}},
         
        {"name": "테스트3 (시작일+종료일 추가)", 
         "tr_id": "FHPUP02120000", 
         "params": {"FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": "0001", "FID_INPUT_DATE_1": today_str, "FID_INPUT_DATE_2": today_str}},
         
        {"name": "테스트4 (일별수급 TR코드로 우회)", 
         "tr_id": "FHPUP02110000", 
         "params": {"FID_COND_MRKT_DIV_CODE": "U", "FID_INPUT_ISCD": "0001", "FID_INPUT_DATE_1": today_str}}
    ]
    
    # 순서대로 한국투자증권 서버 폭격
    for case in test_cases:
        msg += f"\n▶ {case['name']} 시도 중...\n"
        headers['tr_id'] = case['tr_id']
            
        r = requests.get(url, headers=headers, params=case['params'])
        data = r.json()
        rt_cd = data.get('rt_cd')
        msg1 = data.get('msg1')
        
        msg += f"└ 응답: [{rt_cd}] {msg1}\n"
        
        # 정답을 찾았을 경우
        if rt_cd == '0':
            records = data.get('output2') or data.get('output')
            if records:
                msg += f"🎉 빙고! 데이터를 찾았습니다.\n"
                msg += f"└ 데이터 키값 목록:\n{list(records[0].keys())}\n"
                msg += f"└ 첫 번째 줄 데이터:\n{str(records[0])[:150]}\n"
            else:
                msg += f"└ 데이터 배열이 비어있습니다 (장 시작 전이거나 휴장일 가능성)\n"
                
    msg += "```\n\n위 결과를 그대로 복사해서 저에게 던져주시면, 10초 만에 완벽한 코드로 조립해 드리겠습니다!"
    return msg

def send_telegram(message):
    requests.post(
        f"[https://api.telegram.org/bot](https://api.telegram.org/bot){TELEGRAM_TOKEN}/sendMessage",
        data={'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
    )

if __name__ == "__main__":
    send_telegram(run_api_scanner())