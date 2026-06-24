# -*- coding: utf-8 -*-
"""
FINAL_V2_NO_NA - 실전형 텔레그램 아침 매매 브리핑

핵심 원칙
1) N/A 투성이 보고서는 보내지 않는다.
2) yfinance 제거. Yahoo 직접 API + ETF 대체 + Stooq 백업 사용.
3) 데이터가 부족하면 분석 보고서 대신 실패 알림만 보낸다.
4) OPENAI_API_KEY가 있으면 AI 분석, 실패하면 규칙 기반 보고서.

GitHub Secrets:
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
- OPENAI_API_KEY
"""

import os, re, csv, io, json, time, math, datetime as dt
from urllib.parse import quote, quote_plus
import requests
import feedparser

KST = dt.timezone(dt.timedelta(hours=9))
VERSION = "FINAL_V2_NO_NA"
HEADERS = {"User-Agent":"Mozilla/5.0 Chrome/126 Safari/537.36", "Accept-Language":"ko-KR,ko;q=0.9,en;q=0.8"}
TIMEOUT = 15
MIN_MARKET_OK = 8
MIN_SEMI_OK = 7

MARKET = [
    ("sp500","S&P500",["^GSPC","SPY"],["spy.us"],True,"미국 대형주"),
    ("nasdaq","나스닥",["^IXIC","QQQ"],["qqq.us"],True,"기술주/성장주"),
    ("dow","다우",["^DJI","DIA"],["dia.us"],False,"경기민감주"),
    ("russell","러셀2000",["^RUT","IWM"],["iwm.us"],False,"중소형 위험선호"),
    ("semi","반도체지표(SOX/SMH)",["^SOX","SOXX","SMH"],["soxx.us","smh.us"],True,"한국 반도체 선행"),
    ("vix","VIX",["^VIX","VIXY"],["vixy.us"],False,"공포지수"),
    ("tnx","미국10년물금리",["^TNX"],[],False,"금리"),
    ("dxy","달러인덱스",["DX-Y.NYB","UUP"],["uup.us"],False,"달러 강약"),
    ("usdkrw","달러/원",["KRW=X"],[],False,"외국인 수급"),
    ("oil","WTI유가",["CL=F","USO"],["uso.us"],False,"유가"),
    ("gold","금",["GC=F","GLD"],["gld.us"],False,"안전자산"),
    ("ewy","한국ETF(EWY)",["EWY"],["ewy.us"],False,"한국 선반영"),
]
SEMI = [
    ("NVDA","엔비디아","AI GPU/HBM"),("MU","마이크론","메모리/HBM"),("AMD","AMD","AI칩"),
    ("AVGO","브로드컴","AI 네트워크"),("ARM","ARM","반도체 설계"),("TSM","TSMC","파운드리"),
    ("ASML","ASML","EUV 장비"),("AMAT","AMAT","반도체 장비"),("LRCX","램리서치","반도체 장비"),("KLAC","KLA","검사장비")]
WATCH = {
    "NVDA":("엔비디아","AI/반도체"),"MU":("마이크론","메모리/HBM"),"AMD":("AMD","AI/반도체"),
    "AVGO":("브로드컴","AI/반도체"),"ARM":("ARM","반도체설계"),"TSM":("TSMC","파운드리"),
    "ASML":("ASML","반도체장비"),"AMAT":("AMAT","반도체장비"),"LRCX":("램리서치","반도체장비"),"KLAC":("KLA","검사장비"),
    "MSFT":("마이크로소프트","AI/클라우드"),"GOOGL":("알파벳","AI/광고"),"AMZN":("아마존","클라우드/소비"),"META":("메타","AI/광고"),"AAPL":("애플","스마트폰"),"TSLA":("테슬라","전기차/로봇"),
    "VST":("비스트라","AI전력"),"CEG":("컨스텔레이션","원전/전력"),"GEV":("GE버노바","전력"),"CCJ":("카메코","우라늄/원전"),"ETN":("이튼","전력기기"),"PWR":("콴타서비스","전력망"),
    "XOM":("엑슨모빌","정유"),"CVX":("셰브론","정유"),"ALB":("앨버말","리튬"),"LLY":("일라이릴리","비만/바이오"),"NVO":("노보노디스크","비만/바이오"),"LMT":("록히드마틴","방산"),"RTX":("RTX","방산/항공")}
