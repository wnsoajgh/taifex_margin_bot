import bot.service as svc

MARGINS = {"updated_at": "2026/06/11", "contracts": [
    {"code": "CSF", "stock_id": "1605", "name": "華新期貨",
     "underlying_name": "華新麗華股份有限公司", "category": "stock",
     "level": "級距2", "clearing_rate": 0.12,
     "maintenance_rate": 0.1242, "initial_rate": 0.162},
    {"code": "PBF", "stock_id": "2492", "name": "華新科期貨",
     "underlying_name": "華新科技股份有限公司", "category": "stock",
     "level": "級距2", "clearing_rate": 0.12,
     "maintenance_rate": 0.1242, "initial_rate": 0.162},
]}
SETTLEMENTS = {"date": "20260611", "prices": {"CSF": 34.2}}


def _patch(monkeypatch, today="2026/06/12"):
    monkeypatch.setattr(svc.data_source, "get_margins", lambda: MARGINS)
    monkeypatch.setattr(svc.data_source, "get_settlements", lambda: SETTLEMENTS)
    monkeypatch.setattr(svc.quotes, "get_live_price", lambda sid: 37.65)
    monkeypatch.setattr(svc, "_today_str", lambda: today)


def test_hit(monkeypatch):
    _patch(monkeypatch)
    msg = svc.build_answer("華新")
    assert "華新期貨 (CSF)" in msg and "11,081" in msg and "⚠️" not in msg


def test_candidates(monkeypatch):
    _patch(monkeypatch)
    msg = svc.build_answer("華")
    assert "華新期貨" in msg and "華新科期貨" in msg and "找到多筆" in msg


def test_not_found(monkeypatch):
    _patch(monkeypatch)
    msg = svc.build_answer("完全不存在的東西")
    assert "找不到" in msg


def test_stale_data_warning(monkeypatch):
    _patch(monkeypatch, today="2026/06/20")
    assert "⚠️" in svc.build_answer("華新")


def test_internal_error_is_masked(monkeypatch):
    monkeypatch.setattr(svc.data_source, "get_margins",
                        lambda: (_ for _ in ()).throw(RuntimeError("secret detail")))
    msg = svc.build_answer("華新")
    assert "secret" not in msg and "稍後再試" in msg


def test_extract_query_prefix_variants():
    assert svc.extract_query("P群創") == "群創"
    assert svc.extract_query("p1605") == "1605"
    assert svc.extract_query("P+群創") == "+群創"
    assert svc.extract_query("Ｐ群創") == "群創"        # 全形經 NFKC 正規化
    assert svc.extract_query("P/群創") == "群創"        # 相容舊的斜線格式
    assert svc.extract_query("p/1605") == "1605"
    assert svc.extract_query("Ｐ／群創") == "群創"
    assert svc.extract_query("  P/ 華新  ") == "華新"


def test_extract_query_bare_prefix_returns_none():
    # 只打前綴、沒帶查詢字 → 不回應（避免群組裡單一 P 字誤觸）
    assert svc.extract_query("P") is None
    assert svc.extract_query("P/") is None


def test_extract_query_non_command_returns_none():
    assert svc.extract_query("群創") is None
    assert svc.extract_query("早安") is None
    assert svc.extract_query("") is None


def test_empty_query_returns_help(monkeypatch):
    _patch(monkeypatch)
    assert "P+華新" in svc.build_answer("")


def _patch_subs(monkeypatch, store):
    monkeypatch.setattr(svc.subscriptions, "add",
                        lambda uid, code: store.setdefault(uid, []).append(code) or True
                        if code not in store.get(uid, []) else False)
    monkeypatch.setattr(svc.subscriptions, "remove",
                        lambda uid, code: store.get(uid, []).remove(code) or True
                        if code in store.get(uid, []) else False)
    monkeypatch.setattr(svc.subscriptions, "codes_for", lambda uid: store.get(uid, []))


def test_subscribe_and_duplicate(monkeypatch):
    _patch(monkeypatch)
    store = {}
    _patch_subs(monkeypatch, store)
    assert "已訂閱 華新期貨 (CSF)" in svc.build_answer("+華新", "U1")
    assert store == {"U1": ["CSF"]}
    assert "已經訂閱過" in svc.build_answer("+華新", "U1")


def test_unsubscribe(monkeypatch):
    _patch(monkeypatch)
    store = {"U1": ["CSF"]}
    _patch_subs(monkeypatch, store)
    assert "已取消訂閱" in svc.build_answer("-華新", "U1")
    assert "你沒有訂閱" in svc.build_answer("-華新", "U1")


def test_subscribe_ambiguous_name(monkeypatch):
    _patch(monkeypatch)
    store = {}
    _patch_subs(monkeypatch, store)
    msg = svc.build_answer("+華", "U1")
    assert "找到多筆" in msg and store == {}


def test_subscription_requires_user_id(monkeypatch):
    _patch(monkeypatch)
    assert "一對一" in svc.build_answer("+華新", None)
    assert "一對一" in svc.build_answer("訂閱", None)


def test_list_subscriptions(monkeypatch):
    _patch(monkeypatch)
    _patch_subs(monkeypatch, {"U1": ["CSF"]})
    msg = svc.build_answer("訂閱", "U1")
    assert "華新期貨 (CSF)" in msg
    assert "沒有任何訂閱" in svc.build_answer("訂閱", "U2")
