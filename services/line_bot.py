import os
import asyncio
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, PushMessageRequest
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from dotenv import load_dotenv

from database.models import get_db, User

load_dotenv()

channel_secret = os.getenv('LINE_CHANNEL_SECRET', 'YOUR_SECRET')
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', 'YOUR_TOKEN')

configuration = Configuration(access_token=channel_access_token)
handler = WebhookHandler(channel_secret)

async def send_push_message(user_id: str, text: str):
    if channel_access_token == 'YOUR_TOKEN' or not channel_access_token:
        print(f"Mock LINE Push to {user_id}: {text[:50]}...")
        return
        
    def _send():
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.push_message(
                PushMessageRequest(
                    to=user_id,
                    messages=[TextMessage(text=text)]
                )
            )
    await asyncio.to_thread(_send)

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text.strip()
    
    # 獲取 DB session
    db_gen = get_db()
    db = next(db_gen)
    
    try:
        user = db.query(User).filter(User.line_user_id == user_id).first()
        if not user:
            user = User(line_user_id=user_id)
            db.add(user)
            db.commit()
            db.refresh(user)
        import re
        
        add_match = re.match(r'^(?:新增追蹤|新增|追蹤|\+)\s*(.+)$', user_message, re.IGNORECASE)
        del_match = re.match(r'^(?:刪除追蹤|刪除|取消|\-)\s*(.+)$', user_message, re.IGNORECASE)
        email_match = re.match(r'^(?:設定信箱|信箱|email)\s*(.+)$', user_message, re.IGNORECASE)
        query_match = re.match(r'^(?:查詢|分析)\s*(.+)$', user_message, re.IGNORECASE)

        if add_match:
            stocks_str = add_match.group(1)
            # 支援用逗號或多個空白分隔的多個代碼
            stock_codes = [s for s in re.split(r'[\s,]+', stocks_str.strip()) if s]
            
            current_tracking = user.tracking_stocks.split(",") if user.tracking_stocks else []
            added = []
            existed = []
            
            for code in stock_codes:
                if code not in current_tracking:
                    current_tracking.append(code)
                    added.append(code)
                else:
                    existed.append(code)
                    
            if added:
                user.tracking_stocks = ",".join(filter(None, current_tracking))
                db.commit()
                
            reply_parts = []
            if added:
                reply_parts.append(f"✅ 已成功加入：{', '.join(added)}")
            if existed:
                reply_parts.append(f"⚠️ 已經在清單中：{', '.join(existed)}")
            reply_parts.append(f"目前追蹤清單：{user.tracking_stocks}")
            reply_text = "\n".join(reply_parts)

        elif del_match:
            stocks_str = del_match.group(1)
            stock_codes = [s for s in re.split(r'[\s,]+', stocks_str.strip()) if s]
            
            current_tracking = user.tracking_stocks.split(",") if user.tracking_stocks else []
            removed = []
            not_found = []
            
            for code in stock_codes:
                if code in current_tracking:
                    current_tracking.remove(code)
                    removed.append(code)
                else:
                    not_found.append(code)
                    
            if removed:
                user.tracking_stocks = ",".join(filter(None, current_tracking))
                db.commit()
                
            reply_parts = []
            if removed:
                reply_parts.append(f"✅ 已成功移除：{', '.join(removed)}")
            if not_found:
                reply_parts.append(f"⚠️ 不在清單中：{', '.join(not_found)}")
            reply_parts.append(f"目前追蹤清單：{user.tracking_stocks if user.tracking_stocks else '無'}")
            reply_text = "\n".join(reply_parts)

        elif email_match:
            email = email_match.group(1).strip()
            user.email = email
            db.commit()
            reply_text = f"✅ 已成功設定您的信箱為：{email}\n未來重大通知將同步發送至此信箱。"

        elif query_match:
            stock_code = query_match.group(1).strip()
            reply_text = f"⏳ 正在為您查詢並分析 {stock_code}，請稍候..."
            
            async def _do_query():
                from services.data_fetcher import data_fetcher
                from services.llm_strategy import strategy_engine
                
                try:
                    data = await data_fetcher.get_daily_data(stock_code)
                    if not data:
                        await send_push_message(user_id, f"❌ 找不到 {stock_code} 的資料，請確認代碼是否正確。")
                        return
                    
                    strategy = await strategy_engine.generate_strategy(data)
                    
                    msg = f"📊 【{stock_code} 即時分析】\n"
                    msg += f"收盤價：{data.get('close')}\n"
                    msg += f"趨勢：{strategy.get('trend_analysis', '無')}\n\n"
                    msg += f"💡 建議：{strategy.get('strategy_advice', '無')}\n"
                    msg += f"🔥 動作：{strategy.get('action', '無')}"
                    if 'risk_warning' in strategy:
                        msg += f"\n⚠️ 風險：{strategy.get('risk_warning')}"
                        
                    await send_push_message(user_id, msg)
                except Exception as e:
                    print(f"Query error: {e}")
                    await send_push_message(user_id, f"❌ 查詢時發生錯誤，請稍後再試。")
                    
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_do_query())
            except Exception as e:
                print(f"Failed to create background task: {e}")

        else:
             reply_text = "歡迎使用台股投資策略機器人！\n支援更彈性的指令：\n- 新增多檔：新增 2330 0050\n- 刪除多檔：刪除 2330,0050\n- 設定信箱 email@gmail.com\n- 即時查詢：查詢 2330"
             
        if channel_access_token != 'YOUR_TOKEN' and channel_access_token:
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply_text)]
                    )
                )
        else:
            print(f"Mock LINE Reply to {user_id}: {reply_text}")
    finally:
        db.close()
