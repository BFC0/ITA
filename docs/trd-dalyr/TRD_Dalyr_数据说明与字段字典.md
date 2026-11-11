# TRD_Dalyr 2016–2025 数据说明与数据字典

## 当前快照

ITA 当前使用已验收快照 `20261111T171040402190+0800`。主表是证券日面板，以 `instrument, Trddt` 为唯一主键。覆盖 2016-01-04 至 2025-12-31、499 只沪深证券、2,430 个市场交易日，共 **1,009,083 行、50 列**。其中 996,232 行有源成交，12,851 行为已确认停牌或暂停上市的对齐行，980,572 行满足研究样本筛选条件。覆盖范围由本批证券和各自可核验区间决定。

| 文件 | 行 × 列 | 用途 |
| --- | ---: | --- |
| | 1,009,083 × 50 | 研究主表 |
| | 12,851 × 6 | 停牌缺行与证据 |
| | 54,554 × 21 | 报价、限价或收益异常筛查 |
| | 128 × 9 | 独立归档的规则推导限价 |

主表 SHA-256 为 `8f1ed95c5e6f62c2c8f433b8eade3d7858b57d6f7ffcc7ba164264682cd24aff`。日历用 Qlib 对齐，停牌对照行情用于审计。上交所行情和派息公告用于修订安琪酵母自 2021-06-29 起的 1,096 条含红利后复权收盘，其中 2 日重算 `Dretwd`。东凌国际 122 个交易日使用公告核验后的有效交易状态。

## 使用口径

