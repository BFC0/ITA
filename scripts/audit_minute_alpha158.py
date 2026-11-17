"""Audit the final ITA minute grid against the archived strict Alpha158 formulas."""
import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import numpy as np
import polars as pl
import qlib

from inputs import DAILY, DAILY_SHA256, ITA, digest

BASE = ITA / "outputs/final-factor-data-20261116"
ARCHIVE = ITA.parent.parent / "artifacts/factor-library/alpha158-minute-validation/20261115T195417+0800"
LIBRARY = ITA.parent / "factor-library"
KEY = ["code", "date"]
SAMPLES = ["20160104", "20160620", "20180903", "20200203", "20240927", "20251230"]
c = pl.col


def main(out):
    assert digest(DAILY) == DAILY_SHA256
    sys.path[:0] = [str(ARCHIVE), str(LIBRARY)]
    from audit import EXPRS, FIELDS, NAMES, SHAPES, eligible, self_check
    from replay import qlib_endpoints

    self_check()
    provenance = json.loads((BASE / "manifest.json").read_text(encoding="utf-8"))
    assert provenance["daily_snapshot"] == DAILY.parent.name
    hashes = provenance["output_sha256"]
    used = ["daily_inputs.parquet", "outcomes.parquet", *(f"minutes/{y}.parquet" for y in range(2016, 2026))]
    assert all(digest(BASE / name) == hashes[name] for name in used)
    universe = (pl.read_parquet(BASE / "daily_inputs.parquet", columns=[*KEY, "observed_trade", "research_eligible", "Dnvaltrd"])
                .join(pl.read_parquet(BASE / "outcomes.parquet", columns=[*KEY, "forward_return_d1_d2"]),
                      on=KEY, validate="1:1"))
    out.mkdir(parents=True, exist_ok=False)
    panels, replay = [], []
    for year in range(2016, 2026):
        bars = (pl.read_parquet(BASE / "minutes" / f"{year}.parquet",
                                columns=[*KEY, "lag", "open", "high", "low", "close", "vol", "vwap"])
                .rename({"vol": "volume"}))
        keys = bars.filter(c("lag") == 0).select(KEY)
        assert keys.select(KEY).n_unique() == keys.height and bars.height == keys.height * 61
        assert np.array_equal(bars["lag"].to_numpy().reshape(-1, 61)[::1],
                              np.broadcast_to(np.arange(60, -1, -1), (keys.height, 61)))
        values = bars.select(FIELDS).to_numpy().reshape(keys.height, 61, len(FIELDS))
        masks = eligible(values)
        assert np.array_equal(masks[:, NAMES.index("ROC60")], np.isfinite(values[:, [0, -1], 3]).all(axis=1))
        zero = values[:, -1, FIELDS.index("volume")] == 0
        panels.append(keys.hstack(pl.DataFrame(masks, schema=NAMES)).with_columns(pl.Series("zero_volume_now", zero)))
        sample = keys["date"].is_in(SAMPLES).to_numpy()
        if sample.any():
            replay.append((keys.filter(pl.Series(sample)), values[sample], masks[sample]))
        print(f"{year}: {keys.height:,} security-days audited", flush=True)

    panel = pl.concat(panels)
    universe = universe.join(panel, on=KEY, how="left", validate="1:1")
    assert universe.filter(c("observed_trade") != c("zero_volume_now").is_not_null()).is_empty()
    universe = universe.with_columns(c(NAMES).fill_null(False),
        (c("research_eligible") & c("forward_return_d1_d2").is_not_null()).alias("matched"),
        c("date").str.slice(0, 4).alias("year"), c("code").str.slice(-2).alias("market"),
        pl.when(c("Dnvaltrd") < 50e6).then(pl.lit("<50m"))
        .when(c("Dnvaltrd") < 200e6).then(pl.lit("50m-200m")).otherwise(pl.lit(">=200m")).alias("turnover_group"),
    ).with_columns(pl.sum_horizontal(*[c(n).cast(pl.UInt16) for n in NAMES]).alias("eligible_count"))
    universe.select(*KEY, "eligible_count", *NAMES).sort(KEY).write_parquet(out / "input_eligibility.parquet")
    traded = universe.filter("observed_trade")
    matched = universe.filter("matched")
    assert matched.height == 978561 and traded.height == 996232
    native_keys, vals, flags = map(list, zip(*replay))
    vals, flags = np.concatenate(vals), np.concatenate(flags)
    with TemporaryDirectory(dir=out) as temp:
        native = qlib_endpoints(vals, Path(temp) / "provider")
    finite = np.isfinite(native)
    strict = flags & finite
    pl.concat(native_keys).hstack(pl.DataFrame(strict, schema=NAMES)).write_parquet(out / "native_sample_validity.parquet")
    formulas = pl.DataFrame({"factor": NAMES, "expression": EXPRS,
        "family": [family for family, _, _ in SHAPES], "window": [width for _, width, _ in SHAPES],
        "required_fields_and_lags": ["; ".join(f"{FIELDS[f]}:{','.join(str(-p) for p in offsets)}" for f, offsets in req)
                                     for _, _, req in SHAPES],
        "traded_rows": traded.height, "traded_input_eligible": traded.select(c(NAMES).sum()).row(0),
        "matched_rows": matched.height, "matched_input_eligible": matched.select(c(NAMES).sum()).row(0),
        "native_sample_rows": len(vals), "native_sample_input_eligible": flags.sum(axis=0),
        "native_sample_strict_finite": strict.sum(axis=0),
        "native_sample_finite_with_bad_inputs": (finite & ~flags).sum(axis=0),
        "matched_input_eligible_at_zero_current_volume": matched.filter(c("zero_volume_now")).select(c(NAMES).sum()).row(0),
    }).with_columns((c("matched_input_eligible") / c("matched_rows")).alias("matched_input_coverage"))
    formulas.write_csv(out / "factor_coverage.csv")
    metrics = [pl.len().alias("rows"), (c("eligible_count") == 158).sum().alias("all_158_inputs"),
               (c("eligible_count") > 0).sum().alias("any_inputs"), c("eligible_count").median().alias("median_eligible"),
               c(NAMES).sum()]
    for group, stem in [(["date"], "by_date"), (["year", "market"], "by_year_market"),
                        (["market", "turnover_group"], "by_turnover_market")]:
        matched.group_by(*group).agg(*metrics).sort(group).write_csv(out / f"{stem}.csv")
    checks = {"traded": traded.height, "matched": matched.height,
              "matched_all": matched.filter(c("eligible_count") == 158).height,
              "matched_any": matched.filter(c("eligible_count") > 0).height,
              "matched_cells": matched["eligible_count"].sum(),
              "native_sample_rows": len(vals), "sample_dates": SAMPLES,
              "native_eligible_but_nonfinite": int((flags & ~finite).sum()),
              "native_finite_with_bad_inputs": int((finite & ~flags).sum())}
    assert sum(formulas["matched_input_eligible"]) == checks["matched_cells"]
    assert pl.read_parquet(out / "input_eligibility.parquet").height == universe.height
    (out / "manifest.json").write_text(json.dumps({"results": checks, "daily_sha256": DAILY_SHA256,
        "qlib": qlib.__version__, "numpy": np.__version__, "polars": pl.__version__,
        "input_sha256": {name: hashes[name] for name in used},
        "script_sha256": {str(p): digest(p) for p in (Path(__file__), ARCHIVE / "audit.py", ARCHIVE / "replay.py")},
        "output_sha256": {p.name: digest(p) for p in out.iterdir() if p.is_file()}}, indent=2), encoding="utf-8")
    print(json.dumps(checks), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    arg = parser.parse_args().output
    if arg.name != str(arg) or arg.name in {"", ".", ".."}:
        parser.error("output must be a new directory name")
    main(ITA / "outputs" / arg)
