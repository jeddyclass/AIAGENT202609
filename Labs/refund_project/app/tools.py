from typing import Literal

def query_order_db(order_id: str) -> dict:
    """查詢訂單詳情與出貨狀態。

    Args:
        order_id: 以 'ORD-' 開頭的 8 碼訂單編號，例如 ORD-10029381
    """
    # 模擬資料庫查詢
    return {
        "order_id": order_id,
        "amount": 250.0,
        "status": "DELIVERED",
        "item": "無線降噪耳機"
    }

def execute_refund(
    order_id: str,
    amount: float,
    reason: Literal["defective", "missing_item", "other"] = "defective"
) -> dict:
    """高風險操作：執行退款退帳。

    Args:
        order_id: 訂單編號
        amount: 退款金額，必須大於 0 且小於等於 500
        reason: 退款原因
    """
    if amount > 500.0:
        return {"status": "FAILED", "error": "退款金額超過上限 500 元"}
        
    return {
        "status": "REFUNDED",
        "tx_id": "TX-998811",
        "amount": amount,
        "order_id": order_id
    }
