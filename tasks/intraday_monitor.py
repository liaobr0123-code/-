import asyncio
from datetime import datetime, timezone, timedelta
from database.models import SessionLocal, User
from services.data_fetcher import data_fetcher
from services.llm_strategy import strategy_engine
from services.email_calendar import email_calendar_service
from services.line_bot import send_push_message

alert_cache = {}

async def intraday_monitor():
    print("啟動盤中監控模組...")
    # 設定台灣時區 (UTC+8)
    tw_tz = timezone(timedelta(hours=8))
    
    while True:
        now = datetime.now(tw_tz)
        # 僅在交易時間執行 (台灣時間 09:00 - 13:30)，週一到週五
        if 9 <= now.hour <= 13 and now.weekday() < 5:
            db = SessionLocal()
            try:
                users = db.query(User).all()
                all_tracking = set()
                for u in users:
                    if u.tracking_stocks:
                        all_tracking.update(u.tracking_stocks.split(","))
                all_tracking.discard("")
                all_tracking.add("TAIEX")
                
                async def check_stock(stock_code):
                    cache_key = f"{stock_code}_{now.date()}"
                    if cache_key in alert_cache:
                        return 
                        
                    data = await data_fetcher.get_intraday_data(stock_code)
                    if data and abs(data.get('change_pct', 0)) >= 3.0:
                        print(f"【警報】{stock_code} 發生劇烈波動: {data['change_pct']}%")
                        strategy = await strategy_engine.generate_emergency_strategy(data)
                        
                        alert_msg = f"⚠️ 【緊急警報】{stock_code} 劇烈波動 ({data['change_pct']}%)\nAI 應變策略：{strategy.get('advice', '無')}"
                        
                        if data.get('recent_news'):
                            alert_msg += f"\n\n📰 【近期重要新聞】"
                            for news_title in data['recent_news'][:3]:
                                alert_msg += f"\n- {news_title}"
                        
                        notify_tasks = []
                        for u in users:
                            if stock_code in (u.tracking_stocks or "") or stock_code == "TAIEX":
                                notify_tasks.append(send_push_message(u.line_user_id, alert_msg))
                                if u.email:
                                    notify_tasks.append(email_calendar_service.send_email(u.email, f"【緊急警報】{stock_code} 波動通知", alert_msg))
                                    
                        await asyncio.gather(*notify_tasks)
                        alert_cache[cache_key] = True 
                        
                # 依序檢查每檔股票，避免同時呼叫太多次 Gemini API 導致 429 錯誤
                for s in all_tracking:
                    await check_stock(s)
                    await asyncio.sleep(2) # 每次檢查間隔 2 秒，降低 API 請求頻率
            except Exception as e:
                print(f"Intraday Monitor Error: {e}")
            finally:
                db.close()
                
        # 每分鐘輪詢一次
        await asyncio.sleep(60)
