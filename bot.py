import os
import datetime
import urllib.request
import yfinance as yf
from bs4 import BeautifulSoup
import traceback

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def get_yf_data(ticker, name):
    try:
        df = yf.download(ticker, period="1d", interval="1m", progress=False)
        if df.empty:
            return {"current": 0.0, "30m_diff": 0.0, "1h_diff": 0.0, "error": "데이터 없음"}
            
        closes = df['Close'].dropna().values
        current_price = float(closes[-1])
        
        idx_30m = -31 if len(closes) > 30 else 0
        idx_1h = -61 if len(closes) > 60 else 0
        
        return {
            "current": current_price,
            "30m_diff": round(current_price - float(closes[idx_30m]), 2),
            "1h_diff": round(current_price - float(closes[idx_1h]), 2),
            "error": ""
        }
    except Exception as e:
        return {"current": 0.0, "30m_diff": 0.0, "1h_diff": 0.0, "error": str(e)}

def get_investor_trend_time(biztype, name):
    """네이버 시간별 수급 동향을 가져와 현재/30분/1시간 전을 비교합니다."""
    # biztype: 0(코스피), 1(코스닥), 2(선물)
    records = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Referer': 'https://finance.naver.com/'
    }

    try:
        # 1~6페이지 (약 1.5시간 분량) 스캔
        for page in range(1, 7):
            url = f"https://finance.naver.com/sise/investorDealTrendTime.naver?biztype={biztype}&page={page}"
            req = urllib.request.Request(url, headers=headers)
            
            response = urllib.request.urlopen(req, timeout=5)
            html = response.read().decode('euc-kr', errors='ignore')
            
            if "error_content" in html or "접근이 제한되었습니다" in html:
                return None, f"[{name}] WAF 차단됨 (에러페이지 반환)\n미리보기: {html[:150]}"
                
            soup = BeautifulSoup(html, 'html.parser')
            
            for tr in soup.find_all('tr'):
                tds = tr.find_all('td')
                if len(tds) >= 4:
                    time_str = tds[0].text.strip()
                    if ':' in time_str:
                        try:
                            # 개인, 외국인, 기관 순매수 추출
                            retail = int(tds[1].text.strip().replace(',', ''))
                            foreigner = int(tds[2].text.strip().replace(',', ''))
                            institution = int(tds[3].text.strip().replace(',', ''))
                            records.append({
                                'time': time_str,
                                'retail': retail,
                                'foreigner': foreigner,
                                'institution': institution
                            })
                        except:
                            pass
        
        if not records:
            return None, f"[{name}] 데이터 파싱 실패 (구조 다름)\n미리보기: {html[:150]}"

        # 시간 매칭
        now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
        target_30m = (now - datetime.timedelta(minutes=30)).strftime("%H:%M")
        target_1h = (now - datetime.timedelta(minutes=60)).strftime("%H:%M")

        current = records[0]
        
        past_30m = current
        for r in records:
            if r['time'] <= target_30m:
                past_30m = r
                break
                
        past_1h = records[-1] if len(records) > 0 else current
        for r in records:
            if r['time'] <= target_1h:
                past_1h = r
                break

        return {
            "current": current,
            "diff_30m": {
                "retail": current['retail'] - past_30m['retail'],
                "foreigner": current['foreigner'] - past_30m['foreigner'],
                "institution": current['institution'] - past_30m['institution']
            },
            "diff_1h": {
                "retail": current['retail'] - past_1h['retail'],
                "foreigner": current['foreigner'] - past_1h['foreigner'],
                "institution": current['institution'] - past_1h['institution']
            }
        }, ""

    except Exception as e:
        error_trace = traceback.format_exc()
        return None, f"[{name}] 파이썬 실행 오류:\n{error_trace[:200]}"