NEWS_Q = [
    ("미국증시","Nasdaq S&P 500 Nvidia Micron Treasury yields oil dollar market today"),
    ("반도체AI","Nvidia Micron AMD Broadcom ARM semiconductor AI HBM chips today"),
    ("금리환율","Federal Reserve Treasury yields dollar inflation CPI PCE jobs market"),
    ("원자재","WTI crude oil gold copper commodities stock market impact"),
    ("한국장","Korea stock market outlook Samsung Electronics SK Hynix semiconductor today"),
    ("전력원전","AI data center power nuclear uranium electricity stocks"),
    ("정책규제","US China export controls tariffs semiconductor Korea market"),]
KEYWORDS = "nasdaq s&p yield treasury fed fomc powell cpi pce jobs inflation dollar won oil wti nvidia micron amd broadcom arm tsmc asml semiconductor ai hbm chip earnings guidance tariff export china 데이터센터 금리 환율 달러 유가 원유 엔비디아 마이크론 반도체 삼성전자 하이닉스 실적 관세 수출규제 전력 원전 우라늄".split()
BAD = "포토 영상 광고 홍보 모집 무료 이벤트 연예 스포츠".split()

def now(): return dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M")
def sf(x):
    try:
        x=float(x)
        return None if math.isnan(x) or math.isinf(x) else x
    except Exception: return None
def pct(p): return "확인불가" if p is None else f"{p:+.2f}%"
def price(x): return "확인불가" if x is None else (f"{x:,.2f}" if abs(x)>=1000 else f"{x:.2f}")
def clean(s,n=170):
    s=re.sub(r"<.*?>"," ",str(s or "")); s=s.replace("&amp;","&").replace("&quot;",'"')
    s=re.sub(r"\s+"," ",s).strip()
    return s[:n-1]+"…" if len(s)>n else s

def get_json(url):
    try:
        r=requests.get(url,headers=HEADERS,timeout=TIMEOUT)
        return r.json() if r.status_code==200 else None
    except Exception: return None

def get_text(url):
    try:
        r=requests.get(url,headers=HEADERS,timeout=TIMEOUT)
        return r.text if r.status_code==200 else None
    except Exception: return None

def yahoo_batch(symbols):
    out={}
    sy=list(symbols)
    for i in range(0,len(sy),40):
        url="https://query1.finance.yahoo.com/v7/finance/quote?symbols="+quote(",".join(sy[i:i+40]))
        data=get_json(url)
        for it in (data or {}).get("quoteResponse",{}).get("result",[]):
            sym=it.get("symbol"); pr=sf(it.get("regularMarketPrice")); pc=sf(it.get("regularMarketChangePercent")); prev=sf(it.get("regularMarketPreviousClose"))
            if sym and pr is not None and pc is not None: out[sym]={"symbol":sym,"price":pr,"pct":pc,"prev":prev,"src":"YahooQuote"}
    return out

def yahoo_chart(sym):
    data=get_json(f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(sym,safe='')}?range=10d&interval=1d")
    try:
        res=data["chart"]["result"][0]; closes=res["indicators"]["quote"][0].get("close",[])
        vals=[sf(c) for c in closes]; vals=[v for v in vals if v is not None]
        if len(vals)<2 or vals[-2]==0: return None
        return {"symbol":sym,"price":vals[-1],"pct":(vals[-1]-vals[-2])/vals[-2]*100,"prev":vals[-2],"src":"YahooChart"}
    except Exception: return None

def stooq(sym):
    txt=get_text(f"https://stooq.com/q/d/l/?s={quote(sym)}&i=d")
    if not txt: return None
    try:
        rows=list(csv.DictReader(io.StringIO(txt))); vals=[sf(r.get("Close")) for r in rows]; vals=[v for v in vals if v is not None]
        if len(vals)<2 or vals[-2]==0: return None
        return {"symbol":sym,"price":vals[-1],"pct":(vals[-1]-vals[-2])/vals[-2]*100,"prev":vals[-2],"src":"Stooq"}
    except Exception: return None

def stooq_us(sym):
    if sym.startswith("^") or "=" in sym or "-" in sym: return None
    return stooq(sym.lower()+".us")

