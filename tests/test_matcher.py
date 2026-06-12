from bot.matcher import find

C = [
    {"code": "CSF", "stock_id": "1605", "name": "華新期貨", "category": "stock"},
    {"code": "PBF", "stock_id": "2492", "name": "華新科期貨", "category": "stock"},
    {"code": "CDF", "stock_id": "2330", "name": "台積電期貨", "category": "stock"},
    {"code": "QFF", "stock_id": "2330", "name": "小型台積電期貨", "category": "stock"},
    {"code": "NYF", "stock_id": "0050", "name": "元大台灣50ETF期貨", "category": "etf"},
]


def test_exact_short_name():
    hit, cands = find("華新", C)
    assert hit["code"] == "CSF" and cands == []


def test_exact_short_name_beats_substring():
    hit, _ = find("台積電", C)          # 不應撞到「小型台積電期貨」
    assert hit["code"] == "CDF"


def test_stock_id():
    hit, cands = find("1605", C)
    assert hit["code"] == "CSF"


def test_stock_id_multiple_hits_returns_candidates():
    hit, cands = find("2330", C)        # 大小台積電同標的
    assert hit is None and {c["code"] for c in cands} == {"CDF", "QFF"}


def test_futures_code_case_insensitive():
    hit, _ = find("csf", C)
    assert hit["code"] == "CSF"


def test_fullwidth_input():
    hit, _ = find("１６０５", C)
    assert hit["code"] == "CSF"


def test_substring_candidates():
    hit, cands = find("華", C)
    assert hit is None and len(cands) == 2


def test_no_match_close_suggestions():
    hit, cands = find("台積店", C)      # 錯字 → difflib 相近建議
    assert hit is None and any("台積電" in c["name"] for c in cands)


def test_no_match_at_all():
    hit, cands = find("完全不存在的東西", C)
    assert hit is None and cands == []
