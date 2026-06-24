# -*- coding: utf-8 -*-
"""
텔레그램 아침 매매 브리핑 - 강화판
- 해외지수/환율/유가
- 엔비디아·마이크론 등 반도체 5종목
- 미국 주요 관심종목 급등 2개 / 급락 2개
- 장전 핵심 뉴스 8개 + 한 줄 매매 해석
- 오늘 한국장 관심 섹터
"""

import os, re, math, html, datetime as dt
from urllib.parse import quote_plus
import requests, feedparser, yfinance as yf

KST = dt.timezone(dt.timedelta(hours=9))

MARKET_ITEMS = [
    ("S&P500", ["^GSPC", "SPY"], "idx"),
    ("나스닥", ["^IXIC", "QQQ"], "idx"),
    ("다우", ["^DJI", "DIA"], "idx"),
    ("러셀2000", ["^RUT", "IWM"], "idx"),
    ("필라델피아반도체/SOX", ["^SOX", "SOXX", "SMH"], "idx"),
    ("VIX 공포지수", ["^VIX"], "idx"),
    ("미국10년물 금리", ["^TNX"], "yield"),
    ("달러인덱스", ["DX-Y.NYB", "UUP"], "idx"),
    ("달러/원", ["KRW=X"], "fx"),
    ("WTI유가", ["CL=F", "USO"], "cmd"),
    ("금", ["GC=F", "GLD"], "cmd"),
    ("한국ETF(EWY)", ["EWY"], "etf"),
]

SEMI5 = [
    ("NVDA", "엔비디아", "AI GPU/HBM"),
    ("MU", "마이크론", "메모리/HBM"),
    ("AMD", "AMD", "AI칩/CPU"),
    ("AVGO", "브로드컴", "AI 네트워크"),
    ("ARM", "ARM", "반도체 설계"),
]

WATCH = {
    "NVDA": ("엔비디아", "AI/반도체"), "MU": ("마이크론", "메모리/HBM"),
    "AMD": ("AMD", "AI/반도체"), "AVGO": ("브로드컴", "AI/반도체"),
    "ARM": ("ARM", "반도체 설계"), "TSM": ("TSMC", "파운드리"),
    "ASML": ("ASML", "반도체 장비"), "AMAT": ("AMAT", "반도체 장비"),
    "LRCX": ("램리서치", "반도체 장비"), "KLAC": ("KLA", "반도체 장비"),
    "QCOM": ("퀄컴", "모바일 반도체"), "INTC": ("인텔", "반도체"),
    "AAPL": ("애플", "빅테크"), "MSFT": ("마이크로소프트", "AI/클라우드"),
    "GOOGL": ("알파벳", "AI/광고"), "AMZN": ("아마존", "클라우드/소비"),
    "META": ("메타", "AI/광고"), "TSLA": ("테슬라", "전기차/로봇"),
    "NFLX": ("넷플릭스", "미디어"), "LLY": ("일라이릴리", "바이오/비만"),
    "NVO": ("노보노디스크", "바이오/비만"), "MRNA": ("모더나", "바이오"),
    "XOM": ("엑슨모빌", "정유/에너지"), "CVX": ("셰브론", "정유/에너지"),
    "CCJ": ("카메코", "우라늄/원전"), "CEG": ("컨스텔레이션", "원전/전력"),
    "VST": ("비스트라", "전력/AI전력"), "GEV": ("GE버노바", "전력/가스터빈"),
    "ALB": ("앨버말", "리튬/2차전지"), "RIVN": ("리비안", "전기차"),
    "LMT": ("록히드마틴", "방산"), "RTX": ("RTX", "방산/항공"),
    "BA": ("보잉", "항공"), "JPM": ("JP모건", "금융"),
    "BAC": ("뱅크오브아메리카", "금융"), "WMT": ("월마트", "소비"),
    "COST": ("코스트코", "소비"),
}

NEWS_QUERIES = [
    ("미국증시", "뉴욕증시 나스닥 S&P500 엔비디아 마이크론 반도체 when:1d"),
    ("반도체/AI", "엔비디아 마이크론 HBM AI 반도체 삼성전자 SK하이닉스 when:1d"),
    ("금리/환율", "미국 국채금리 달러 원 환율 FOMC 파월 CPI PCE 고용 when:1d"),
    ("원자재/유가", "WTI 유가 원유 금 구리 원자재 한국 증시 영향 when:1d"),
    ("한국장전", "오늘 증시 전망 코스피 코스닥 외국인 기관 수급 when:1d"),
    ("국내테마", "장전 특징주 급등주 테마주 반도체 바이오 2차전지 로봇 원전 조선 when:1d"),
    ("정책/수출규제", "미국 관세 수출규제 중국 한국 반도체 배터리 증시 영향 when:1d"),
    ("기업실적", "미국 기업 실적 가이던스 AI 반도체 한국 증시 영향 when:1d"),
]

