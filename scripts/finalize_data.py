"""Export fixed-pool factor inputs and separate outcomes from the accepted ITA snapshot."""
import argparse
import json
from pathlib import Path

import polars as pl

from audit import CALENDAR, FIELDS, KEY, WINDOWS
from inputs import DAILY, DAILY_SHA256, ITA, digest
from minute_research import BASE, QUALITY, RELEASE, scan_minutes

AUDIT = ITA / "artifacts/minute-cleaning/20261116T182000+0800"
OK = [p + "_ok" for p in FIELDS]
c = pl.col


def gate_slots(slots):
    # Every slot absent from the accepted gap table must have all seven usable fields.
    return slots.with_columns(
        c("applicable").fill_null(True),
        *[pl.when(c(p + "_ok").fill_null(True) & c("applicable").fill_null(True))
          .then(p).alias(p) for p in FIELDS],
    )


def window_flags(windows):
    groups = {"close_path": ["close"], "ohlc": FIELDS[:4], "turnover": ["vol", "amount"],
              "vwap_path": ["vwap"]}
    return windows.with_columns(
        *[pl.all_horizontal(*[c(f"w{w}_{p}_ok") == w for p in fields]).fill_null(False)
          .alias(f"w{w}_{name}_ok") for w in WINDOWS for name, fields in groups.items()],
        ((c("w1_close_ok") == 1) & c("lag60_close_ok")).fill_null(False).alias("ret60_endpoints_ok"),
    )


def label_return():
    return pl.when((c("d1_status") == "priced") & (c("d2_status") == "priced")
                   & c("d2_return_total").is_finite()).then("d2_return_total").alias("forward_return_d1_d2")


def minute_day(day, keys, gaps):
    bars = (scan_minutes(day).filter(c("trade_time").str.slice(-8).is_between(
        pl.lit("13:56:00"), pl.lit("14:56:00")))
        .select("code", c("trade_time").str.slice(-8).alias("clock"), *FIELDS[:-1])
        .with_columns(pl.when(c("vol") > 0).then(c("amount").cast(pl.Float64) / c("vol")).alias("vwap"))
        .collect())
    grid = pl.DataFrame({"clock": [f"{(896 - i) // 60:02}:{(896 - i) % 60:02}:00" for i in range(61)],
                         "lag": pl.Series(range(61), dtype=pl.UInt8)})
    joined = (keys.join(grid, how="cross")
              .join(bars, on=["code", "clock"], how="left", validate="1:1")
              .join(gaps.select(*KEY, "clock", "applicable", "reason", *OK),
                    on=[*KEY, "clock"], how="left", validate="1:1"))
    assert joined.filter(c("reason").is_null() & ~pl.all_horizontal(*[
        (c(p).is_finite() & (c(p) > 0)).fill_null(False) for p in FIELDS])).is_empty(), day
    return gate_slots(joined).select(*KEY, "clock", "lag", "applicable", "reason", *FIELDS)


def verify_minutes(minutes, windows):
    checks = minutes.group_by(KEY).agg(
        *[c("applicable").filter(c("lag") < w).sum().cast(pl.UInt8).alias(f"w{w}_expected") for w in WINDOWS],
        *[c(p).filter(c("lag") < w).count().cast(pl.UInt8).alias(f"w{w}_{p}_ok")
          for w in WINDOWS for p in FIELDS],
        *[pl.all_horizontal(*[c(p).is_not_null() for p in FIELDS]).filter(c("lag") < w)
          .sum().cast(pl.UInt8).alias(f"w{w}_all") for w in WINDOWS],
        *[c(p).filter(c("lag") == 60).first().is_not_null().alias(f"lag60_{p}_ok") for p in FIELDS],
        c("applicable").filter(c("lag") == 60).first().alias("lag60_applicable"),
    )
    assert checks.sort(KEY).equals(windows.select(checks.columns).sort(KEY)), "Minute fields differ from the audit"
    assert minutes.select(*KEY, "clock").n_unique() == minutes.height == windows.height * 61


