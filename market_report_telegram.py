import os
import sys
import time
import json
import textwrap
import requests
from datetime import datetime, timezone, timedelta

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()

KST = timezone(timedelta(hours=9))
TODAY_KST = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")

PROMPT = f"""
You are a professional Korea-market pre-open strategist.
Current Seoul time: {TODAY_KST}

Write a concise Korean morning report for a Korean stock investor.
Target length: one page; maximum two pages.

Required sections:
1) One-line conclusion: Risk-on / Neutral / Risk-off for today's Korean market.
2) US market summary: Dow, S&P 500, Nasdaq, Russell 2000, Philadelphia Semiconductor Index.
3) US sector map: strongest and weakest sectors, with reason.
4) Unusual stocks: large gainers and large losers that may affect Korean stocks.
5) Macro: WTI/Brent oil, USD/KRW, Dollar Index, US 10Y yield, gold, copper, lithium or battery-related commodities if meaningful.
6) Korea-linked sectors:
   - Semiconductors: NVIDIA, AMD, Intel, Broadcom, Micron, TSMC, ASML, Applied Materials, Lam Research, Marvell, Super Micro if relevant.
   - Bio/Pharma: major US bio/pharma movers and policy/news impact.
   - Secondary battery/EV: Tesla, battery metals, US EV/battery policy, key suppliers.
   - Optical communication/AI infrastructure: Broadcom, Marvell, Coherent, Lumentum, Arista, Cisco if relevant.
   - Nuclear/power/ESS/grid: uranium, nuclear, utilities, power equipment, ESS, grid news.
   - Shipbuilding/defense/industrial: oil, LNG, defense, shipping, industrial capex.
   - MLCC/electronics parts: Apple, Tesla, auto/electronics demand indicators.
   - Quantum/robotics/automation: only if there is meaningful news or stock movement.
7) Important remarks: US President, Fed, Treasury, major CEOs, large institutions, or policymakers. Include only market-relevant remarks.
8) Today's Korea market checklist:
   - Sectors to watch
   - Sectors to be careful with
   - Expected market direction: 상승 / 중립 / 하락

Style rules:
- Korean language.
- Very clear headings.
- No long essay.
- Mention uncertainty when data is incomplete.
- Do not fabricate numbers. If exact data is unavailable, say '확인 필요'.
- Focus on actionable pre-market implications for KOSPI/KOSDAQ.
""".strip()


def require_env():
    missing = []
    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_CHAT_ID:
        missing.append("TELEGRAM_CHAT_ID")
    if missing:
        raise RuntimeError("Missing environment variables: " + ", ".join(missing))


def extract_output_text(data):
    if isinstance(data, dict):
        if data.get("output_text"):
            return data["output_text"]
        parts = []
        for item in data.get("output", []) or []:
            for c in item.get("content", []) or []:
                if c.get("type") in ("output_text", "text") and c.get("text"):
                    parts.append(c["text"])
        if parts:
            return "\n".join(parts)
    return json.dumps(data, ensure_ascii=False, indent=2)[:3500]


def call_openai():
    url = "https://api.openai.com/v1/responses"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_MODEL,
        "tools": [{"type": "web_search_preview"}],
        "input": PROMPT,
        "temperature": 0.2,
        "max_output_tokens": 3500,
    }
    r = requests.post(url, headers=headers, json=payload, timeout=120)

    # Fallback: if the selected model/tool rejects web search, try without web search.
    if r.status_code >= 400:
        fallback = dict(payload)
        fallback.pop("tools", None)
        r2 = requests.post(url, headers=headers, json=fallback, timeout=120)
        if r2.status_code >= 400:
            raise RuntimeError(f"OpenAI error: {r.status_code} {r.text[:1000]} | fallback: {r2.status_code} {r2.text[:1000]}")
        return extract_output_text(r2.json())

    return extract_output_text(r.json())


def split_text(text, limit=3900):
    text = text.strip()
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        chunk = text[:limit]
        cut = max(chunk.rfind("\n\n"), chunk.rfind("\n"), chunk.rfind(". "))
        if cut < limit * 0.5:
            cut = limit
        chunks.append(text[:cut].strip())
        text = text[cut:].strip()
    return chunks


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    chunks = split_text(text)
    total = len(chunks)
    for i, chunk in enumerate(chunks, start=1):
        prefix = ""
        if total > 1:
            prefix = f"[Part {i}/{total}]\n"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": prefix + chunk,
            "disable_web_page_preview": True,
        }
        r = requests.post(url, data=payload, timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"Telegram error: {r.status_code} {r.text[:1000]}")
        time.sleep(1)


def main():
    require_env()
    report = call_openai()
    title = f"[미국시장 장전 리포트] {datetime.now(KST).strftime('%Y-%m-%d %H:%M')}"
    final_text = title + "\n\n" + report
    send_telegram(final_text)
    print("SUCCESS: report sent to Telegram")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        err = "ERROR: " + str(e)
        print(err, file=sys.stderr)
        # Try to notify Telegram if possible.
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            try:
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                    data={"chat_id": TELEGRAM_CHAT_ID, "text": err[:3500]},
                    timeout=30,
                )
            except Exception:
                pass
        sys.exit(1)
