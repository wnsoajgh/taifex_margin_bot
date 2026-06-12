import pytest

from crawler.run import validate_margins, validate_settlements


def _margins(n=150, rate=0.162):
    return {"updated_at": "2026/06/11", "contracts": [
        {"code": f"C{i:03d}", "stock_id": str(1000 + i), "name": f"測試{i}期貨",
         "underlying_name": "x", "category": "stock", "level": "級距1",
         "clearing_rate": 0.10, "maintenance_rate": 0.1035, "initial_rate": rate}
        for i in range(n)
    ]}


def test_validate_margins_ok():
    validate_margins(_margins())  # 不應拋錯


def test_validate_margins_too_few_rows():
    with pytest.raises(ValueError, match="too few"):
        validate_margins(_margins(n=50))


def test_validate_margins_bad_rate():
    with pytest.raises(ValueError, match="rate"):
        validate_margins(_margins(rate=0.9))


def test_validate_margins_bad_etf_amount():
    data = _margins()
    data["contracts"].append({
        "code": "NYF", "stock_id": "0050", "name": "元大台灣50ETF期貨",
        "underlying_name": "x", "category": "etf",
        "clearing_amount": 52000, "maintenance_amount": 54000, "initial_amount": 100})
    with pytest.raises(ValueError, match="amount"):
        validate_margins(data)


def test_validate_settlements_coverage():
    codes = {c["code"] for c in _margins()["contracts"]}
    prices = {c: 10.0 for c in list(codes)[:130]}
    validate_settlements({"date": "20260611", "prices": prices}, codes)  # 86% 覆蓋 OK
    with pytest.raises(ValueError, match="coverage"):
        validate_settlements({"date": "20260611", "prices": {}}, codes)


def test_validate_settlements_missing_date():
    with pytest.raises(ValueError, match="date"):
        validate_settlements({"date": "", "prices": {"A": 1.0}}, {"A"})
