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
