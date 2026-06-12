from crawler.settlements import parse_settlements

ROWS = [
    # 正常列：近月 + 次月（應取近月 202606）
    {"Date": "20260611", "Contract": "CSF", "ContractMonth(Week)": "202606",
     "SettlementPrice": "34.2", "TradingSession": "一般"},
    {"Date": "20260611", "Contract": "CSF", "ContractMonth(Week)": "202607",
     "SettlementPrice": "34.25", "TradingSession": "一般"},
    # 盤後時段：略過
    {"Date": "20260611", "Contract": "CSF", "ContractMonth(Week)": "202606",
     "SettlementPrice": "NULL", "TradingSession": "盤後"},
    # 價差單（月份含 /）：略過
    {"Date": "20260611", "Contract": "CSF", "ContractMonth(Week)": "202606/202607",
     "SettlementPrice": "0.16", "TradingSession": "一般"},
    # 無效結算價：略過（CDF 不應出現在結果）
    {"Date": "20260611", "Contract": "CDF", "ContractMonth(Week)": "202606",
     "SettlementPrice": "-", "TradingSession": "一般"},
]


def test_nearest_month_settlement():
    out = parse_settlements(ROWS)
    assert out == {"date": "20260611", "prices": {"CSF": 34.2}}


def test_empty_input():
    assert parse_settlements([]) == {"date": "", "prices": {}}
