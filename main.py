# main.py
import os
import math
import time
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
from config import STOCK_MAP

# حل مشكلة النظام المقروء فقط (Read-only) على خوادم Vercel وتوجيه الكاش لمجلد الـ /tmp
os.environ["YFINANCE_CACHE_DIR"] = "/tmp/py-yfinance"

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
    return {"status": "success", "message": "سيرفر البورصة المصرية اللحظي الحقيقي يعمل بنجاح"}

@app.get("/stocks/{symbol}")
def get_stock(symbol: str, response: Response):
    # إجبار السيرفر على منع الكاش لضمان تسليم بيانات حية ودقيقة
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, proxy-revalidate"
    
    clean_symbol = symbol.upper().strip()
    yahoo_ticker = STOCK_MAP.get(clean_symbol)

    if not yahoo_ticker:
        raise HTTPException(status_code=400, detail=f"رمز السهم غير مسجل: {clean_symbol}")

    try:
        # استخدام المكتبة الرسمية مباشرة والتي تتكفل ببناء الرابط الصحيح تلقائياً بدون أخطاء إملائية
        ticker = yf.Ticker(yahoo_ticker)
        info = ticker.info

        # استخراج الأسعار بشكل آمن
        current_price = info.get('regularMarketPrice') or info.get('currentPrice')
        previous_close = info.get('regularMarketPreviousClose') or info.get('previousClose')

        if not current_price:
            raise HTTPException(status_code=502, detail="فشل استخراج السعر الحالي من المزود")

        daily_change_percent = 0.0
        if current_price and previous_close:
            daily_change_percent = round(((current_price - previous_close) / previous_close) * 100, 2)

        eps = info.get('trailingEps', 0.0)
        book_value = info.get('bookValue', 0.0)

        # حساب معادلة جراهام الاستثمارية
        fair_value = calculate_graham_fair_value(eps, book_value)
        is_undervalued = fair_value > current_price if fair_value > 0 else False
        
        fair_value_deviation = 0.0
        if fair_value > 0:
            fair_value_deviation = round(((fair_value - current_price) / current_price) * 100, 2)

        return {
            "symbol": clean_symbol,
            "currentPrice": current_price,
            "dailyChangePercent": daily_change_percent,
            "dayLow": info.get('regularMarketDayLow') or info.get('dayLow'),
            "dayHigh": info.get('regularMarketDayHigh') or info.get('dayHigh'),
            "eps": eps,
            "bookValuePerShare": book_value,
            "fairValue": fair_value,
            "isUndervalued": is_undervalued,
            "fairValueDeviationPercent": fair_value_deviation,
            "lastUpdated": int(time.time() * 1000)
        }

    except Exception as e:
        raise HTTPException(status_code=502, detail=f"خطأ في جلب البيانات: {str(e)}")
