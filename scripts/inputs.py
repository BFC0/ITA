"""Read the frozen ITA inputs. Daily reference logic derives from the archived upstream source."""
import hashlib
from pathlib import Path

import polars as pl

ITA = Path(__file__).resolve().parents[1]
ROOT = ITA / "data/snapshots"
ARTIFACTS = ROOT / "artifacts/factor-library"
DAILY = ARTIFACTS / "trd-dalyr-clean/20261111T171040402190+0800/trd_dalyr_clean.parquet"
DAILY_SHA256 = "8f1ed95c5e6f62c2c8f433b8eade3d7858b57d6f7ffcc7ba164264682cd24aff"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


QUOTES = ['Opnprc', 'Hiprc', 'Loprc', 'Clsprc', 'PreClosePrice', 'LimitDown', 'LimitUp']
LIMITS = ARTIFACTS / "trd-dalyr-official/20261111T150000+0800/rule_derived_limits.parquet"
REVIEW = ARTIFACTS / "trd-dalyr-reconcile/20261111T1537435340915+0800/limit_review.parquet"
POPULATED_REVIEW = ARTIFACTS / "trd-dalyr-reconcile/20261111T1558459168167+0800/populated_limit_review.parquet"
DEST = ROOT / "data/factor-library/clean/minute_trd_dalyr"
KEY = ["code", "trade_time"]
PRICES = ["open", "high", "low", "close"]
DAILY_PRICES = QUOTES[:4]
DAILY_FIELDS = [
    "observed_trade", "price_adjustment_factor", "Markettype", "Trdsta_effective",
    "Dnshrtrd", "Dnvaltrd", *QUOTES,
]
TOL = 0.001
c = pl.col


def daily_reference():
    if digest(DAILY) != DAILY_SHA256:
        raise ValueError("Daily reference digest does not match the published snapshot")
    key = ["instrument", "Trddt"]
    review = pl.read_parquet(REVIEW, columns=[*key, "limit_review", "source_url"])
    legacy = (pl.read_parquet(POPULATED_REVIEW, columns=[*key, "category"])
              .filter(c("category") == "legacy_ipo_source_band_candidate")
              .select(*key, c("category").alias("limit_review"), pl.lit(None, dtype=pl.String).alias("source_url")))
    daily = (pl.read_parquet(DAILY, columns=[*key, *DAILY_FIELDS])
             .join(pl.concat([review, legacy]), on=key, how="left", validate="1:1")
             .join(pl.read_parquet(LIMITS, columns=[*key, "limit_down_raw", "limit_up_raw"]),
                   on=key, how="left", validate="1:1")
             .with_columns(
                 (c("instrument").str.slice(2) + "." + c("instrument").str.slice(0, 2)).alias("code"),
                 c("Trddt").dt.strftime("%Y%m%d").alias("date"),
                 *[(c(x) / c("price_adjustment_factor")).round(2).alias(x) for x in QUOTES],
             ))
    pct = (pl.when((c("Markettype") == 32) | ((c("Markettype") == 16) & (c("date") >= "20200824")))
           .then(20).when(c("Trdsta_effective").is_in([2.0, 3.0])).then(5).otherwise(10))
    ref_cents = (c("PreClosePrice") * 100).round().cast(pl.Int64)
    down = pl.min_horizontal((ref_cents * (100 - pct) + 50) // 100, ref_cents - 1) / 100
    up = pl.max_horizontal((ref_cents * (100 + pct) + 50) // 100, ref_cents + 1) / 100
    return daily.with_columns(
        down.alias("regular_down"), up.alias("regular_up"), pct.alias("regular_pct"),
    ).with_columns(
        pl.when(~c("observed_trade")).then(pl.lit("nontrading"))
        .when(c("limit_review").str.ends_with("_no_daily_limit")).then(pl.lit("event_no_daily_limit"))
        .when(c("limit_review") == "ipo_first_five_rule_consistent").then(pl.lit("ipo_first_five_candidate"))
        .when(c("limit_review").str.starts_with("legacy_")).then(pl.lit("legacy_ipo_candidate"))
        .when(((c("LimitUp") - c("regular_up")).abs() < TOL)
              & ((c("LimitDown") - c("regular_down")).abs() < TOL))
        .then(pl.lit("regular_confirmed"))
        .when(c("limit_up_raw").is_not_null()).then(pl.lit("regular_derived"))
        .when(c("LimitUp").is_not_null() & c("LimitDown").is_not_null()).then(pl.lit("source_conflict"))
        .otherwise(pl.lit("unresolved")).alias("limit_status"),
    ).with_columns(
        pl.coalesce("LimitDown", "limit_down_raw").alias("down"),
        pl.coalesce("LimitUp", "limit_up_raw").alias("up"),
    )
