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
    return {"status": "success", "message": "سيرفر البورصة المصرية اللحظي الحقيقي يعمل بنجاح"}

@app.get("/stocks/{symbol}")
def get_stock(symbol: str, response: Response):
    # إجبار السيرفر على منع الكاش تماماً لتحديث البيانات اللحظية في التطبيق
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, proxy-revalidate"
    
    clean_symbol = symbol.upper().strip()
    yahoo_ticker = STOCK_MAP.get(clean_symbol)

    if not yahoo_ticker:
        raise HTTPException(status_code=400, detail=f"رمز السهم غير مسجل: {clean_symbol}")

    # الاستعانة بمحرك الأسعار المفتوح المباشر (تخطي حظر خوادم Vercel تماماً وبدون بروكسي)
    url = f"https://yahoo.com{yahoo_ticker}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }

    try:
        res = requests.get(url, headers=headers, timeout=5)
        
        if res.status_code != 200:
            raise HTTPException(status_code=502, detail="فشل الاتصال بالمزود العالمي للأسعار")
            
        json_data = res.json()
        option_chain = json_data.get('optionChain', {})
        result_list = option_chain.get('result', [])
        
        if not result_list:
            raise HTTPException(status_code=502, detail="لم يتم العثور على بيانات حية لهذا السهم")
            
        quote = result_list[0].get('quote', {})
        
        # استخراج السعر اللحظي الحالي ونسبة التغير بدقة وبدون أي داتا قديمة
        current_price = quote.get('regularMarketPrice') or quote.get('currentPrice')
        daily_change_percent = round(quote.get('regularMarketChangePercent', 0.0), 2)
        
        if not current_price:
            raise HTTPException(status_code=502, detail="فشل استخراج السعر اللحظي الحالي")

        # استخراج المؤشرات الأساسية لحساب جراهام (EPS و القيمة الدفترية)
        eps = quote.get('epsTrailingTwelveMonths', 0.0)
        book_value = quote.get('bookValue', 0.0)

        # حساب القيمة العادلة بناءً على السعر اللحظي الجديد
        fair_value = calculate_graham_fair_value(eps, book_value)
        is_undervalued = fair_value > current_price if fair_value > 0 else False
        
        fair_value_deviation = 0.0
        if fair_value > 0:
            fair_value_deviation = round(((fair_value - current_price) / current_price) * 100, 2)

        return {
            "symbol": clean_symbol,
            "currentPrice": current_price,
            "dailyChangePercent": daily_change_percent,
            "dayLow": quote.get('regularMarketDayLow'),
            "dayHigh": quote.get('regularMarketDayHigh'),
            "eps": eps,
            "bookValuePerShare": book_value,
            "fairValue": fair_value,
            "isUndervalued": is_undervalued,
            "fairValueDeviationPercent": fair_value_deviation,
            "lastUpdated": int(time.time() * 1000)
        }

    except Exception as e:
        raise HTTPException(status_code=502, detail=f"خطأ في جلب الأسعار اللحظية: {str(e)}")
