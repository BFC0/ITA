"""Audit the frozen ITA minute input and daily close endpoints without writing to source."""
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl

from inputs import ITA, ROOT, DAILY, DAILY_SHA256, daily_reference, digest
from minute_research import (
    ARTIFACTS, BASE, QUALITY, RELEASE, OPENING_REFERENCE_PATCH,
    ADDITIONAL_OPENING_REFERENCE_PATCH, scan_minutes, scan_stock_day_corrections,
)

c = pl.col
KEY = ["code", "date"]
FIELDS = ["open", "high", "low", "close", "vol", "amount", "vwap"]
WINDOWS = [1, 5, 10, 20, 30, 60]
CALENDAR = ROOT / "data/qlib/cn_data/calendars/day.parquet"
MEMBERS = ROOT / "data/qlib/cn_data/instruments/csi500.parquet"
COVER = ARTIFACTS / "min2016-25-quote-coverage/20261115T181018664+0800/stock_day_coverage.parquet"
OFFICIAL = ARTIFACTS / "min2016-25-official-followup/20261115T190000+0800/official_daily_corrections.parquet"
TAIL = ARTIFACTS / "min2016-25-official-tail/20261115T183013986+0800/closing_auction_reconstruction.parquet"
JAN22 = ARTIFACTS / "min2016-25-official/20261113T174005891555+0800/official_turnover_gaps.csv"
MANIFEST = ARTIFACTS / "minute-trd-dalyr-clean" / BASE.name / "manifest.json"
PLANS = ITA / "artifacts/minute-cleaning"
PLAN = PLANS / "20261116T180338+0800/execution.md"


