import requests
from bs4 import BeautifulSoup
import datetime
import os

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# 크롤링 차단 방지를 위한 일반 브라우저 헤더 설정
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_index_data(code):
    prices = []
    
    # 1시간 전 데이터를 여유 있게 확보하기 위해 1~15페이지(약 90분 분량)를 탐색합니다.
    for page in range(1, 16):
        url = f"https://finance.naver.com/sise/sise_index_time.naver?code={code}&thistime=&page={page}"
        try:
            res = requests.get(url, headers=HEADERS, timeout=5)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 시간(date)과 가격(number_1)이 있는 셀을 직접 추출
            dates = soup.find_all('td', class_='date')
            numbers = soup.find_all('td', class_='number_1')
            
            # number_1 클래스 안에 체결가, 전일비 등 여러 숫자가 섞여 있으므로
            # 4칸 간격(체결가 위치)으로 데이터를 추출합니다.
            if dates and numbers:
                for i in range(len(dates)):
                    time_str = dates[i].text.strip()
                    price_str = numbers[i * 4].text.strip().replace(',', '')
                    
                    if time_str and price_str:
                        try:
                            price = float(price_str)
                            prices.append({'time': time_str, 'price': price})
                        except ValueError:
                            continue
        except Exception as e:
            print(f"{code} 페이지 {page} 파싱 에러:", e)

    # 데이터를 가져오지 못했을 때의 기본값
    if not prices:
        return {"current": 0.0, "30m_diff": 0.0, "1h_diff": 0.0}

    current_price = prices[0]['price']
    
    # 깃허브 액션은 UTC 기준이므로 9시간을 더해 한국 시간(KST)으로 맞춤
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    target_30m = (now - datetime.timedelta(minutes=30)).strftime("%H:%M")
    target_1h = (now - datetime.timedelta(minutes=60)).strftime("%H:%M")

    # 과거 가격 탐색 (목표 시간과 일치하거나 그 이전 시간의 첫 번째 데이터)
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
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 테이블 행을 한 줄씩 돌며 코스피/코스닥 데이터를 찾습니다.
        rows = soup.find_all('tr')
        for row in rows:
            cols = row.find_all(['th', 'td'])
            
            # 데이터가 유효한 행(열이 충분히 많은 경우)만 필터링
            if len(cols) >= 8:
                first_col_text = cols[0].text.strip()
                
                # 표 구조상 비차익 순매수 금액은 7번째(인덱스 6)에 위치합니다.
                if '거래소' in first_col_text or '코스피' in first_col_text:
                    try:
                        val_str = cols[6].text.strip().replace(',', '')
                        kospi_val = round(int(val_str) / 100) # 백만 원 -> 억 단위 변환
                    except:
                        pass
                
                elif '코스닥' in first_col_text:
                    try:
                        val_str = cols[6].text.strip().replace(',', '')
                        kosdaq_val = round(int(val_str) / 100) # 백만 원 -> 억 단위 변환
                    except:
                        pass
    except Exception as e:
        print("프로그램 데이터 에러:", e)

    return {"KOSPI": kospi_val, "KOSDAQ": kosdaq_val}

def format_message():
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    time_str = now.strftime("%Y-%m-%d %H:%M 기준")
    
    kospi_data = get_index_data('KOSPI')
    kosdaq_data = get_index_data('KOSDAQ')
    program_data = get_program_data()
    
    msg = f"📊 시장 변동성 및 수급 브리핑 ({time_str})\n\n"
    
    msg += "📉 지수 변동 (현재가 / 30분 / 1시간)\n"
    msg += f"- 코스피: {kospi_data['current']:,.2f} (30분: {kospi_data['30m_diff']:+.2f} / 1시간: {kospi_data['1h_diff']:+.2f})\n"
    msg += f"- 코스닥: {kosdaq_data['current']:,.2f} (30분: {kosdaq_data['30m_diff']:+.2f} / 1시간: {kosdaq_data['1h_diff']:+.2f})\n\n"
    
    msg += "🤖 비차익 프로그램 누적 (단위: 억원)\n"
    msg += f"- 코스피: {program_data['KOSPI']:+,d}억\n"
    msg += f"- 코스닥: {program_data['KOSDAQ']:+,d}억\n"
    
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