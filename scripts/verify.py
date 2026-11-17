"""Read back the release and cross-check prior evidence without modifying inputs."""
import argparse
import json
from pathlib import Path

import polars as pl

from inputs import ITA
from audit import (
    ARTIFACTS, DAILY, KEY, FIELDS, RELEASE, TAIL, WINDOWS, c, digest, scan_minutes,
)

OLD = ARTIFACTS / "min2016-25-cross-source/20261114T122835936+0800/outage_crosscheck.csv"
EXTENSION = ARTIFACTS / "alpha158-close-auction/20261116T120513+0800/endpoints.csv"
ACTIONS = ARTIFACTS / "min2016-25-official-followup/20261115T190000+0800/corporate_actions.csv"
PILOT = ARTIFACTS / "alpha158-close-auction/20261115T210828+0800/bigquant_pilot.sql"


def main():
    receipt = json.loads((OUT / "verification.json").read_text(encoding="utf-8"))
    assert all(digest(OUT / p) == h for p, h in receipt["outputs"].items())
    assert receipt["trade_dates"] == 2430 and receipt["source_keys"] == 243001264
    counts = pl.read_parquet(OUT / "minute_stock_days.parquet")
    assert counts.select(KEY).n_unique() == counts.height == 1009085
    daily = pl.read_parquet(OUT / "daily_evidence.parquet")
    assert daily.select(KEY).n_unique() == daily.height == 1009083
    assert daily.filter(c("independent_trade_auction_shares").is_not_null()).is_empty()
    assert daily.filter(c("auction_status") == "inferred_only").height == 30
    frozen = pl.read_parquet(DAILY, columns=["instrument", "Trddt", "Clsprc"])
    checked = daily.join(frozen, on=["instrument", "Trddt"], validate="1:1")
    assert checked.filter(c("adjusted_close").is_not_null() &
                          (c("adjusted_close") != c("Clsprc_right"))).is_empty()

    patches = pl.read_parquet(RELEASE / "auction_backfill.parquet")
    assert patches.height == 119 and patches.select(KEY).n_unique() == 119
    assert patches.filter(c("trade_time").str.slice(-8) <= "14:56:00").is_empty()
    inferred = pl.read_parquet(TAIL)
    assert inferred.height == 30 and inferred.filter(c("trade_time").str.slice(-8) <= "14:56:00").is_empty()
    assert daily.filter(c("backfill_source").is_not_null()).height == patches.height
    for day in patches["date"].unique():
        restored = scan_minutes(day).filter(c("backfill_source").is_not_null()).collect()
        expected = patches.filter(c("date") == day)
        actual = restored.select(*KEY, "trade_time", "close", "vol", "amount").sort(KEY)
        assert actual.equals(expected.select(*KEY, "trade_time", c("backfill_price").alias("close"),
                                             c("backfill_vol").alias("vol"),
                                             c("backfill_amount").alias("amount")).sort(KEY))

    actions = pl.read_csv(ACTIONS, schema_overrides={"date": pl.String})
    action_check = actions.join(daily.select(*KEY, "reference_preclose"),
                                on=KEY, validate="1:1")
    assert action_check.height == 3 and action_check.filter(
        c("official_reference") != c("reference_preclose")).is_empty()
    extension = pl.read_csv(EXTENSION).filter(c("date") > "2025-12-31")
    assert extension.select(KEY).n_unique() == extension.height and extension["price_verified"].all()
    extension.write_parquet(OUT / "external_endpoint_evidence_2026.parquet")

    cover = pl.read_csv(OUT / "window_coverage.csv")
    summary = (cover.group_by("labels").agg(pl.exclude("labels", "market", "board", "year").sum())
               .sort("labels").with_columns(
                   (c("all") / c("expected_slots")).alias("all_fields_slot_rate"),
                   pl.when(c("labels") < 61).then(c("full_all") / c("fully_applicable_days"))
                   .alias("all_fields_complete_window_rate"),
               ))
    summary.write_csv(OUT / "window_totals.csv")
    for w in WINDOWS:
        row = summary.filter(c("labels") == w).row(0, named=True)
        assert row["full_all"] <= row["fully_applicable_days"]
        assert all(row[p + "_ok"] <= row["expected_slots"] for p in FIELDS)
    gaps = pl.scan_parquet(str(OUT / "gaps_*.parquet"))
    day_evidence = (gaps.group_by("date", "market", "reason", "applicable").agg(
        pl.len().alias("keys"), c("code").n_unique().alias("securities"))
        .sort("date", "market", "reason").collect())
    day_evidence.write_csv(OUT / "daily_gap_causes.csv")
    assert day_evidence.filter((c("date") == "20160620") &
                               c("reason").is_in(["source_timing_gap", "source_timing_boundary"]))["keys"].sum() == 846

    outage = pl.read_csv(OLD, schema_overrides={"date": pl.String})
    assert outage.height == 289
    outage.join(day_evidence.filter(c("reason").is_in(["source_timing_gap", "source_timing_boundary"]))
                .group_by("date", "market").agg(c("keys").sum().alias("window_anomaly_keys")),
                on="date", how="left", validate="m:1").write_csv(OUT / "timing_gap_source_review.csv")

    pilot_dates = ["20160122", "20200103", "20200203", "20200218", "20241122", "20260105"]
    pilot = pl.DataFrame({"date": pilot_dates})
    (pilot.join(daily.filter(c("date").is_in(pilot_dates)).group_by("date", "market", "auction_status").len(),
                on="date", how="left").with_columns(
                    pl.lit(None, dtype=pl.UInt32).alias("independent_export_rows"),
                    pl.lit("historical_export_unavailable").alias("pilot_status"),
                ).sort("date", "market", "auction_status")).write_csv(OUT / "auction_pilot_status.csv")
    inputs = [OLD, EXTENSION, ACTIONS, PILOT, Path(__file__)]
    outputs = ["external_endpoint_evidence_2026.parquet", "window_totals.csv", "daily_gap_causes.csv",
               "timing_gap_source_review.csv", "auction_pilot_status.csv"]
    verification = {
        "input_sha256": {str(p): digest(p) for p in inputs},
        "output_sha256": {p: digest(OUT / p) for p in outputs},
        "tail_backfill_keys": patches.height, "inferred_tail_keys": inferred.height,
        "verified_independent_auction_keys": 0, "tail_patch_keys_before_or_at_1456": 0,
        "external_2026_endpoint_keys": extension.height, "corporate_action_sample_keys": action_check.height,
    }
    (OUT / "handoff_verification.json").write_text(json.dumps(verification, indent=2), encoding="utf-8")
    print(summary.select("labels", "trade_days", "fully_applicable_days", "expected_slots", "all",
                         "full_all", "all_fields_slot_rate", "all_fields_complete_window_rate"))
    print("PASS release fingerprints, source-key totals, exact adjusted closes, tail scope, and archived evidence")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", help="Existing run directory name under outputs/", type=Path)
    args = parser.parse_args()
    if args.run.name != str(args.run) or args.run.name in {"", ".."}:
        parser.error("run must be a single directory name")
    OUT = ITA / "outputs" / args.run
    main()