def dump(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def write(name, frame, key):
    assert frame.select(key).n_unique() == frame.height, name
    path = OUT / (name + ".parquet")
    frame.sort(key).write_parquet(path)
    assert frame.sort(key).equals(pl.read_parquet(path)), name


def audit_day(day, ref, part):
    path = BASE / part["file"]
    assert digest(path) == part["sha256"], day
    bars = scan_minutes(day).collect()
    assert bars.height == part["rows"] == bars.select("code", "trade_time").n_unique()
    source_counts = bars.group_by("code").len(name="observed_source_rows")
    bars = bars.with_columns(c("trade_time").str.slice(-8).alias("clock"))
    day_ref = ref.filter(c("date") == day).select(*KEY, "observed_trade", "gap_status", "market", "board")
    counts = day_ref.join(source_counts, on="code", how="full", coalesce=True).with_columns(pl.lit(day).alias("date"))
    tail = bars.filter(c("clock") == "15:00:00").select(
        *KEY, "session", "base_bar_status", "bar_status", "backfill_source",
        "valid_trade_quote", c("close").alias("minute_close"),
        c("vol").alias("minute_shares"), c("amount").alias("minute_yuan"),
    )
    grid = pl.DataFrame({
        "clock": [(datetime(2000, 1, 1, 14, 56) - timedelta(minutes=i)).strftime("%H:%M:%S")
                  for i in range(61)],
        "lag": pl.Series(range(61), dtype=pl.UInt8),
    })
    active = day_ref.filter(c("observed_trade"))
    slots = active.join(grid, how="cross").join(
        bars.drop("date"), on=["code", "clock"], how="left", validate="1:1"
    )
    assert slots.height == active.height * 61
    forbidden = pl.lit(day in ("20160104", "20160107"))
    slots = slots.with_columns(
        (~forbidden & (c("bar_status") != "intraday_halt").fill_null(True)).alias("applicable"),
        (c("valid_trade_quote") & (c("vol") > 0) & (c("amount") > 0)).fill_null(False).alias("priced"),
        (c("bar_status").is_in(["zero_volume", "intraday_halt"]) & (c("vol") == 0) &
         (c("amount") == 0)).fill_null(False).alias("known_zero"),
    ).with_columns(
        pl.when(forbidden).then(pl.lit("market_circuit_breaker"))
        .when(c("trade_time").is_null()).then(pl.lit("source_missing"))
        .when(c("minute_quality_reason").is_not_null()).then(c("minute_quality_reason"))
        .when(c("vwap_ohlc_conflict")).then(pl.lit("vwap_ohlc_conflict"))
        .when(c("bar_status") == "quote_conflict").then(pl.lit("field_conflict"))
        .otherwise("bar_status").alias("reason"),
        *[(c("applicable") & c("priced") & c(p).is_finite() & (c(p) > 0))
          .fill_null(False).alias(p + "_ok") for p in FIELDS[:4]],
        *[(c("applicable") & (c("priced") | c("known_zero")) & c(p).is_finite())
          .fill_null(False).alias(p + "_ok") for p in ["vol", "amount"]],
        (c("applicable") & c("priced")).alias("vwap_ok"),
    )
    ok = [p + "_ok" for p in FIELDS]
    windows = slots.group_by(*KEY, "market", "board").agg(
        *[c(p).filter(c("lag") == 60).first().alias("lag60_" + p) for p in ok],
        c("applicable").filter(c("lag") == 60).first().alias("lag60_applicable"),
        *[c("applicable").filter(c("lag") < w).sum().cast(pl.UInt8).alias(f"w{w}_expected")
          for w in WINDOWS],
        *[c(p).filter(c("lag") < w).sum().cast(pl.UInt8).alias(f"w{w}_{p}")
          for w in WINDOWS for p in ok],
        *[pl.all_horizontal(ok).filter(c("lag") < w).sum().cast(pl.UInt8).alias(f"w{w}_all")
          for w in WINDOWS],
    )
    gaps = slots.filter(~pl.all_horizontal(ok)).select(
        *KEY, "clock", "lag", "market", "board", "applicable", "reason", "base_bar_status",
        "bar_status", "quality_evidence", *ok,
    )
    assert gaps.height + slots.filter(pl.all_horizontal(ok)).height == slots.height
    assert tail.filter(c("backfill_source").is_not_null()).height == bars.filter(
        c("backfill_source").is_not_null()).height
    return counts, tail, windows, gaps


def main(smoke):
    parts = {Path(x["file"]).stem: x for x in json.loads(MANIFEST.read_text())["files"]}
    calendar = pl.read_parquet(CALENDAR).select(c("date").str.replace_all("-", ""))
    dates = calendar.filter(c("date").is_between(pl.lit("20160104"), pl.lit("20251231")))
    assert dates["date"].to_list() == sorted(parts)
    assert digest(DAILY) == DAILY_SHA256
    initial = [MANIFEST, DAILY, COVER, CALENDAR, MEMBERS, OFFICIAL, TAIL, JAN22, PLAN,
               PLANS / "20261116T123633+0800/plan.md",
               ROOT / "projects/factor-library/docs/datasets/minute_trd_dalyr_clean.md",
               QUALITY / "minute_quality.parquet", QUALITY / "stock_day_corrections.parquet",
               RELEASE / "auction_backfill.parquet", OPENING_REFERENCE_PATCH,
               ADDITIONAL_OPENING_REFERENCE_PATCH, Path(__file__).with_name("minute_research.py"),
               Path(__file__).with_name("inputs.py"), Path(__file__).resolve()]
    rules = json.loads(MANIFEST.read_text())["rule_inputs"]
    rules = {str(ARTIFACTS / Path(*Path(p).parts[4:])): h
             for p, h in rules.items()}
    inputs = {str(p): digest(p) for p in [*initial, *map(Path, rules)]}
    assert all(inputs[p] == h for p, h in rules.items())
    ref = daily_reference().with_columns(
        c("code").str.slice(-2).alias("market"),
        c("Markettype").replace_strict({1: "沪市主板", 4: "深市主板", 16: "创业板", 32: "科创板"}).alias("board")
    ).join(pl.read_parquet(DAILY, columns=[
        "instrument", "Trddt", "gap_status", "invalid_quote", "Capchgdt", "quote_crosscheck",
        "trade_status_sources", "suspension_sources", "review_sources", "source_row",
        "return_total_daily_checked", "return_span_status", "is_st", "research_eligible",
        "Clsprc",
    ]).rename({"Clsprc": "snapshot_adjusted_close"}), on=["instrument", "Trddt"], validate="1:1")
    assert ref.height == 1009083 and ref["code"].n_unique() == 499
    dump("inputs.json", {"inputs": inputs, "polars": pl.__version__,
                    "partitions": {d: p["sha256"] for d, p in parts.items()}})
    samples = ["20251230", "20160122", "20160620", "20240927"]
    result = {day: audit_day(day, ref, parts[day]) for day in samples}
    smoke_rows = []
    for day, (counts, tail, windows, gaps) in result.items():
        smoke_rows.append({"date": day, "trade_days": windows.height,
                           "source_rows": counts["observed_source_rows"].sum(),
                           "gap_keys": gaps.height, "tail_backfills": tail["backfill_source"].is_not_null().sum()})
    assert result["20160122"][1]["backfill_source"].is_not_null().sum() > 0
    assert result["20160620"][3].filter(c("market") == "SZ").height > 0
    assert result["20240927"][3].filter(c("market") == "SH").height > 0
    assert result["20251230"][2].filter(c("w60_all") == 60).height > 0
    dump("smoke.json", smoke_rows)
    print("SMOKE", smoke_rows, flush=True)
    if smoke:
        return

    all_counts, all_tail, cover_rows, priority = [], [], [], []
    for year in range(2016, 2026):
        batch = [result[day] if day in result else audit_day(day, ref, part)
                 for day, part in parts.items() if day.startswith(str(year))]
        counts, tail, windows, gaps = map(pl.concat, zip(*batch))
        all_counts.append(counts)
        all_tail.append(tail)
        write(f"windows_{year}", windows, KEY)
        write(f"gaps_{year}", gaps, [*KEY, "clock"])
        for w in WINDOWS:
            vals = [f"w{w}_{p}" for p in [*(p + "_ok" for p in FIELDS), "all"]]
            groups = windows.group_by("market", "board").agg(
                pl.len().alias("trade_days"), (c(f"w{w}_expected") == w).sum().alias("fully_applicable_days"),
                c(f"w{w}_expected").sum().alias("expected_slots"),
                *[c(v).sum().alias(v.removeprefix(f"w{w}_")) for v in vals],
                *[(c(v) == w).sum().alias("full_" + v.removeprefix(f"w{w}_")) for v in vals],
            ).with_columns(pl.lit(year).alias("year"), pl.lit(w).alias("labels"))
            cover_rows.append(groups)
        cover_rows.append(windows.group_by("market", "board").agg(
            pl.len().alias("trade_days"), c("lag60_applicable").sum().alias("fully_applicable_days"),
            c("lag60_applicable").sum().alias("expected_slots"),
            *[c("lag60_" + p + "_ok").sum().alias(p + "_ok") for p in FIELDS],
            pl.all_horizontal(*["lag60_" + p + "_ok" for p in FIELDS]).sum().alias("all"),
        ).with_columns(pl.lit(year).alias("year"), pl.lit(61).alias("labels")))
        priority.append(gaps.with_columns(c("lag").replace_strict(
            {i: sum(i < w for w in WINDOWS if w != 1) for i in range(61)}).alias("windows_hit"))
            .group_by("date", "market", "board", "reason", "applicable")
            .agg(pl.len().alias("gap_keys"), c("code").n_unique().alias("stock_days"),
                 c("windows_hit").sum().alias("window_label_impacts"),
                 c("lag").eq(0).sum().alias("at_1456"), c("lag").eq(60).sum().alias("at_lag60")))
        print("YEAR", year, "trade-days", windows.height, "gap keys", gaps.height, flush=True)
    pl.concat(cover_rows, how="diagonal_relaxed").sort("year", "labels", "market", "board").write_csv(OUT / "window_coverage.csv")
    pl.concat(priority).sort("window_label_impacts", "stock_days", descending=True).write_csv(OUT / "gap_priority.csv")
    finish(ref, dates, pl.concat(all_counts), pl.concat(all_tail), parts, inputs)


def finish(ref, dates, counts, tail, parts, inputs):
    assert counts["observed_source_rows"].sum() == sum(p["rows"] for p in parts.values())
    coverage = pl.read_parquet(COVER)
    assert counts.join(coverage.select(*KEY, "source_minutes"), on=KEY, how="full", coalesce=True,
                       validate="1:1").filter(
        c("observed_source_rows").fill_null(0) != c("source_minutes").fill_null(0)).is_empty()
    write("minute_stock_days", counts, KEY)
    assert counts.group_by("date").agg(c("observed_source_rows").sum()).height == len(parts)
    members = pl.read_parquet(MEMBERS).join_where(
        dates, c("date") >= c("start_datetime").str.replace_all("-", ""),
        c("date") <= c("end_datetime").str.replace_all("-", ""),
    ).select("instrument", "date").unique()
    roster = ref.select("code", "instrument").unique()
    members = members.join(roster, on="instrument", how="left", validate="m:1").join(
        counts.select(*KEY, "observed_source_rows"), on=KEY, how="left", validate="m:1")
    members.group_by("date").agg(
        pl.len().alias("local_roster_members"), c("code").is_not_null().sum().alias("in_fixed_pool"),
        (c("observed_source_rows").fill_null(0) > 0).sum().alias("with_minute_rows"),
    ).sort("date").write_csv(OUT / "csi500_overlap.csv")
    write("csi500_missing", members.filter(c("observed_source_rows").fill_null(0) == 0), ["instrument", "date"])

    official = pl.read_parquet(OFFICIAL).select(*KEY, "official_close")
    corrections = scan_stock_day_corrections().collect()
    assert corrections.select(KEY).n_unique() == corrections.height
    jan22 = pl.read_csv(JAN22, schema_overrides={"date": pl.String}).select(
        *KEY, c("official_close").alias("official_jan22"))
    inferred = pl.read_parquet(TAIL).select(*KEY).unique().with_columns(pl.lit(True).alias("inferred_tail"))
    daily = ref.join(coverage.select(*KEY, "minute_close", "ohlc_status"),
                     on=KEY, how="left", validate="1:1").rename({"minute_close": "last_valid_minute_close"})
    daily = (daily.join(official, on=KEY, how="left", validate="1:1")
             .join(jan22, on=KEY, how="left", validate="1:1")
             .join(corrections.select(*KEY, "official_day_close", "reference_preclose", "reference_basis",
                                      "remaining_share_gap", "remaining_amount_gap"),
                   on=KEY, how="left", validate="1:1")
             .join(inferred, on=KEY, how="left", validate="1:1")
             .join(tail, on=KEY, how="left", validate="1:1")
             .with_columns(pl.coalesce("official_close", "official_jan22", "official_day_close").alias("exchange_close"))
             .with_columns(
        pl.when(~c("observed_trade")).then(pl.coalesce("gap_status", pl.lit("nontrading")))
        .when(c("invalid_quote").fill_null(True) | ~c("Clsprc").is_finite().fill_null(False) |
              (c("Clsprc") <= 0).fill_null(True)).then(pl.lit("invalid_daily_quote"))
        .when(c("exchange_close").is_not_null() & ((c("Clsprc") - c("exchange_close")).abs() > 0.001))
        .then(pl.lit("exchange_source_conflict")).otherwise(pl.lit("priced")).alias("close_status"))
             .with_columns(pl.when(c("close_status") == "priced").then("Clsprc").alias("raw_close"),
                           pl.when(c("close_status") == "priced").then("snapshot_adjusted_close").alias("adjusted_close"),
                           c("backfill_source").is_null().and_(c("base_bar_status") == "trade")
                           .and_(c("valid_trade_quote")).fill_null(False).alias("original_1500_report")))
    daily = daily.with_columns(
        pl.when(~c("observed_trade")).then(pl.lit("nontrading"))
        .when(c("date").is_in(["20160104", "20160107"])).then(pl.lit("circuit_breaker_day"))
        .when((c("market") == "SH") & (c("date") < "20180820")).then(pl.lit("sh_legacy_close"))
        .when(c("backfill_source").is_not_null()).then(pl.lit("crosschecked_backfill"))
        .when(c("inferred_tail").fill_null(False)).then(pl.lit("inferred_only"))
        .when(~c("original_1500_report")).then(pl.lit("missing_eligible_1500"))
        .when(c("raw_close").is_null()).then(pl.lit("daily_close_unusable"))
        .when((c("minute_close") - c("raw_close")).abs() <= 0.005)
        .then(pl.lit("price_matches_bucket_unverified")).otherwise(pl.lit("price_mismatch")).alias("auction_status"),
        pl.lit(None, dtype=pl.Float64).alias("independent_trade_auction_shares"),
        pl.lit(None, dtype=pl.Float64).alias("independent_trade_auction_yuan"))
    write("daily_evidence", daily, KEY)
    daily.with_columns(c("date").str.slice(0, 4).alias("year")).group_by(
        "year", "market", "auction_status", "close_status").len().sort(
        "year", "market", "auction_status", "close_status").write_csv(OUT / "close_coverage.csv")

    shifts = dates.sort("date").with_columns(c("date").shift(-1).alias("d1"), c("date").shift(-2).alias("d2"))
    endpoints = daily.select(*KEY, "observed_trade").join(shifts, on="date", validate="m:1")
    for d in ["d1", "d2"]:
        endpoints = endpoints.join(daily.select(
            "code", c("date").alias(d), c("raw_close").alias(d + "_raw_close"),
            c("close_status").alias(d + "_status"),
            c("return_total_daily_checked").alias(d + "_return_total"),
        ), on=["code", d], how="left", validate="m:1").with_columns(
            pl.when(c(d).is_null()).then(pl.lit("outside_frozen_sample"))
            .otherwise(c(d + "_status").fill_null("missing_stock_day")).alias(d + "_status"))
    write("endpoints", endpoints, KEY)
    assert all(digest(Path(p)) == h for p, h in inputs.items())
    dump("verification.json", {
        "trade_dates": len(parts), "source_keys": counts["observed_source_rows"].sum(),
        "stock_day_keys": counts.height, "daily_keys": daily.height,
        "csi500_keys": members.height, "csi500_in_pool": members["code"].is_not_null().sum(),
        "csi500_minute_present": (members["observed_source_rows"].fill_null(0) > 0).sum(),
        "csi500_distinct": members["instrument"].n_unique(),
        "csi500_never_in_pool": members.filter(c("code").is_null())["instrument"].n_unique(),
        "daily_close": daily.group_by("close_status").len().to_dicts(),
        "auction": daily.group_by("auction_status").len().to_dicts(),
        "both_priced_on_traded_signal": endpoints.filter(
            c("observed_trade") & (c("d1_status") == "priced") & (c("d2_status") == "priced")).height,
        "outputs": {p.name: digest(p) for p in sorted(OUT.iterdir()) if p.suffix in (".csv", ".parquet")},
    })
    print("PASS reference fingerprints, source-key conservation, readbacks", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", help="New run directory name under outputs/", type=Path)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    if args.output.name != str(args.output) or args.output.name in {"", ".."}:
        parser.error("output must be a single new directory name")
    OUT = ITA / "outputs" / args.output
    OUT.mkdir(parents=True, exist_ok=False)
    main(args.smoke)