1. **价格和撮合。** `price_adjustment_factor = Adjprcwd / 原始收盘价`，价格基准为上市首日，含现金红利再投资。OHLC、前收参考价、双边限价均以当日因子换算，`Clsprc` 等于 `Adjprcwd`。撮合和按成交价格计算费用时，用相应报价除以因子还原。成交量和成交额保留原单位。
2. **收益和标签。** 连续市场日的含红利收盘收益用 `return_total_daily_checked`。源收益及 `return_total_source_checked` 可包含首观测和跨停牌收益。交易涨跌幅 `ChangeRatio` 使用交易所前收参考价。开盘到开盘总收益需按实际开盘价和持有期公司行动权益计算，收盘复权因子在除息日包含当天收盘信息。
3. **停牌、估值与可交易性。** 已确认停牌日的成交股数为 0，实报价格、成交额与收益为空。`reference_close` 可用于估值，连续确认停牌达 300 个市场交易日时留空。`research_eligible` 用于当日收盘后研究筛选。实际下单另查执行日成交、停牌和涨跌停约束。
4. **核验范围。** 当前版两套收盘收益均通过源内一致性核查。主表成交行仍有 672 对源限价为空，128 对规则推导结果保存在独立补充表。全样本公司行动及上市至样本前的复权倍率尚未逐笔按独立公告核验。 [CSMAR 字段与公式](https://file.csmar.com/group1/M00/AA/99/CuIKV2XAnKiABeLbAB4nDGC5Ano840.pdf)

## 主表字典

类型和空值数来自本版 Parquet 实测。币种为人民币。收益率为小数，`0.05` 表示 5%。空值计数保留 `null` 与真实零值的区别。

### 标识与来源

| 字段 | 类型 | 空值数 | 定义 |
| --- | --- | ---: | --- |
| `instrument` | `String` | 0 | 主键。交易所前缀 `SH` 或 `SZ` 加六位证券代码。 |
| `Trddt` | `Date` | 0 | 主键。北京时间的市场交易日期。 |
| `Stkcd` | `String` | 12851 | CSMAR 六位证券代码，保留前导零。对齐行可从 `instrument` 取代码。 |
| `Markettype` | `Float64` | 12851 | 源枚举。1 沪市 A 股主板，4 深市 A 股主板，16 创业板，32 科创板。 |
| `Capchgdt` | `Date` | 12851 | 源记录对应的最近一次股本变动日。 |
| `source_row` | `Boolean` | 0 | 真表示有 CSMAR 源行，包含基于该源行修订的记录。假表示日历对齐行。 |

### 报价、成交和市值

| 字段 | 类型 | 空值数 | 定义 |
| --- | --- | ---: | --- |
| `Opnprc` | `Float64` | 12851 | 后复权开盘价，元/股。 |
| `Hiprc` | `Float64` | 12851 | 后复权最高价，元/股。 |
| `Loprc` | `Float64` | 12851 | 后复权最低价，元/股。 |
| `Clsprc` | `Float64` | 12851 | 后复权收盘价，元/股，与 `Adjprcwd` 一致。 |
| `PreClosePrice` | `Float64` | 12851 | 按当日因子换算的交易所前收参考价，元/股。 |
| `LimitDown` | `Float64` | 13523 | 源跌停价按当日因子换算，元/股。空值包含 672 个成交日。 |
| `LimitUp` | `Float64` | 13523 | 源涨停价按当日因子换算，元/股。空值包含 672 个成交日。 |
| `Dnshrtrd` | `Float64` | 0 | 日成交股数，股。确认停牌日为 0。 |
| `Dnvaltrd` | `Float64` | 12851 | 日成交额，元。 |
| `Ahshrtrd_D` | `Float64` | 307174 | 盘后成交股数，股。源字段缺失保留为空。 |
| `Ahvaltrd_D` | `Float64` | 307174 | 盘后成交额，元。源字段缺失保留为空。 |
| `Dsmvosd` | `Float64` | 12851 | 流通市值，千元。 |
| `Dsmvtll` | `Float64` | 12851 | 总市值，千元。 |

### 复权和收益

| 字段 | 类型 | 空值数 | 定义 |
| --- | --- | ---: | --- |
| `Adjprcwd` | `Float64` | 12851 | 含现金红利再投资的后复权收盘价，元/股。安琪酵母修订已并入。 |
| `price_adjustment_factor` | `Float64` | 12851 | 含红利后复权收盘价除以原始收盘价，无量纲。 |
| `ChangeRatio` | `Float64` | 12851 | 源交易涨跌幅，与 `Clsprc / PreClosePrice - 1` 在舍入容差内一致。 |
| `Dretwd` | `Float64` | 12851 | 含现金红利再投资的日个股收益。安琪酵母两日使用核验值。 |
| `Dretnd` | `Float64` | 12851 | 源日个股收益，不计现金红利，仍反映送转等股本调整。 |
| `return_total_source_checked` | `Float64` | 12851 | 通过报价检查且无已知含红利复权冲突的 `Dretwd`，可包含首观测和跨停牌收益。 |
| `return_total_daily_checked` | `Float64` | 13921 | 当天与前一市场交易日均有有效成交报价且通过含红利对账时保留的 `Dretwd`。 |
| `return_conflict` | `Boolean` | 13350 | 相邻源记录的 `Adjprcwd` 环比与 `Dretwd` 相差超过 `1e-5` 时为真。停牌行和各证券首观测为空。 |
| `return_ex_div_conflict` | `Boolean` | 13350 | 相邻源记录的不含红利复权收盘环比与 `Dretnd` 相差超过 `1e-5` 时为真。停牌行和各证券首观测为空。源字段 `Adjprcnd` 用于计算此标记。 |

### 交易状态与停牌

| 字段 | 类型 | 空值数 | 定义 |
| --- | --- | ---: | --- |
| `Trdsta` | `Float64` | 12851 | 源交易状态。1 正常、2 ST、3 *ST。代码 10 的本批口径待确认。 |
| `Trdsta_effective` | `Float64` | 12851 | 有公告修订时使用核验状态，其余沿用 `Trdsta`。 |
| `trade_status_sources` | `List[String]` | 1008961 | 122 个交易状态修订键的证据链接。 |
| `LimitStatus` | `Float64` | 13393 | 源收盘限价状态。−1 跌停，0 未触限，1 涨停。 |
| `is_st` | `Boolean` | 20020 | 有效状态为 2 或 3 时真，为 1 时假。状态 10 和停牌对齐行为空。 |
| `observed_trade` | `Boolean` | 0 | 有源行且成交股数有限并大于零时为真，已确认停牌行取假。 |
| `gap_status` | `String` | 996232 | 本版停牌和暂停上市对齐行均为 `confirmed_suspension`，源行为空。 |
| `suspension_sources` | `List[String]` | 996232 | 停牌或暂停上市证据链接。 |
| `suspension_days_so_far` | `UInt32` | 996232 | 截至当日连续确认停牌的市场交易日数，首日为 1。 |
| `reference_close` | `Float64` | 1097 | 成交日取有效后复权收盘。连续确认停牌期间沿用停牌前可用后复权收盘，满 300 个市场交易日或缺少前值时为空。 |

### 质量标记与审阅

| 字段 | 类型 | 空值数 | 定义 |
| --- | --- | ---: | --- |
| `invalid_quote` | `Boolean` | 12851 | 必需字段缺失或非有限、指定价格或价量非正、OHLC 关系错误，或成交均价越过高低价容差时为真。 |
| `limit_prices_missing` | `Boolean` | 12851 | 源行至少一个限价为空时为真。 |
| `outside_limits` | `Boolean` | 12851 | 源最高或最低报价越过源限价容差 0.001 元，或限价关系无效时为真。需结合限价缺失标记判读。 |
| `limit_status_diff` | `Boolean` | 13523 | 源状态与收盘触限方向不一致时为真。缺少核验输入时为空。 |
| `one_price_day` | `Boolean` | 12851 | 源日高低价差不超过 0.001 元。 |
| `large_return` | `Boolean` | 12851 | `abs(Dretwd) > 0.15` 时为真。 |
| `return_iqr_outlier` | `Boolean` | 25705 | 当日连续日收益低于 Q1 − 1.5 × IQR 或高于 Q3 ＋ 1.5 × IQR 时为真。Q1、Q3 取此前 60 个市场交易日，窗口至少 20 个有效收益且 IQR 大于 0。 |
| `research_eligible` | `Boolean` | 0 | 有成交、有效报价、双边限价齐备且状态一致、无已知复权冲突、非一字报价、有效状态为 1 时为真。 |
| `anomaly_review` | `String` | 954529 | 异常筛查分类，现有枚举见下表。 |
| `quote_crosscheck` | `String` | 1008938 | 选定记录的外部收盘和成交量核对，取 `qlib_close_and_volume` 或 `sse_close_and_volume`。 |
| `return_span_status` | `String` | 1008903 | 选定收益端点的核验类别。见下文。 |
| `review_sources` | `List[String]` | 1008758 | 逐键补充审阅的证据链接。 |

`return_span_status` 取 `confirmed_ipo`（确认上市首日）、`ipo_candidate`（候选上市首日）、`confirmed_resume`（已有证据确认复牌）、`resume_crosschecked`（另有外部核对）或 `resume_inferred_from_trade`（按下一次实际成交定位）。

| `anomaly_review` 实际值 | 行数 | 含义 |
| --- | ---: | --- |
| `within_source_limits` | 53654 | 命中筛查，源报价通过限价检查。 |
| `unverified_missing_limits` | 672 | 源限价缺失。 |
| `cash_dividend_effect_and_within_source_limits` | 180 | 源限价检查通过，且两种收益绝对差超过 `1e-5`。 |
| `unverified_return_span` | 48 | 前一市场交易日缺有效成交，需核对收益区间。 |

## 附表字典

### 停牌缺行核对表

与主表 `source_row = false` 的记录一一对应。本版全部键在 Qlib 有对齐行，且没有同时满足正收盘价和正成交量条件的记录。

| 字段 | 类型 | 空值数 | 定义 |
| --- | --- | ---: | --- |
| `instrument` | `String` | 0 | 主键，证券标识。 |
| `Trddt` | `Date` | 0 | 主键，市场交易日。 |
| `qlib_row` | `Boolean` | 0 | Qlib 是否存在对应键，本版全部为真。 |
| `crosscheck` | `String` | 0 | 本版均为 `qlib_row_without_positive_price_volume`。 |
| `gap_status` | `String` | 0 | 本版均为 `confirmed_suspension`。 |
| `suspension_sources` | `List[String]` | 0 | 停牌证据链接。 |

### 异常审阅表

从主表选取 `anomaly_review` 有值的记录。以下字段定义与主表相同，空值数按本附表统计。

| 字段 | 类型 | 空值数 |
| --- | --- | ---: |
| `instrument` | `String` | 0 |
| `Trddt` | `Date` | 0 |
| `Markettype` | `Float64` | 0 |
| `Trdsta` | `Float64` | 0 |
| `Dretwd` | `Float64` | 0 |
| `Dretnd` | `Float64` | 0 |
| `ChangeRatio` | `Float64` | 0 |
| `LimitStatus` | `Float64` | 542 |
| `LimitDown` | `Float64` | 672 |
| `LimitUp` | `Float64` | 672 |
| `return_iqr_outlier` | `Boolean` | 607 |
| `large_return` | `Boolean` | 0 |
| `limit_prices_missing` | `Boolean` | 0 |
| `return_conflict` | `Boolean` | 197 |
| `research_eligible` | `Boolean` | 0 |
| `anomaly_review` | `String` | 0 |
| `quote_crosscheck` | `String` | 54409 |
| `return_span_status` | `String` | 54506 |
| `review_sources` | `List[String]` | 54361 |
| `Trdsta_effective` | `Float64` | 0 |
| `trade_status_sources` | `List[String]` | 54554 |

### 规则推导限价补充表

独立归档了 2016-03-08 的 128 对规则推导限价。以未复权前收参考价计算 ±10% 限价，先在原始报价单位取整至分，再乘当日因子。主表对应的源限价仍为空。

| 字段 | 类型 | 空值数 | 定义 |
| --- | --- | ---: | --- |
| `instrument` | `String` | 0 | 主键，证券标识。 |
| `Trddt` | `Date` | 0 | 主键，市场交易日。 |
| `PreClosePrice` | `Float64` | 0 | 未复权前收参考价，元/股。 |
| `factor` | `Float64` | 0 | 当日含红利后复权因子。 |
| `limit_down_raw` | `Float64` | 0 | 规则推导未复权跌停价，元/股。 |
| `limit_up_raw` | `Float64` | 0 | 规则推导未复权涨停价，元/股。 |
| `limit_down_adjusted` | `Float64` | 0 | 规则推导后复权跌停价，元/股。 |
| `limit_up_adjusted` | `Float64` | 0 | 规则推导后复权涨停价，元/股。 |
| `rule_url` | `String` | 0 | 规则来源链接。 |

## 复现与历史版本

每次研究运行记录快照 ID 和主表 SHA-256。清洗代码、输入、补证和验收身份可从当前快照清单追溯。旧运行按其原始清单复现。若接入 FMZ 日 K 线，用有源成交行映射 OHLCV，适配器将 `Trddt` 转为约定的北京时间周期起点毫秒时间戳。 [FMZ Record](https://www.fmz.com/syntax-guide/struct#record)
