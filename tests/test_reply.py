from bot.reply import calc_margin, format_reply, multiplier

CSF = {"code": "CSF", "stock_id": "1605", "name": "華新期貨",
       "underlying_name": "華新麗華股份有限公司", "category": "stock",
       "level": "級距2", "clearing_rate": 0.12,
       "maintenance_rate": 0.1242, "initial_rate": 0.162}


def test_multiplier_rules():
    assert multiplier({"name": "華新期貨"}) == 2000
    assert multiplier({"name": "小型台積電期貨"}) == 100


def test_format_reply_disposal_contract():
    dqf = dict(CSF, code="DQF", stock_id="3481", name="群創期貨",
               underlying_name="群創光電股份有限公司", level="",
               clearing_rate=0.18, maintenance_rate=0.1863, initial_rate=0.243)
    msg = format_reply(dqf, settlement_price=48.05, settlement_date="20260612",
                       live_price=None, data_date="2026/06/12", stale=False)
    assert "處置中" in msg and "另行再加收" in msg
    assert f"{int(48.05 * 2000 * 0.243 + 0.5):,}" in msg          # 23,352


def test_format_reply_normal_contract_has_minimum_note_no_disposal():
    msg = format_reply(CSF, settlement_price=34.2, settlement_date="20260611",
                       live_price=None, data_date="2026/06/11", stale=False)
    assert "最低標準" in msg and "處置中" not in msg


def test_format_reply_etf_fixed_amounts():
    nyf = {"code": "NYF", "stock_id": "0050", "name": "元大台灣50ETF期貨",
           "underlying_name": "元大台灣卓越50證券投資信託基金", "category": "etf",
           "clearing_amount": 52000, "maintenance_amount": 54000, "initial_amount": 71000}
    msg = format_reply(nyf, settlement_price=None, settlement_date="",
                       live_price=None, data_date="2026/06/11", stale=False)
    assert "71,000" in msg and "54,000" in msg and "52,000" in msg
    assert "固定金額" in msg and "結算價" not in msg


def test_calc_margin_rounds_half_up():
    assert calc_margin(34.2, 0.162, 2000) == 11081      # 11080.8
    assert calc_margin(34.2, 0.1242, 2000) == 8495      # 8495.28
    assert calc_margin(0.25, 0.10, 2000) == 50          # 50.0 整數邊界


def test_format_reply_full():
    msg = format_reply(CSF, settlement_price=34.2, settlement_date="20260611",
                       live_price=37.65, data_date="2026/06/11", stale=False)
    assert "華新期貨 (CSF)" in msg
    assert "1605" in msg and "華新麗華" in msg
    assert "級距2" in msg and "16.20%" in msg
    assert "11,081" in msg                      # 正式原始保證金
    assert "8,495" in msg                       # 正式維持保證金
    assert "12,199" in msg                      # 盤中估算 37.65*2000*0.162=12198.6
    assert "2026/06/11" in msg


def test_format_reply_no_live_price():
    msg = format_reply(CSF, settlement_price=34.2, settlement_date="20260611",
                       live_price=None, data_date="2026/06/11", stale=False)
    assert "即時" in msg and "無法取得" in msg


def test_format_reply_no_settlement():
    msg = format_reply(CSF, settlement_price=None, settlement_date="",
                       live_price=37.65, data_date="2026/06/11", stale=False)
    assert "12,199" in msg and "結算價" in msg and "缺" in msg


def test_format_reply_stale_warning():
    msg = format_reply(CSF, settlement_price=34.2, settlement_date="20260611",
                       live_price=None, data_date="2026/06/01", stale=True)
    assert "⚠️" in msg