def get_price(symbols, stooqs, cache):
    for i,s in enumerate(symbols):
        if s in cache:
            d=dict(cache[s]); d["used"]=s; d["proxy"]=i>0; return d
    for i,s in enumerate(symbols):
        d=yahoo_chart(s)
        if d: d["used"]=s; d["proxy"]=i>0; return d
    for ss in stooqs:
        d=stooq(ss)
        if d: d["used"]=ss; d["proxy"]=True; return d
    for s in symbols:
        d=stooq_us(s)
        if d: d["used"]=d["symbol"]; d["proxy"]=True; return d
    return None

def collect_prices():
    sy=set()
    for _,_,ticks,_,_,_ in MARKET: sy.update(ticks)
    sy.update([t for t,_,_ in SEMI]); sy.update(WATCH.keys())
    cache=yahoo_batch(sy)
    market=[]; semi=[]; errors=[]
    for key,name,ticks,stqs,must,note in MARKET:
        d=get_price(ticks,stqs,cache)
        if d: market.append({"key":key,"name":name,"symbol":d["used"],"price":d["price"],"pct":d["pct"],"src":d["src"],"proxy":d.get("proxy",False),"note":note,"ok":True})
        else:
            errors.append(name+" 수집 실패"); market.append({"key":key,"name":name,"symbol":"/".join(ticks),"price":None,"pct":None,"src":"FAIL","proxy":False,"note":note,"ok":False})
    for t,n,desc in SEMI:
        d=get_price([t],[],cache)
        if d: semi.append({"ticker":t,"name":n,"desc":desc,"price":d["price"],"pct":d["pct"],"src":d["src"],"ok":True})
        else: errors.append(f"{n}({t}) 수집 실패"); semi.append({"ticker":t,"name":n,"desc":desc,"price":None,"pct":None,"src":"FAIL","ok":False})
    watch=[]
    for t,(n,sec) in WATCH.items():
        d=get_price([t],[],cache)
        if d: watch.append({"ticker":t,"name":n,"sector":sec,"price":d["price"],"pct":d["pct"],"src":d["src"],"ok":True})
    up=sorted(watch,key=lambda x:x["pct"],reverse=True)[:3]
    down=sorted(watch,key=lambda x:x["pct"])[:3]
    val={"market_ok":sum(x["ok"] for x in market),"market_total":len(market),"semi_ok":sum(x["ok"] for x in semi),"semi_total":len(semi),"errors":errors[:20]}
    val["total_ok"]=val["market_ok"]+val["semi_ok"]; val["total"]=len(market)+len(semi); val["ratio"]=val["total_ok"]/val["total"]
    val["pass"]=val["market_ok"]>=MIN_MARKET_OK and val["semi_ok"]>=MIN_SEMI_OK
    return market,semi,up,down,val

def news_score(title,cat):
    t=title.lower(); sc=2 if cat in ("미국증시","반도체AI","금리환율") else 0
    sc += sum(3 for k in KEYWORDS if k.lower() in t)
    if any(b.lower() in t for b in BAD): sc-=8
    if len(title)<18: sc-=4
    return sc

def collect_news():
    rows=[]
    for cat,q in NEWS_Q:
        url="https://news.google.com/rss/search?q="+quote_plus(q)+"&hl=ko&gl=KR&ceid=KR:ko"
        try: feed=feedparser.parse(url)
        except Exception: continue
        for e in feed.entries[:10]:
            title=clean(e.get("title","")); src=""
            try: src=clean(e.source.get("title",""),40)
            except Exception: pass
            if title:
                rows.append({"category":cat,"title":title,"source":src,"score":news_score(title,cat)})
    # Yahoo Finance ticker news
    url="https://feeds.finance.yahoo.com/rss/2.0/headline?s="+quote_plus("NVDA,MU,AMD,AVGO,ARM,TSM,ASML,SMH,QQQ,SPY")+"&region=US&lang=en-US"
    try:
        feed=feedparser.parse(url)
        for e in feed.entries[:20]:
            title=clean(e.get("title",""));
            if title: rows.append({"category":"미국개별주","title":title,"source":"Yahoo Finance","score":news_score(title,"미국개별주")+2})
    except Exception: pass
    seen=set(); out=[]
    for r in sorted(rows,key=lambda x:x["score"],reverse=True):
        k=re.sub(r"[^가-힣a-zA-Z0-9]","",r["title"]).lower()[:80]
        if k in seen or r["score"]<4: continue
        seen.add(k); out.append(r)
    return out[:10]

