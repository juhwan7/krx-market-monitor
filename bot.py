import requests
from bs4 import BeautifulSoup
import datetime
import os

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# 💡 핵심: 네이버의 봇 차단을 뚫기 위해 완벽한 사람(일반 브라우저)으로 위장합니다.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
    "Referer": "https://finance.naver.com/sise/"
}

def get_index_data(code):
    prices = []
    error_msg = ""
    
    # 넉넉하게 15페이지(약 1시간 반 분량) 스캔
    for page in range(1, 15):
        url = f"https://finance.naver.com/sise/sise_index_time.naver?code={code}&page={page}"
        try:
            res = requests.get(url, headers=HEADERS, timeout=5)
            res.encoding = 'euc-kr'
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 파싱 전략 1: 명확한 클래스명으로 찾기
            dates = soup.find_all('td', class_='date')
            numbers = soup.find_all('td', class_='number_1')
            
            if dates and len(numbers) >= len(dates):
                ratio = len(numbers) // len(dates) # 한 줄에 숫자가 몇 개씩 있는지 비율 계산
                for i in range(len(dates)):
                    time_str = dates[i].text.strip()
                    price_str = numbers[i * ratio].text.strip().replace(',', '')
                    if time_str and price_str:
                        try:
                            prices.append({'time': time_str, 'price': float(price_str)})
                        except:
                            pass
            else:
                # 파싱 전략 2: 만약 테이블 구조가 깨졌다면 무식하게 모든 줄(tr)을 뒤져서 찾기
                for row in soup.find_all('tr'):
                    cols = row.find_all('td')
                    if len(cols) >= 2 and ':' in cols[0].text: # 첫 칸이 시간(HH:MM) 형태면 체결가로 간주
                        time_str = cols[0].text.strip()
                        price_str = cols[1].text.strip().replace(',', '')
                        try:
                            prices.append({'time': time_str, 'price': float(price_str)})
                        except:
                            pass
        except Exception as e:
            error_msg = f"페이지 파싱 중 에러({page}): {e}"
            break

    # 데이터를 아예 못 가져왔을 때의 안전장치
    if not prices:
        return {"current": 0.0, "30m_diff": 0.0, "1h_diff": 0.0, "error": error_msg or "네이버 접속 차단됨 (데이터 없음)"}

    current_price = prices[0]['price']
    
    # 현재 KST 시간 기준으로 30분전, 1시간전 목표 시간 계산
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    target_30m = (now - datetime.timedelta(minutes=30)).strftime("%H:%M")
    target_1h = (now - datetime.timedelta(minutes=60)).strftime("%H:%M")

    # 과거 가격 탐색 (가장 가까운 과거 시점의 가격 매칭)
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
    url = "https://finance.naver.com/sise/sise_program.naver"
    kospi_val = 0
    kosdaq_val = 0
    error_msg = ""
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        res.encoding = 'euc-kr'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 페이지 내의 모든 표(table)를 뒤져서 '거래소', '코스닥' 글자가 있는 줄을 악착같이 찾음
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cols = row.find_all(['th', 'td'])
                if len(cols) >= 7:
                    texts = [c.text.strip().replace(',', '') for c in cols]
                    
                    if '거래소' in texts[0] or '코스피' in texts[0]:
                        try:
                            kospi_val = round(int(texts[6]) / 100) # 7번째 칸(인덱스 6)이 비차익 순매수
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
    
    # 에러가 발생했을 때 텔레그램 메시지 하단에 원인 출력
    errors = []
    if kospi_data.get('error'): errors.append(f"코스피: {kospi_data['error']}")
    if kosdaq_data.get('error'): errors.append(f"코스닥: {kosdaq_data['error']}")
    if program_data.get('error'): errors.append(f"프로그램: {program_data['error']}")
    
    if errors:
        msg += "\n⚠️ *데이터 수집 실패 알림*\n" + "\n".join(errors)
    else:
        msg += "\n💡 프로그램 매도 폭탄이 떨어질 때가 눌림목 기회일 수 있습니다!"
        
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
    print("텔레그램 메시지 전송 완료!")