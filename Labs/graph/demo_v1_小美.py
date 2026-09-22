import pandas as pd

# 定義同學名稱
names = ["小明", "小華", "小美", "小強"]

# 建立鄰接矩陣 (0 和 1)
# 橫排代表出發者，直欄代表接收者
matrix_data = [
    [0, 1, 0, 0],  # 小明：只喜歡小華
    [0, 0, 1, 0],  # 小華：只喜歡小美
    [0, 0, 0, 1],  # 小美：只喜歡小強
    [0, 0, 1, 0]   # 小強：只喜歡小美
]

df = pd.DataFrame(matrix_data, index=names, columns=names)
print("--- 班級八卦鄰接矩陣 ---")
print(df)

# 電腦應用：算直欄加總，找出誰最受歡迎
popularity = df.sum(axis=0)
print("\n--- 每個人被喜歡的次數 (直欄加總) ---")
print(popularity)
print(f"\n電腦自動判定：全班最受歡迎的人是【{popularity.idxmax()}】！")
