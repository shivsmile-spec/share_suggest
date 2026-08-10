import json, math, time, subprocess, sys
from datetime import datetime
subprocess.check_call([sys.executable,"-m","pip","install","-q","-U","yfinance","curl_cffi","pandas"])
import pandas as pd, yfinance as yf

SYMBOL_URL="https://raw.githubusercontent.com/ganeshbiyer/Nse_Historical_Data/main/nifty500_symbols.csv"
symbols_df=pd.read_csv(SYMBOL_URL)
col=next(c for c in symbols_df.columns if "symbol" in c.lower())
symbols=[str(x).strip().upper() for x in symbols_df[col].dropna() if str(x).strip()]
symbols=sorted(set(symbols))
tickers=[s+".NS" for s in symbols]
print("Nifty 500 symbols:",len(symbols))

# 1 year OHLCV in bulk. yfinance uses curl_cffi in modern releases and is much more resilient than browser requests.
hist=yf.download(tickers=tickers,period="1y",interval="1d",group_by="ticker",auto_adjust=False,threads=True,progress=False)

def calc_rsi(c,n=14):
    if len(c)<n+1:return None
    d=c.diff().dropna();g=d.clip(lower=0);l=-d.clip(upper=0)
    ag=g.rolling(n).mean().iloc[-1];al=l.rolling(n).mean().iloc[-1]
    return 100 if al==0 else float(100-100/(1+ag/al))
def calc_one(sym):
    t=sym+".NS"
    try:
        h=hist[t].dropna()
        close=h["Close"].astype(float); vol=h["Volume"].astype(float)
        if len(close)<30:return None
        p=float(close.iloc[-1]); prev=float(close.iloc[-2]) if len(close)>1 else None
        ma50=float(close.tail(50).mean()) if len(close)>=50 else None
        ma200=float(close.tail(200).mean()) if len(close)>=200 else None
        e12=close.ewm(span=12,adjust=False).mean().iloc[-1];e26=close.ewm(span=26,adjust=False).mean().iloc[-1]
        macd=float(e12-e26);rsi=calc_rsi(close)
        mom=float((p/close.iloc[-127]-1)*100) if len(close)>=127 else None
        rets=close.pct_change().dropna().tail(20)
        volatility=float(rets.std()*math.sqrt(252)*100) if len(rets)>5 else None
        hi=float(close.max());lo=float(close.min());range_pos=float((p-lo)/(hi-lo)*100) if hi>lo else 50
        av=float(vol.tail(20).mean());volratio=float(vol.iloc[-1]/av) if av else None
        score=50;checks=[]
        def add(f,reading,signal,w,delta):
            nonlocal score
            checks.append({"factor":f,"reading":reading,"signal":signal,"weight":w})
            score+=delta*w/2
        add("Trend vs 200 DMA", "Above" if ma200 and p>ma200 else "Below" if ma200 else "Unavailable", "Bullish" if ma200 and p>ma200 else "Bearish" if ma200 else "Unavailable",20,1 if ma200 and p>ma200 else -1 if ma200 else 0)
        add("RSI", f"{rsi:.1f}" if rsi is not None else "Unavailable", "Oversold" if rsi is not None and rsi<30 else "Overbought" if rsi is not None and rsi>70 else "Positive" if rsi is not None and rsi>=50 else "Weak" if rsi is not None else "Unavailable",15,.5 if rsi is not None and rsi<30 else -1 if rsi is not None and rsi>70 else 1 if rsi is not None and rsi>=50 else -.5 if rsi is not None else 0)
        add("MACD",f"{macd:.2f}","Positive" if macd>0 else "Negative",10,1 if macd>0 else -1)
        add("6-month momentum",f"{mom:.1f}%" if mom is not None else "Unavailable","Strong" if mom is not None and mom>10 else "Positive" if mom is not None and mom>0 else "Negative",10,1 if mom and mom>10 else .5 if mom and mom>0 else -1 if mom is not None else 0)
        score=max(0,min(100,score))
        return {"symbol":sym,"company":sym,"price":p,"change":((p-prev)/prev*100 if prev else None),"rsi":rsi,"ma50":ma50,"ma200":ma200,"macd":macd,"momentum6m":mom,"volatility":volatility,"volume":float(vol.iloc[-1]),"volumeVsAvg":("Above 20-day average" if volratio and volratio>1 else "Below 20-day average"),"rangePosition":range_pos,"pe":None,"forwardPE":None,"roe":None,"roa":None,"debtEquity":None,"margin":None,"revenueGrowth":None,"dividendYield":None,"score":score,"verdict":"Potentially attractive" if score>=70 else "Positive / watch" if score>=55 else "Neutral / mixed" if score>=40 else "High risk / weak","reason":"Technical score based on trend, RSI, MACD, momentum and risk. Fundamental fields are populated when a reliable fundamentals snapshot is available.","checks":checks}
    except Exception as e:
        print("skip",sym,e);return None

out=[]
for i,s in enumerate(symbols,1):
    x=calc_one(s)
    if x:out.append(x)
    if i%50==0:print(i,"/",len(symbols))
data={"updated":datetime.now().strftime("%d %b %Y, %I:%M %p IST"),"count":len(out),"universe":"NIFTY 500","stocks":out}
with open("data/stocks.json","w",encoding="utf-8") as f:json.dump(data,f,ensure_ascii=False)
print("Saved",len(out))
