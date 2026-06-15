import pytest

from crawler.settlements import parse_settlements

# 期交所「每日行情下載」CSV 的真實表頭（big5/cp950）；欄位以位置解析
HEADER = ("交易日期,契約,到期月份(週別),開盤價,最高價,最低價,收盤價,漲跌價,漲跌%,"
          "成交量,結算價,未沖銷契約數,最後最佳買價,最後最佳賣價,歷史最高價,歷史最低價,"
          "是否因訊息面暫停交易,交易時段,價差對單式委託成交量")


def _row(date, code, month, settle, session):
    c = [""] * 19
    c[0], c[1], c[2], c[10], c[17] = date, code, month, settle, session
    return ",".join(c)


def _csv(*rows):
    return "\n".join((HEADER, *rows))


def test_nearest_month_settlement():
    csv = _csv(
        # 盤後帶數字結算價且排最前：時段過濾一旦失效，CSF 會變 34.5 而非 34.2
        _row("2026/06/11", "CSF", "202606", "34.5", "盤後"),
        # 正常列：近月 + 次月（應取近月 202606）
        _row("2026/06/11", "CSF", "202606", "34.2", "一般"),
        _row("2026/06/11", "CSF", "202607", "34.25", "一般"),
        # 價差單（月份含 /），且 CDF 沒有其他有效列：價差過濾一旦失效，CDF 會出現在結果
        _row("2026/06/11", "CDF", "202606/202607", "0.16", "一般"),
        # 無效結算價：略過（ZZF 不應出現在結果）
        _row("2026/06/11", "ZZF", "202606", "-", "一般"),
    )
    assert parse_settlements(csv) == {"date": "20260611", "prices": {"CSF": 34.2}}


def test_picks_latest_trading_day():
    # 範圍查詢會回多個交易日，只取最新「有結算價」的那天
    csv = _csv(
        _row("2026/06/10", "CSF", "202606", "30.0", "一般"),
        _row("2026/06/11", "CSF", "202606", "34.2", "一般"),
    )
    assert parse_settlements(csv) == {"date": "20260611", "prices": {"CSF": 34.2}}


def test_empty_input():
    assert parse_settlements("") == {"date": "", "prices": {}}


def test_header_only_no_data_rows():
    assert parse_settlements(HEADER) == {"date": "", "prices": {}}


def test_bad_header_fails_loud():
    # 期交所改版讓欄位位移時必須拋錯，絕不讓壞資料寫進 data/
    with pytest.raises(ValueError, match="header"):
        parse_settlements("欄1,欄2,欄3\n2026/06/11,CSF,202606")
