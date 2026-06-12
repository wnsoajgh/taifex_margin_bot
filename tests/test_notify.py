import json

import pytest

import crawler.notify as notify
from crawler.notify import build_notification, diff_contracts


def _stock(code, name, level, init, maint=0.1242, clear=0.12):
    return {"code": code, "stock_id": "0000", "name": name, "underlying_name": "x",
            "category": "stock", "level": level,
            "clearing_rate": clear, "maintenance_rate": maint, "initial_rate": init}


def _etf(code, name, init, maint=54000, clear=52000):
    return {"code": code, "stock_id": "0000", "name": name, "underlying_name": "x",
            "category": "etf",
            "clearing_amount": clear, "maintenance_amount": maint, "initial_amount": init}


OLD = {"updated_at": "2026/06/11", "contracts": [
    _stock("DQF", "群創期貨", "級距2", 0.162),
    _stock("CSF", "華新期貨", "級距2", 0.162),
    _etf("NYF", "元大台灣50ETF期貨", 71000),
]}
NEW = {"updated_at": "2026/06/12", "contracts": [
    _stock("DQF", "群創期貨", "", 0.243, maint=0.1863, clear=0.18),   # 列入處置
    _stock("CSF", "華新期貨", "級距2", 0.162),                        # 沒變
    _etf("NYF", "元大台灣50ETF期貨", 75000),                          # 金額調整
]}


def test_diff_detects_disposal_and_rate_change():
    changes = diff_contracts(OLD, NEW)
    assert "CSF" not in changes
    assert any("處置中" in line for line in changes["DQF"])
    assert any("16.20%" in line and "24.30%" in line for line in changes["DQF"])


def test_diff_detects_etf_amount_change():
    changes = diff_contracts(OLD, NEW)
    assert any("71,000" in line and "75,000" in line for line in changes["NYF"])


def test_diff_no_changes():
    assert diff_contracts(OLD, OLD) == {}


def test_build_notification_only_subscribed():
    changes = diff_contracts(OLD, NEW)
    msg = build_notification(NEW, changes, ["DQF"])
    assert msg is not None
    assert "群創期貨 (DQF)" in msg and "NYF" not in msg
    assert "2026/06/12" in msg


def test_build_notification_none_when_no_subscribed_change():
    changes = diff_contracts(OLD, NEW)
    assert build_notification(NEW, changes, ["CSF"]) is None
    assert build_notification(NEW, changes, []) is None


def test_diff_detects_removed_and_reclassified():
    old = {"updated_at": "x", "contracts": [
        _stock("AAA", "甲期貨", "級距1", 0.135), _stock("BBB", "乙期貨", "級距1", 0.135)]}
    new = {"updated_at": "y", "contracts": [_etf("BBB", "乙期貨", 71000)]}
    changes = diff_contracts(old, new)
    assert "移除" in changes["AAA"][0]
    assert "類別變更" in changes["BBB"][0]


def test_build_notification_truncates_under_line_limit():
    contracts = [_stock(f"S{i:03d}", f"測試{i}期貨", "級距1", 0.135) for i in range(300)]
    old = {"updated_at": "2026/06/11", "contracts": contracts}
    new = {"updated_at": "2026/06/12",
           "contracts": [dict(c, initial_rate=0.2025) for c in contracts]}
    changes = diff_contracts(old, new)
    msg = build_notification(new, changes, [c["code"] for c in contracts])
    assert len(msg) <= 5000          # 季調全市場變動也不能超過 LINE 上限
    assert "另有" in msg


def test_main_skips_when_gist_unconfigured(monkeypatch, capsys):
    monkeypatch.delenv("SUBS_GIST_ID", raising=False)
    notify.main("nonexistent_old.json", "nonexistent_new.json")   # 短路在開檔之前
    assert "skipping" in capsys.readouterr().out


def test_main_isolates_push_failures(monkeypatch, tmp_path):
    old = {"updated_at": "2026/06/11", "contracts": [_stock("DQF", "群創期貨", "級距2", 0.162)]}
    new = {"updated_at": "2026/06/12", "contracts": [_stock("DQF", "群創期貨", "", 0.243)]}
    po, pn = tmp_path / "old.json", tmp_path / "new.json"
    po.write_text(json.dumps(old), encoding="utf-8")
    pn.write_text(json.dumps(new), encoding="utf-8")
    monkeypatch.setenv("SUBS_GIST_ID", "fake")
    monkeypatch.setattr(notify.subscriptions, "load", lambda: {"U1": ["DQF"], "U2": ["DQF"]})
    pushed = []

    def fake_push(uid, text):
        if uid == "U1":
            raise notify.httpx.ConnectError("down")
        pushed.append(uid)

    monkeypatch.setattr(notify, "_push", fake_push)
    with pytest.raises(SystemExit):                  # 有失敗仍要讓 run 變紅
        notify.main(str(po), str(pn))
    assert pushed == ["U2"]                          # 但其他訂閱者照樣收到