SECTOR_KEYS = {
    "AI/HBM/반도체": ["엔비디아","nvidia","마이크론","micron","hbm","반도체","ai","tsmc","브로드컴","amd"],
    "반도체 장비": ["euv","asml","장비","소부장","램리서치","kla","amat"],
    "2차전지/리튬": ["2차전지","배터리","리튬","전기차","테슬라","앨버말","리비안"],
    "원전/전력/ESS": ["원전","전력","전력망","ess","우라늄","카메코","ai 전력"],
    "조선/방산": ["조선","방산","군사","전쟁","수주","lng","록히드","rtx"],
    "바이오/제약": ["바이오","제약","비만","일라이릴리","노보","fda","임상"],
    "로봇/자동화": ["로봇","자동화","휴머노이드"],
    "금융/증권": ["금리","은행","증권","보험","배당"],
    "정유/화학": ["유가","원유","정유","화학","wti"],
    "환율수혜/수출": ["환율","달러","수출","원화"],
}

def sf(x):
    try:
        x = float(x)
        return None if math.isnan(x) or math.isinf(x) else x
    except Exception:
        return None

def pct_txt(x):
    if x is None: return "N/A"
    return ("+" if x >= 0 else "") + f"{x:.2f}%"

def esc(x):
    return html.escape(str(x))

