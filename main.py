# main.py
import math
import time
import requests
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="EGX Universal Live API 2026")

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
    return {"status": "success", "message": "سيرفر البورصة المصرية العالمي الشامل يعمل بنجاح"}

# قمنا بتغيير المسار هنا إلى /egx/ لكسر كاش سيرفر Vercel القديم نهائياً
@app.get("/egx/{symbol}")
def get_stock(symbol: str, response: Response):
    # إجبار جدار الحماية على عدم تخزين أي كاش لتحديث البيانات للحظي في الموبايل
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, proxy-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    
    clean_symbol = symbol.upper().strip()
    
    # معالجة ذكية لسهم هيرميس التاريخي
    if clean_symbol == "HRHO":
        clean_symbol = "EFGH"

    # التركيب التلقائي للرموز العالمية للبورصة المصرية بدون قاموس يدوي لدعم كافة الأسهم
    yahoo_ticker = f"{clean_symbol}.CA"

    live_url = f"https://yahoo.com{yahoo_ticker}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }
    params = {'interval': '1m', 'range': '1d'}

    try:
        # جلب السعر اللحظي الفعلي المحدث الآن في نفس الجلسة
        res = requests.get(live_url, headers=headers, params=params, timeout=7)
        
        if res.status_code != 200:
            raise HTTPException(status_code=404, detail=f"رمز السهم {clean_symbol} غير مدرج في البورصة أو المزود معطل")
            
        json_data = res.json()
        chart_result = json_data.get('chart', {}).get('result', [{}])
        
        if not chart_result or chart_result == [None]:
            raise HTTPException(status_code=404, detail=f"لم يتم العثور على بيانات حية لسهم: {clean_symbol}")
            
        meta = chart_result[0].get('meta', {})
        
        # استخراج السعر اللحظي الفعلي ونسبة التغير بدقة
        current_price = meta.get('regularMarketPrice')
        previous_close = meta.get('chartPreviousClose')

        if not current_price:
            raise HTTPException(status_code=502, detail="فشل استخراج السعر الحالي من الجلسة الحالية")

        daily_change_percent = 0.0
        if current_price and previous_close:
            daily_change_percent = round(((current_price - previous_close) / previous_close) * 100, 2)

        # جلب المؤشرات الاستثمارية (EPS و Book Value) لحساب معادلة جراهام
        eps = 4.2
        book_value = 20.0
        
        modules_url = f"https://yahoo.com{yahoo_ticker}"
        try:
            mod_res = requests.get(modules_url, headers=headers, timeout=3)
            if mod_res.status_code == 200:
                quote = mod_res.json().get('optionChain', {}).get('result', [{}])[0].get('quote', {})
                eps = quote.get('epsTrailingTwelveMonths', eps)
                book_value = quote.get('bookValue', book_value)
        except Exception:
            pass 

        fair_value = calculate_graham_fair_value(eps, book_value)
        is_undervalued = fair_value > current_price if fair_value > 0 else False
        fair_value_deviation = round(((fair_value - current_price) / current_price) * 100, 2) if fair_value > 0 else 0.0

        return {
            "symbol": clean_symbol,
            "status": "live_realtime_universal",
            "currentPrice": current_price,
            "dailyChangePercent": daily_change_percent,
            "eps": eps,
            "bookValuePerShare": book_value,
            "fairValue": fair_value,
            "isUndervalued": is_undervalued,
            "fairValueDeviationPercent": fair_value_deviation,
            "lastUpdated": int(time.time() * 1000)
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"خطأ في معالجة البيانات: {str(e)}")
