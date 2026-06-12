import json
from pathlib import Path

from crawler.margins import fetch_margin_html, parse_margins
from crawler.settlements import fetch_daily_report, parse_settlements

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def validate_margins(data: dict) -> None:
    rows = data["contracts"]
    if len(rows) <= 100:
        raise ValueError(f"too few margin rows: {len(rows)}")
    if not data["updated_at"]:
        raise ValueError("missing updated_at date")
    for c in rows:
        if not (c["code"] and c["stock_id"] and c["name"]):
            raise ValueError(f"empty field in row: {c}")
        if c["category"] == "stock":
            for k in ("clearing_rate", "maintenance_rate", "initial_rate"):
                # 範圍放寬於 spec 的 5%-40%：處置股票加收後比例較高
                if not 0.03 <= c[k] <= 0.45:
                    raise ValueError(f"{c['code']} {k} rate out of range: {c[k]}")
        else:  # ETF 期貨為公告固定金額
            for k in ("clearing_amount", "maintenance_amount", "initial_amount"):
                if not 1_000 <= c[k] <= 10_000_000:
                    raise ValueError(f"{c['code']} {k} amount out of range: {c[k]}")


def validate_settlements(data: dict, margin_codes: set[str]) -> None:
    if not data["date"]:
        raise ValueError("missing settlement date")
    covered = margin_codes & set(data["prices"])
    if len(covered) < 0.8 * len(margin_codes):
        raise ValueError(f"settlement coverage too low: {len(covered)}/{len(margin_codes)}")


def main() -> None:
    margins = parse_margins(fetch_margin_html())
    validate_margins(margins)
    settlements = parse_settlements(fetch_daily_report())
    validate_settlements(settlements, {c["code"] for c in margins["contracts"]})
    DATA_DIR.mkdir(exist_ok=True)
    for name, payload in (("margins.json", margins), ("settlements.json", settlements)):
        (DATA_DIR / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK margins={len(margins['contracts'])} settlements={len(settlements['prices'])}")


if __name__ == "__main__":
    main()
