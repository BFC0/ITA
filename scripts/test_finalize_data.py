import unittest

import polars as pl

from finalize_data import gate_slots, label_return, window_flags


class FinalDataTests(unittest.TestCase):
    def test_field_masks_keep_real_zero_but_not_unknown_values(self):
        fields = ["open", "high", "low", "close", "vol", "amount", "vwap"]
        slots = pl.DataFrame({**{p: [0.0, 99.0, 3.0, 3.0] for p in fields},
                              "applicable": [True, True, None, False],
                              **{f"{p}_ok": [p in {"vol", "amount"}, False, None, False]
                                 for p in fields}})
        got = gate_slots(slots)
        self.assertEqual(got["vol"].to_list(), [0, None, 3, None])
        self.assertEqual(got["close"].to_list(), [None, None, 3, None])

    def test_missing_interior_does_not_block_fixed_endpoints(self):
        fields = ["open", "high", "low", "close", "vol", "amount", "vwap"]
        row = {f"w{w}_{p}_ok": [w if p in {"vol", "amount"} or w == 1 else w - 1]
               for w in (1, 5, 10, 20, 30, 60) for p in fields}
        row.update(w60_expected=[60], lag60_close_ok=[True])
        got = window_flags(pl.DataFrame(row)).row(0, named=True)
        self.assertTrue(got["ret60_endpoints_ok"])
        self.assertFalse(got["w60_close_path_ok"])
        self.assertTrue(got["w60_turnover_ok"])

    def test_missing_market_endpoint_is_not_zero_return(self):
        got = pl.DataFrame({"d1_status": ["priced", "confirmed_suspension", "priced"],
                            "d2_status": ["priced"] * 3,
                            "d2_return_total": [0.0, 0.1, None]}).select(label_return())
        self.assertEqual(got.to_series().to_list(), [0.0, None, None])


if __name__ == "__main__":
    unittest.main()