def format_message():
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    time_str = now.strftime("%Y-%m-%d %H:%M 기준")
    
    kospi = get_yf_data('^KS11', 'KOSPI')
    kosdaq = get_yf_data('^KQ11', 'KOSDAQ')
    
    usdkrw = get_yf_data('KRW=X', '원/달러 환율')
    nq_fut = get_yf_data('NQ=F', '나스닥 100 선물')
    vix = get_yf_data('^VIX', 'VIX (공포지수)')
    
    gold = get_yf_data('GC=F', '금 선물')
    oil = get_yf_data('CL=F', 'WTI 원유 선물')
    copper = get_yf_data('HG=F', '구리 선물')
    
    # 수급 데이터 (0:코스피, 1:코스닥, 2:선물)
    inv_kospi, err_kospi = get_investor_trend_time("0", "코스피")
    inv_kosdaq, err_kosdaq = get_investor_trend_time("1", "코스닥")
    inv_fut, err_fut = get_investor_trend_time("2", "선물")
    
    msg = f"📊 *시장 변동성 및 매크로 브리핑* ({time_str})\n\n"
    
    msg += "📉 *국내 지수 변동* (현재가 / 30분 / 1시간)\n"
    msg += f"- 코스피: `{kospi['current']:,.2f}` (30분: `{kospi['30m_diff']:+.2f}` / 1시간: `{kospi['1h_diff']:+.2f}`)\n"
    msg += f"- 코스닥: `{kosdaq['current']:,.2f}` (30분: `{kosdaq['30m_diff']:+.2f}` / 1시간: `{kosdaq['1h_diff']:+.2f}`)\n\n"
    
    msg += "👥 *투자자별 수급 흐름* (현재누적 / 30분변동 / 1시간변동)\n"
    
    for name, data in [("코스피", inv_kospi), ("코스닥", inv_kosdaq), ("선  물", inv_fut)]:
        msg += f"*[ {name} ]*\n"
        if data:
            unit = "계약" if name == "선  물" else "억"
            c = data['current']
            d30 = data['diff_30m']
            d1h = data['diff_1h']
            
            msg += f"- 개인: `{c['retail']:+,d}{unit}` (`{d30['retail']:+,d}` / `{d1h['retail']:+,d}`)\n"
            msg += f"- 외인: `{c['foreigner']:+,d}{unit}` (`{d30['foreigner']:+,d}` / `{d1h['foreigner']:+,d}`)\n"
            msg += f"- 기관: `{c['institution']:+,d}{unit}` (`{d30['institution']:+,d}` / `{d1h['institution']:+,d}`)\n"
        else:
            msg += f"- 데이터 수집 실패 (하단 디버깅 로그 참조)\n"
        msg += "\n"
        
    msg += "🌍 *글로벌 매크로 지표* (현재가 / 30분 변동)\n"
    msg += f"- 환율(원/달러): `{usdkrw['current']:,.2f}원` ({usdkrw['30m_diff']:+.2f}원)\n"
    msg += f"- 나스닥 선물: `{nq_fut['current']:,.2f}` ({nq_fut['30m_diff']:+.2f})\n"
    msg += f"- VIX(공포지수): `{vix['current']:,.2f}` ({vix['30m_diff']:+.2f})\n\n"

    msg += "🛢️ *주요 원자재 변동* (현재가 / 30분 변동)\n"
    msg += f"- 금(Gold): `{gold['current']:,.2f}$` ({gold['30m_diff']:+.2f}$)\n"
    msg += f"- WTI 원유: `{oil['current']:,.2f}$` ({oil['30m_diff']:+.2f}$)\n"
    msg += f"- 구리(Copper): `{copper['current']:,.4f}$` ({copper['30m_diff']:+.4f}$)\n"
    
    # 상세 에러 로그 섹션
    raw_errors = [e for e in [err_kospi, err_kosdaq, err_fut] if e]
    if raw_errors:
        msg += "\nㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ\n"
        msg += "🛠️ *상세 오류 디버깅 (Raw Error)*\n```text\n"
        msg += "\n\n".join(raw_errors)
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