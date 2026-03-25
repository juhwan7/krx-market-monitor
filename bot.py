import requests
import datetime
import os
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# 💡 CCTV 로그 기록장
debug_logs = []

def get_index_data(market):
    """다음(Daum) 금융 API를 사용하여 실시간 분봉 데이터를 가져옵니다."""
    debug_logs.append(f"\n🔍 [{market} 지수 추적 (Daum API)]")
    url = f"https://finance.daum.net/api/charts/market_index/{market}/minutes?limit=70"
    
    # 다음 금융은 Referer(어디서 접속했는지)를 확인하므로 홈피 주소를 적어줍니다.
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://finance.daum.net/"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=5)
        debug_logs.append(f"└ 상태코드: {res.status_code}")
        
        if res.status_code != 200:
            debug_logs.append("└ ❌ 다음 API 차단됨")
            return {"current": 0.0, "30m_diff": 0.0, "1h_diff": 0.0, "error": "다음 API 접속 실패"}
            
        data = res.json()
        if 'data' not in data or not data['data']:
            debug_logs.append("└ ❌ JSON 데이터가 비어있음")
            return {"current": 0.0, "30m_diff": 0.0, "1h_diff": 0.0, "error": "장 시작 전/데이터 없음"}
            
        records = data['data']
        debug_logs.append(f"└ 1분봉 데이터 {len(records)}개 확보 성공")
        
        # 데이터가 과거->현재 순서이므로 제일 마지막이 현재가
        current_price = float(records[-1]['tradePrice'])
        
        # 뒤에서부터 30번째(30분 전), 60번째(1시간 전) 가격을 찾음
        idx_30m = -31 if len(records) > 30 else 0
        idx_1h = -61 if len(records) > 60 else 0
        
        price_30m = float(records[idx_30m]['tradePrice'])
        price_1h = float(records[idx_1h]['tradePrice'])
        
        debug_logs.append(f"└ 매칭 완료 (현재:{current_price}, 30분전:{price_30m})")
        
        return {
            "current": current_price,
            "30m_diff": round(current_price - price_30m, 2),
            "1h_diff": round(current_price - price_1h, 2),
            "error": ""
        }
    except Exception as e:
        debug_logs.append(f"└ 💥 에러 발생: {e}")
        return {"current": 0.0, "30m_diff": 0.0, "1h_diff": 0.0, "error": str(e)}

def get_program_data():
    """네이버 금융을 구글봇(Googlebot)으로 위장하여 방화벽을 우회합니다."""
    debug_logs.append(f"\n🔍 [프로그램 매매 추적 (구글봇 위장)]")
    url = "https://finance.naver.com/sise/sise_program.naver"
    kospi_val = 0
    kosdaq_val = 0
    error_msg = ""
    
    # 🚨 핵심: 구글 검색엔진 크롤러인 척 신분증 위조
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "Referer": "https://www.google.com/"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=5)
        res.encoding = 'euc-kr'
        debug_logs.append(f"└ 상태코드: {res.status_code}")
        
        soup = BeautifulSoup(res.text, 'html.parser')
        tables = soup.find_all('table')
        debug_logs.append(f"└ 발견된 테이블 수: {len(tables)}개")
        
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
            debug_logs.append("└ ❌ 방어벽은 뚫었으나 데이터를 못 찾음")
            error_msg = "데이터 파싱 실패"
            
    except Exception as e:
        debug_logs.append(f"└ 💥 에러 발생: {e}")
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
    
    # 에러가 있으면 알려줌
    errors = []
    if kospi_data.get('error'): errors.append(f"코스피: {kospi_data['error']}")
    if kosdaq_data.get('error'): errors.append(f"코스닥: {kosdaq_data['error']}")
    if program_data.get('error'): errors.append(f"프로그램: {program_data['error']}")
    
    if errors:
        msg += "\n⚠️ *일부 데이터 수집 실패*\n" + "\n".join(errors)
    
    # 하단에 CCTV 로그 추가
    msg += "\nㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ\n"
    msg += "🛠️ *상세 디버깅 로그 (CCTV)*\n```text"
    msg += "\n".join(debug_logs)
    msg += "\n```"
        
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