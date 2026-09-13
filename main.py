# main.py
import time
import requests
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "success", "message": "سيرفر البورصة المصرية اللحظي الحقيقي يعمل بنجاح"}

@app.get("/stocks/{symbol}")
def get_stock(symbol: str, response: Response):
    # إجبار السيرفر على إلغاء الكاش تماماً لتحديث البيانات للحظي في الموبايل
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, proxy-revalidate"
    
    clean_symbol = symbol.upper().strip()

    # الاتصال المباشر بمحرك أسعار البحث العالمي لـ TradingView (مسموح به على Vercel ولا يُحظر)
    url = "https://tradingview.com"
    params = {
        'text': f"EGX:{clean_symbol}",
        'lang': 'en'
    }

    try:
        res = requests.get(url, params=params, timeout=5)
        
        if res.status_code != 200:
            raise HTTPException(status_code=502, detail="فشل الاتصال بمزود الأسعار العالمي")
            
        data = res.json()
        candidates = data.get('candidates', [])
        
        stock_info = None
        for candidate in candidates:
            if candidate.get('exchange') == 'EGX' and candidate.get('symbol') == clean_symbol:
                stock_info = candidate
                break
                
        if not stock_info:
            raise HTTPException(status_code=404, detail=f"رمز السهم غير موجود في البورصة المصرية: {clean_symbol}")

        # استخراج السعر الحالي الحي ونسبة التغير الفعلي في نفس الثانية بدون داتا قديمة
        current_price = stock_info.get('last_price')
        daily_change_percent = round(stock_info.get('chp', 0.0), 2)

        if not current_price:
            raise HTTPException(status_code=502, detail="فشل استخراج السعر الحقيقي للسهم")

        return {
            "symbol": clean_symbol,
            "name": stock_info.get('description'),
            "currentPrice": current_price,
            "dailyChangePercent": daily_change_percent,
            "currency": stock_info.get('currency'),
            "lastUpdated": int(time.time() * 1000)
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"خطأ في جلب الأسعار اللحظية: {str(e)}")
