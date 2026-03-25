import requests
from bs4 import BeautifulSoup
import datetime
import os

# GitHub Secrets에서 가져올 텔레그램 정보
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def get_market_data():
    # 💡 주의: 실제 구현 시에는 네이버 금융 API(json/xml)나 pykrx 라이브러리를 활용해 
    # 코스피/코스닥/선물 분봉 데이터 및 프로그램 비차익 매매 동향을 크롤링해야 합니다.
    # 아래는 구조를 보여주기 위한 가상의 데이터 반환 예시입니다.
    
    return {
        "KOSPI": {"current": 2750.12, "30m_diff": -5.2, "1h_diff": -12.4},
        "KOSDAQ": {"current": 900.45, "30m_diff": +2.1, "1h_diff": -3.0},
        "FUTURES": {"current": 365.10, "30m_diff": -0.5, "1h_diff": -1.2},
        "PROGRAM_KOSPI": {"non_arbitrage": -1500}, # 단위: 억원 (순매도)
        "PROGRAM_KOSDAQ": {"non_arbitrage": +300}  # 단위: 억원 (순매수)
    }

def format_message(data):
    # 가독성을 높이기 위해 이모지와 포맷팅을 사용합니다.
    # 상승은 🔴, 하락은 🔵, 프로그램 순매수는 📈, 순매도는 📉 등으로 표현
    
    now = datetime.datetime.now()
    time_str = now.strftime("%Y-%m-%d %H:%M 기준")
    
    msg = f"📊 **시장 동향 브리핑** ({time_str})\n\n"
    
    # 지수 및 선물 변동
    msg += "📉 **지수 & 선물 변동 (30분 / 1시간)**\n"
    msg += f"• 코스피: {data['KOSPI']['current']} ({data['KOSPI']['30m_diff']} / {data['KOSPI']['1h_diff']})\n"
    msg += f"• 코스닥: {data['KOSDAQ']['current']} ({data['KOSDAQ']['30m_diff']} / {data['KOSDAQ']['1h_diff']})\n"
    msg += f"• 선  물: {data['FUTURES']['current']} ({data['FUTURES']['30m_diff']} / {data['FUTURES']['1h_diff']})\n\n"
    
    # 비차익 프로그램 동향
    msg += "🤖 **비차익 프로그램 동향 (누적)**\n"
    msg += f"• 코스피: {data['PROGRAM_KOSPI']['non_arbitrage']}억\n"
    msg += f"• 코스닥: {data['PROGRAM_KOSDAQ']['non_arbitrage']}억\n"
    
    return msg

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown' # 굵은 글씨 등 마크다운 적용
    }
    requests.post(url, data=payload)

if __name__ == "__main__":
    market_data = get_market_data()
    message = format_message(market_data)
    send_telegram(message)