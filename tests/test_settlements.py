from crawler.settlements import parse_settlements

ROWS = [
    # 盤後時段帶「數字」結算價，且排在最前：時段過濾一旦失效，CSF 會變 34.5 而非 34.2
    {"Date": "20260611", "Contract": "CSF", "ContractMonth(Week)": "202606",
     "SettlementPrice": "34.5", "TradingSession": "盤後"},
    # 正常列：近月 + 次月（應取近月 202606）
    {"Date": "20260611", "Contract": "CSF", "ContractMonth(Week)": "202606",
     "SettlementPrice": "34.2", "TradingSession": "一般"},
    {"Date": "20260611", "Contract": "CSF", "ContractMonth(Week)": "202607",
     "SettlementPrice": "34.25", "TradingSession": "一般"},
    # 價差單（月份含 /），且 CDF 沒有其他有效列：價差過濾一旦失效，CDF 會出現在結果
    {"Date": "20260611", "Contract": "CDF", "ContractMonth(Week)": "202606/202607",
     "SettlementPrice": "0.16", "TradingSession": "一般"},
    # 無效結算價：略過（ZZF 不應出現在結果）
    {"Date": "20260611", "Contract": "ZZF", "ContractMonth(Week)": "202606",
     "SettlementPrice": "-", "TradingSession": "一般"},
]


def test_nearest_month_settlement():
    out = parse_settlements(ROWS)
    assert out == {"date": "20260611", "prices": {"CSF": 34.2}}


def test_empty_input():
    assert parse_settlements([]) == {"date": "", "prices": {}}
