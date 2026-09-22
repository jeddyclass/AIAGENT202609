使用者
    │
    ▼
python app.py 19880501
    │
    ▼
LLM

「我的生日是19880501，
請幫我計算今天命重」

    │
    ▼
Tool Call

calculate_fate_weight(
    date_of_birth="19880501"
)

    │
    ▼
Python Function

{
  "birth_date":"19880501",
  "current_datetime":"20260609153510",
  "weight":5.7,
  "level":"昌盛之命"
}

    │
    ▼
回傳給 LLM
    │
    ▼
最終文字解讀