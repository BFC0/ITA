# TRD_Dalyr 股票池分钟行情清洗版

快照 `20261113T165539897346+0800` 覆盖 2016-01-04 至 2025-12-31。499 只股票、2,430 个交易日、243,001,264 条源分钟键全部保留。按 `YYYY/YYYYMMDD.parquet` 分片，`code, trade_time` 为唯一键。 清洗版 Parquet（本地 `data/snapshots/data/factor-library/clean/minute_trd_dalyr/20261113T165539897346+0800`） · 源分钟行情（本地 `data/snapshots/projects/factor-library/docs/datasets/minute_trd_dalyr.md`）

严格审查与验收（本地 `data/snapshots/projects/factor-library/docs/datasets/min2016_25_audit.md`）

正式研究从[分钟数据最终版](final-factor-data.md)读取。13:56–14:56 的研究表结构见[最终版字段字典](final-factor-data-fields.md)。本页说明清洗上游的整日分钟分片、字段和审计入口。

## 清洗上游读取入口

从 ITA 的 `scripts/` 运行以下 Polars 读法。版本 `20261114T120000+0800` 叠加在冻结分片和上一轮质量修订上，按原分钟键读取。 续查验收（本地 `data/snapshots/artifacts/factor-library/min2016-25-cleaning/20261114T120000+0800/work_log.md`）

```python
from minute_research import scan_minutes, scan_stock_day_corrections

bars = scan_minutes("20160122").filter(code="002739.SZ").collect()
corrections = scan_stock_day_corrections().filter(date="20160122").collect()
```

- `auction_backfilled` 表示从外部归档确认有对应的 15:00 成交，并用官方收盘价和已对账的量额重建该分钟。四个未复权价格都取官方收盘价，后复权价格使用冻结日线因子。原状态、质量原因及补录来源可分别查 `base_bar_status`、`minute_quality_reason` 和 `backfill_source`。
- `research_unavailable` 的八个价格字段和两项量额均为空，涵盖原分钟 VWAP 冲突、已屏蔽的时序异常和仍待补证的尾盘。已证实的临停标为 `intraday_halt` 并保留双零。源量额在冻结分片中可审计。
- 续查后，默认读取另外屏蔽 1,243 个原因待核的长零成交分钟，涉及缺临停时刻的 IPO 上界分钟、临停边界和聚隆科技个股疑点。复现 2026-11-14 12:00 读取口径时传入 `mask_unverified_zero=False`。 续查范围与验收（本地 `data/snapshots/artifacts/factor-library/min2016-25-cross-source/20261114T122835936+0800/work_log.md`）
- 证券日更正表提供原始差额、已恢复差额及剩余差额。日量额使用 `Dnshrtrd`、`Dnvaltrd`。分钟量额为空时，相应的区间合计及成交量因子须传播缺失。连续分钟收益须检查两个有效价格端点和分钟相邻性。
- 深交所官方日行情核实的开盘参考前收通过 `scan_stock_day_corrections()` 按 `code, date` 读取。使用 `reference_preclose`，源 09:30 值见 `raw_open_reference`。本轮接入 2024-05-30、2025-05-30、2025-06-13 共 35 条；仅有前收更正的记录，量额差额字段为空。 对账和验收（本地 `data/snapshots/artifacts/factor-library/min2016-25-opening-reference/20261115T200000+0800/work_log.md`）

## 2016-01-22 尾盘研究修订

研究修订分片（本地 `data/snapshots/artifacts/factor-library/min2016-25-official-tail/20261115T183013986+0800/research_20160122_inferred.parquet`） 可用 `pl.scan_parquet(...)` 读取，键和字段沿用当日 `scan_minutes("20160122")`。其中 30 个创业板 15:00 键标为 `bar_status = "auction_inferred_from_daily"`。四价取深交所官方日收盘价，股数取日线与原始分钟的差额，成交额按股数乘官方收盘价推算。用 `bar_status` 筛选推算记录用于敏感性分析，盘中撮合和时序验证应使用正式研究入口。现有证券日覆盖资格按正式研究入口计算。 逐键对账（本地 `data/snapshots/artifacts/factor-library/min2016-25-official-tail/20261115T183013986+0800/closing_auction_reconstruction.csv`） · 复核与验收（本地 `data/snapshots/artifacts/factor-library/min2016-25-official-tail/20261115T183013986+0800/work_log.md`）

## 证券日可用性清单

