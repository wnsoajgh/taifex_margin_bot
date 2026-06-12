def multiplier(contract: dict) -> int:
    # 僅股票期貨以價格計算保證金；「小型」契約乘數為 100 股
    return 100 if contract["name"].startswith("小型") else 2_000


def calc_margin(price: float, rate: float, mult: int) -> int:
    return int(price * rate * mult + 0.5)  # round half up；內建 round() 是銀行家捨入


def _fmt_date(yyyymmdd: str) -> str:
    return f"{yyyymmdd[4:6]}/{yyyymmdd[6:8]}" if len(yyyymmdd) == 8 else yyyymmdd


def _footer(data_date: str, stale: bool) -> list[str]:
    lines = ["", f"資料日期：{data_date}"]
    if stale:
        lines.append("⚠️ 資料日期較舊，金額僅供參考")
    return lines


def format_reply(contract: dict, settlement_price: float | None, settlement_date: str,
                 live_price: float | None, data_date: str, stale: bool) -> str:
    header = [
        f"{contract['name']} ({contract['code']})",
        f"標的：{contract['stock_id']} {contract['underlying_name']}",
    ]
    if contract["category"] == "etf":
        return "\n".join(header + [
            "ETF 期貨保證金為公告固定金額：",
            f"原始：{contract['initial_amount']:,} 元",
            f"維持：{contract['maintenance_amount']:,} 元",
            f"結算：{contract['clearing_amount']:,} 元",
        ] + _footer(data_date, stale))

    mult = multiplier(contract)
    init, maint = contract["initial_rate"], contract["maintenance_rate"]
    lines = header + [
        f"{contract['level']}｜原始 {init:.2%}｜維持 {maint:.2%}｜結算 {contract['clearing_rate']:.2%}",
        "",
    ]
    if settlement_price is not None:
        lines += [
            f"📌 正式保證金（{_fmt_date(settlement_date)} 結算價 {settlement_price:g}）",
            f"原始：{settlement_price:g} × {mult:,} × {init:.2%} = {calc_margin(settlement_price, init, mult):,} 元",
            f"維持：{calc_margin(settlement_price, maint, mult):,} 元",
        ]
    else:
        lines.append("📌 正式保證金：結算價資料缺漏，暫無法計算")
    lines.append("")
    if live_price is not None:
        lines += [
            f"📈 盤中估算（即時 {live_price:g}）",
            f"原始：≈ {calc_margin(live_price, init, mult):,} 元",
        ]
    else:
        lines.append("📈 即時價暫時無法取得")
    return "\n".join(lines + _footer(data_date, stale))