def item(rows,key):
    return next((r for r in rows if r.get("key")==key),None)

def tone_and_themes(market,semi,up,news):
    score=0; rs=[]
    for key,w,thr,plus,minus in [("sp500",1,.3,"S&P500 강세","S&P500 약세"),("nasdaq",2,.3,"나스닥 강세","나스닥 약세"),("semi",3,.5,"반도체지표 강세","반도체지표 약세")]:
        r=item(market,key); p=r and r["pct"]
        if p is not None:
            if p>=thr: score+=w; rs.append(plus+" "+pct(p))
            elif p<=-thr: score-=w; rs.append(minus+" "+pct(p))
    v=item(market,"vix")
    if v and v["pct"] is not None:
        if v["pct"]<-3: score+=1; rs.append("VIX 하락")
        elif v["pct"]>3: score-=1; rs.append("VIX 상승")
    tone = "위험선호 우세: 반도체/AI/HBM 우선" if score>=3 else "중립 이상: 대장테마 선별" if score>=1 else "위험회피: 추격 금지" if score<=-3 else "경계: 대장주 음봉이면 제외" if score<=-1 else "혼조: 거래대금 확인 전 관망"
    themes={"AI/HBM/반도체":[0,[]],"반도체 장비/소부장":[0,[]],"전력기기/원전/ESS":[0,[]],"2차전지/리튬":[0,[]],"정유/조선/방산":[0,[]],"바이오/제약":[0,[]]}
    sx=item(market,"semi")
    if sx and sx["pct"] is not None and sx["pct"]>=.5: themes["AI/HBM/반도체"][0]+=4; themes["AI/HBM/반도체"][1].append("반도체지표 "+pct(sx["pct"])); themes["반도체 장비/소부장"][0]+=2
    for s in semi:
        if not s["ok"] or s["pct"] is None: continue
        if s["ticker"] in "NVDA MU AMD AVGO ARM TSM".split() and s["pct"]>=1:
            themes["AI/HBM/반도체"][0]+=2; themes["AI/HBM/반도체"][1].append(f"{s['name']} {pct(s['pct'])}")
        if s["ticker"] in "ASML AMAT LRCX KLAC".split() and s["pct"]>=1:
            themes["반도체 장비/소부장"][0]+=2; themes["반도체 장비/소부장"][1].append(f"{s['name']} {pct(s['pct'])}")
    for m in up:
        sec=m["sector"]
        if any(x in sec for x in ["전력","원전","우라늄"]): themes["전력기기/원전/ESS"][0]+=3; themes["전력기기/원전/ESS"][1].append(m["name"]+" 강세")
        if any(x in sec for x in ["리튬","2차전지"]): themes["2차전지/리튬"][0]+=3; themes["2차전지/리튬"][1].append(m["name"]+" 강세")
        if any(x in sec for x in ["방산","항공"]): themes["정유/조선/방산"][0]+=2; themes["정유/조선/방산"][1].append(m["name"]+" 강세")
        if "바이오" in sec: themes["바이오/제약"][0]+=2; themes["바이오/제약"][1].append(m["name"]+" 강세")
    nt=" ".join(n["title"].lower() for n in news)
    if any(k in nt for k in ["nvidia","micron","semiconductor","hbm","엔비디아","마이크론","반도체"]): themes["AI/HBM/반도체"][0]+=2; themes["AI/HBM/반도체"][1].append("반도체/AI 뉴스")
    if any(k in nt for k in ["power","nuclear","uranium","전력","원전","우라늄"]): themes["전력기기/원전/ESS"][0]+=2; themes["전력기기/원전/ESS"][1].append("전력/원전 뉴스")
    ranked=[{"theme":k,"score":v[0],"reasons":list(dict.fromkeys(v[1]))[:4]} for k,v in themes.items() if v[0]>0]
    ranked.sort(key=lambda x:x["score"],reverse=True)
    return tone,rs[:6],ranked[:3]

