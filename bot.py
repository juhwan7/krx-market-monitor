import os
import datetime
import urllib.request
import urllib.error
import yfinance as yf
from bs4 import BeautifulSoup
import pandas as pd
from io import StringIO
import traceback
import re

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

def parse_number(text):
    cleaned = text.replace(',', '').strip()
    if not cleaned: return 0
    try:
        # 플러스(+) 기호가 붙어있는 경우 처리
        return int(cleaned.replace('+', ''))
    except:
        return 0

def get_investor_trend_time(biztype, name):
    records = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
        'Referer': 'https://www.google.com/'
    }
    error_logs = []

    try:
        for page in range(1, 7):
            url = f"https://finance.naver.com/sise/investorDealTrendTime.naver?biztype={biztype}&page={page}"
            req = urllib.request.Request(url, headers=headers)
            try:
                response = urllib.request.urlopen(req, timeout=10)
                html = response.read().decode('euc-kr', errors='ignore')
            except Exception as e:
                error_logs.append(f"[{page}p 접속실패]: {e}")
                continue

            # 💡 전략 1: lxml 파서로 지저분한 태그 강제 돌파
            soup = BeautifulSoup(html, 'lxml')
            found_in_bs4 = False
            for tr in soup.find_all('tr'):
                tds = tr.find_all('td')
                if len(tds) >= 4:
                    t_str = tds[0].get_text(strip=True)
                    if re.match(r'^\d{2}:\d{2}$', t_str):
                        records.append({
                            'time': t_str,
                            'retail': parse_number(tds[1].get_text(strip=True)),
                            'foreigner': parse_number(tds[2].get_text(strip=True)),
                            'institution': parse_number(tds[3].get_text(strip=True))
                        })
                        found_in_bs4 = True
            
            # 💡 전략 2: 만약 bs4가 실패하면 Pandas 불도저 가동
            if not found_in_bs4:
                try:
                    dfs = pd.read_html(StringIO(html), thousands=',')
                    for df in dfs:
                        if df.shape[1] >= 4:
                            for _, row in df.iterrows():
                                t_val = str(row.iloc[0]).strip()
                                if re.match(r'^\d{2}:\d{2}$', t_val):
                                    records.append({
                                        'time': t_val,
                                        'retail': parse_number(str(row.iloc[1])),
                                        'foreigner': parse_number(str(row.iloc[2])),
                                        'institution': parse_number(str(row.iloc[3]))
                                    })
                except Exception as e:
                    error_logs.append(f"[{page}p pandas 에러]: {e}")

        if not records:
            return None, f"[{name}] 모든 파싱 전략 실패\n로그: {'; '.join(error_logs[:3])}"

        # 데이터 정렬 및 시간 비교
        records.sort(key=lambda x: x['time'], reverse=True)
        current = records[0]
        now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
        t30 = (now - datetime.timedelta(minutes=30)).strftime("%H:%M")
        t60 = (now - datetime.timedelta(minutes=60)).strftime("%H:%M")

        past_30m = next((r for r in records if r['time'] <= t30), records[-1])
        past_1h = next((r for r in records if r['time'] <= t60), records[-1])

        return {
            "current": current,
            "diff_30m": {k: current[k] - past_30m[k] for k in ['retail', 'foreigner', 'institution']},
            "diff_1h": {k: current[k] - past_1h[k] for k in ['retail', 'foreigner', 'institution']}
        }, ""

    except Exception as e:
        return None, f"[{name}] 치명적 오류:\n{str(e)[:100]}"

def format_message():
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    time_str = now.strftime("%Y-%m-%d %H:%M 기준")
    
    kospi = get_yf_data('^KS11', 'KOSPI')
    kosdaq = get_yf_data('^KQ11', 'KOSDAQ')
    
    # 매크로 지표
    usdkrw = get_yf_data('KRW=X', '환율')
    nq = get_yf_data('NQ=F', '나스닥선물')
    vix = get_yf_data('^VIX', 'VIX')
    gold = get_yf_data('GC=F', '금')
    oil = get_yf_data('CL=F', '원유')
    
    # 수급 (0:코스피, 1:코스닥, 2:선물)
    i_kp, e_kp = get_investor_trend_time("0", "코스피")
    i_kd, e_kd = get_investor_trend_time("1", "코스닥")
    i_ft, e_ft = get_investor_trend_time("2", "선물")
    
    msg = f"📊 *시장 변동성 및 매크로 브리핑* ({time_str})\n\n"
    msg += "📉 *국내 지수 변동* (현재가 / 30분 / 1시간)\n"
    msg += f"- 코스피: `{kospi['current']:,.2f}` (30분: `{kospi['30m_diff']:+.2f}` / 1시간: `{kospi['1h_diff']:+.2f}`)\n"
    msg += f"- 코스닥: `{kosdaq['current']:,.2f}` (30분: `{kosdaq['30m_diff']:+.2f}` / 1시간: `{kosdaq['1h_diff']:+.2f}`)\n\n"
    
    msg += "👥 *투자자별 수급 흐름* (현재누적 / 30분변동 / 1시간변동)\n"
    for name, data in [("코스피", i_kp), ("코스닥", i_kd), ("선  물", i_ft)]:
        msg += f"*[ {name} ]*\n"
        if data:
            u = "계약" if name == "선  물" else "억"
            c, d3, d6 = data['current'], data['diff_30m'], data['diff_1h']
            msg += f"- 개인: `{c['retail']:+,d}{u}` (`{d3['retail']:+,d}` / `{d6['retail']:+,d}`)\n"
            msg += f"- 외인: `{c['foreigner']:+,d}{u}` (`{d3['foreigner']:+,d}` / `{d6['foreigner']:+,d}`)\n"
            msg += f"- 기관: `{c['institution']:+,d}{u}` (`{d3['institution']:+,d}` / `{d6['institution']:+,d}`)\n"
        else:
            msg += f"- 수집 실패 (로그: {name})\n"
        msg += "\n"
        
    msg += "🌍 *글로벌 지표* (현재가 / 30분 변동)\n"
    msg += f"- 환율: `{usdkrw['current']:,.2f}원` ({usdkrw['30m_diff']:+.2f})\n"
    msg += f"- 나스닥선물: `{nq['current']:,.2f}` ({nq['30m_diff']:+.2f})\n"
    msg += f"- VIX: `{vix['current']:,.2f}` ({vix['30m_diff']:+.2f})\n"
    msg += f"- 금: `{gold['current']:,.2f}$` ({gold['30m_diff']:+.2f})\n"
    msg += f"- 원유: `{oil['current']:,.2f}$` ({oil['30m_diff']:+.2f})\n"
    
    errs = [e for e in [e_kp, e_kd, e_ft] if e]
    if errs:
        msg += "\nㅡㅡㅡㅡㅡㅡㅡㅡㅡㅡ\n🛠️ *디버깅 로그*\n```text\n" + "\n".join(errs) + "\n```"
    return msg

def send_telegram(message):
    import requests
    requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                  data={'chat_id': CHAT_ID, 'text': message, 'parse_mode': 'Markdown'})

if __name__ == "__main__":
    send_telegram(format_message())