深市集中断档的官方日级更正表（本地 `data/snapshots/artifacts/factor-library/min2016-25-official-followup/20261115T190000+0800/official_daily_corrections.parquet`）按 `code, date` 连接，覆盖 2016-01-25 和 2016-06-20 的 289 个证券日。用 `official_open/high/low/close` 和 `official_preclose` 做日级分析。`official_shares_all`、`official_yuan_all` 包含大宗交易；需精确股数及与交易所扣除大宗成交后对账的口径，使用 `Dnshrtrd`、`Dnvaltrd`。这张表不改变对应分钟窗口的资格和空值。复核与验收（本地 `data/snapshots/artifacts/factor-library/min2016-25-official-followup/20261115T190000+0800/work_log.md`）

读取当前证券日 Parquet（本地 `data/snapshots/artifacts/factor-library/min2016-25-quote-coverage/20261115T181018664+0800/stock_day_coverage.parquet`），按 `code, date` 关联，覆盖 1,009,085 个证券日。用 `coverage_status` 区分成交日、全天停牌和上市前占位。只有完整 241 标签且量额无缺失时才提供 `minute_shares`、`minute_yuan`。691,847 个成交日量额完整并通过日线对账；304,385 个成交日含未知分钟，日汇总留空。

- `minute_open/high/low/close` 是当前研究分钟的首开、最高、最低、末收；`Opnprc/Hiprc/Loprc/Clsprc` 是冻结日线未复权价格。各自价差大于 0.001 元时，`open_diff/high_diff/low_diff/close_diff` 为真；缺少比较值时为空。部分分钟聚合值仅供诊断。
- `daily_ohlc_eligible` 仅在成交日量额完整且四价均匹配时为真。量额完整的证券日中，591,108 日通过，69,091 日存在其他价格差异，31,648 日是沪市旧制期间仅收盘价不同；对应 `ohlc_status` 为 `matches_daily`、`daily_price_diff`、`legacy_sh_close_only`。有未知分钟或无成交分别标为 `unknown_minutes`、`no_trade`。
- 日 OHLC 与日收益优先读取日线；分钟窗口因子仍应独立检查窗口。日价吻合不能证明分钟成交时刻正确。 本轮核查与验收（本地 `data/snapshots/artifacts/factor-library/min2016-25-quote-coverage/20261115T181018664+0800/work_log.md`） · 上一版数量覆盖与字段说明（本地 `data/snapshots/artifacts/factor-library/min2016-25-coverage/20261114T181927501+0800/work_log.md`）

## 盘中研究修订

对快照 `20261113T165539897346+0800` 应用修订表（本地 `data/snapshots/data/factor-library/clean/minute_trd_dalyr/20261113T220240141+0800`）。`minute_quality.parquet` 按 `code, trade_time` 左连接，涵盖 71,225 个已有分钟键。两个 2016 年深市集中断档及紧随的量额集中标签、2024-09-27 沪市成交确认异常窗口、攀钢钒钛部分缺量尾盘均有风险标记。2,304 个有披露支持的临停分钟仍保留零量额，公告转载与原始披露分别标记。 范围、依据及验收（本地 `data/snapshots/artifacts/factor-library/min2016-25-repair/20261113T220240141+0800/work_log.md`）

以下读取方式用于复现 2026-11-13 版。它将异常窗口的研究量额设为空，并按修订资格屏蔽实报及复权 OHLC。用修订键是否命中判断量额覆盖，显式空值代表该分钟量额未知。

```python
from pathlib import Path
import polars as pl

root = Path("../data/snapshots/data/factor-library/clean/minute_trd_dalyr")
revision = root / "20261113T220240141+0800"
key = ["code", "trade_time"]
prices = ["open", "high", "low", "close", "open_adj", "high_adj", "low_adj", "close_adj"]
patch = pl.scan_parquet(revision / "minute_quality.parquet").select(
    *key, "minute_quality_reason", "valid_trade_quote_revised", "research_vol", "research_amount"
)
bars = (
    pl.scan_parquet(root / "20261113T165539897346+0800/2016/20160125.parquet")
    .join(patch, on=key, how="left", validate="1:1")
    .with_columns(
        pl.coalesce("valid_trade_quote_revised", "valid_trade_quote").alias("valid_trade_quote"),
        pl.when(pl.col("minute_quality_reason").is_not_null())
        .then("research_vol").otherwise("vol").alias("vol"),
        pl.when(pl.col("minute_quality_reason").is_not_null())
        .then("research_amount").otherwise("amount").alias("amount"),
    )
    .with_columns(*(pl.when(pl.col("valid_trade_quote")).then(p).alias(p) for p in prices))
    .drop("valid_trade_quote_revised", "research_vol", "research_amount")
)
```

