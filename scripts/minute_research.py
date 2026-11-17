"""Read the versioned TRD_Dalyr minute research view."""

import polars as pl

from inputs import ARTIFACTS, DEST, KEY, PRICES


BASE = DEST / "20261113T165539897346+0800"
QUALITY = DEST / "20261113T220240141+0800"
RELEASE = DEST / "20261114T120000+0800"
OPENING_REFERENCE_PATCH = (
    ARTIFACTS / "min2016-25-official-followup/20261115T190000+0800/opening_reference_patch.parquet"
)
ADDITIONAL_OPENING_REFERENCE_PATCH = (
    ARTIFACTS / "min2016-25-opening-reference/20261115T200000+0800/opening_reference_patch.parquet"
)
PRICE_FIELDS = [*PRICES, *(f"{p}_adj" for p in PRICES)]
UNVERIFIED_ZERO_REASONS = (
    "zero_trade_cause_unresolved",
    "ipo_halt_overlap_unresolved_boundary",
    "ipo_upper_notice_unavailable",
)
c = pl.col


def scan_minutes(day: str, *, mask_unverified_zero: bool = True) -> pl.LazyFrame:
    """Read one YYYYMMDD partition with research prices, quantities and quality flags."""
    base = pl.scan_parquet(BASE / day[:4] / f"{day}.parquet")
    quality = (
        pl.scan_parquet(QUALITY / "minute_quality.parquet")
        .filter(c("date") == day)
        .select(*KEY, "minute_quality_reason", "quality_evidence", "valid_trade_quote_revised",
                "research_vol", "research_amount")
    )
    auction = (
        pl.scan_parquet(RELEASE / "auction_backfill.parquet")
        .filter(c("date") == day)
        .select(*KEY, "backfill_source", "backfill_price", "backfill_price_adj",
                "backfill_vol", "backfill_amount")
    )
    restored = c("backfill_source").is_not_null()
    revised = c("minute_quality_reason").is_not_null()
    unverified_zero = (
        c("minute_quality_reason").is_in(UNVERIFIED_ZERO_REASONS).fill_null(False)
        & pl.lit(mask_unverified_zero)
    )
    masked = c("vwap_ohlc_conflict") | (revised & c("research_vol").is_null()) | unverified_zero
    return (
        base.join(quality, on=KEY, how="left", validate="1:1", maintain_order="left")
        .join(auction, on=KEY, how="left", validate="1:1", maintain_order="left")
        .with_columns(
            (restored | pl.coalesce("valid_trade_quote_revised", "valid_trade_quote"))
            .alias("valid_trade_quote"),
            c("bar_status").alias("base_bar_status"),
            pl.when(restored).then(pl.lit("auction_backfilled"))
            .when(masked).then(pl.lit("research_unavailable"))
            .when(c("minute_quality_reason").str.starts_with("intraday_halt")).then(pl.lit("intraday_halt"))
            .otherwise("bar_status").alias("bar_status"),
            pl.when(restored).then("backfill_vol").when(masked).then(None)
            .when(revised).then("research_vol").otherwise("vol").alias("vol"),
            pl.when(restored).then("backfill_amount").when(masked).then(None)
            .when(revised).then("research_amount").otherwise("amount").alias("amount"),
            *(pl.when(restored).then("backfill_price_adj" if p.endswith("_adj") else "backfill_price")
              .otherwise(p).alias(p) for p in PRICE_FIELDS),
        )
        .with_columns(*(pl.when(c("valid_trade_quote")).then(p).alias(p) for p in PRICE_FIELDS))
        .drop("valid_trade_quote_revised", "research_vol", "research_amount", "backfill_vol",
              "backfill_amount", "backfill_price", "backfill_price_adj")
    )


def scan_stock_day_corrections() -> pl.LazyFrame:
    """Expose stock-day reference corrections and gaps remaining after auction backfill."""
    restored = pl.scan_parquet(RELEASE / "auction_backfill.parquet").select(
        "code", "date", "recovered_share_gap", "recovered_amount_gap"
    )
    return (
        pl.concat(
            [pl.scan_parquet(QUALITY / "stock_day_corrections.parquet"),
             pl.scan_parquet(OPENING_REFERENCE_PATCH),
             pl.scan_parquet(ADDITIONAL_OPENING_REFERENCE_PATCH)], how="diagonal"
        )
        .join(restored, on=["code", "date"], how="left", validate="1:1")
        .with_columns(
            (c("unallocated_share_gap") - c("recovered_share_gap").fill_null(0)).alias("remaining_share_gap"),
            (c("unallocated_amount_gap") - c("recovered_amount_gap").fill_null(0)).alias("remaining_amount_gap"),
        )
    )
