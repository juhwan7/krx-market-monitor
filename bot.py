import os
import datetime
import yfinance as yf

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def get_yf_data(ticker, name):
    """야후 파이낸스를 이용해 지수, 환율, 선물, 원자재 데이터를 수집합니다."""
    try:
        df = yf.download(ticker, period="1d", interval="1m", progress=False)
        
        if df.empty:
            return {"current": 0.0, "30m_diff": 0.0, "1h_diff": 0.0, "error": "데이터 없음"}
            
        closes = df['Close'].dropna().values
        current_price = float(closes[-1])
        
        idx_30m = -31 if len(closes) > 30 else 0
        idx_1h = -61 if len(closes) > 60 else 0
        
        price_30m = float(closes[idx_30m])
        price_1h = float(closes[idx_1h])
        
        return {
            "current": current_price,
            "30m_diff": round(current_price - price_30m, 2),
            "1h_diff": round(current_price - price_1h, 2),
            "error": ""
        }
    except Exception as e:
        return {"current": 0.0, "30m_diff": 0.0, "1h_diff": 0.0, "error": str(e)}

def format_message():
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    time_str = now.strftime("%Y-%m-%d %H:%M 기준")
    
    # 1. 국내 지수
    kospi = get_yf_data('^KS11', 'KOSPI')
    kosdaq = get_yf_data('^KQ11', 'KOSDAQ')
    
    # 2. 글로벌 매크로 지표
    usdkrw = get_yf_data('KRW=X', '원/달러 환율')
    nq_fut = get_yf_data('NQ=F', '나스닥 100 선물')
    vix = get_yf_data('^VIX', 'VIX (공포지수)')
    
    # 3. 주요 원자재 (추가됨)
    # GC=F(금 선물), CL=F(WTI 원유 선물), HG=F(구리 선물)
    gold = get_yf_data('GC=F', '금 선물')
    oil = get_yf_data('CL=F', 'WTI 원유 선물')
    copper = get_yf_data('HG=F', '구리 선물')
    
    msg = f"📊 *시장 변동성 및 매크로 브리핑* ({time_str})\n\n"
    
    msg += "📉 *국내 지수 변동* (현재가 / 30분 / 1시간)\n"
    msg += f"- 코스피: `{kospi['current']:,.2f}` (30분: `{kospi['30m_diff']:+.2f}` / 1시간: `{kospi['1h_diff']:+.2f}`)\n"
    msg += f"- 코스닥: `{kosdaq['current']:,.2f}` (30분: `{kosdaq['30m_diff']:+.2f}` / 1시간: `{kosdaq['1h_diff']:+.2f}`)\n\n"
    
    msg += "🌍 *글로벌 매크로 지표* (현재가 / 30분 변동)\n"
    msg += f"- 환율(원/달러): `{usdkrw['current']:,.2f}원` ({usdkrw['30m_diff']:+.2f}원)\n"
    msg += f"- 나스닥 선물: `{nq_fut['current']:,.2f}` ({nq_fut['30m_diff']:+.2f})\n"
    msg += f"- VIX(공포지수): `{vix['current']:,.2f}` ({vix['30m_diff']:+.2f})\n\n"

    msg += "🛢️ *주요 원자재 변동* (현재가 / 30분 변동)\n"
    msg += f"- 금(Gold): `{gold['current']:,.2f}$` ({gold['30m_diff']:+.2f}$)\n"
    msg += f"- WTI 원유: `{oil['current']:,.2f}$` ({oil['30m_diff']:+.2f}$)\n"
    msg += f"- 구리(Copper): `{copper['current']:,.4f}$` ({copper['30m_diff']:+.4f}$)\n\n"
    
    msg += "💡 *매매 Tip*: 매크로가 안정적인데 지수만 빠지면 좋은 눌림 타점입니다. 단, 금이나 원유의 급등, 혹은 환율 상승은 위험 회피 신호이니 비중을 조절하세요!\n"
    
    errors = []
    for d, name in zip(
        [kospi, kosdaq, usdkrw, nq_fut, vix, gold, oil, copper], 
        ['코스피', '코스닥', '환율', '나스닥선물', 'VIX', '금', '원유', '구리']
    ):
        if d.get('error'): errors.append(f"{name}: {d['error']}")
        
    if errors:
        msg += "\n⚠️ *일부 데이터 수집 실패*\n" + "\n".join(errors)
        
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