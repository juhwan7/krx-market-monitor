import os
import datetime
import urllib.request
import yfinance as yf
import pandas as pd
from io import StringIO
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
    """pandas의 read_html을 이용해 네이버의 지저분한 HTML 구조를 무시하고 표만 뜯어옵니다."""
    records = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://finance.naver.com/'
    }

    try:
        # 1~8페이지 (약 1시간 20분 분량 넉넉하게 스캔)
        for page in range(1, 9):
            url = f"https://finance.naver.com/sise/investorDealTrendTime.naver?biztype={biztype}&page={page}"
            req = urllib.request.Request(url, headers=headers)
            
            response = urllib.request.urlopen(req, timeout=5)
            html = response.read().decode('euc-kr', errors='ignore')
            
            if "error_content" in html or "접근이 제한되었습니다" in html:
                return None, f"[{name}] WAF 차단됨\n미리보기: {html[:150]}"
                
            try:
                # 💡 핵심: pandas 불도저 파싱 (콤마 자동 제거)
                dfs = pd.read_html(StringIO(html), thousands=',')
                df = dfs[0]
                
                # '시간' 컬럼이 있는 정상적인 표인지 확인
                if '시간' in df.columns:
                    df = df.dropna(subset=['시간']) # 빈 줄(NaN) 제거
                    for _, row in df.iterrows():
                        time_str = str(row['시간'])
                        if ':' in time_str:
                            # 데이터가 비어있을 경우 0으로 처리하는 안전장치
                            retail = int(float(row['개인'])) if pd.notna(row['개인']) else 0
                            foreigner = int(float(row['외국인'])) if pd.notna(row['외국인']) else 0
                            institution = int(float(row['기관계'])) if pd.notna(row['기관계']) else 0
                            
                            records.append({
                                'time': time_str,
                                'retail': retail,
                                'foreigner': foreigner,
                                'institution': institution
                            })
            except ValueError:
                pass # 해당 페이지에 표가 없으면 무시하고 다음 페이지로
        
        if not records:
            return None, f"[{name}] 표 추출 실패 (데이터 없음)\n미리보기: {html[:150]}"

        # 목표 시간 계산 (KST 기준 30분 전, 1시간 전)
        now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
        target_30m = (now - datetime.timedelta(minutes=30)).strftime("%H:%M")
        target_1h = (now - datetime.timedelta(minutes=60)).strftime("%H:%M")

        # 최신 데이터를 기준으로 과거 데이터를 탐색
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