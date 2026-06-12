import httpx

OPENAPI_URL = "https://openapi.taifex.com.tw/v1/DailyMarketReportFut"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def fetch_daily_report() -> list[dict]:
    resp = httpx.get(OPENAPI_URL, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    return resp.json()


def parse_settlements(rows: list[dict]) -> dict:
    best: dict[str, tuple[str, float]] = {}
    date = ""
    for r in rows:
        month = (r.get("ContractMonth(Week)") or "").strip()
        if r.get("TradingSession") != "一般" or not month or "/" in month:
            continue
        try:
            price = float(r.get("SettlementPrice", ""))
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        code = (r.get("Contract") or "").strip()
        if code and (code not in best or month < best[code][0]):
            best[code] = (month, price)
        date = r.get("Date", date)
    return {"date": date, "prices": {c: p for c, (_, p) in sorted(best.items())}}
