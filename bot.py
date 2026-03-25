import os
import datetime
import requests
import yfinance as yf
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def get_market_summary():
    """야후 파이낸스를 통해 지수와 매크로 데이터를 통합 수집합니다."""
    tickers = {
        'KOSPI': '^KS11', 'KOSDAQ': '^KQ11', 
        'USD/KRW': 'KRW=X', 'Nasdaq_Fut': 'NQ=F', 
        'VIX': '^VIX', 'Gold': 'GC=F'
    }
    
    results = {}
    for name, ticker in tickers.items():
        try:
            df = yf.download(ticker, period="1d", interval="1m", progress=False)
            if not df.empty:
                cur = float(df['Close'].iloc[-1])
                # 30분 전 데이터와 비교 (데이터가 부족하면 시가와 비교)
                prev = float(df['Close'].iloc[-31]) if len(df) > 30 else float(df['Open'].iloc[0])
                results[name] = {"cur": cur, "diff": round(cur - prev, 2)}
            else:
                results[name] = {"cur": 0, "diff": 0}
        except:
            results[name] = {"cur": 0, "diff": 0}
    return results

def get_investor_data():
    """네이버 메인 수급 페이지가 아닌, 비교적 보안이 허술한 '업종별 수급' 데이터를 찌릅니다."""
    url = "https://finance.naver.com/sise/sise_index.naver?code=KOSPI"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.content, 'html.parser')
        
        # '개인', '외국인', '기관' 글자가 포함된 span 태그를 직접 수색
        investors = soup.find_all('dd', class_='p11')
        # 수급 데이터 추출 (네이버 지수 메인 페이지 하단 데이터)
        # 이 부분은 실시간 누적 수치만 제공하므로, 30분 변동은 지수 변동으로 갈음합니다.
        return {
            "retail": investors[0].text if len(investors) > 0 else "데이터 없음",
            "foreigner": investors[1].text if len(investors) > 1 else "데이터 없음",
            "institution": investors[2].text if len(investors) > 2 else "데이터 없음"
        }
    except:
        return {"retail": "N/A", "foreigner": "N/A", "institution": "N/A"}

def format_message():
    m = get_market_summary()
    inv = get_investor_data()
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    
    msg = f"📊 *실시간 시장 레이더* ({now.strftime('%H:%M')})\n\n"
    
    msg += "📈 *주요 지수 (30분 변동)*\n"
    msg += f"- 코스피: `{m['KOSPI']['cur']:,.2f}` ({m['KOSPI']['diff']:+.2f})\n"
    msg += f"- 코스닥: `{m['KOSDAQ']['cur']:,.2f}` ({m['KOSDAQ']['diff']:+.2f})\n\n"
    
    msg += "👥 *당일 누적 수급 흐름*\n"
    msg += f"- 개인: `{inv['retail']}`\n"
    msg += f"- 외인: `{inv['foreigner']}`\n"
    msg += f"- 기관: `{inv['institution']}`\n\n"
    
    msg += "🌍 *글로벌 매크로*\n"
    msg += f"- 환율: `{m['USD/KRW']['cur']:,.1f}원` ({m['USD/KRW']['diff']:+.1f})\n"
    msg += f"- 나스닥선물: `{m['Nasdaq_Fut']['cur']:,.1f}` ({m['Nasdaq_Fut']['diff']:+.1f})\n"
    msg += f"- 공포지수(VIX): `{m['VIX']['cur']:.2f}`\n"
    
    return msg

if __name__ == "__main__":
    message = format_message()
    # 텔레그램 전송
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                  data={'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'Markdown'})