def main(out):
    inputs = {DAILY: DAILY_SHA256}
    assert digest(DAILY) == DAILY_SHA256
    audit = json.loads((AUDIT / "inputs.json").read_text(encoding="utf-8"))
    for p in (CALENDAR, QUALITY / "minute_quality.parquet", RELEASE / "auction_backfill.parquet"):
        inputs[p] = audit["inputs"][str(ITA.parent.parent / p.relative_to(ITA / "data/snapshots"))]
    expected = json.loads((AUDIT / "verification.json").read_text(encoding="utf-8"))["outputs"]
    years = range(2016, 2026)
    for name in ["daily_evidence", "endpoints", *(f"{kind}_{y}" for y in years for kind in ("gaps", "windows"))]:
        p = AUDIT / f"{name}.parquet"
        inputs[p] = expected[p.name]
    assert all(digest(p) == h for p, h in inputs.items()), "Source hash mismatch"
    out.mkdir(parents=True, exist_ok=False)
    (out / "minutes").mkdir()
    daily = pl.read_parquet(DAILY).with_columns(
        (c("instrument").str.slice(2) + "." + c("instrument").str.slice(0, 2)).alias("code"),
        c("Trddt").dt.strftime("%Y%m%d").alias("date"),
    ).sort(KEY)
    assert daily.height == daily.select(KEY).n_unique() == 1009083 and daily["code"].n_unique() == 499
    daily.write_parquet(out / "daily_inputs.parquet")
    evidence = pl.read_parquet(AUDIT / "daily_evidence.parquet")
    calendar = pl.DataFrame({"date": sorted(audit["partitions"])})
    assert pl.read_parquet(CALENDAR).select(c("date").str.replace_all("-", "")).filter(
        c("date").is_between(pl.lit("20160104"), pl.lit("20251231"))).equals(calendar)
    calendar.write_parquet(out / "calendar.parquet")
    outcomes = pl.read_parquet(AUDIT / "endpoints.parquet").drop("observed_trade", "d1_return_total")
    shifts = calendar.with_columns(c("date").shift(-1).alias("d1"), c("date").shift(-2).alias("d2"))
    assert outcomes.select("date", "d1", "d2").unique().sort("date").equals(shifts)
    outcomes = outcomes.with_columns(label_return()).drop("d2_return_total").join(
        evidence.select("code", c("date").alias("d1"), c("auction_status").alias("d1_auction_status"),
                        c("independent_trade_auction_shares").alias("d1_independent_auction_shares"),
                        c("independent_trade_auction_yuan").alias("d1_independent_auction_yuan")),
        on=["code", "d1"], how="left", validate="m:1").sort(KEY)
    assert outcomes.select(KEY).equals(daily.select(KEY))
    outcomes.write_parquet(out / "outcomes.parquet")
    day_panels = []
    for year in years:
        windows = pl.read_parquet(AUDIT / f"windows_{year}.parquet")
        gaps = pl.read_parquet(AUDIT / f"gaps_{year}.parquet").partition_by("date", as_dict=True)
        days = windows.select(KEY).partition_by("date", as_dict=True)
        empty = next(iter(gaps.values())).head(0)
        batches = []
        for day, h in audit["partitions"].items():
            if day[:4] != str(year):
                continue
            p = BASE / str(year) / f"{day}.parquet"
            assert digest(p) == h, day
            batches.append(minute_day(day, days[(day,)], gaps.get((day,), empty)))
        minute_path = out / "minutes" / f"{year}.parquet"
        pl.concat(batches).sort(*KEY, "clock").write_parquet(minute_path)
        del batches
        verify_minutes(pl.read_parquet(minute_path), windows)
        day_panels.append(windows)
        print(year, "verified minute slots", windows.height * 61, flush=True)
    panel = window_flags(daily.select(*KEY, "observed_trade", "research_eligible").join(
        pl.concat(day_panels), on=KEY, how="left", validate="1:1")).sort(KEY)
    panel.write_parquet(out / "minute_eligibility.parquet")
    counts = panel.join(outcomes.select(*KEY, "forward_return_d1_d2"), on=KEY, validate="1:1")
    flags = [p for p in panel.columns if panel.schema[p] == pl.Boolean]
    counts.group_by("date").agg(
        *[c(p).sum().alias(p) for p in flags],
        *[(c(p) & c("research_eligible") & c("forward_return_d1_d2").is_not_null())
          .sum().alias(p + "_matched") for p in flags if p not in {"observed_trade", "research_eligible"}],
        *[(c(f"w{w}_all") == w).sum().alias(f"w{w}_strict") for w in WINDOWS],
        c("forward_return_d1_d2").count().alias("label_count"),
    ).sort("date").write_csv(out / "coverage_by_date.csv")
    for name, df in [("daily_inputs", daily), ("outcomes", outcomes), ("minute_eligibility", panel)]:
        assert pl.read_parquet(out / f"{name}.parquet").equals(df), name
    assert all(digest(p) == h for p, h in inputs.items()), "Source changed during export"
    (out / "manifest.json").write_text(json.dumps({
        "daily_snapshot": DAILY.parent.name, "minute_snapshot": BASE.name, "minute_audit": AUDIT.name,
        "polars": pl.__version__, "daily_rows": daily.height, "securities": daily["code"].n_unique(),
        "trading_dates": calendar.height, "minute_rows": sum(p.height for p in day_panels) * 61,
        "input_sha256": {str(p.relative_to(ITA)): h for p, h in inputs.items()},
        "minute_partition_sha256": audit["partitions"],
        "code_sha256": {p.name: digest(p) for p in map(Path, [__file__, Path(__file__).with_name("minute_research.py"),
                                                              Path(__file__).with_name("inputs.py")])},
        "output_sha256": {p.relative_to(out).as_posix(): digest(p) for p in sorted(out.rglob("*")) if p.is_file()},
    }, indent=2), encoding="utf-8")
    print("PASS final data readback and fingerprints", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    arg = parser.parse_args().output
    if arg.name != str(arg) or arg.name in {"", "..", "."}:
        parser.error("output must be a single new directory name")
    main(ITA / "outputs" / arg)
