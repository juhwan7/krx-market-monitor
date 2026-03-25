import requests
from bs4 import BeautifulSoup
import datetime
import os

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def get_index_data(code):
    prices = []
    # 1페이지당 약 6분치 데이터가 있습니다. 
    # 1시간 전 데이터를 찾기 위해 넉넉히 1~12페이지를 모두 긁어옵니다.
    for page in range(1, 13):
        url = f"https://finance.naver.com/sise/sise_index_time.naver?code={code}&thistime=&page={page}"
        res = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(res.text, 'html.parser')
        
        for tr in soup.find_all('tr'):
            tds = tr.find_all('td')
            # 시간이랑 가격 데이터가 있는 줄만 파싱
            if len(tds) >= 2 and tds[0].text.strip() and tds[1].text.strip():
                try:
                    time_str = tds[0].text.strip()
                    price = float(tds[1].text.strip().replace(',', ''))
                    prices.append({'time': time_str, 'price': price})
                except:
                    pass

    # 데이터를 못 가져왔을 경우 안전장치
    if not prices:
        return {"current": 0.0, "30m_diff": 0.0, "1h_diff": 0.0}

    current_price = prices[0]['price']
    
    # 현재 한국 시간 기준으로 30분 전, 1시간 전 목표 시간 계산
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    target_30m = (now - datetime.timedelta(minutes=30)).strftime("%H:%M")
    target_1h = (now - datetime.timedelta(minutes=60)).strftime("%H:%M")

    # 과거 가격 찾기 (기본값은 현재가로 세팅)
    price_30m = current_price
    price_1h = prices[-1]['price'] if len(prices) > 0 else current_price

    # 최신 데이터부터 과거로 거슬러 올라가며 목표 시간과 가장 가까운 가격을 매칭
    for p in prices:
        if p['time'] <= target_30m:
            price_30m = p['price']
            break

    for p in prices:
        if p['time'] <= target_1h:
            price_1h = p['price']
            break

    return {
        "current": current_price,
        "30m_diff": current_price - price_30m,
        "1h_diff": current_price - price_1h
    }

def get_program_data():
    url = "https://finance.naver.com/sise/sise_program.naver"
    res = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(res.text, 'html.parser')
    
    kospi_val = 0
    kosdaq_val = 0
    
    try:
        # 프로그램 매매 종합 테이블을 직접 찾아갑니다.
        table = soup.find('table', {'class': 'type_1'})
        rows = table.find_all('tr')
        
        for row in rows:
            th = row.find('th')
            if th and '거래소' in th.text:
                tds = row.find_all('td')
                try:
                    # 5번째 칸이 비차익 순매수 (백만원 단위)
                    val_str = tds[5].text.strip().replace(',', '')
                    kospi_val = round(int(val_str) / 100) # 억 단위로 보기 쉽게 변환
                except ValueError:
                    pass
            elif th and '코스닥' in th.text:
                tds = row.find_all('td')
                try:
                    val_str = tds[5].text.strip().replace(',', '')
                    kosdaq_val = round(int(val_str) / 100)
                except ValueError:
                    pass
    except Exception as e:
        print("프로그램 데이터 파싱 중 에러 발생:", e)

    return {"KOSPI": kospi_val, "KOSDAQ": kosdaq_val}

def format_message():
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    time_str = now.strftime("%Y-%m-%d %H:%M 기준")
    
    kospi_data = get_index_data('KOSPI')
    kosdaq_data = get_index_data('KOSDAQ')
    program_data = get_program_data()
    
    msg = f"📊 **시장 변동성 & 수급 브리핑** ({time_str})\n\n"
    
    msg += "📉 **지수 변동 (현재가 / 30분 / 1시간)**\n"
    # :+.2f 는 양수일 때 + 기호를 붙여주는 포맷팅입니다.
    msg += f"• 코스피: {kospi_data['current']:,.2f} (30분: {kospi_data['30m_diff']:+.2f} / 1시간: {kospi_data['1h_diff']:+.2f})\n"
    msg += f"• 코스닥: {kosdaq_data['current']:,.2f} (30분: {kosdaq_data['30m_diff']:+.2f} / 1시간: {kosdaq_data['1h_diff']:+.2f})\n\n"
    
    msg += "🤖 **비차익 프로그램 누적 (단위: 억원)**\n"
    msg += f"• 코스피: {program_data['KOSPI']:+,d}억\n"
    msg += f"• 코스닥: {program_data['KOSDAQ']:+,d}억\n"
    
    return msg

def send_telegram(message):
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