from pathlib import Path
from crawler.margins import parse_margins

FIXTURE = Path(__file__).parent / "fixtures" / "margin.html"


def _load():
    return parse_margins(FIXTURE.read_text(encoding="utf-8"))


def test_parses_csf_row():
    data = _load()
    csf = next(c for c in data["contracts"] if c["code"] == "CSF")
    assert csf["stock_id"] == "1605"
    assert csf["name"] == "華新期貨"
    assert "華新麗華" in csf["underlying_name"]
    assert csf["category"] == "stock"
    assert csf["level"].startswith("級距")
    assert 0.05 <= csf["clearing_rate"] <= csf["maintenance_rate"] <= csf["initial_rate"] <= 0.40


def test_contract_count_and_categories():
    data = _load()
    cats = {c["category"] for c in data["contracts"]}
    assert len(data["contracts"]) > 100
    assert cats == {"stock", "etf"}


def test_updated_at_format():
    data = _load()
    assert len(data["updated_at"]) == 10 and data["updated_at"][4] == "/"


def test_values_are_stripped():
    data = _load()
    for c in data["contracts"]:
        for k in ("code", "stock_id", "name"):
            assert c[k] == c[k].strip() and c[k]
