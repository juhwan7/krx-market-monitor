import requests
import datetime
import os
import json
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://finance.naver.com/"
}

def get_index_data(symbol):
    """네이버 차트용 JSON API를 호출하여 방화벽을 완벽 우회합니다."""
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    today_str = now.strftime("%Y%m%d")
    
    # KOSPI / KOSDAQ 분봉 데이터를 가져오는 API 엔드포인트
    url = f"https://api.finance.naver.com/siseJson.naver?symbol={symbol}&requestType=1&startTime={today_str}090000&endTime={today_str}153000&timeframe=minute"
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        # Javascript 배열 형태를 Python에서 읽을 수 있는 JSON으로 변환
        text = res.text.strip().replace("'", '"')
        data = json.loads(text)
        
        if len(data) <= 1:
            return {"current": 0.0, "30m_diff": 0.0, "1h_diff": 0.0, "error": "장 시작 전이거나 데이터 없음"}
            
        # data[0]은 컬럼명, data[1:]부터 실제 분봉 데이터
        records = data[1:]
        current_price = float(records[-1][4]) # 4번째 인덱스가 종가(현재가)
        
        target_30m = (now - datetime.timedelta(minutes=30)).strftime("%Y%m%d%H%M")
        target_1h = (now - datetime.timedelta(minutes=60)).strftime("%Y%m%d%H%M")
        
        price_30m = current_price
        price_1h = current_price
        
        # 뒤에서부터 과거로 거슬러 올라가며 시간 매칭
        for row in reversed(records):
            time_str = str(row[0])
            if time_str <= target_30m and price_30m == current_price:
                price_30m = float(row[4])
            if time_str <= target_1h and price_1h == current_price:
                price_1h = float(row[4])
                
        return {
            "current": current_price,
            "30m_diff": round(current_price - price_30m, 2),
            "1h_diff": round(current_price - price_1h, 2),
            "error": ""
        }
    except Exception as e:
        return {"current": 0.0, "30m_diff": 0.0, "1h_diff": 0.0, "error": f"API 에러: {e}"}

def get_program_data():
    """세션(Session)을 유지하여 쿠키를 발급받아 방화벽을 우회합니다."""
    url_program = "https://finance.naver.com/sise/sise_program.naver"
    kospi_val = 0
    kosdaq_val = 0
    error_msg = ""
    
    try:
        # 1. 세션 열기 및 네이버 증권 메인 방문 (정상 유저 쿠키 획득)
        session = requests.Session()
        session.get("https://finance.naver.com/", headers=HEADERS, timeout=5)
        
        # 2. 획득한 쿠키를 들고 프로그램 매매 페이지 접근
        res = session.get(url_program, headers=HEADERS, timeout=5)
        res.encoding = 'euc-kr'
        soup = BeautifulSoup(res.text, 'html.parser')
        
        if "error_content" in res.text:
            return {"KOSPI": 0, "KOSDAQ": 0, "error": "쿠키 우회 실패 (WAF 강력 차단)"}
            
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cols = row.find_all(['th', 'td'])
                if len(cols) >= 7:
                    texts = [c.text.strip().replace(',', '') for c in cols]
                    if '거래소' in texts[0] or '코스피' in texts[0]:
                        try: kospi_val = round(int(texts[6]) / 100)
                        except: pass
                    elif '코스닥' in texts[0]:
                        try: kosdaq_val = round(int(texts[6]) / 100)
                        except: pass
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
        msg += "\n⚠️ *일부 데이터 수집 실패*\n" + "\n".join(errors)
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