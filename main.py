# main.py
import math
import time
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
from config import STOCK_MAP

app = FastAPI()

# تفعيل الـ CORS لربط تطبيق الموبايل بدون أي مشاكل أمنية
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
    return {"status": "success", "message": "سيرفر البورصة المصرية الذكي ببايثون يعمل بنجاح ومستعد للموبايل"}

@app.get("/stocks/{symbol}")
def get_stock(symbol: str, response: Response):
    # إجبار السيرفر على منع الكاش ليرى مستخدم الموبايل أسعاراً حية ودقيقة
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, proxy-revalidate"
    
    clean_symbol = symbol.upper().strip()
    yahoo_ticker = STOCK_MAP.get(clean_symbol)

    if not yahoo_ticker:
        raise HTTPException(status_code=400, detail=f"رمز السهم غير مسجل في السيرفر: {clean_symbol}")

    try:
        # جلب البيانات عبر مكتبة yfinance مع نظام التمويه التلقائي المانع للحظر
        ticker = yf.Ticker(yahoo_ticker)
        info = ticker.info

        current_price = info.get('regularMarketPrice') or info.get('currentPrice')
        previous_close = info.get('regularMarketPreviousClose') or info.get('previousClose')

        if not current_price:
            raise HTTPException(status_code=502, detail="فشل في سحب السعر الحالي من خوادم البورصة العالمية")

        daily_change_percent = 0.0
        if current_price and previous_close:
            daily_change_percent = round(((current_price - previous_close) / previous_close) * 100, 2)

        eps = info.get('trailingEps')
        book_value = info.get('bookValue')

        # العمليات الحسابية ومقارنات جراهام الاستثمارية لتطبيقك
        fair_value = calculate_graham_fair_value(eps, book_value)
        is_undervalued = fair_value > current_price if fair_value > 0 else False
        
        fair_value_deviation = 0.0
        if fair_value > 0:
            fair_value_deviation = round(((fair_value - current_price) / current_price) * 100, 2)

        # المخرجات بصيغة JSON خفيفة وسريعة جداً ومثالية لتطبيق الموبايل
        return {
            "symbol": clean_symbol,
            "currentPrice": current_price,
            "dailyChangePercent": daily_change_percent,
            "dayLow": info.get('regularMarketDayLow'),
            "dayHigh": info.get('regularMarketDayHigh'),
            "eps": eps,
            "bookValuePerShare": book_value,
            "fairValue": fair_value,
            "isUndervalued": is_undervalued,
            "fairValueDeviationPercent": fair_value_deviation,
            "lastUpdated": int(time.time() * 1000)
        }

    except Exception as e:
        raise HTTPException(status_code=502, detail=f"خطأ في الاتصال بالبورصة: {str(e)}")
