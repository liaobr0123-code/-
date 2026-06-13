import requests
import json

API_KEY = "M2JlNjFlODEtYzIxMC00ZWU4LWIxNDktNGNmMzJkNjAwZmZmIGY3YWM2YWNhLTI0MDItNDIzMC1hMzRlLTQ4Njc2ZmI2YTM5MQ=="
headers = {"X-API-KEY": API_KEY}

def test():
    # Test TAIEX
    url = "https://api.fugle.tw/marketdata/v1.0/stock/intraday/quote/IX0001"
    res = requests.get(url, headers=headers)
    print("TAIEX Quote:", res.status_code, res.text[:200])

    # Test 2330 candles
    url = "https://api.fugle.tw/marketdata/v1.0/stock/historical/candles/2330"
    res = requests.get(url, headers=headers)
    print("2330 Candles:", res.status_code, res.text[:200])

if __name__ == "__main__":
    test()
