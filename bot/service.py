import logging
import unicodedata
from datetime import date, datetime

from bot import data_source, quotes, subscriptions
from bot.matcher import find
from bot.reply import format_reply

log = logging.getLogger(__name__)
STALE_DAYS = 3
HELP_TEXT = ("查詢：P/股票名稱、P/代號 或 P/期貨代碼，例如 P/華新、P/1605、P/CSF\n"
             "訂閱保證金調整通知：P/+華新；退訂：P/-華新；看清單：P/訂閱")
NEED_DM = "訂閱功能請在與 bot 的一對一聊天中使用"


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


def build_answer(query: str, user_id: str | None = None) -> str:
    try:
        if query[:1] in ("+", "-"):
            return _subscribe_cmd(query, user_id)
        if query in ("訂閱", "訂閱清單"):
            return _list_subscriptions(user_id)
        return _answer(query)
    except Exception:
        log.exception("query failed: %r", query)   # 細節只進 log，不回給使用者
        return "系統暫時無法服務，請稍後再試"


def _resolve(name: str) -> tuple:
    """以查詢邏輯解析出唯一契約；回 (contract|None, 錯誤訊息|None)。"""
    margins = data_source.get_margins()
    hit, candidates = find(name, margins["contracts"])
    if hit is None and candidates:
        names = "\n".join(f"・{c['name']} ({c['code']})" for c in candidates)
        return None, f"找到多筆相符，請再輸入完整一點：\n{names}"
    if hit is None:
        return None, f"找不到「{name[:20]}」相關的股票期貨。\n{HELP_TEXT}"   # 截斷避免超過 LINE 5000 字元上限
    return hit, None


def _subscribe_cmd(query: str, user_id: str | None) -> str:
    if not user_id:
        return NEED_DM
    action, name = query[0], query[1:].strip()
    if not name:
        return HELP_TEXT
    hit, err = _resolve(name)
    if err:
        return err
    label = f"{hit['name']} ({hit['code']})"
    if action == "+":
        if subscriptions.add(user_id, hit["code"]):
            return f"✅ 已訂閱 {label} 的保證金調整通知"
        return f"你已經訂閱過 {label} 了"
    if subscriptions.remove(user_id, hit["code"]):
        return f"🗑️ 已取消訂閱 {label}"
    return f"你沒有訂閱 {label}"


def _list_subscriptions(user_id: str | None) -> str:
    if not user_id:
        return NEED_DM
    codes = subscriptions.codes_for(user_id)
    if not codes:
        return "你目前沒有任何訂閱。\n" + HELP_TEXT
    name_by = {c["code"]: c["name"] for c in data_source.get_margins()["contracts"]}
    lines = [f"・{name_by.get(c, c)} ({c})" for c in codes]
    return "你訂閱的保證金調整通知：\n" + "\n".join(lines)


def _answer(query: str) -> str:
    if not query:
        return HELP_TEXT
    hit, err = _resolve(query)
    if err:
        return err

    margins = data_source.get_margins()
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
