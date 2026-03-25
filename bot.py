import os
import datetime
import urllib.request
import yfinance as yf
from bs4 import BeautifulSoup

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

def get_investor_trend():
    """모바일 환경으로 위장하여 코스피/코스닥/선물의 주체별 실시간 순매수 동향을 수집합니다."""
    trends = {}
    # 0: KOSPI, 1: KOSDAQ, 2: 선물
    codes = [("0", "코스피"), ("1", "코스닥"), ("2", "선  물")]
    
    for biztype, name in codes:
        url = f"https://finance.naver.com/sise/investorDealTrendData.naver?biztype={biztype}"
        
        # 🚨 WAF(방화벽)를 뚫기 위해 모바일 아이폰(iPhone) 접속으로 완벽 위장
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
            'Referer': 'https://m.naver.com/'
        })
        
        try:
            response = urllib.request.urlopen(req, timeout=5)
            xml_data = response.read().decode('euc-kr', errors='ignore')
            
            soup = BeautifulSoup(xml_data, 'html.parser')
            items = soup.find_all('item')
            
            if items:
                last = items[-1]
                # purval1(개인), purval2(외국인), purval3(기관)
                retail = int(last.find('purval1').text.replace(',', ''))
                foreigner = int(last.find('purval2').text.replace(',', ''))
                institution = int(last.find('purval3').text.replace(',', ''))
                
                trends[name] = {
                    "retail": retail, 
                    "foreigner": foreigner, 
                    "institution": institution, 
                    "error": ""
                }
            else:
                trends[name] = {"error": "방화벽 차단됨"}
        except Exception as e:
            trends[name] = {"error": str(e)}
            
    return trends

def format_message():
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    time_str = now.strftime("%Y-%m-%d %H:%M 기준")
    
    # 1. 국내 지수
    kospi = get_yf_data('^KS11', 'KOSPI')
    kosdaq = get_yf_data('^KQ11', 'KOSDAQ')
    
    # 2. 투자자별 수급 동향 (추가됨)
    investors = get_investor_trend()
    
    # 3. 글로벌 매크로 및 원자재
    usdkrw = get_yf_data('KRW=X', '원/달러 환율')
    nq_fut = get_yf_data('NQ=F', '나스닥 100 선물')
    vix = get_yf_data('^VIX', 'VIX (공포지수)')
    gold = get_yf_data('GC=F', '금 선물')
    oil = get_yf_data('CL=F', 'WTI 원유 선물')
    copper = get_yf_data('HG=F', '구리 선물')
    
    # 메시지 조합 시작
    msg = f"📊 *시장 변동성 및 매크로 브리핑* ({time_str})\n\n"
    
    msg += "📉 *국내 지수 변동* (현재가 / 30분 / 1시간)\n"
    msg += f"- 코스피: `{kospi['current']:,.2f}` (30분: `{kospi['30m_diff']:+.2f}` / 1시간: `{kospi['1h_diff']:+.2f}`)\n"
    msg += f"- 코스닥: `{kosdaq['current']:,.2f}` (30분: `{kosdaq['30m_diff']:+.2f}` / 1시간: `{kosdaq['1h_diff']:+.2f}`)\n\n"
    
    # 수급 동향 섹션 추가
    msg += "👥 *투자자별 수급 동향* (단위: 억원)\n"
    for name in ["코스피", "코스닥", "선  물"]:
        data = investors.get(name, {})
        if not data.get('error'):
            msg += f"- {name}: 개인 `{data['retail']:+,d}` | 외국인 `{data['foreigner']:+,d}` | 기관 `{data['institution']:+,d}`\n"
        else:
            msg += f"- {name}: 수급 데이터 파싱 실패\n"
    msg += "\n"
            
    msg += "🌍 *글로벌 매크로 지표* (현재가 / 30분 변동)\n"
    msg += f"- 환율(원/달러): `{usdkrw['current']:,.2f}원` ({usdkrw['30m_diff']:+.2f}원)\n"
    msg += f"- 나스닥 선물: `{nq_fut['current']:,.2f}` ({nq_fut['30m_diff']:+.2f})\n"
    msg += f"- VIX(공포지수): `{vix['current']:,.2f}` ({vix['30m_diff']:+.2f})\n\n"

    msg += "🛢️ *주요 원자재 변동* (현재가 / 30분 변동)\n"
    msg += f"- 금(Gold): `{gold['current']:,.2f}$` ({gold['30m_diff']:+.2f}$)\n"
    msg += f"- WTI 원유: `{oil['current']:,.2f}$` ({oil['30m_diff']:+.2f}$)\n"
    msg += f"- 구리(Copper): `{copper['current']:,.4f}$` ({copper['30m_diff']:+.4f}$)\n"
    
    # 에러 체크
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