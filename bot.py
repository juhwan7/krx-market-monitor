import requests
from bs4 import BeautifulSoup
import datetime
import os

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# 차단 방지를 위한 브라우저 헤더 설정
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_index_data(code):
    prices = []
    
    # 약 1시간 30분치 분량의 페이지 탐색
    for page in range(1, 15):
        url = f"https://finance.naver.com/sise/sise_index_time.naver?code={code}&thistime=&page={page}"
        try:
            res = requests.get(url, headers=HEADERS, timeout=5)
            res.encoding = 'euc-kr' # 💡 핵심: 한글 깨짐 방지
            soup = BeautifulSoup(res.text, 'html.parser')
            
            table = soup.find('table', {'class': 'type_1'})
            if not table:
                continue
                
            rows = table.find_all('tr')
            for row in rows:
                tds = row.find_all('td')
                if len(tds) >= 2:
                    time_str = tds[0].text.strip()
                    price_str = tds[1].text.strip().replace(',', '')
                    
                    # 시간이 정상적이고 가격이 숫자인 데이터만 추출
                    if ":" in time_str and "." in price_str:
                        try:
                            price = float(price_str)
                            prices.append({'time': time_str, 'price': price})
                        except ValueError:
                            pass
        except Exception as e:
            print(f"페이지 에러: {e}")

    # 비상용 기본값
    if not prices:
        return {"current": 0.0, "30m_diff": 0.0, "1h_diff": 0.0}

    current_price = prices[0]['price']
    
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    target_30m = (now - datetime.timedelta(minutes=30)).strftime("%H:%M")
    target_1h = (now - datetime.timedelta(minutes=60)).strftime("%H:%M")

    # 과거 가격 탐색
    price_30m = current_price
    for p in prices:
        if p['time'] <= target_30m:
            price_30m = p['price']
            break

    price_1h = prices[-1]['price'] if len(prices) > 0 else current_price
    for p in prices:
        if p['time'] <= target_1h:
            price_1h = p['price']
            break

    return {
        "current": current_price,
        "30m_diff": round(current_price - price_30m, 2),
        "1h_diff": round(current_price - price_1h, 2)
    }

def get_program_data():
    url = "https://finance.naver.com/sise/sise_program.naver"
    kospi_val = 0
    kosdaq_val = 0
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        res.encoding = 'euc-kr' # 💡 핵심: '거래소' 글자 인식
        soup = BeautifulSoup(res.text, 'html.parser')
        
        table = soup.find('table', {'class': 'type_1'})
        if table:
            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all(['th', 'td'])
                
                # 표의 구조(8칸)에 맞는 유효한 데이터만 처리
                if len(cols) >= 7:
                    col_texts = [c.text.strip() for c in cols]
                    
                    if '거래소' in col_texts[0]:
                        try:
                            # 6번째 인덱스가 비차익 순매수 위치
                            val_str = col_texts[6].replace(',', '')
                            kospi_val = round(int(val_str) / 100) # 백만 단위 -> 억 단위
                        except:
                            pass
                    elif '코스닥' in col_texts[0]:
                        try:
                            val_str = col_texts[6].replace(',', '')
                            kosdaq_val = round(int(val_str) / 100)
                        except:
                            pass
    except Exception as e:
        print(f"프로그램 에러: {e}")

    return {"KOSPI": kospi_val, "KOSDAQ": kosdaq_val}

def format_message():
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    time_str = now.strftime("%Y-%m-%d %H:%M 기준")
    
    kospi_data = get_index_data('KOSPI')
    kosdaq_data = get_index_data('KOSDAQ')
    program_data = get_program_data()
    
    msg = f"📊 *시장 변동성 및 수급 브리핑* ({time_str})\n\n"
    
    msg += "📉 *지수 변동* (현재가 / 30분 / 1시간)\n"
    msg += f"- 코스피: `{kospi_data['current']:,.2f}` (30분: `{kospi_data['30m_diff']:+.2f}` / 1시간: `{kospi_data['1h_diff']:+.2f}`)\n"
    msg += f"- 코스닥: `{kosdaq_data['current']:,.2f}` (30분: `{kosdaq_data['30m_diff']:+.2f}` / 1시간: `{kosdaq_data['1h_diff']:+.2f}`)\n\n"
    
    msg += "🤖 *비차익 프로그램 누적* (단위: 억원)\n"
    msg += f"- 코스피: `{program_data['KOSPI']:+,d}억`\n"
    msg += f"- 코스닥: `{program_data['KOSDAQ']:+,d}억`\n"
    
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