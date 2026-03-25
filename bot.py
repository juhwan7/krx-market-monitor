import os
import datetime
import requests
import yfinance as yf
import traceback

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# 깃허브 시크릿에서 한화투자증권 API 키 불러오기
APP_KEY = os.environ.get('HANWHA_APP_KEY')
APP_SECRET = os.environ.get('HANWHA_APP_SECRET')

# 🚨 현재 목적지는 한국투자증권입니다. (한화 매뉴얼을 보고 수정해야 함!)
API_BASE_URL = "https://openapi.koreainvestment.com:9443"

def get_yf_data(ticker, name):
    try:
        df = yf.download(ticker, period="1d", interval="1m", progress=False)
        if df.empty:
            return {"current": 0.0, "30m_diff": 0.0, "1h_diff": 0.0, "error": "데이터 없음"}
            
        closes = df['Close'].dropna().values
        current_price = float(closes[-1])
        
        idx_30m = -31 if len(closes) > 30 else 0
        idx_1h = -61 if len(closes) > 60 else 0
        
        return {
            "current": current_price,
            "30m_diff": round(current_price - float(closes[idx_30m]), 2),
            "1h_diff": round(current_price - float(closes[idx_1h]), 2),
            "error": ""
        }
    except Exception as e:
        return {"current": 0.0, "30m_diff": 0.0, "1h_diff": 0.0, "error": str(e)}

def get_api_token():
    if not APP_KEY or not APP_SECRET:
        return None, "시크릿 키(HANWHA_APP_KEY 등)가 깃허브에 등록되지 않았습니다."
        
    url = f"{API_BASE_URL}/oauth2/tokenP"
    headers = {"content-type": "application/json"}
    body = {
        "grant_type": "client_credentials", 
        "appkey": APP_KEY, 
        "appsecret": APP_SECRET
    }
    
    try:
        res = requests.post(url, headers=headers, json=body, timeout=5)
        # 💡 JSON 파싱 에러(complexjson)를 잡기 위한 방어벽
        try:
            data = res.json()
            return data.get('access_token'), ""
        except Exception:
            return None, f"토큰 발급 실패 (JSON 아님)\n상태코드: {res.status_code}\n응답 텍스트: {res.text[:150]}"
    except Exception as e:
        return None, f"토큰 요청 네트워크 에러: {e}"

def get_investor_trend_api(token, market_code, name):
    if not token:
        return None, f"[{name}] API 토큰이 없어 실행 불가"
        
    url = f"{API_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-investor-time"
    
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "FHPUP02120000", 
        "custtype": "P"
    }
    
    params = {
        "FID_COND_MRKT_DIV_CODE": "U",
        "FID_INPUT_ISCD": market_code 
    }

    try:
        res = requests.get(url, headers=headers, params=params, timeout=5)
        
        # 💡 HTML 에러 페이지를 JSON으로 읽다가 파이썬이 뻗는 현상 완벽 차단!
        try:
            data = res.json()
        except Exception:
            return None, f"[{name}] 서버가 에러를 뱉었습니다 (JSON 아님)\n상태코드: {res.status_code}\n응답 원본: {res.text[:150]}"
            
        if data.get('rt_cd') != '0':
            return None, f"[{name}] API 자체 에러 반환: {data.get('msg1')}"
            
        return None, "증권사 JSON 키값 매핑 필요 (한화 매뉴얼 확인 필요)"
        
    except Exception as e:
        error_trace = traceback.format_exc()
        return None, f"[{name}] 파이썬 실행 오류:\n{error_trace[:150]}"

def format_message():
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    time_str = now.strftime("%Y-%m-%d %H:%M 기준")
    
    kospi = get_yf_data('^KS11', 'KOSPI')
    kosdaq = get_yf_data('^KQ11', 'KOSDAQ')
    
    usdkrw = get_yf_data('KRW=X', '원/달러 환율')
    nq_fut = get_yf_data('NQ=F', '나스닥 100 선물')
    vix = get_yf_data('^VIX', 'VIX (공포지수)')
    
    gold = get_yf_data('GC=F', '금 선물')
    oil = get_yf_data('CL=F', 'WTI 원유 선물')
    copper = get_yf_data('HG=F', '구리 선물')
    
    # API 토큰 발급
    api_token, token_err = get_api_token()
    
    # 수급 데이터 호출
    inv_kospi, err_kospi = get_investor_trend_api(api_token, "0001", "코스피")
    inv_kosdaq, err_kosdaq = get_investor_trend_api(api_token, "1001", "코스닥")
    
    msg = f"📊 *시장 변동성 및 매크로 브리핑* ({time_str})\n\n"
    
    msg += "📉 *국내 지수 변동* (현재가 / 30분 / 1시간)\n"
    msg += f"- 코스피: `{kospi['current']:,.2f}` (30분: `{kospi['30m_diff']:+.2f}` / 1시간: `{kospi['1h_diff']:+.2f}`)\n"
    msg += f"- 코스닥: `{kosdaq['current']:,.2f}` (30분: `{kosdaq['30m_diff']:+.2f}` / 1시간: `{kosdaq['1h_diff']:+.2f}`)\n\n"
    
    msg += "👥 *투자자별 수급 흐름* (현재누적 / 30분변동 / 1시간변동)\n"
    for name, data in [("코스피", inv_kospi), ("코스닥", inv_kosdaq)]:
        msg += f"*[ {name} ]*\n"
        if data:
            c, d30, d1h = data['current'], data['diff_30m'], data['diff_1h']
            msg += f"- 개인: `{c['retail']:+,d}억` (`{d30['retail']:+,d}` / `{d1h['retail']:+,d}`)\n"
            msg += f"- 외인: `{c['foreigner']:+,d}억` (`{d30['foreigner']:+,d}` / `{d1h['foreigner']:+,d}`)\n"
            msg += f"- 기관: `{c['institution']:+,d}억` (`{d30['institution']:+,d}` / `{d1h['institution']:+,d}`)\n\n"
        else:
            msg += f"- 데이터 수집 실패 (하단 디버깅 로그 참조)\n\n"
            
    msg += "🌍 *글로벌 매크로 지표* (현재가 / 30분 변동)\n"
    msg += f"- 환율(원/달러): `{usdkrw['current']:,.2f}원` ({usdkrw['30m_diff']:+.2f}원)\n"
    msg += f"- 나스닥 선물: `{nq_fut['current']:,.2f}` ({nq_fut['30m_diff']:+.2f})\n"
    msg += f"- VIX(공포지수): `{vix['current']:,.2f}` ({vix['30m_diff']:+.2f})\n"
    
    # 💡 에러 로그 통합 출력
    raw_errors = [e for e in [token_err, err_kospi, err_kosdaq] if e]
    if raw_errors:
        msg += "\nㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ\n"
        msg += "🛠️ *상세 오류 디버깅 (Raw Error)*\n```text\n"
        msg += "\n\n".join(raw_errors)
        msg += "\n```"
        
    return msg

def send_telegram(message):
    import requests
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    requests.post(url, data=payload)

if __name__ == "__main__":
    message = format_message()
    send_telegram(message)