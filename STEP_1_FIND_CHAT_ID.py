# -*- coding: utf-8 -*-
"""
텔레그램 CHAT_ID 찾기 도우미

사용법:
1. 텔레그램에서 내 봇에게 아무 말이나 보냅니다. 예: 안녕
2. 아래 코드의 YOUR_BOT_TOKEN_HERE 부분에 봇 토큰을 넣습니다.
3. 실행하면 chat_id가 표시됩니다.
"""

import requests

BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
r = requests.get(url, timeout=20)
print(r.text)
