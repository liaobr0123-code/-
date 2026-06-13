import asyncio
from datetime import datetime
from database.models import SessionLocal, User
from services.data_fetcher import data_fetcher
from services.llm_strategy import strategy_engine
from services.email_calendar import email_calendar_service
from services.line_bot import send_push_message

alert_cache = {}

async def intraday_monitor():
    print("啟動盤中監控模組...")
    while True:
        now = datetime.now()
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
                        
                        notify_tasks = []
                        for u in users:
                            if stock_code in (u.tracking_stocks or "") or stock_code == "TAIEX":
                                notify_tasks.append(send_push_message(u.line_user_id, alert_msg))
                                if u.email:
                                    notify_tasks.append(email_calendar_service.send_email(u.email, f"【緊急警報】{stock_code} 波動通知", alert_msg))
                                    
                        await asyncio.gather(*notify_tasks)
                        alert_cache[cache_key] = True 
                        
                tasks = [check_stock(s) for s in all_tracking]
                await asyncio.gather(*tasks)
            except Exception as e:
                print(f"Intraday Monitor Error: {e}")
            finally:
                db.close()
                
        # 每分鐘輪詢一次
        await asyncio.sleep(60)
