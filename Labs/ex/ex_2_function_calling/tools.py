tools = [
    {
        "type": "function",
        "function": {
            "name": "calculate_fate_weight",
            "description": "依據生日與目前時間計算今日命重指數",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_of_birth": {
                        "type": "string",
                        "description": "生日，格式 YYYYMMDD，例如 19880501"
                    }
                },
                "required": [
                    "date_of_birth"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查詢指定城市的天氣狀況",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "要查詢的城市，例如：台北、台中、高雄"
                    }
                },
                "required": ["location"]
            }
        }
    }
]