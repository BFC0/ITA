"""Fetch a small set of public exchange daily controls and record data-service access."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
import argparse
import json

import polars as pl
import requests

ITA = Path(__file__).resolve().parents[1]
DAILY = ITA / "artifacts/minute-cleaning/20261116T182000+0800/daily_evidence.parquet"
DAILY_HASH = "3e88f42687d3cf68e6d083f3bfbaa4fd66fa0dc430b35d423850702338a39888"
SSE = "https://yunhq.sse.com.cn:32042/v1/sh1/dayk/600004"
SZSE = "https://www.szse.cn/api/report/ShowReport/data"
SAMPLES = [
    ("SH-new", "20251231", "600004.SH", SSE, {"begin": -320, "end": -1, "period": "day"}),
    ("SZ-old", "20160122", "300001.SZ", SZSE, {
        "SHOWTYPE": "JSON", "CATALOGID": "1815_stock", "TABKEY": "tab1",
        "txtDMorJC": "300001", "txtBeginDate": "2016-01-22",
    }),
    ("SZ-overlap", "20241122", "300001.SZ", SZSE, {
        "SHOWTYPE": "JSON", "CATALOGID": "1815_stock", "TABKEY": "tab1",
        "txtDMorJC": "300001", "txtBeginDate": "2024-11-22",
    }),
]


def fetch(sample):
    name, day, code, url, params = sample
    response = requests.get(url, params=params, headers={
        "User-Agent": "Mozilla/5.0", "Referer": "https://www.szse.cn/market/trend/index.html",
    }, timeout=18)
    raw = OUT / "source" / (name + ".json")
    raw.write_bytes(response.content)
    response.raise_for_status()
    payload = response.json()
    if code.endswith(".SH"):
        assert payload["code"] == code[:6]
        rows = [row for row in payload["kline"] if str(row[0]) == day]
        assert len(rows) <= 1
        close = float(rows[0][4]) if rows else None
    else:
        rows = [row for tab in payload for row in tab["data"]
                if row["zqdm"] == code[:6] and row["jyrq"].replace("-", "") == day]
        assert len(rows) <= 1
        close = float(rows[0]["ss"]) if rows else None
    return {"date": day, "code": code, "official_close": close, "source_rows": len(rows),
            "source_url": response.url, "http_status": response.status_code,
            "source_sha256": sha256(raw.read_bytes()).hexdigest()}


def main():
    assert sha256(DAILY.read_bytes()).hexdigest() == DAILY_HASH
    with ThreadPoolExecutor(max_workers=3) as pool:
        source = pl.DataFrame(list(pool.map(fetch, SAMPLES)))
    local = pl.scan_parquet(DAILY).select(
        "code", "date", "raw_close", "minute_close", "minute_shares", "minute_yuan", "auction_status",
    ).collect()
    evidence = source.join(local, on=["code", "date"], how="left", validate="1:1").with_columns(
        ((pl.col("official_close") - pl.col("raw_close")).abs() <= 0.005).alias("official_close_matches"),
        pl.lit(None, dtype=pl.Float64).alias("official_auction_shares"),
    )
    assert evidence.height == len(SAMPLES)
    assert evidence["raw_close"].null_count() == 0
    evidence = evidence.sort("date", "code")
    evidence.write_csv(OUT / "daily_controls.csv")
    assert pl.read_csv(OUT / "daily_controls.csv").height == evidence.height
    files = [Path(__file__), OUT / "daily_controls.csv", *sorted((OUT / "source").glob("*"))]
    result = {
        "official_close_matches": evidence["official_close_matches"].sum(),
        "requested_controls": evidence.height,
        "official_auction_shares_verified": evidence["official_auction_shares"].count(),
        "input_sha256": {str(DAILY): DAILY_HASH},
        "output_sha256": {str(path.relative_to(OUT)): sha256(path.read_bytes()).hexdigest() for path in files},
    }
    (OUT / "verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(evidence.select("date", "code", "official_close", "raw_close", "auction_status", "http_status"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", help="New run directory name under outputs/", type=Path)
    args = parser.parse_args()
    if args.output.name != str(args.output) or args.output.name in {"", ".."}:
        parser.error("output must be a single new directory name")
    OUT = ITA / "outputs" / args.output
    (OUT / "source").mkdir(parents=True, exist_ok=False)
    main()
