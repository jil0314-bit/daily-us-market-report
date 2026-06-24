# -*- coding: utf-8 -*-
"""
매일 아침 텔레그램 시장 브리핑 자동 발송 코드

필요한 비밀값:
1) TELEGRAM_BOT_TOKEN : 텔레그램 봇 토큰
2) TELEGRAM_CHAT_ID   : 텔레그램 받을 방/채팅 ID

GitHub Actions에서 자동 실행됩니다.
"""

import os
import sys
import math
import html
import time
import datetime as dt
from urllib.parse import quote_plus

import requests
import feedparser
import yfinance as yf


KST = dt.timezone(dt.timedelta(hours=9))


# =========================
# 1. 기본 설정
# =========================

NEWS_QUERIES = [
    ("미국 증시와 한국 영향", "미국 증시 한국 증시 영향 나스닥 S&P500 반도체"),
    ("국내 급등주·테마주", "국내 증시 급등주 테마주 특징주"),
    ("경제지표·금리·환율", "미국 금리 환율 달러 원 경제지표 CPI PCE 고용"),
    ("AI·반도체·기술 뉴스", "AI 반도체 엔비디아 삼성전자 SK하이닉스 HBM"),
    ("오늘 한국시장 체크", "한국 증시 오늘 전망 외국인 기관 수급 코스피 코스닥"),
]

MARKET_TICKERS = {
    "S&P500": "^GSPC",
    "나스닥": "^IXIC",
    "다우": "^DJI",
    "필라델피아반도체": "^SOX",
    "VIX": "^VIX",
    "달러/원": "KRW=X",
    "WTI유가": "CL=F",
    "금": "GC=F",
    "한국ETF(EWY)": "EWY",
}


# =========================
# 2. 유틸 함수
# =========================

def now_kst() -> dt.datetime:
    return dt.datetime.now(KST)


def safe_float(x):
    try:
        if x is None:
            return None
        if isinstance(x, float) and math.isnan(x):
            return None
        return float(x)
    except Exception:
        return None


def fmt_pct(x):
    if x is None:
        return "N/A"
    sign = "+" if x >= 0 else ""
    return f"{sign}{x:.2f}%"


def clean_text(s: str, max_len: int = 90) -> str:
    s = html.unescape(str(s or ""))
    s = s.replace("\n", " ").replace("\r", " ").strip()
    while "  " in s:
        s = s.replace("  ", " ")
    if len(s) > max_len:
        s = s[:max_len - 1] + "…"
    return s


def get_market_snapshot():
    """주요 지수/환율/원자재 등락률 가져오기"""
    results = []
    for name, ticker in MARKET_TICKERS.items():
        try:
            data = yf.download(
                ticker,
                period="5d",
                interval="1d",
                progress=False,
                auto_adjust=False,
                threads=False,
            )
            if data is None or data.empty or "Close" not in data:
                results.append((name, "N/A", "N/A"))
                continue

            closes = data["Close"].dropna()
            if len(closes) < 2:
                last = safe_float(closes.iloc[-1]) if len(closes) else None
                results.append((name, f"{last:.2f}" if last else "N/A", "N/A"))
                continue

            last = safe_float(closes.iloc[-1])
            prev = safe_float(closes.iloc[-2])
            pct = ((last - prev) / prev * 100) if last and prev else None

            # 달러/원, VIX 등은 숫자 자리수 간단 조정
            if name == "달러/원":
                last_txt = f"{last:,.2f}원" if last else "N/A"
            elif name in ["VIX"]:
                last_txt = f"{last:.2f}" if last else "N/A"
            else:
                last_txt = f"{last:,.2f}" if last else "N/A"

            results.append((name, last_txt, fmt_pct(pct)))
        except Exception as e:
            results.append((name, "N/A", "N/A"))
    return results


def google_news_rss(query: str, max_items: int = 3):
    """Google News RSS에서 뉴스 제목 가져오기"""
    url = (
        "https://news.google.com/rss/search?q="
        + quote_plus(query)
        + "&hl=ko&gl=KR&ceid=KR:ko"
    )
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries[:max_items]:
        title = clean_text(entry.get("title", ""), 110)
        source = ""
        if hasattr(entry, "source") and entry.source:
            source = clean_text(entry.source.get("title", ""), 30)
        published = clean_text(entry.get("published", ""), 30)
        items.append({
            "title": title,
            "source": source,
            "published": published,
        })
    return items


