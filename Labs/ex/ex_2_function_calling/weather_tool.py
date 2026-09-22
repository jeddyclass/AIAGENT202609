import os, json
from datetime import datetime
from dotenv import load_dotenv

# 假的天氣 API
def get_weather(location: str) -> str:
    weather_data = {
        "台北": "今天台北天氣不太好唷，可能會下陣雨，最高溫 36 度",
        "台中": "今天台中上午天氣不錯，下午之後可能有局部降雨，最高溫 34 度",
        "高雄": "今天高雄跟以往一樣，都很熱，最高溫 37 度，注意不要被曬傷"
    }
    return weather_data.get(location, f"我是模擬天氣預報，目前沒有 {location} 的天氣資料")