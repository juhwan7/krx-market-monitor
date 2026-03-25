import requests
import os

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://finance.naver.com/"
}

def run_debug():
    url = "https://finance.naver.com/sise/sise_index_time.naver?code=KOSPI&page=1"
    
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.encoding = 'euc-kr'
        
        msg = "🚨 네이버 접속 디버깅 리포트 🚨\n\n"
        msg += f"✅ 상태 코드: {res.status_code}\n\n"
        msg += "📄 응답 텍스트 앞부분:\n"
        msg += res.text[:300]
        
    except Exception as e:
        msg = f"💥 요청 실패 에러:\n{e}"

    # 텔레그램으로 쏘기
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={'chat_id': CHAT_ID, 'text': msg}
    )

if __name__ == "__main__":
    run_debug()