`stock_day_corrections.parquet` 按 `code, date` 使用。149 日的 `official_day_close` 用作证券日收盘价，冻结表 113 日的 `reference_preclose` 用作对应日期的参考前收。现行 `scan_stock_day_corrections()` 另外接入 2016-06-20 的 3 个除权除息参考前收，共 116 日。量额差额 `unallocated_share_gap` 和 `unallocated_amount_gap` 是冻结日线与分钟汇总的对账值。大宗交易另有 `block_volume` 和 `block_amount`。日量额使用 `Dnshrtrd`、`Dnvaltrd`，分钟空值保持未知。

## 字段字典

| 字段 | 类型及用途 |
| --- | --- |
| `code` | String。保留前导零的六位证券代码及 `.SH` 或 `.SZ` 后缀。 |
| `date` | String。交易日，`YYYYMMDD`。 |
| `trade_time` | String。北京时间源分钟标签，`YYYY-MM-DD HH:MM:00`。按此列排序，精确聚合边界待供应商确认。 |
| `session` | String。分钟标签所在时段，见下表。 |
| `bar_status` | String。记录质量与交易状态，见下表。 |
| `valid_trade_quote` | Boolean。成交量额均为有限正数且下列八个异常标志均为 false。用作本行报价读取条件。 |
| `open`, `high`, `low`, `close` | Float32。合格源未复权分钟报价，其他状态留空。 |
| `vol`, `amount` | Float32。源量额，按日线对账支持股或存托凭证份数、人民币元口径。普通零成交保留 0，148 条疑似缺失收盘分钟的量额留空。 |
| `open_adj`, `high_adj`, `low_adj`, `close_adj` | Float64。合格分钟报价乘当日 TRD_Dalyr 含红利后复权因子。日线因子含当日收盘信息，盘中撮合及点时收益应使用实报价格并单独处理公司行动。 |
| `trade_on_unconfirmed_day` | Boolean。日线未确认有成交，分钟量额却均为正。 |
| `invalid_volume_amount` | Boolean。量额既不同时为零，也不同时为有限正数。 |
| `invalid_ohlc_tick` | Boolean。有成交，但 OHLC 非正、非有限、顺序冲突或偏离一分报价档位。 |
| `outside_daily_limit` | Boolean。有成交，分钟高低越出已确认或已归档推导的常规日限价。 |
| `outside_candidate_band` | Boolean。有成交，分钟高低越出待核源限价或旧制 IPO 候选区间。 |
| `trade_outside_session` | Boolean。熔断内段或源网格外有成交。 |
| `auction_timing_conflict` | Boolean。适用收盘集合竞价的证券日，14:59 标签出现正成交量额。 |
| `vwap_ohlc_conflict` | Boolean。`amount / vol` 超出本分钟低价至高价区间 0.011 元以上。 |

| `session` 枚举 | 含义 |
| --- | --- |
| `open_boundary` | 09:30 标签。 |
| `continuous` | 源常规网格，集合竞价及熔断特定标签除外。14:57 标签归在此类。 |
| `closing_auction_window` | 深市及 2018-08-20 起沪市的 14:58–15:00 标签。 |
| `circuit_breaker` / `circuit_breaker_boundary` | 两个熔断日的内段或边界标签。 |
| `outside_source_grid` | 其他分钟标签，本次数据未出现。 |

| `bar_status` 枚举 | 条数 | 含义 |
| --- | ---: | --- |
| `trade` | 235,729,258 | 有成交且报价检查通过。 |
| `quote_conflict` | 716,597 | 本版均为分钟 VWAP 与高低价冲突。报价为空，量额保留。 |
| `zero_volume` | 3,556,492 | 普通零量零额分钟，含个股盘中临停等占位。 |
| `circuit_breaker` | 89,417 | 熔断内段零量零额分钟。 |
| `suspended` | 2,908,870 | 对应日线已确认全天停牌的零量零额分钟。 |
| `outside_daily_panel` | 482 | 本版为两个上市前占位证券日。 |
| `missing_close_candidate` | 148 | 2016-01-22 深市疑似缺失收盘成交。报价和量额均留空。 |
| `unconfirmed_trade` | 0 | 日线未确认成交的证券日出现正成交量额。 |

用 Polars 读取冻结基准中的单日合格实报价格和原始单位量额。清洗审计通过上面的 `scan_minutes` 读取版本叠加后的分片。

```python
import polars as pl

bars = (
    pl.scan_parquet(
        r"data\snapshots\data\factor-library\clean\minute_trd_dalyr\20261113T165539897346+0800\2025\20251231.parquet"
    )
    .filter((pl.col("code") == "600298.SH") & pl.col("valid_trade_quote"))
    .select("code", "trade_time", "open", "high", "low", "close", "vol", "amount")
    .sort("trade_time")
    .collect()
)
```

