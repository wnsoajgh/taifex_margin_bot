import difflib
import unicodedata


def _norm(text: str) -> str:
    # NFKC：全形轉半形；upper：期貨代碼不分大小寫
    return unicodedata.normalize("NFKC", text).strip().upper()


def _base_name(contract: dict) -> str:
    name = contract["name"]
    return name[:-2] if name.endswith("期貨") else name


def find(query: str, contracts: list[dict]) -> tuple[dict | None, list[dict]]:
    """回傳 (唯一命中, 候選清單)。唯一命中時候選為空；多重/零命中時命中為 None。"""
    q = _norm(query)
    if not q:
        return None, []

    for key in ("code", "stock_id"):
        hits = [c for c in contracts if _norm(c[key]) == q]
        if len(hits) == 1:
            return hits[0], []
        if hits:
            return None, hits

    hits = [c for c in contracts if _base_name(c) == q or c["name"] == q]
    if len(hits) == 1:
        return hits[0], []
    if hits:
        return None, hits

    subs = [c for c in contracts if q in _base_name(c)]
    if len(subs) == 1:
        return subs[0], []
    if subs:
        return None, subs[:5]

    by_base = {_base_name(c): c for c in contracts}
    close = difflib.get_close_matches(q, by_base.keys(), n=3, cutoff=0.5)
    return None, [by_base[n] for n in close]
