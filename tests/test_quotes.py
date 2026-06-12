from bot.quotes import parse_mis_price, parse_yahoo_price


def test_parse_yahoo_price():
    payload = {"chart": {"result": [{"meta": {"regularMarketPrice": 37.65}}]}}
    assert parse_yahoo_price(payload) == 37.65


def test_parse_yahoo_price_missing():
    assert parse_yahoo_price({"chart": {"result": None}}) is None
    assert parse_yahoo_price({}) is None


def test_parse_mis_price():
    assert parse_mis_price({"msgArray": [{"z": "37.6500"}]}) == 37.65


def test_parse_mis_price_no_trade():
    assert parse_mis_price({"msgArray": [{"z": "-"}]}) is None
    assert parse_mis_price({"msgArray": []}) is None
