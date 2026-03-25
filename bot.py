import os
import datetime
import urllib.request
import yfinance as yf
import pandas as pd
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
debug_logs = []

def get_index_data_yf(ticker, name):
    """야후 파이낸스를 이용해 지수 1분봉 데이터를 가져옵니다. (방화벽 절대 안막힘)"""
    debug_logs.append(f"\n🔍 [{name} 지수 추적 (Yahoo Finance)]")
    try:
        # 야후 파이낸스 KOSPI: ^KS11, KOSDAQ: ^KQ11
        df = yf.download(ticker, period="1d", interval="1m", progress=False)
        
        if df.empty:
            debug_logs.append("└ ❌ 데이터 없음 (휴장일이거나 장 시작 전)")
            return {"current": 0.0, "30m_diff": 0.0, "1h_diff": 0.0, "error": "데이터 없음"}
            
        debug_logs.append(f"└ 1분봉 데이터 {len(df)}개 확보 성공")
        
        # 종가(Close) 리스트 추출
        closes = df['Close'].dropna().values
        current_price = float(closes[-1])
        
        # 30분 전(30개 전), 1시간 전(60개 전) 가격
        idx_30m = -31 if len(closes) > 30 else 0
        idx_1h = -61 if len(closes) > 60 else 0
        
        price_30m = float(closes[idx_30m])
        price_1h = float(closes[idx_1h])
        
        debug_logs.append(f"└ 매칭 완료 (현재:{current_price:.2f}, 30분전:{price_30m:.2f})")
        
        return {
            "current": current_price,
            "30m_diff": round(current_price - price_30m, 2),
            "1h_diff": round(current_price - price_1h, 2),
            "error": ""
        }
    except Exception as e:
        debug_logs.append(f"└ 💥 야후 파이낸스 에러: {e}")
        return {"current": 0.0, "30m_diff": 0.0, "1h_diff": 0.0, "error": "야후 API 에러"}

def get_program_data():
    """urllib 모듈을 활용해 브라우저 엔진 레벨로 위장하여 네이버 방화벽을 찌릅니다."""
    debug_logs.append(f"\n🔍 [프로그램 매매 추적 (urllib 위장)]")
    url = "https://finance.naver.com/sise/sise_program.naver"
    kospi_val = 0
    kosdaq_val = 0
    error_msg = ""
    
    # requests 모듈 특유의 흔적을 지우고 urllib으로 직접 요청
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Referer': 'https://finance.naver.com/'
    })
    
    try:
        response = urllib.request.urlopen(req, timeout=10)
        html = response.read().decode('euc-kr', errors='ignore')
        debug_logs.append(f"└ 상태코드: {response.getcode()}")
        
        soup = BeautifulSoup(html, 'html.parser')
        tables = soup.find_all('table')
        
        found = False
        for table in tables:
            for row in table.find_all('tr'):
                cols = row.find_all(['th', 'td'])
                if len(cols) >= 7:
                    texts = [c.text.strip().replace(',', '') for c in cols]
                    if '거래소' in texts[0] or '코스피' in texts[0]:
                        try:
                            kospi_val = round(int(texts[6]) / 100)
                            found = True
                        except: pass
                    elif '코스닥' in texts[0]:
                        try:
                            kosdaq_val = round(int(texts[6]) / 100)
                            found = True
                        except: pass
                        
        if found:
            debug_logs.append(f"└ 뚫기 성공! 코스피 {kospi_val}억, 코스닥 {kosdaq_val}억")
        else:
            debug_logs.append("└ ❌ 테이블은 읽었으나 데이터 구조가 다름 (WAF 방어막일 확률 높음)")
            error_msg = "프로그램 데이터 파싱 실패"
            
    except Exception as e:
        debug_logs.append(f"└ 💥 접속 에러 발생: {e}")
        error_msg = "네이버 접속 완전 차단됨"

    return {"KOSPI": kospi_val, "KOSDAQ": kosdaq_val, "error": error_msg}

def format_message():
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    time_str = now.strftime("%Y-%m-%d %H:%M 기준")
    
    # 야후 파이낸스 티커 입력
    kospi_data = get_index_data_yf('^KS11', 'KOSPI')
    kosdaq_data = get_index_data_yf('^KQ11', 'KOSDAQ')
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
    
    msg += "\nㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ\n"
    msg += "🛠️ *상세 디버깅 로그 (CCTV)*\n```text"
    msg += "\n".join(debug_logs)
    msg += "\n```"
        
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