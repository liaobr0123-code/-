import os
import asyncio
from fastapi import FastAPI, Request, HTTPException
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from linebot.v3.exceptions import InvalidSignatureError

from services.line_bot import handler
from tasks.daily_job import daily_morning_routine
from tasks.intraday_monitor import intraday_monitor
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Stock Strategy Line Bot")

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def startup_event():
    # 設定每日 07:00 執行
    scheduler.add_job(daily_morning_routine, CronTrigger(hour=7, minute=0, timezone='Asia/Taipei'))
    scheduler.start()
    
    # 啟動盤中背景監控
    asyncio.create_task(intraday_monitor())
    
    print("======================================")
    print("系統啟動成功！排程任務與監控已載入。")
    print("======================================")

@app.post("/webhook/line")
async def line_webhook(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_str = body.decode("utf-8")
    
    try:
        handler.handle(body_str, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        print(f"Webhook Error: {e}")
        
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "Stock Strategy Line Bot is running."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
