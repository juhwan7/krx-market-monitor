import os
import datetime
import requests
import yfinance as yf
import pandas as pd

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

def get_investor_data(market_code):
    """
    1안: 네이버 내부 데이터 API 직접 호출 (웹페이지보다 차단이 덜함)
    2안: Daum 금융 API (해외 IP 차단 없음)
    """
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    # 네이버 내부 API 경로 (KOSPI: '0', KOSDAQ: '1')
    biz_type = '0' if market_code == 'KOSPI' else '1'
    
    # 1안: 네이버 내부 API 시도
    try:
        url = f"https://finance.naver.com/sise/investorDealTrendTime.naver?biztype={biz_type}&page=1"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
        res = requests.get(url, headers=headers, timeout=5)
        dfs = pd.read_html(res.text, thousands=',')
        df = dfs[0].dropna()
        
        # 시간, 개인, 외인, 기관 컬럼 추출
        data = df.iloc[:, [0, 1, 2, 3]]
        data.columns = ['time', 'retail', 'foreign', 'inst']
        
        current = data.iloc[0]
        p30 = data.iloc[min(len(data)-1, 3)] # 약 30분 전
        p60 = data.iloc[min(len(data)-1, 6)] # 약 60분 전
        
        return {
            'cur': current,
            'd30': {'r': current['retail']-p30['retail'], 'f': current['foreign']-p30['foreign'], 'i': current['inst']-p60['inst']},
            'd60': {'r': current['retail']-p60['retail'], 'f': current['foreign']-p60['foreign'], 'i': current['inst']-p60['inst']}
        }
    except:
        # 2안: Daum 금융 (네이버 실패 시 백업)
        try:
            url = f"https://finance.daum.net/api/investor/days?symbol={'KOSPI' if market_code == 'KOSPI' else 'KOSDAQ'}"
            headers = {'Referer': 'https://finance.daum.net', 'User-Agent': 'Mozilla/5.0'}
            res = requests.get(url, headers=headers, timeout=5).json()
            # Daum은 일별 데이터 중심이라 시간별 변동은 지수 변동성으로 보정 로직 추가 가능
            return None
        except:
            return None

def get_market_indices():
    tickers = {'코스피': '^KS11', '코스닥': '^KQ11', '환율': 'KRW=X', '나스닥선물': 'NQ=F'}
    res = {}
    for name, tk in tickers.items():
        try:
            df = yf.download(tk, period="1d", interval="1m", progress=False)
            cur = float(df['Close'].iloc[-1])
            prev = float(df['Close'].iloc[-31]) if len(df) > 30 else float(df['Open'].iloc[0])
            res[name] = {"cur": cur, "diff": round(cur - prev, 2)}
        except: res[name] = {"cur": 0, "diff": 0}
    return res

def format_message():
    m = get_market_indices()
    kp_inv = get_investor_data('KOSPI')
    kd_inv = get_investor_data('KOSDAQ')
    
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    msg = f"📊 *실시간 수급 변동 브리핑* ({now.strftime('%H:%M')})\n\n"
    
    msg += "📉 *지수 현황*\n"
    msg += f"- 코스피: `{m['코스피']['cur']:,.2f}` ({m['코스피']['diff']:+.2f})\n"
    msg += f"- 코스닥: `{m['코스닥']['cur']:,.2f}` ({m['코스닥']['diff']:+.2f})\n\n"

    msg += "👥 *투자자 수급 (단위: 억 / 30분변동 / 1시간변동)*\n"
    for name, data in [("코스피", kp_inv), ("코스닥", kd_inv)]:
        msg += f"*[ {name} ]*\n"
        if data:
            c, d3, d6 = data['cur'], data['d30'], data['d60']
            msg += f"- 개인: `{c['retail']:+d}` (`{d3['r']:+d}` / `{d6['r']:+d}`)\n"
            msg += f"- 외인: `{c['foreign']:+d}` (`{d3['f']:+d}` / `{d6['f']:+d}`)\n"
            msg += f"- 기관: `{c['inst']:+d}` (`{d3['i']:+d}` / `{d6['i']:+d}`)\n"
        else:
            msg += "- 수급 데이터 일시적 차단 (백업 대기 중)\n"
        msg += "\n"

    msg += "🌍 *글로벌 매크로*\n"
    msg += f"- 환율: `{m['환율']['cur']:,.1f}원` | 나스닥선물: `{m['나스닥선물']['cur']:,.1f}`"
    
    return msg

if __name__ == "__main__":
    from requests import post
    post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
         data={'chat_id': CHAT_ID, 'text': format_message(), 'parse_mode': 'Markdown'})