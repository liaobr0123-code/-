import os
import requests
import pandas as pd
import asyncio
from datetime import datetime

class DataFetcher:
    def __init__(self):
        self.api_key = os.getenv('FUGLE_API_KEY', '')
        self.headers = {"X-API-KEY": self.api_key}

    def _format_ticker(self, stock_code: str) -> str:
        # 將 yfinance 的格式轉為 Fugle 的格式
        if stock_code.upper() in ["TAIEX", "^TWII", "大盤"]:
            return "IX0001"
        return stock_code.replace(".TW", "")

    async def get_daily_data(self, stock_code: str, period="3mo") -> dict:
        """獲取日K與技術指標"""
        ticker = self._format_ticker(stock_code)
        
        def fetch():
            # Fugle 預設給最近一年資料，足夠算 60MA
            url = f"https://api.fugle.tw/marketdata/v1.0/stock/historical/candles/{ticker}"
            res = requests.get(url, headers=self.headers)
            if res.status_code != 200:
                print(f"Fugle API error: {res.text}")
                return None
            
            data = res.json().get("data", [])
            if not data:
                return None
                
            # data 預設由新到舊排，轉換為 DataFrame 並反轉成由舊到新
            df = pd.DataFrame(data)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
            
            # 確保欄位名稱與後續計算相容
            df.rename(columns={'close': 'Close', 'volume': 'Volume'}, inplace=True)
            
            # 計算簡單的均線 (MA)
            df['MA5'] = df['Close'].rolling(window=5).mean()
            df['MA20'] = df['Close'].rolling(window=20).mean()
            df['MA60'] = df['Close'].rolling(window=60).mean()
            
            # 計算 RSI (簡單版)
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            # 取最後一筆資料
            last_row = df.iloc[-1]
            
            # 轉換近5日資料
            recent_5_days = df[['date', 'Close']].tail(5).to_dict('records')
            recent_5_str = ", ".join([f"{row['date'].strftime('%Y-%m-%d')}: {row['Close']:.2f}" for row in recent_5_days])
            
            return {
                "stock_code": stock_code,
                "date": last_row['date'].strftime('%Y-%m-%d'),
                "close": round(last_row['Close'], 2),
                "volume": int(last_row['Volume']),
                "ma_5": round(last_row['MA5'], 2) if not pd.isna(last_row['MA5']) else None,
                "ma_20": round(last_row['MA20'], 2) if not pd.isna(last_row['MA20']) else None,
                "ma_60": round(last_row['MA60'], 2) if not pd.isna(last_row['MA60']) else None,
                "rsi_14": round(last_row['RSI'], 2) if not pd.isna(last_row['RSI']) else None,
                "price_history_json": recent_5_str
            }
            
        return await asyncio.to_thread(fetch)

    async def get_intraday_data(self, stock_code: str) -> dict:
        """獲取盤中即時報價"""
        ticker = self._format_ticker(stock_code)
        
        def fetch():
            url = f"https://api.fugle.tw/marketdata/v1.0/stock/intraday/quote/{ticker}"
            res = requests.get(url, headers=self.headers)
            if res.status_code != 200:
                return None
            
            data = res.json()
            current_price = data.get('closePrice', 0)
            change_pct = data.get('changePercent', 0)
            
            return {
                "stock_code": stock_code,
                "current_price": round(current_price, 2),
                "change_pct": round(change_pct, 2)
            }
            
        return await asyncio.to_thread(fetch)

data_fetcher = DataFetcher()
