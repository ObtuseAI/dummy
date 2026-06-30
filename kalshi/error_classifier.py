from enum import Enum

class KalshiErrorCategory(str, Enum):
    AUTH = "AUTH"
    RATE_LIMIT = "RATE_LIMIT"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION = "VALIDATION"
    MARKET_CLOSED = "MARKET_CLOSED"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    NETWORK = "NETWORK"
    UNKNOWN = "UNKNOWN"

def classify(status: int, body: dict | str) -> KalshiErrorCategory:
    if status == 401 or status == 403:
        return KalshiErrorCategory.AUTH
    if status == 429:
        return KalshiErrorCategory.RATE_LIMIT
    if status == 404:
        return KalshiErrorCategory.NOT_FOUND
    if status == 400:
        return KalshiErrorCategory.VALIDATION
    if status >= 500:
        return KalshiErrorCategory.NETWORK
    text = str(body).lower()
    if "market" in text and "closed" in text:
        return KalshiErrorCategory.MARKET_CLOSED
    if "insufficient" in text or "funds" in text:
        return KalshiErrorCategory.INSUFFICIENT_FUNDS
    return KalshiErrorCategory.UNKNOWN