def context(market,semi,up,down,news,val):
    tone,rs,themes=tone_and_themes(market,semi,up,news)
    def ok_rows(rows):
        out=[]
        for r in rows:
            if not r.get("ok",True): continue
            d=dict(r); d["pct_text"]=pct(d.get("pct")); d["price_text"]=price(d.get("price")); out.append(d)
        return out
    return {"version":VERSION,"time_kst":now(),"validation":val,"tone":tone,"tone_reasons":rs,"market":ok_rows(market),"semiconductors":ok_rows(semi),"movers_up":ok_rows(up),"movers_down":ok_rows(down),"news":news[:8],"themes":themes,"rules":["음봉 매수 금지","양봉+VWAP 위만 관심","대장테마 거래대금 1~3등주","급등 직후 추격 금지","눌림 후 기준봉 재돌파","양봉 거래량 증가+음봉 거래량 감소는 매집 참고"]}

def openai_report(ctx):
    key=os.getenv("OPENAI_API_KEY","").strip()
    if not key: return None,"OPENAI_API_KEY 없음"
    prompt="""너는 한국 주식 장초반 단기매매 전문 애널리스트다. 아래 JSON 원자료만 사용해 한국어 텔레그램 보고서를 작성하라.
규칙: 없는 데이터 지어내지 말 것. 뉴스 나열 금지, 한국장 섹터와 매매 판단으로 연결. 매수 추천 단정 금지. 음봉 매수 금지, VWAP 위 양봉, 거래대금 1~3등주, 눌림 재돌파 기준 반영.
형식:
📌 AI 실전형 아침 매매 브리핑
1) 오늘 한 줄 결론
2) 미국시장 핵심: 의미 있는 수치와 한국장 영향
3) 반도체 핵심주: 엔비디아·마이크론·AMD·브로드컴·ARM 중심
4) 급등/급락 미국 관심종목과 한국 연결
5) 오늘 한국장 관심 테마 TOP 3: 근거/볼 것/매수금지
6) 뉴스 5~8개: 왜 중요한가/매매 해석
7) 9시 이후 실행 순서 5줄
8) 오늘 피해야 할 매매 5줄
JSON:
"""+json.dumps(ctx,ensure_ascii=False)
    headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"}
    errs=[]
    for model in [os.getenv("OPENAI_MODEL",""),"gpt-4.1-mini","gpt-4o-mini"]:
        if not model: continue
        try:
            r=requests.post("https://api.openai.com/v1/responses",headers=headers,json={"model":model,"input":prompt,"temperature":0.2,"max_output_tokens":2200},timeout=45)
            if r.status_code==200:
                txt=r.json().get("output_text")
                if txt and len(txt)>500: return txt.strip(),None
            errs.append(r.text[:200])
        except Exception as e: errs.append(str(e))
    return None,"; ".join(errs)[-500:]

