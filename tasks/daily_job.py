import asyncio
from datetime import datetime
from database.models import SessionLocal, User
from services.data_fetcher import data_fetcher
from services.llm_strategy import strategy_engine
from services.email_calendar import email_calendar_service
from services.line_bot import send_push_message

async def process_user(user: User):
    market_data = await data_fetcher.get_daily_data("TAIEX")
    market_strategy = await strategy_engine.generate_strategy(market_data)
    
    report_lines = []
    report_lines.append(f"📈 【大盤今日策略 ({datetime.now().strftime('%Y-%m-%d')})】")
    report_lines.append(f"分析：{market_strategy.get('trend_analysis', '無')}")
    report_lines.append(f"建議：{market_strategy.get('strategy_advice', '無')} ({market_strategy.get('action', 'WATCH')})")
    report_lines.append("-" * 20)
    
    if user.tracking_stocks:
        stocks = user.tracking_stocks.split(",")
        async def fetch_and_analyze(stock_code):
            data = await data_fetcher.get_daily_data(stock_code)
            strategy = await strategy_engine.generate_strategy(data)
            return stock_code, data, strategy
            
        tasks = [fetch_and_analyze(s) for s in stocks if s]
        results = await asyncio.gather(*tasks)
        
        for stock_code, data, strategy in results:
            if not data:
                continue
            report_lines.append(f"🎯 【{stock_code}】 收盤: {data.get('close')}")
            report_lines.append(f"分析：{strategy.get('trend_analysis', '無')}")
            report_lines.append(f"建議：{strategy.get('strategy_advice', '無')} ({strategy.get('action', 'WATCH')})")
            report_lines.append("-" * 20)

    full_report = "\n".join(report_lines)
    
    await send_push_message(user.line_user_id, full_report)
    
    if user.email:
        await email_calendar_service.send_email(user.email, f"{datetime.now().date()} 股市每日策略報告", full_report)
        if market_strategy.get('action') in ['BUY', 'SELL']:
            await email_calendar_service.add_calendar_event(
                user.email, 
                f"台股大盤關鍵轉折: {market_strategy.get('action')}",
                market_strategy.get('trend_analysis', '')
            )

async def daily_morning_routine():
    print(f"[{datetime.now()}] 開始執行每日晨間策略生成任務...")
    db = SessionLocal()
    try:
        users = db.query(User).all()
        tasks = [process_user(u) for u in users]
        await asyncio.gather(*tasks)
    except Exception as e:
        print(f"Daily Job Error: {e}")
    finally:
        db.close()
    print(f"[{datetime.now()}] 每日晨間任務完成。")
