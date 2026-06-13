import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# 設定 Gemini API Key
api_key = os.getenv("GEMINI_API_KEY")
if api_key and api_key != "your_gemini_api_key_here":
    genai.configure(api_key=api_key)

SYSTEM_PROMPT = """
你是一位擁有 20 年經驗的台股頂尖技術分析師與量化交易員。
你的專長是透過 K 線型態、價量關係以及技術指標來判讀市場情緒，並提供客觀、紀律嚴明的投資策略建議。

【分析準則】
1. 必須關注「價量關係」與「技術指標」。
2. 必須綜合考量傳入的「近期新聞消息」，判斷市場情緒與潛在利多/利空。
3. 判斷趨勢方向與重要支撐/壓力位。
4. 策略建議必須包含明確的「操作方向」(觀望、分批建倉、突破追價、嚴格停損)。
5. 語氣需專業、冷靜。

【輸出格式要求】
請務必以純 JSON 格式輸出，不要包含 Markdown 語法或任何其他說明文字，格式如下：
{
  "trend_analysis": "針對 K 線與指標的整體走向分析 (約 100-150 字)",
  "key_observations": ["關鍵觀察點 1", "關鍵觀察點 2"],
  "strategy_advice": "今日具體的投資策略建議 (約 50-100 字)",
  "action": "BUY | SELL | HOLD | WATCH",
  "risk_warning": "風險提示與停損防守建議"
}
"""

class StrategyEngine:
    def __init__(self):
        self.use_system_prompt_in_user = False
        try:
            self.model = genai.GenerativeModel(
                'gemini-2.5-flash',
                system_instruction=SYSTEM_PROMPT,
                generation_config={"response_mime_type": "application/json"}
            )
        except Exception as e:
            print(f"Model init warning: {e}")
            self.model = genai.GenerativeModel('gemini-2.5-flash')
            self.use_system_prompt_in_user = True

    async def generate_strategy(self, data: dict) -> dict:
        if not data:
            return {}
            
        user_prompt = f"""
請分析以下標的今日狀態：
- 標的名稱：{data.get('stock_code')}
- 交易日期：{data.get('date')}
- 近期價格走勢：{data.get('price_history_json')}
- 技術指標狀態：
  - 收盤價: {data.get('close')}
  - 5日均線 (5MA): {data.get('ma_5')}
  - 20日均線 (20MA): {data.get('ma_20')}
  - 60日均線 (60MA): {data.get('ma_60')}
  - RSI (14日): {data.get('rsi_14')}
- 近期市場新聞：
{chr(10).join(data.get('recent_news', [])) if data.get('recent_news') else '無最新新聞'}
  
請綜合技術面與消息面，依照 System Prompt 要求的 JSON 格式回傳。
"""
        if self.use_system_prompt_in_user:
            user_prompt = SYSTEM_PROMPT + "\n\n" + user_prompt
        try:
            response = await self.model.generate_content_async(user_prompt)
            # 若無 response_mime_type 支援，可能會帶有 ```json 前綴，故簡單處理
            text = response.text.replace('```json', '').replace('```', '').strip()
            return json.loads(text)
        except Exception as e:
            print(f"LLM Error: {e}")
            return {
                "trend_analysis": "策略生成失敗",
                "strategy_advice": f"無法獲取策略: {str(e)}",
                "action": "WATCH"
            }

    async def generate_emergency_strategy(self, data: dict) -> dict:
        if not data:
             return {}
             
        user_prompt = f"""
【緊急變動通知】
標的 {data.get('stock_code')} 目前發生劇烈波動！
目前價格：{data.get('current_price')}
漲跌幅：{data.get('change_pct')}%

近期市場新聞參考：
{chr(10).join(data.get('recent_news', [])) if data.get('recent_news') else '無最新新聞'}

請綜合波動情況與近期新聞，給予緊急應變策略。
輸出格式要求(純JSON):
{{
  "trend_analysis": "針對此異常波動的快速判讀",
  "advice": "緊急處置建議 (如: 減碼、停損、或是假跌破買進)",
  "action": "BUY | SELL | HOLD | WATCH"
}}
"""
        if self.use_system_prompt_in_user:
            user_prompt = SYSTEM_PROMPT + "\n\n" + user_prompt
        try:
            response = await self.model.generate_content_async(user_prompt)
            text = response.text.replace('```json', '').replace('```', '').strip()
            return json.loads(text)
        except Exception as e:
            print(f"LLM Error: {e}")
            return {"advice": f"系統異常，請留意風險: {str(e)}"}

strategy_engine = StrategyEngine()
