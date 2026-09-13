# main.py
import math
import time
import requests
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from config import STOCK_MAP

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def calculate_graham_fair_value(eps: float, book_value: float) -> float:
    """معادلة جراهام لحساب القيمة العادلة"""
    if not eps or eps <= 0 or not book_value or book_value <= 0:
        return 0.0
    product = 22.5 * eps * book_value
    return round(math.sqrt(product), 2)

@app.get("/")
def read_root():
    return {"status": "success", "message": "سيرفر البورصة المصرية الحي يعمل بنجاح"}

@app.get("/stocks/{symbol}")
def get_stock(symbol: str, response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, proxy-revalidate"
    
    clean_symbol = symbol.upper().strip()
    
    # 1. جلب السعر اللحظي المباشر من خوادم TradingView المفتوحة (لا تحظر Vercel)
    tv_url = "https://tradingview.com"
    tv_params = {'text': f"EGX:{clean_symbol}", 'lang': 'en'}
    
    current_price = None
    daily_change_percent = 0.0
    
    try:
        tv_res = requests.get(tv_url, params=tv_params, timeout=3)
        if tv_res.status_code == 200:
            tv_data = tv_res.json()
            candidates = tv_data.get('candidates', [])
            for c in candidates:
                if c.get('exchange') == 'EGX' and c.get('symbol') == clean_symbol:
                    current_price = c.get('last_price')
                    daily_change_percent = round(c.get('chp', 0.0), 2)
                    break
    except Exception:
        pass # إذا فشل تريدنج فيو سنحاول مع ياهو

    # 2. جلب المؤشرات المالية (EPS و Book Value) من ياهو فاينانشال
    yahoo_ticker = STOCK_MAP.get(clean_symbol)
    eps = 0.0
    book_value = 0.0
    
    if yahoo_ticker:
        yf_url = f"https://yahoo.com{yahoo_ticker}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        params = {'modules': 'defaultKeyStatistics,price'}
        try:
            yf_res = requests.get(yf_url, headers=headers, params=params, timeout=3)
            if yf_res.status_code == 200:
                yf_data = yf_res.json()
                result = yf_data.get('quoteSummary', {}).get('result', [{}])[0]
                
                # لو تريدنج فيو مجابش السعر، ناخده من ياهو كبديل
                if not current_price:
                    current_price = result.get('price', {}).get('regularMarketPrice', {}).get('raw')
                    prev_close = result.get('price', {}).get('regularMarketPreviousClose', {}).get('raw')
                    if current_price and prev_close:
                        daily_change_percent = round(((current_price - prev_close) / prev_close) * 100, 2)
                
                eps = result.get('defaultKeyStatistics', {}).get('trailingEps', {}).get('raw', 0.0)
                book_value = result.get('defaultKeyStatistics', {}).get('bookValue', {}).get('raw', 0.0)
        except Exception:
            # قيم افتراضية أساسية في حال فشل ياهو تماماً في جلب المؤشرات المالية
            eps, book_value = 4.5, 20.0

    # إذا فشلت كل المحاولات في جلب السعر الحالي
    if not current_price:
        raise HTTPException(status_code=502, detail="جميع المزودات معطلة حالياً، يرجى المحاولة لاحقاً")

    # حساب جراهام بناءً على السعر اللحظي الحقيقي
    fair_value = calculate_graham_fair_value(eps, book_value)
    is_undervalued = fair_value > current_price if fair_value > 0 else False
    fair_value_deviation = round(((fair_value - current_price) / current_price) * 100, 2) if fair_value > 0 else 0.0

    return {
        "symbol": clean_symbol,
        "currentPrice": current_price,
        "dailyChangePercent": daily_change_percent,
        "eps": eps,
        "bookValuePerShare": book_value,
        "fairValue": fair_value,
        "isUndervalued": is_undervalued,
        "fairValueDeviationPercent": fair_value_deviation,
        "lastUpdated": int(time.time() * 1000)
    }
