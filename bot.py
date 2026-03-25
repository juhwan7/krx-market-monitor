import requests
from bs4 import BeautifulSoup
import datetime
import os
import time  # 💡 사람처럼 쉬어주는 기능 추가

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://finance.naver.com/"
}

def get_index_data(code):
    prices = []
    error_msg = ""
    
    # 💡 무식하게 다 찾지 않고 딱 현재(1), 30분전(6), 1시간전(11) 페이지만 스나이핑
    target_pages = [1, 6, 11]
    
    for page in target_pages:
        url = f"https://finance.naver.com/sise/sise_index_time.naver?code={code}&page={page}"
        try:
            res = requests.get(url, headers=HEADERS, timeout=5)
            res.encoding = 'euc-kr'
            soup = BeautifulSoup(res.text, 'html.parser')
            
            dates = soup.find_all('td', class_='date')
            numbers = soup.find_all('td', class_='number_1')
            
            if dates and len(numbers) >= len(dates):
                ratio = len(numbers) // len(dates)
                for i in range(len(dates)):
                    time_str = dates[i].text.strip()
                    price_str = numbers[i * ratio].text.strip().replace(',', '')
                    if time_str and price_str:
                        try:
                            prices.append({'time': time_str, 'price': float(price_str)})
                        except:
                            pass
            
            # 🚨 핵심: 네이버가 봇으로 인식하지 못하도록 1.5초 대기 (사람인 척 연기)
            time.sleep(1.5)
            
        except Exception as e:
            error_msg = f"{page}페이지 파싱 에러"
            break

    if not prices:
        return {"current": 0.0, "30m_diff": 0.0, "1h_diff": 0.0, "error": error_msg or "네이버 차단됨"}

    current_price = prices[0]['price']
    
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    target_30m = (now - datetime.timedelta(minutes=30)).strftime("%H:%M")
    target_1h = (now - datetime.timedelta(minutes=60)).strftime("%H:%M")

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
        "1h_diff": round(current_price - price_1h, 2),
        "error": ""
    }

def get_program_data():
    time.sleep(1) # 프로그램 데이터 가기 전에도 1초 휴식
    url = "https://finance.naver.com/sise/sise_program.naver"
    kospi_val = 0
    kosdaq_val = 0
    error_msg = ""
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        res.encoding = 'euc-kr'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cols = row.find_all(['th', 'td'])
                if len(cols) >= 7:
                    texts = [c.text.strip().replace(',', '') for c in cols]
                    
                    if '거래소' in texts[0] or '코스피' in texts[0]:
                        try:
                            kospi_val = round(int(texts[6]) / 100)
                        except:
                            pass
                    elif '코스닥' in texts[0]:
                        try:
                            kosdaq_val = round(int(texts[6]) / 100)
                        except:
                            pass
    except Exception as e:
        error_msg = str(e)

    return {"KOSPI": kospi_val, "KOSDAQ": kosdaq_val, "error": error_msg}

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
    
    errors = []
    if kospi_data.get('error'): errors.append(f"코스피: {kospi_data['error']}")
    if kosdaq_data.get('error'): errors.append(f"코스닥: {kosdaq_data['error']}")
    if program_data.get('error'): errors.append(f"프로그램: {program_data['error']}")
    
    if errors:
        msg += "\n⚠️ *데이터 수집 실패*\n" + "\n".join(errors)
    else:
        msg += "\n💡 프로그램 매도 폭탄이 떨어질 때가 눌림 타점의 기회일 수 있습니다!"
        
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