def clean(s, n=145):
    s = html.unescape(str(s or ""))
    s = re.sub(r"<.*?>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:n-1] + "…" if len(s) > n else s

def emoji(p):
    if p is None: return "⚪"
    if p >= 2: return "🔥"
    if p >= 0.5: return "🟢"
    if p <= -2: return "🔻"
    if p <= -0.5: return "🔴"
    return "⚪"

def close_series(ticker):
    try:
        df = yf.download(ticker, period="7d", interval="1d", progress=False, auto_adjust=False, threads=False)
        if df is None or df.empty: return None
        if "Close" in df.columns:
            c = df["Close"]
        else:
            cols = [x for x in df.columns if isinstance(x, tuple) and x[0] == "Close"]
            if not cols: return None
            c = df[cols[0]]
        c = c.dropna()
        return c if len(c) >= 2 else None
    except Exception:
        return None

def ticker_change(ticker):
    c = close_series(ticker)
    if c is None: return None
    last, prev = sf(c.iloc[-1]), sf(c.iloc[-2])
    if last is None or prev in [None, 0]: return None
    return {"ticker": ticker, "last": last, "pct": (last-prev)/prev*100}

def fallback(tickers):
    for i, t in enumerate(tickers):
        r = ticker_change(t)
        if r:
            r["proxy"] = i > 0
            return r
    return None

def market_rows():
    rows = []
    for name, tickers, typ in MARKET_ITEMS:
        r = fallback(tickers)
        if not r:
            rows.append({"name": name, "ticker": tickers[0], "last": "N/A", "pct": None, "note": ""})
            continue
        last = r["last"]
        if typ == "fx": last_txt = f"{last:,.2f}원"
        elif typ == "yield":
            y = last/10 if last > 20 else last
            last_txt = f"{y:.2f}%"
        else:
            last_txt = f"{last:,.2f}"
        rows.append({"name": name, "ticker": r["ticker"], "last": last_txt, "pct": r["pct"], "note": "대체지표" if r["proxy"] else ""})
    return rows

def stock_rows(items):
    out=[]
    for t, name, desc in items:
        r=ticker_change(t)
        out.append({"ticker":t,"name":name,"desc":desc,"pct":None if not r else r["pct"],"last":"N/A" if not r else f'{r["last"]:,.2f}'})
    return out

def movers():
    rows=[]
    for t,(name,sector) in WATCH.items():
        r=ticker_change(t)
        if r: rows.append({"ticker":t,"name":name,"sector":sector,"pct":r["pct"]})
    return sorted(rows,key=lambda x:x["pct"],reverse=True)[:2], sorted(rows,key=lambda x:x["pct"])[:2]

def news_rss(query, max_items=5):
    url="https://news.google.com/rss/search?q="+quote_plus(query)+"&hl=ko&gl=KR&ceid=KR:ko"
    try: feed=feedparser.parse(url)
    except Exception: return []
    res=[]
    for e in feed.entries[:max_items]:
        title=clean(e.get("title",""))
        if not title: continue
        src=""
        try:
            if hasattr(e,"source") and e.source: src=clean(e.source.get("title",""),35)
        except Exception: pass
        res.append({"title":title,"source":src})
    return res

def view(category,title):
    t=title.lower()
    if any(k in t for k in ["엔비디아","nvidia","마이크론","micron","hbm","반도체","ai","tsmc","브로드컴","amd"]):
        return "삼성전자·SK하이닉스·HBM·반도체장비주 장초반 수급 우선 확인."
    if any(k in t for k in ["금리","fed","fomc","파월","국채","cpi","pce","고용"]):
        return "금리 상승이면 성장주 추격 자제, 금리 하락이면 기술주 반등 가능성 체크."
    if any(k in t for k in ["환율","달러","원화"]):
        return "달러/원 상승은 외국인 수급 부담, 하락은 대형주 수급 개선 가능성."
    if any(k in t for k in ["유가","wti","원유","정유"]):
        return "유가 상승은 정유·조선 일부 관심, 항공·화학은 비용 부담 체크."
    if any(k in t for k in ["전력","원전","ess","우라늄"]):
        return "AI 전력·원전·전력기기·ESS 테마로 연결되는지 거래대금 확인."
    if any(k in t for k in ["방산","전쟁","지정학","군사"]):
        return "지정학 이슈는 방산·조선·에너지 단기 수급 가능성 체크."
    if any(k in t for k in ["바이오","제약","임상","fda","비만"]):
        return "바이오는 개별 재료 성격, 대장주와 거래대금 지속 여부가 핵심."
    if any(k in t for k in ["급등","특징주","상한가","테마"]):
        return "대장테마 안에서 거래대금 1~3위, 양봉·VWAP 위 종목만 선별."
    return "뉴스만 보고 매수하지 말고 거래대금·양봉·VWAP 위 여부 확인."

def news_blocks(n=8):
    out=[]; seen=set()
    for cat,q in NEWS_QUERIES:
        for it in news_rss(q,4):
            key=re.sub(r"[^가-힣a-z0-9]","",it["title"].lower())[:60]
            if key in seen: continue
            seen.add(key)
            out.append({"cat":cat,"title":it["title"],"source":it["source"],"view":view(cat,it["title"])})
            break
        if len(out)>=n: break
    return out[:n]

def sectors(news, markets, semis, up, down):
    score={k:0 for k in SECTOR_KEYS}
    text=" ".join([x["title"] for x in news] + [f'{x["name"]} {pct_txt(x["pct"])} {x["desc"]}' for x in semis] + [f'{x["name"]} {x["sector"]}' for x in up+down]).lower()
    for sec, keys in SECTOR_KEYS.items():
        for k in keys:
            if k.lower() in text: score[sec]+=1
    for m in markets:
        if "필라델피아" in m["name"] and m["pct"] is not None and m["pct"] > 0.5:
            score["AI/HBM/반도체"] += 2; score["반도체 장비"] += 1
        if m["name"] == "WTI유가" and m["pct"] is not None and m["pct"] > 1:
            score["정유/화학"] += 2
        if m["name"] == "달러/원" and m["pct"] is not None and m["pct"] > 0.3:
            score["환율수혜/수출"] += 1
    return [(k,v) for k,v in sorted(score.items(), key=lambda x:x[1], reverse=True) if v>0][:5]

def tone(markets):
    d={x["name"]:x["pct"] for x in markets}
    arr=[]
    nas=d.get("나스닥"); sox=d.get("필라델피아반도체/SOX"); vix=d.get("VIX 공포지수"); krw=d.get("달러/원")
    if nas is not None: arr.append("나스닥 강세 → 성장주 우호" if nas>0.5 else "나스닥 약세 → 성장주 추격 주의" if nas<-0.5 else "나스닥 보합 → 개별 테마 장세")
    if sox is not None: arr.append("반도체 강세 → HBM/장비 우선" if sox>0.7 else "반도체 약세 → 반도체 추격 금지" if sox<-0.7 else "반도체 보합 → 종목 선별")
    if vix is not None and vix>5: arr.append("VIX 상승 → 변동성 주의")
    if krw is not None and krw>0.3: arr.append("환율 상승 → 외국인 수급 부담")
    return " / ".join(arr) if arr else "시장 방향성 판단 데이터 부족"

def make_report():
    m=market_rows(); s=stock_rows(SEMI5); up,down=movers(); n=news_blocks(8); sec=sectors(n,m,s,up,down)
    lines=[]
    lines += ["📌 <b>아침 매매 브리핑 - 강화판</b>", f"기준: {dt.datetime.now(KST).strftime('%Y-%m-%d %H:%M')} KST", "", "🧭 <b>오늘 한 줄 결론</b>", esc(tone(m)), ""]
    lines.append("✅ <b>1) 해외시장 핵심 수치</b>")
    for x in m:
        note=f" / {x['note']}" if x['note'] else ""
        lines.append(f"{emoji(x['pct'])} {esc(x['name'])}: {esc(x['last'])} / {esc(pct_txt(x['pct']))} ({esc(x['ticker'])}{esc(note)})")
    lines += ["", "🧠 <b>2) 밤사이 반도체 핵심 5종목</b>"]
    for x in s:
        lines.append(f"{emoji(x['pct'])} {esc(x['name'])}({esc(x['ticker'])}): {esc(pct_txt(x['pct']))} / {esc(x['desc'])}")
    lines.append("→ 한국 연결: 삼성전자·SK하이닉스·HBM·반도체장비·소부장")
    lines += ["", "🚀 <b>3) 미국 관심종목 급등/급락</b>", "<b>급등 2종목</b>"]
    for x in up: lines.append(f"🔥 {esc(x['name'])}({esc(x['ticker'])}): {esc(pct_txt(x['pct']))} / 섹터: {esc(x['sector'])}")
    lines.append("<b>급락 2종목</b>")
    for x in down: lines.append(f"🔻 {esc(x['name'])}({esc(x['ticker'])}): {esc(pct_txt(x['pct']))} / 섹터: {esc(x['sector'])}")
    lines += ["", "📰 <b>4) 장전 핵심 뉴스 8개 + 한 줄 매매 해석</b>"]
    for i,x in enumerate(n,1):
        lines += ["", f"{i}. <b>[{esc(x['cat'])}]</b> {esc(x['title'])}"]
        if x['source']: lines.append(f"   출처: {esc(x['source'])}")
        lines.append(f"   → {esc(x['view'])}")
    lines += ["", "🎯 <b>5) 오늘 한국장 관심 섹터 후보</b>"]
    if sec:
        for i,(name,score) in enumerate(sec,1): lines.append(f"{i}. {esc(name)} / 점수: {score} / 장초반 거래대금 확인")
    else: lines.append("뚜렷한 섹터 점수 없음 → 장초반 거래대금 상위 테마 확인")
    lines += ["", "📍 <b>6) 형의 장초반 매매 체크리스트</b>", "1. 거래대금 상위 테마부터 본다.", "2. 대장테마 안에서도 1~3등주만 본다.", "3. 음봉 매수 금지. 양봉 + VWAP 위 종목만 본다.", "4. 전일 동시간 대비 거래량 2~3배 이상인지 확인한다.", "5. 급등 직후 추격 금지. 눌림 후 기준봉 고가 재돌파만 본다.", "6. 음봉 거래량 감소 + 양봉 거래량 증가면 매집 가능성 가산점.", "7. 손절 기준이 애매한 종목은 매수하지 않는다.", "", "⚠️ 자동 수집 자료입니다. 실제 매수 전 현재가·거래량·뉴스 원문을 반드시 확인하세요."]
    return "\n".join(lines)

def split_msg(msg, max_len=3600):
    parts=[]; cur=[]
    for line in msg.splitlines():
        test="\n".join(cur+[line])
        if len(test)>max_len and cur:
            parts.append("\n".join(cur)); cur=[line]
        else: cur.append(line)
    if cur: parts.append("\n".join(cur))
    return parts

def send_telegram(msg):
    token=os.getenv("TELEGRAM_BOT_TOKEN","").strip(); chat_id=os.getenv("TELEGRAM_CHAT_ID","").strip()
    if not token: raise RuntimeError("TELEGRAM_BOT_TOKEN 환경변수가 없습니다.")
    if not chat_id: raise RuntimeError("TELEGRAM_CHAT_ID 환경변수가 없습니다.")
    url=f"https://api.telegram.org/bot{token}/sendMessage"
    parts=split_msg(msg)
    for i,p in enumerate(parts,1):
        head=f"({i}/{len(parts)})\n" if len(parts)>1 else ""
        r=requests.post(url,json={"chat_id":chat_id,"text":head+p,"parse_mode":"HTML","disable_web_page_preview":True},timeout=30)
        if r.status_code!=200: raise RuntimeError(f"텔레그램 발송 실패: {r.status_code} / {r.text}")
    return True

def main():
    msg=make_report()
    print(msg.replace("<b>","").replace("</b>","")[:5000])
    send_telegram(msg)
    print("Telegram send success")

if __name__ == "__main__":
    main()
