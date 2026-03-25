import os
import datetime
import requests
import yfinance as yf
import traceback

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# 💡 깃허브 시크릿에서 증권사 API 키 불러오기
APP_KEY = os.environ.get('HANWHA_APP_KEY')
APP_SECRET = os.environ.get('HANWHA_APP_SECRET')

# 증권사 API 도메인 (아래는 한국투자증권 실전투자 기준입니다)
API_BASE_URL = "https://openapi.koreainvestment.com:9443"

def get_yf_data(ticker, name):
    """야후 파이낸스 매크로 및 지수 데이터 수집 (이전과 동일)"""
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
    """1. 증권사 API 접근용 토큰을 발급받습니다."""
    if not APP_KEY or not APP_SECRET:
        return None
        
    url = f"{API_BASE_URL}/oauth2/tokenP"
    headers = {"content-type": "application/json"}
    body = {
        "grant_type": "client_credentials", 
        "appkey": APP_KEY, 
        "appsecret": APP_SECRET
    }
    
    try:
        res = requests.post(url, headers=headers, json=body, timeout=5)
        return res.json().get('access_token')
    except:
        return None

def get_investor_trend_api(token, market_code, name):
    """2. 증권사 API를 호출하여 시간대별 수급 데이터를 가져옵니다."""
    if not token:
        return None, f"[{name}] API 토큰 발급 실패 (시크릿 키 등록 확인 필요)"
        
    # 🚨 아래 URL과 파라미터는 한국투자증권(KIS) 기준 뼈대입니다.
    url = f"{API_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-investor-time"
    
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "FHPUP02120000", # 증권사 매뉴얼의 '시간대별 수급 TR 코드' 입력
        "custtype": "P"
    }
    
    params = {
        "FID_COND_MRKT_DIV_CODE": "U",
        "FID_INPUT_ISCD": market_code # 0001(코스피), 1001(코스닥)
    }

    try:
        res = requests.get(url, headers=headers, params=params, timeout=5)
        data = res.json()
        
        if data.get('rt_cd') != '0':
            return None, f"[{name}] API 자체 에러 반환: {data.get('msg1')}"
            
        records = data.get('output', [])
        if not records:
            return None, f"[{name}] 데이터 없음 (장 시작 전)"
            
        # =========================================================
        # 💡 [필독] 여기서부터는 증권사 API 매뉴얼을 보고 키값을 맞춰야 합니다!
        # JSON 응답 안에 '개인', '외국인' 숫자가 어떤 영문 키값으로 오는지 확인 후
        # 아래 딕셔너리에 꽂아넣어 주셔야 완벽하게 동작합니다.
        # =========================================================
        
        return {
            "current": {"retail": 0, "foreigner": 0, "institution": 0},
            "diff_30m": {"retail": 0, "foreigner": 0, "institution": 0},
            "diff_1h": {"retail": 0, "foreigner": 0, "institution": 0}
        }, "증권사 JSON 키값 매핑 필요 (하단 설명 참고)"
        
    except Exception as e:
        error_trace = traceback.format_exc()
        return None, f"[{name}] API 호출 중 파이썬 오류:\n{error_trace[:200]}"

def format_message():
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    time_str = now.strftime("%Y-%m-%d %H:%M 기준")
    
    kospi = get_yf_data('^KS11', 'KOSPI')
    kosdaq = get_yf_data('^KQ11', 'KOSDAQ')
    
    usdkrw = get_yf_data('KRW=X', '원/달러 환율')
    nq_fut = get_yf_data('NQ=F', '나스닥 100 선물')
    vix = get_yf_data('^VIX', 'VIX (공포지수)')
    
    # API 토큰 발급
    api_token = get_api_token()
    
    # 수급 데이터 호출 (한국투자증권 코드 기준: 0001 코스피, 1001 코스닥)
    inv_kospi, err_kospi = get_investor_trend_api(api_token, "0001", "코스피")
    inv_kosdaq, err_kosdaq = get_investor_trend_api(api_token, "1001", "코스닥")
    
    msg = f"📊 *시장 변동성 및 매크로 브리핑* ({time_str})\n\n"
    
    msg += "📉 *국내 지수 변동* (현재가 / 30분 / 1시간)\n"
    msg += f"- 코스피: `{kospi['current']:,.2f}` (30분: `{kospi['30m_diff']:+.2f}` / 1시간: `{kospi['1h_diff']:+.2f}`)\n"
    msg += f"- 코스닥: `{kosdaq['current']:,.2f}` (30분: `{kosdaq['30m_diff']:+.2f}` / 1시간: `{kosdaq['1h_diff']:+.2f}`)\n\n"
    
    msg += "👥 *투자자별 수급 흐름* (현재누적 / 30분변동 / 1시간변동)\n"
    for name, data in [("코스피", inv_kospi), ("코스닥", inv_kosdaq)]:
        msg += f"*[ {name} ]*\n"
        if data and "증권사 JSON" not in err_kospi:
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
    
    raw_errors = [e for e in [err_kospi, err_kosdaq] if e]
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