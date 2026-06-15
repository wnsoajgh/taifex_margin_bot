import datetime

import httpx

# 期交所「每日行情下載」CSV：日盤收盤（13:45）後約 15:00 即發布當日結算價。
# （改用此來源取代 OpenAPI DailyMarketReportFut：後者要等夜盤收完、隔日清晨才有當日資料。）
DOWNLOAD_URL = "https://www.taifex.com.tw/cht/3/futDataDown"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.taifex.com.tw/cht/3/dlFutDailyMarketView",
}

# CSV 欄位（cp950）固定位置；期交所改版會讓位置位移，於 parse 的表頭檢查 fail-loud
_DATE, _CODE, _MONTH, _SETTLE, _SESSION = 0, 1, 2, 10, 17


def fetch_daily_report(today: datetime.date | None = None, lookback_days: int = 7) -> str:
    # 查最近一段日期區間（涵蓋連假），parse 再挑「最新有結算價」的交易日，免維護交易日曆。
    # commodity_id 與 commodity_id2 兩者都要 "all"，只設一個只會回表頭。
    today = today or datetime.date.today()
    start = today - datetime.timedelta(days=lookback_days)
    resp = httpx.post(DOWNLOAD_URL, headers=HEADERS, timeout=60, data={
        "down_type": "1",
        "commodity_id": "all",
        "commodity_id2": "all",
        "queryStartDate": start.strftime("%Y/%m/%d"),
        "queryEndDate": today.strftime("%Y/%m/%d"),
    })
    resp.raise_for_status()
    return resp.content.decode("cp950", errors="replace")


def parse_settlements(csv_text: str) -> dict:
    lines = [ln for ln in csv_text.splitlines() if ln.strip()]
    if not lines:
        return {"date": "", "prices": {}}
    header = lines[0].split(",")
    if (len(header) <= _SESSION or "結算價" not in header[_SETTLE]
            or "交易時段" not in header[_SESSION]):
        raise ValueError(f"unexpected settlement CSV header: {lines[0][:200]}")

    # (date, code, month, price)：只收日盤(一般)、非價差、結算價為正的列
    candidates: list[tuple[str, str, str, float]] = []
    for ln in lines[1:]:
        c = ln.split(",")
        if len(c) <= _SESSION or c[_SESSION].strip() != "一般":
            continue
        month = c[_MONTH].strip()
        # 月份字串字典序比較即可；週契約（含 /）僅存在於指數契約，本 bot 不查那些代碼
        if not month or "/" in month:
            continue
        try:
            price = float(c[_SETTLE].strip().replace(",", ""))  # "-"／空／非數字 -> 略過
        except ValueError:
            continue
        if price <= 0:
            continue
        candidates.append((c[_DATE].strip(), c[_CODE].strip(), month, price))

    if not candidates:
        return {"date": "", "prices": {}}
    latest = max(d for d, *_ in candidates)   # 取區間內最新、且有結算價的交易日
    best: dict[str, tuple[str, float]] = {}
    for d, code, month, price in candidates:
        if d != latest or not code:
            continue
        if code not in best or month < best[code][0]:
            best[code] = (month, price)
    return {"date": latest.replace("/", ""),
            "prices": {c: p for c, (_, p) in sorted(best.items())}}