def fallback(ctx,err=None):
    L=["📌 AI 실전형 아침 매매 브리핑",f"기준: {ctx['time_kst']} KST",f"데이터 정상: {ctx['validation']['total_ok']}/{ctx['validation']['total']}"]
    if err: L.append("※ AI 실패, 규칙 기반 보고서: "+err[:120])
    L += ["","1) 오늘 한 줄 결론","- "+ctx["tone"],"- 근거: "+(", ".join(ctx["tone_reasons"]) or "혼조")]
    L += ["","2) 밤사이 미국시장 핵심"]
    for r in ctx["market"][:12]: L.append(f"- {r['name']}: {r['pct_text']} ({r.get('symbol','')}/{r.get('src','')}) → {r.get('note','')}")
    L += ["","3) 반도체 핵심주"]
    for r in ctx["semiconductors"][:10]: L.append(f"- {r['name']}({r['ticker']}): {r['pct_text']} → {r.get('desc','')}")
    L.append("→ 한국 연결: 삼성전자·SK하이닉스·HBM·장비/소부장. 장초반 대장주 음봉이면 제외.")
    L += ["","4) 미국 관심종목 급등/급락","급등:"]
    for r in ctx["movers_up"]: L.append(f"- {r['name']}({r['ticker']}): {r['pct_text']} / {r['sector']}")
    L.append("급락:")
    for r in ctx["movers_down"]: L.append(f"- {r['name']}({r['ticker']}): {r['pct_text']} / {r['sector']}")
    L += ["","5) 오늘 한국장 관심 테마 TOP 3"]
    if ctx["themes"]:
        for i,t in enumerate(ctx["themes"],1):
            L.append(f"{i}. {t['theme']} / 점수 {t['score']} / 근거: {', '.join(t['reasons']) or '미국시장 연동'}")
            L.append("   볼 것: 거래대금 1~3등주, 양봉+VWAP 위, 눌림 후 기준봉 재돌파")
            L.append("   금지: 갭상승 후 음봉, 윗꼬리, 시가 이탈, 거래대금 약화")
    else: L.append("- 뚜렷한 우위 테마 없음. 장초반 거래대금 확인 전 관망.")
    L += ["","6) 뉴스 핵심"]
    for i,n in enumerate(ctx["news"][:8],1): L.append(f"{i}. [{n['category']}] {n['title']} / {n.get('source','')}")
    L += ["","7) 9시 이후 실행 순서","1. 지수보다 거래대금 상위 테마 확인","2. 테마 안 대장주 1~3등만 남김","3. 음봉 매수 금지, VWAP 위 양봉만 관찰","4. 급등 직후 추격 금지, 눌림 후 재돌파만 관심","5. 손절선 불명확하면 매수하지 않음","","8) 오늘 피해야 할 매매","- 뉴스만 보고 매수","- 갭상승 후 음봉 전환","- 윗꼬리 긴 종목","- 대장주 약한데 2~3등주 추격","- 손절 기준 없는 매매",f"\n버전: {VERSION}"]
    return "\n".join(L)

def fail_msg(val,market,semi):
    L=["⚠️ 아침 매매 브리핑 중단",f"기준: {now()} KST","","N/A 보고서를 보내지 않기 위해 분석을 중단했습니다.",f"시장 데이터 성공: {val['market_ok']}/{val['market_total']}",f"반도체 데이터 성공: {val['semi_ok']}/{val['semi_total']}",f"전체 성공률: {val['ratio']:.0%}","","성공한 데이터:"]
    for x in [*market,*semi]:
        if x.get("ok"): L.append(f"- {x.get('name')} {x.get('ticker','')}: {pct(x.get('pct'))} ({x.get('symbol',x.get('ticker',''))}/{x.get('src')})")
    L += ["","대표 실패:"] + ["- "+e for e in val.get("errors",[])[:8]]
    L.append("\n조치: 데이터 원천 문제입니다. 허접한 N/A 보고서보다 이 알림이 안전합니다.")
    return "\n".join(L)

def send(msg):
    token=os.getenv("TELEGRAM_BOT_TOKEN","").strip(); chat=os.getenv("TELEGRAM_CHAT_ID","").strip()
    if not token or not chat: raise RuntimeError("TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID 없음")
    parts=[]; cur=[]
    for line in msg.splitlines():
        if len("\n".join(cur+[line]))>3600 and cur: parts.append("\n".join(cur)); cur=[line]
        else: cur.append(line)
    if cur: parts.append("\n".join(cur))
    url=f"https://api.telegram.org/bot{token}/sendMessage"
    for i,p in enumerate(parts,1):
        text=(f"({i}/{len(parts)})\n" if len(parts)>1 else "")+p
        r=requests.post(url,json={"chat_id":chat,"text":text,"disable_web_page_preview":True},timeout=30)
        if r.status_code!=200: raise RuntimeError(f"텔레그램 실패 {r.status_code}: {r.text}")

def main():
    print("VERSION",VERSION)
    market,semi,up,down,val=collect_prices(); news=collect_news()
    print(json.dumps(val,ensure_ascii=False,indent=2)); print("NEWS",len(news))
    if not val["pass"]:
        msg=fail_msg(val,market,semi); print(msg); send(msg); return
    ctx=context(market,semi,up,down,news,val)
    txt,err=openai_report(ctx)
    msg=(txt+f"\n\n데이터 정상: {val['total_ok']}/{val['total']} / 버전: {VERSION}") if txt else fallback(ctx,err)
    print(msg[:5000]); send(msg)

if __name__ == "__main__": main()
