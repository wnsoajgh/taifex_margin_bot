import logging
import unicodedata
from datetime import date, datetime

from bot import data_source, quotes
from bot.matcher import find
from bot.reply import format_reply

log = logging.getLogger(__name__)
STALE_DAYS = 3
HELP_TEXT = "請輸入 P/股票名稱、P/代號 或 P/期貨代碼，例如：P/華新、P/1605、P/CSF"


def extract_query(text: str) -> str | None:
    """只回應「P/查詢字」格式（不分大小寫、容許全形 Ｐ／）；其他訊息回 None 表示不回覆。"""
    t = unicodedata.normalize("NFKC", text).strip()
    if len(t) >= 2 and t[0] in "Pp" and t[1] == "/":
        return t[2:].strip()
    return None


def _today_str() -> str:
    return date.today().strftime("%Y/%m/%d")


def _is_stale(data_date: str) -> bool:
    try:
        d = datetime.strptime(data_date, "%Y/%m/%d").date()
    except ValueError:
        return True
    today = datetime.strptime(_today_str(), "%Y/%m/%d").date()
    return (today - d).days > STALE_DAYS


def build_answer(query: str) -> str:
    try:
        return _answer(query)
    except Exception:
        log.exception("query failed: %r", query)   # 細節只進 log，不回給使用者
        return "系統暫時無法服務，請稍後再試"


def _answer(query: str) -> str:
    if not query:
        return HELP_TEXT
    margins = data_source.get_margins()
    hit, candidates = find(query, margins["contracts"])
    if hit is None and candidates:
        names = "\n".join(f"・{c['name']} ({c['code']})" for c in candidates)
        return f"找到多筆相符，請再輸入完整一點：\n{names}"
    if hit is None:
        return f"找不到「{query[:20]}」相關的股票期貨。\n{HELP_TEXT}"   # 截斷避免回覆超過 LINE 5000 字元上限

    settlements = data_source.get_settlements()
    is_etf = hit["category"] == "etf"   # ETF 期貨為公告固定金額，不需任何報價
    return format_reply(
        hit,
        settlement_price=None if is_etf else settlements["prices"].get(hit["code"]),
        settlement_date=settlements.get("date", ""),
        live_price=None if is_etf else quotes.get_live_price(hit["stock_id"]),
        data_date=margins["updated_at"],
        stale=_is_stale(margins["updated_at"]),
    )
