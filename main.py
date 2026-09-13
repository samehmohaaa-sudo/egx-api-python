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
    """معادلة جراهام القياسية لحساب القيمة العادلة للسهم"""
    if not eps or eps <= 0 or not book_value or book_value <= 0:
        return 0.0
    product = 22.5 * eps * book_value
    return round(math.sqrt(product), 2)

@app.get("/")
def read_root():
    return {"status": "success", "message": "سيرفر البورصة المصرية ببايثون يعمل بنجاح ومتوافق مع الموبايل"}

@app.get("/stocks/{symbol}")
def get_stock(symbol: str, response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, proxy-revalidate"
    
    clean_symbol = symbol.upper().strip()
    yahoo_ticker = STOCK_MAP.get(clean_symbol)

    if not yahoo_ticker:
        raise HTTPException(status_code=400, detail=f"رمز السهم غير مسجل: {clean_symbol}")

    # الرابط المصحح بدقة للاتصال بالـ API الخلفي لياهو فاينانشال
    url = f"https://yahoo.com{yahoo_ticker}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Referer': 'https://yahoo.com'
    }
    params = {
        'modules': 'price,defaultKeyStatistics'
    }

    try:
        res = requests.get(url, headers=headers, params=params, timeout=10)
        
        if res.status_code != 200:
            raise HTTPException(status_code=502, detail=f"المزود العالمي يرفض الطلب. كود الخطأ: {res.status_code}")
            
        data = res.json()
        result_list = data.get('quoteSummary', {}).get('result', [])
        
        if not result_list:
            raise HTTPException(status_code=502, detail="لم يتم العثور على بيانات لهذا السهم في البورصة العالمية")
            
        result = result_list[0]
        price_mod = result.get('price', {})
        key_stats = result.get('defaultKeyStatistics', {})

        # استخراج الأسعار بشكل آمن تماماً
        current_price = price_mod.get('regularMarketPrice', {}).get('raw') or price_mod.get('currentPrice', {}).get('raw')
        previous_close = price_mod.get('regularMarketPreviousClose', {}).get('raw')

        if not current_price:
            raise HTTPException(status_code=502, detail="فشل استخراج سعر السهم الحالي من البيانات المستلمة")

        daily_change_percent = 0.0
        if current_price and previous_close:
            daily_change_percent = round(((current_price - previous_close) / previous_close) * 100, 2)

        eps = key_stats.get('trailingEps', {}).get('raw', 0.0)
        book_value = key_stats.get('bookValue', {}).get('raw', 0.0)

        fair_value = calculate_graham_fair_value(eps, book_value)
        is_undervalued = fair_value > current_price if fair_value > 0 else False
        
        fair_value_deviation = 0.0
        if fair_value > 0:
            fair_value_deviation = round(((fair_value - current_price) / current_price) * 100, 2)

        return {
            "symbol": clean_symbol,
            "currentPrice": current_price,
            "dailyChangePercent": daily_change_percent,
            "dayLow": price_mod.get('regularMarketDayLow', {}).get('raw'),
            "dayHigh": price_mod.get('regularMarketDayHigh', {}).get('raw'),
            "eps": eps,
            "bookValuePerShare": book_value,
            "fairValue": fair_value,
            "isUndervalued": is_undervalued,
            "fairValueDeviationPercent": fair_value_deviation,
            "lastUpdated": int(time.time() * 1000)
        }

    except Exception as e:
        raise HTTPException(status_code=502, detail=f"خطأ في جلب البيانات: {str(e)}")
