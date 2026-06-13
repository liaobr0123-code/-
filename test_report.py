import asyncio
import os
import sys

# 將上一層目錄加入 sys.path 確保可以正確 import
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from tasks.daily_job import daily_morning_routine

async def main():
    print("手動觸發每日晨間報告...")
    await daily_morning_routine()
    print("推播完成！")

if __name__ == "__main__":
    asyncio.run(main())