def one_line_trading_view(category: str, title: str) -> str:
    """뉴스 제목을 기준으로 단순 매매 해석 생성"""
    t = title.lower()

    if any(k.lower() in t for k in ["엔비디아", "nvidia", "ai", "hbm", "반도체", "마이크론"]):
        return "반도체·AI 수급 확인, 삼성전자·SK하이닉스·HBM/장비주 관심."
    if any(k.lower() in t for k in ["금리", "fed", "fomc", "파월", "국채"]):
        return "금리 부담 뉴스면 성장주 추격매수 자제, 지수 눌림 후 반등만 확인."
    if any(k.lower() in t for k in ["환율", "달러", "원화"]):
        return "달러/원 상승이면 외국인 수급 약화 가능성, 대형주 매수는 신중."
    if any(k.lower() in t for k in ["유가", "wti", "원유"]):
        return "유가 상승이면 정유·조선·방산 일부 체크, 항공·화학은 부담."
    if any(k.lower() in t for k in ["급등", "특징주", "상한가", "테마"]):
        return "장초반 거래대금 상위와 대장주 1~3위만 추려서 눌림 재돌파 확인."
    if "미국 증시" in category:
        return "미국 지수 방향보다 반도체·나스닥 강약을 한국 장초반 기준으로 활용."
    return "장초반 거래량·양봉·VWAP 위 여부 확인 후 추격매수는 제한."


def get_news_blocks():
    """관심 주제별 뉴스 5개 만들기"""
    selected = []
    seen_titles = set()

    for category, query in NEWS_QUERIES:
        items = google_news_rss(query, max_items=5)
        for item in items:
            title = item["title"]
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            selected.append({
                "category": category,
                "title": title,
                "source": item.get("source", ""),
                "view": one_line_trading_view(category, title),
            })
            break

    # 혹시 5개가 안 차면 추가 검색으로 보충
    if len(selected) < 5:
        for category, query in NEWS_QUERIES:
            for item in google_news_rss(query, max_items=5):
                title = item["title"]
                if title and title not in seen_titles:
                    seen_titles.add(title)
                    selected.append({
                        "category": category,
                        "title": title,
                        "source": item.get("source", ""),
                        "view": one_line_trading_view(category, title),
                    })
                    if len(selected) >= 5:
                        break
            if len(selected) >= 5:
                break

    return selected[:5]


def make_report():
    today = now_kst().strftime("%Y-%m-%d %H:%M")
    market = get_market_snapshot()
    news = get_news_blocks()

    # 시장 분위기 간단 판단
    market_dict = {name: pct for name, _, pct in market}
    nasdaq_txt = market_dict.get("나스닥", "N/A")
    sox_txt = market_dict.get("필라델피아반도체", "N/A")
    vix_txt = market_dict.get("VIX", "N/A")

    lines = []
    lines.append(f"📌 <b>아침 매매 브리핑</b>")
    lines.append(f"기준: {today} KST")
    lines.append("")
    lines.append("✅ <b>해외시장 핵심 수치</b>")
    for name, last, pct in market:
        lines.append(f"- {name}: {last} / {pct}")

    lines.append("")
    lines.append("📰 <b>뉴스 5개 + 한 줄 매매 해석</b>")

    if not news:
        lines.append("뉴스를 가져오지 못했습니다. GitHub Actions 로그를 확인하세요.")
    else:
        for i, item in enumerate(news, 1):
            source = f" ({item['source']})" if item.get("source") else ""
            lines.append("")
            lines.append(f"{i}. <b>[{item['category']}]</b>")
            lines.append(f"   {html.escape(item['title'])}{html.escape(source)}")
            lines.append(f"   → {html.escape(item['view'])}")

    lines.append("")
    lines.append("🎯 <b>오늘 장초반 체크</b>")
    lines.append("- 미국 나스닥·반도체가 강하면: AI/HBM/반도체 장비주 먼저 확인")
    lines.append("- 환율이 급등하면: 외국인 수급 약화 가능성, 추격매수 자제")
    lines.append("- 국내 급등주는: 거래대금 상위 + 양봉 + VWAP 위 + 눌림 재돌파만 관심")
    lines.append("- 음봉·거래량 감소 없는 급등주는: 상투 위험으로 제외")
    lines.append("")
    lines.append("※ 자동 브리핑입니다. 실제 매수 전에는 반드시 현재가·거래량·뉴스 진위를 확인하세요.")

    msg = "\n".join(lines)

    # 텔레그램 메시지 길이 제한 대비
    if len(msg) > 3900:
        msg = msg[:3890] + "\n…"
    return msg


def send_telegram(message: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN 환경변수가 없습니다.")
    if not chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID 환경변수가 없습니다.")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    r = requests.post(url, json=payload, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"텔레그램 발송 실패: {r.status_code} / {r.text}")
    return r.json()


def main():
    msg = make_report()
    print(msg.replace("<b>", "").replace("</b>", ""))
    result = send_telegram(msg)
    print("Telegram send result:", result.get("ok"))


if __name__ == "__main__":
    main()
