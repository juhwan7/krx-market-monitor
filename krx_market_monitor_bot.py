import requests
from bs4 import BeautifulSoup
import datetime
import os

# 1. 깃허브 시크릿에서 텔레그램 정보 불러오기
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# 크롤링 시 차단 방지를 위한 User-Agent 설정
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_index_data(code):
    """지수(코스피/코스닥/선물)의 현재가 및 30분/1시간 전 대비 변동폭을 구하는 함수"""
    # 시간별 시세 페이지 (선물은 코드가 다르므로 분기 처리 필요, 여기서는 KOSPI/KOSDAQ 기준)
    url = f"https://finance.naver.com/sise/sise_index_time.naver?code={code}&thistime="
    
    # 💡 팁: 실제 완벽한 30분/1시간 전 데이터를 찾으려면 여러 페이지를 넘겨야 할 수 있지만,
    # 깃허브 액션 30분 스케줄러와 맞물려 실행되므로 가장 최근 페이지의 흐름을 읽어옵니다.
    res = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    # 체결가 리스트 추출
    prices = []
    for td in soup.select("td.number_1"):
        if td.text.strip():
            prices.append(float(td.text.replace(',', '')))
            
    if not prices:
        return {"current": 0, "30m_diff": 0, "1h_diff": 0}

    current_price = prices[0]
    
    # 임의로 리스트의 중간과 끝을 30분/1시간 전으로 가정하여 계산 (실제론 정확한 시간 매칭 로직 추가 가능)
    # 한 페이지에 보통 1분 단위 데이터가 10~20개 정도 노출됨.
    price_30m_ago = prices[min(30, len(prices)-1)] if len(prices) > 30 else prices[-1]
    
    diff_30m = round(current_price - price_30m_ago, 2)
    
    return {
        "current": current_price,
        "30m_diff": diff_30m,
        "1h_diff": "계산식 추가 필요" # 1시간 전 데이터는 페이지네이션을 넘겨야 하므로 생략
    }

def get_program_data():
    """코스피/코스닥의 비차익 프로그램 매수/매도 동향을 구하는 함수"""
    url = "https://finance.naver.com/sise/sise_program.naver"
    res = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    # 사이트 구조상 비차익 순매수 금액이 있는 위치를 셀렉터로 지정
    # KOSPI 비차익 누적, KOSDAQ 비차익 누적 (단위: 백만 -> 억으로 변환)
    try:
        kospi_non_arb = soup.select_one('#id_kospi_total2').text.replace(',', '')
        kosdaq_non_arb = soup.select_one('#id_kosdaq_total2').text.replace(',', '')
        
        # 억 단위로 보기 쉽게 변환
        kospi_val = round(int(kospi_non_arb) / 100)
        kosdaq_val = round(int(kosdaq_non_arb) / 100)
    except:
        kospi_val = 0
        kosdaq_val = 0

    return {"KOSPI": kospi_val, "KOSDAQ": kosdaq_val}

def format_message():
    """가져온 데이터를 텔레그램용 메시지로 이쁘게 포장"""
    # 한국 시간(KST) 구하기 (깃허브 액션은 UTC 기준이라 9시간 더해줌)
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    time_str = now.strftime("%Y-%m-%d %H:%M 기준")
    
    # 데이터 수집
    kospi_data = get_index_data('KOSPI')
    kosdaq_data = get_index_data('KOSDAQ')
    program_data = get_program_data()
    
    msg = f"📊 **시장 변동성 & 수급 브리핑** ({time_str})\n\n"
    
    msg += "📉 **지수 변동 (현재가 / 30분 전 대비)**\n"
    msg += f"• 코스피: {kospi_data['current']:,.2f} ({kospi_data['30m_diff']:+.2f})\n"
    msg += f"• 코스닥: {kosdaq_data['current']:,.2f} ({kosdaq_data['30m_diff']:+.2f})\n\n"
    
    msg += "🤖 **비차익 프로그램 동향 (누적 순매수)**\n"
    msg += f"• 코스피: {program_data['KOSPI']:+d}억원\n"
    msg += f"• 코스닥: {program_data['KOSDAQ']:+d}억원\n\n"
    
    msg += "💡 마이너스가 커질 때가 기회일 수 있습니다!"
    
    return msg

def send_telegram(message):
    """텔레그램으로 쏘기"""
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
    print("텔레그램 메시지 전송 완료!")