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

# 💡 모든 과정을 기록할 일기장
debug_logs = []

def get_index_data(symbol):
    debug_logs.append(f"\n🔍 [{symbol} 지수 추적]")
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    today_str = now.strftime("%Y%m%d")
    
    url = f"https://api.finance.naver.com/siseJson.naver?symbol={symbol}&requestType=1&startTime={today_str}090000&endTime={today_str}153000&timeframe=minute"
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        debug_logs.append(f"└ 상태코드: {res.status_code}")
        
        raw_text = res.text.strip()
        # 원본 데이터의 앞 100글자만 짤라서 기록
        debug_logs.append(f"└ 응답 텍스트(앞100자): {raw_text[:100]}")
        
        text = raw_text.replace("'", '"')
        try:
            data = json.loads(text)
            debug_logs.append(f"└ JSON 파싱 성공 (데이터 갯수: {len(data)})")
        except Exception as e:
            debug_logs.append(f"└ ❌ JSON 파싱 실패: {e}")
            return {"current": 0.0, "30m_diff": 0.0, "1h_diff": 0.0, "error": "JSON 파싱 에러"}
        
        if len(data) <= 1:
            debug_logs.append(f"└ ❌ 유효한 데이터가 없음 (배열이 비어있음)")
            return {"current": 0.0, "30m_diff": 0.0, "1h_diff": 0.0, "error": "장 시작 전이거나 데이터 없음"}
            
        records = data[1:]
        current_price = float(records[-1][4])
        debug_logs.append(f"└ 최근 추출시간: {records[-1][0]}, 현재가: {current_price}")
        
        target_30m = (now - datetime.timedelta(minutes=30)).strftime("%Y%m%d%H%M")
        target_1h = (now - datetime.timedelta(minutes=60)).strftime("%Y%m%d%H%M")
        
        price_30m = current_price
        price_1h = current_price
        
        for row in reversed(records):
            time_str = str(row[0])
            if time_str <= target_30m and price_30m == current_price:
                price_30m = float(row[4])
            if time_str <= target_1h and price_1h == current_price:
                price_1h = float(row[4])
                
        debug_logs.append(f"└ 30분전 매칭가: {price_30m}, 1시간전 매칭가: {price_1h}")
                
        return {
            "current": current_price,
            "30m_diff": round(current_price - price_30m, 2),
            "1h_diff": round(current_price - price_1h, 2),
            "error": ""
        }
    except Exception as e:
        debug_logs.append(f"└ 💥 치명적 에러 발생: {e}")
        return {"current": 0.0, "30m_diff": 0.0, "1h_diff": 0.0, "error": f"API 에러: {e}"}

def get_program_data():
    debug_logs.append(f"\n🔍 [프로그램 매매 추적]")
    url_program = "https://finance.naver.com/sise/sise_program.naver"
    kospi_val = 0
    kosdaq_val = 0
    error_msg = ""
    
    try:
        session = requests.Session()
        session.get("https://finance.naver.com/", headers=HEADERS, timeout=5)
        
        res = session.get(url_program, headers=HEADERS, timeout=5)
        res.encoding = 'euc-kr'
        debug_logs.append(f"└ 상태코드: {res.status_code}")
        
        if "error_content" in res.text:
            debug_logs.append("└ ❌ 방화벽 에러 페이지(error_content) 감지됨")
            return {"KOSPI": 0, "KOSDAQ": 0, "error": "WAF 강력 차단"}
            
        soup = BeautifulSoup(res.text, 'html.parser')
        tables = soup.find_all('table')
        debug_logs.append(f"└ 페이지 내 테이블 수: {len(tables)}")
        
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
            debug_logs.append(f"└ 파싱 완료: 코스피 {kospi_val}억, 코스닥 {kosdaq_val}억")
        else:
            debug_logs.append("└ ❌ 테이블은 찾았으나 '거래소/코스닥' 단어를 못 찾음")
            
    except Exception as e:
        debug_logs.append(f"└ 💥 치명적 에러 발생: {e}")
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
    
    # 💡 하단에 CCTV 로그 추가
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