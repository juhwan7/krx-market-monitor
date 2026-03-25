import os
import datetime
import requests
import yfinance as yf
import traceback

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# 이름은 HANWHA로 하셨지만, 내용은 한국투자증권 키가 맞습니다! 그대로 씁니다.
APP_KEY = os.environ.get('HANWHA_APP_KEY')
APP_SECRET = os.environ.get('HANWHA_APP_SECRET')

# 한국투자증권 공식 접속 도메인
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
        return None, "깃허브 시크릿 키가 연동되지 않았습니다."
        
    url = f"{API_BASE_URL}/oauth2/tokenP"
    headers = {"content-type": "application/json"}
    body = {
        "grant_type": "client_credentials", 
        "appkey": APP_KEY, 
        "appsecret": APP_SECRET
    }
    
    try:
        res = requests.post(url, headers=headers, json=body, timeout=5)
        data = res.json()
        return data.get('access_token'), ""
    except Exception as e:
        return None, f"토큰 요청 에러: {e}"

def get_investor_trend_api(token, market_code, name):
    if not token:
        return None, f"[{name}] API 토큰 없음"
        
    # 💡 404 에러의 원인이었던 잘못된 URL 주소를 정확하게 수정
    url = f"{API_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-investor"
    
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "FHPUP02120000", # 업종별투자자(시간별) TR 코드
        "custtype": "P"
    }
    
    params = {
        "FID_COND_MRKT_DIV_CODE": "U",
        "FID_INPUT_ISCD": market_code 
    }

    try:
        res = requests.get(url, headers=headers, params=params, timeout=5)
        data = res.json()
            
        if data.get('rt_cd') != '0':
            return None, f"[{name}] API 자체 에러 반환: {data.get('msg1')}"
            
        # 한국투자증권은 시간별 배열 데이터를 'output2'에 담아줍니다.
        records = data.get('output2') or data.get('output')
        if not records:
            return None, f"[{name}] 수급 데이터 배열이 텅 비어있습니다."
            
        first_row = records[0]
        
        # 만약 예상한 키값이 다르면 텔레그램으로 키값 목록을 보내서 바로 수정할 수 있게 방어막 생성
        if 'prsn_ntby_tr_pbmn' not in first_row:
            return None, f"[{name}] 키 매핑 실패! (한국투자가 보내준 키들: {list(first_row.keys())})"
            
        now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
        target_30m = (now - datetime.timedelta(minutes=30)).strftime("%H%M%S")
        target_1h = (now - datetime.timedelta(minutes=60)).strftime("%H%M%S")

        current = records[0]
        
        past_30m = current
        for r in records:
            if str(r.get('stck_cntg_hour', '')) <= target_30m:
                past_30m = r
                break
                
        past_1h = records[-1] if len(records) > 0 else current
        for r in records:
            if str(r.get('stck_cntg_hour', '')) <= target_1h:
                past_1h = r
                break

        # 한국투자는 백만원 단위로 값을 던져주므로 100으로 나눠서 억원으로 변환
        def get_val(row, key):
            try: return round(float(row.get(key, 0)) / 100)
            except: return 0

        c_ret = get_val(current, 'prsn_ntby_tr_pbmn')
        c_for = get_val(current, 'frgn_ntby_tr_pbmn')
        c_org = get_val(current, 'orgn_ntby_tr_pbmn')

        p30_ret = get_val(past_30m, 'prsn_ntby_tr_pbmn')
        p30_for = get_val(past_30m, 'frgn_ntby_tr_pbmn')
        p30_org = get_val(past_30m, 'orgn_ntby_tr_pbmn')

        p1h_ret = get_val(past_1h, 'prsn_ntby_tr_pbmn')
        p1h_for = get_val(past_1h, 'frgn_ntby_tr_pbmn')
        p1h_org = get_val(past_1h, 'orgn_ntby_tr_pbmn')

        return {
            "current": {"retail": c_ret, "foreigner": c_for, "institution": c_org},
            "diff_30m": {"retail": c_ret - p30_ret, "foreigner": c_for - p30_for, "institution": c_org - p30_org},
            "diff_1h": {"retail": c_ret - p1h_ret, "foreigner": c_for - p1h_for, "institution": c_org - p1h_org}
        }, ""
        
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
    
    # 💡 한투 API 토큰 발급 (카톡으로 알림 올 겁니다!)
    api_token, token_err = get_api_token()
    
    # 코스피(0001), 코스닥(1001) 수급 호출
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
    msg += f"- VIX(공포지수): `{vix['current']:,.2f}` ({vix['30m_diff']:+.2f})\n\n"

    msg += "🛢️ *주요 원자재 변동* (현재가 / 30분 변동)\n"
    msg += f"- 금(Gold): `{gold['current']:,.2f}$` ({gold['30m_diff']:+.2f}$)\n"
    msg += f"- WTI 원유: `{oil['current']:,.2f}$` ({oil['30m_diff']:+.2f}$)\n"
    msg += f"- 구리(Copper): `{copper['current']:,.4f}$` ({copper['30m_diff']:+.4f}$)\n"
    
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