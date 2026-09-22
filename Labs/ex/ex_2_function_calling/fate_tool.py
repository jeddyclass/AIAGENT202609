from datetime import datetime


def calculate_fate_weight(date_of_birth: str):

    if len(date_of_birth) != 8:
        raise ValueError("生日格式必須為 YYYYMMDD")

    birth_seed = sum(int(c) for c in date_of_birth)

    current_datetime = datetime.now().strftime("%Y%m%d%H%M%S")

    time_seed = sum(int(c) for c in current_datetime)
    print(f">>> current time_seed: [{time_seed}]")

    seed = birth_seed * 7 + time_seed * 13

    weight = round(
        2.0 + (seed % 50) / 10,
        1
    )

    if weight < 3.0:
        level = "輕羽之命"

    elif weight < 4.0:
        level = "平穩之命"

    elif weight < 5.0:
        level = "厚福之命"

    elif weight < 6.0:
        level = "昌盛之命"

    else:
        level = "天選之命"

    return {
        "birth_date": date_of_birth,
        "current_datetime": current_datetime,
        "weight": weight,
        "level": level
    }