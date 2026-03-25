import os
import requests
import datetime

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
APP_KEY = os.environ.get('HANWHA_APP_KEY')
APP_SECRET = os.environ.get('HANWHA_APP_SECRET')
API_BASE_URL = "https://openapi.koreainvestment.com:9443"

def run_api_scanner():
    msg = "🕵️‍♂️ **한국투자증권 API 데이터 해독기**\n\n```text\n"
    
    res = requests.post(
        f"{API_BASE_URL}/oauth2/tokenP", 
        json={"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET}
    )
    token = res.json().get('access_token')
    if not token:
        return f"❌ 토큰 발급 실패\n{res.text[:100]}"
    
    msg += "✅ 1. 토큰 발급 성공!\n"

    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "FHPUP02120000",
        "custtype": "P"
    }
    url = f"{API_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-investor"

    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    today_str = now.strftime("%Y%m%d")
    
    # 아까 성공했던 파라미터 조합 (시간 정보 포함)
    params = {
        "FID_COND_MRKT_DIV_CODE": "U", 
        "FID_INPUT_ISCD": "0001", 
        "FID_INPUT_DATE_1": today_str, 
        "FID_INPUT_HOUR_1": "153000"
    }
    
    try:
        msg += f"\n▶ 데이터 요청 중...\n"
        r = requests.get(url, headers=headers, params=params)
        data = r.json()
        rt_cd = data.get('rt_cd')
        
        msg += f"└ 응답 코드: [{rt_cd}] {data.get('msg1')}\n"
        
        if rt_cd == '0':
            msg += f"🎉 데이터 수신 성공!\n"
            
            # output 분석 (리스트인지 딕셔너리인지 상관없이 무조건 안전하게 출력)
            for out_key in ['output', 'output2', 'output3']:
                if out_key in data:
                    item = data[out_key]
                    msg += f"\n👉 [{out_key}] 항목 분석:\n"
                    msg += f"   - 타입: {type(item).__name__}\n"
                    
                    if isinstance(item, list) and len(item) > 0:
                        msg += f"   - 키워드 목록: {list(item[0].keys())[:10]} ...\n"
                    elif isinstance(item, dict):
                        msg += f"   - 키워드 목록: {list(item.keys())[:10]} ...\n"
                        
                    msg += f"   - 내용(미리보기): {str(item)[:150]}\n"
                    
    except Exception as e:
         msg += f"\n💥 치명적 에러: {e}\n"
                
    msg += "```\n\n이 결과만 던져주시면 바로 암호 풀고 최종 코드 드립니다!"
    return msg

def send_telegram(message):
    import requests
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
    )

if __name__ == "__main__":
    send_telegram(run_api_scanner())