证券日量额、覆盖和限价应另查对账表。筛出合格报价后直接汇总量额会漏掉 `quote_conflict` 行的源成交量额。计算连续分钟收益时按时间标签和时段检查端点及相邻性，避免跨空值、午休或隔夜自动连乘。

## 按历史规则核验

- **涨跌幅和报价单位。** 用日线逐证券日的未复权前收参考价、板块、有效风险警示状态重算。主板通常 10%，样本期主板风险警示通常 5%，科创板及 2020-08-24 起的创业板通常 20%。上下限按分取整，最小变动一分。995,516 个有成交的证券日与源限价一致，128 日使用已归档规则推导限价；两组分钟报价越限均为 0。 [上交所样本期规则](https://www.sse.com.cn/lawandrules/sselawsrules2025/repeal/rules/c/c_20250612_10824490.shtml) · [深交所 2018 年规则](https://docs.static.szse.cn/www/disclosure/notice/W020180328432928783546.pdf) · [深交所 2023 年规则](https://docs.static.szse.cn/www/lawrules/rule/allrules/bussiness/W020230217564423808793.pdf) · [创业板改革](https://www.szse.cn/aboutus/trends/news/t20200821_580924.html) · [科创板交易制度](https://star.sse.com.cn/star/media/news/c/c_20190719_4866789.shtml)
- **上市及复牌事件。** 480 日符合注册制上市前五日样式，99 日符合旧制首日样式，5 日沿用日线已归档的恢复、重新上市或发行等事件依据。个别事件仍需逐股核实。旧制首日的 64%–144% 是相对发行价的有效申报范围。另有 1 个源限价与规则相差一分的证券日和 3 个常规限价缺失候选，保留在证券日对账表。价格笼子属于逐笔申报规则，分钟 OHLC 缺少所需盘口。 [沪市旧制](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20150912_3988762.shtml) · [深市旧制](https://www.szse.cn/aboutus/trends/news/t20140613_518480.html) · [主板注册制生效事件](https://www.sse.com.cn/aboutus/publication/yearly/documents/c/10764669/files/d712ddc42b2a460483be185fbbb52ea2.pdf)
- **交易时段。** 深市及 2018-08-20 起的沪市按 14:57–15:00 收盘集合竞价检查，保留相邻分钟标签边界。2016-01-04 和 2016-01-07 的熔断内段共有 89,417 条零成交分钟；紧邻熔断或复牌边界的标签单列，源分钟量额可延后出现。源分片截至 15:00，科创板和创业板 15:05 起的盘后定价数据不在本快照覆盖内。 [深市时段](https://www.szse.cn/www/investor/knowledge/stock/deal/t20191204_572383.html) · [沪市收盘机制](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20180806_4607055.shtml) · [1 月 4 日熔断](https://www.sse.com.cn/disclosure/announcement/general/c/c_20160104_4031718.shtml) · [1 月 7 日熔断](https://www.szse.cn/disclosure/notice/general/t20160107_501617.html) · [科创板盘后交易](https://www.sse.com.cn/lawandrules/sselawsrules2025/repeal/rules/c/10785121/files/13843aad02b94a07b65896db8671635c.pdf)

## 已识别的缺口

- **716,597 条分钟价量冲突。** 成交额除以成交量超出本分钟高低价至少约一分。清洗版将这些记录的 OHLC 及后复权 OHLC 留空，保留源量额，原始价量和差异可从审计表回查。供应商的分钟聚合方法尚待确认。
- **149 个证券日量额与日线不符。** 2016-01-22 深市 148 只股票的 15:00 源记录为零，且全天量额低于日线，清洗版标为疑似缺失收盘成交。2016-03-16 的 `000629.SZ` 有日总量额缺口，具体缺失分钟待查。日线差额只用于核对。
- **54,412 个证券日的最后有成交分钟收盘与日线收盘不一致。** 54,264 个发生在沪市 2018-08-20 启用收盘集合竞价之前。历史收盘价计算与分钟末价口径的差异可能解释其中一部分。逐日开高低收、量额对账均保留在证据表。 [沪市收盘规则变更](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20180806_4607055.shtml) · [熔断时收盘价口径](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20151204_4019390.shtml)

任务与验收（本地 `data/snapshots/artifacts/factor-library/minute-trd-dalyr-clean/20261113T165539897346+0800/work_log.md`） · 证券日对账（本地 `data/snapshots/artifacts/factor-library/minute-trd-dalyr-clean/20261113T165539897346+0800/stock_day_reconciliation.parquet`） · 分钟异常明细（本地 `data/snapshots/artifacts/factor-library/minute-trd-dalyr-clean/20261113T165539897346+0800/anomaly_minutes`）
