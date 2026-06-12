import httpx

HEADERS = {"User-Agent": "Mozilla/5.0"}
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=1d&interval=1d"
MIS_URL = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={market}_{stock_id}.tw&json=1&delay=0"


def parse_yahoo_price(payload: dict) -> float | None:
    try:
        return float(payload["chart"]["result"][0]["meta"]["regularMarketPrice"])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def parse_mis_price(payload: dict) -> float | None:
    try:
        return float(payload["msgArray"][0]["z"])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def get_live_price(stock_id: str) -> float | None:
    """上市為主、上櫃備援；Yahoo 失敗再退 TWSE MIS。全失敗回 None（best-effort 報價）。"""
    for symbol in (f"{stock_id}.TW", f"{stock_id}.TWO"):
        try:
            resp = httpx.get(YAHOO_URL.format(symbol=symbol), headers=HEADERS, timeout=5)
            price = parse_yahoo_price(resp.json())
            if price is not None and price > 0:   # 0 不是有效報價，繼續嘗試下一來源
                return price
        except (httpx.HTTPError, ValueError):   # ValueError 含限流時非 JSON 回應的解碼錯誤
            pass
    for market in ("tse", "otc"):
        try:
            resp = httpx.get(MIS_URL.format(market=market, stock_id=stock_id),
                             headers=HEADERS, timeout=5)
            price = parse_mis_price(resp.json())
            if price is not None and price > 0:   # 0 不是有效報價，繼續嘗試下一來源
                return price
        except (httpx.HTTPError, ValueError):
            pass
    return None
