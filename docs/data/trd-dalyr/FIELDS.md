# TRD_Dalyr 日线数据结构

每行对应一只沪深证券的一个市场交易日，主键为 `instrument`、`Trddt`。本版覆盖 2016-01-04 至 2025-12-31，含 499 个证券代码、2,430 个市场交易日。对齐面板 1,008,151 行，其中 996,232 行来自 CSMAR，11,919 行是日历对齐产生的缺行。 [数据源与快照](../../../README.md#唯一数据源)

按 FMZ 的结构与字段说明组织。类型使用本版 Parquet 读出的 Polars 类型。空值数为全表实测值。金额币种为人民币，收益率使用小数，如 `0.05` 表示 5%。 [FMZ Record](https://www.fmz.com/syntax-guide/struct#record) · [CSMAR 字段说明](https://file.csmar.com/group1/M00/AA/99/CuIKV2XAnKiABeLbAB4nDGC5Ano840.pdf)

## 证券标识与时间

| 字段 | 类型 | 标签 | 空值数 | 定义与使用 |
| --- | --- | --- | ---: | --- |
| `instrument` | `String` | 主键 · 派生 | 0 | `Markettype` 映射 `SH` / `SZ` 后拼接六位 `Stkcd`，如 `SZ000009`。 |
| `Trddt` | `Date` | 主键 · 日频 | 0 | 北京时间的交易日期。源行取 CSMAR 日期，对齐行取 Qlib 市场日历。 |
| `Stkcd` | `String` | 证券代码 · 源值 | 11919 | 六位代码，保留前导零。缺行的代码可从 `instrument` 读取。 |
| `Markettype` | `Float64` | 市场枚举 · 源值 | 11919 | 1 上证 A 股（不含科创板），4 深证 A 股（不含创业板），16 创业板，32 科创板。 |

## Record 日 K 线与成交

| 字段 | 类型 | 标签 | 空值数 | 定义与使用 |
| --- | --- | --- | ---: | --- |
| `Opnprc` | `Float64` | Open · 未复权 · 元/股 | 11919 | 日开盘价。 |
| `Hiprc` | `Float64` | High · 未复权 · 元/股 | 11919 | 日最高价。 |
| `Loprc` | `Float64` | Low · 未复权 · 元/股 | 11919 | 日最低价。 |
| `Clsprc` | `Float64` | Close · 未复权 · 元/股 | 11919 | 日收盘价。 |
| `Dnshrtrd` | `Float64` | Volume · 股 | 11919 | 源表日成交股数。 |
| `Dnvaltrd` | `Float64` | 成交额 · 元 | 11919 | 源表日成交金额。与日成交股数相除可核对成交均价量级。 |
| `Ahshrtrd_D` | `Float64` | 盘后成交 · 股 | 306242 | 源表盘后成交股数。源空值表示该字段无值，保留与明确的零成交之间的区别。 |
| `Ahvaltrd_D` | `Float64` | 盘后成交 · 元 | 306242 | 源表盘后成交金额，空值与盘后成交股数同步。 |
| `PreClosePrice` | `Float64` | 前收参考价 · 元/股 | 11919 | 源表当日涨跌幅使用的前收参考价。 |
| `ChangeRatio` | `Float64` | 涨跌幅 · 小数 | 11919 | 本版逐行核对等于 `Clsprc / PreClosePrice - 1`，最大绝对差约 `5e-7`。 |

FMZ `Record.Time` 需要周期起点的 Unix 毫秒时间戳。本版保存 `Trddt` 日期，接入时由适配器约定北京时间的日线周期起点。`OpenInterest` 属于 FMZ 接口字段，本批 A 股日线无对应观测。缺行只用于日历对齐，导出真实 K 线用 `source_row = true`。 [FMZ Record](https://www.fmz.com/syntax-guide/struct#record)

## 复权、收益与市值

| 字段 | 类型 | 标签 | 空值数 | 定义与使用 |
| --- | --- | --- | ---: | --- |
| `Adjprcwd` | `Float64` | 后复权 · 含红利再投资 · 元/股 | 11919 | 以上市首日为基准的可比收盘价。 |
| `Adjprcnd` | `Float64` | 后复权 · 不计现金红利 · 元/股 | 11919 | 以上市首日为基准的可比收盘价。 |
| `Dretwd` | `Float64` | 源收益 · 含红利再投资 · 小数 | 11919 | 源日个股收益率。跨停牌或源缺行时，两个源观测可能相隔多个市场交易日。 |
| `Dretnd` | `Float64` | 源收益 · 不计现金红利 · 小数 | 11919 | 源日个股收益率，不计现金红利。 |
| `return_total_source_checked` | `Float64` | 派生 · 含红利再投资 · 小数 | 11920 | 保留通过报价检查且没有被标记为复权冲突的 `Dretwd`。各证券首条源收益仍可保留，是否做过相邻记录对账以 `return_conflict` 是否为空判断。 |
| `Dsmvosd` | `Float64` | 流通市值 · 千元 | 11919 | 日个股流通市值。 |
| `Dsmvtll` | `Float64` | 总市值 · 千元 | 11919 | 日个股总市值。 |
| `Capchgdt` | `Date` | 股本变动 · 源值 | 11919 | 当日记录对应的最近一次股本变动日期。 |

## 交易状态与涨跌停

| 字段 | 类型 | 标签 | 空值数 | 定义与使用 |
| --- | --- | --- | ---: | --- |
| `Trdsta` | `Float64` | 历史状态枚举 · 源值 | 11919 | 1 正常，2 ST，3 *ST。代码 10 保留，批次口径待确认。 |
| `LimitDown` | `Float64` | 跌停价 · 未复权 · 元/股 | 12591 | 源当日下限，空值表示源未提供该限价或整行缺失。 |
| `LimitUp` | `Float64` | 涨停价 · 未复权 · 元/股 | 12591 | 源当日上限，空值表示源未提供该限价或整行缺失。 |
| `LimitStatus` | `Float64` | 收盘限价枚举 · 源值 | 12461 | 与源限价可核对时，`-1` 收盘跌停，`0` 收盘未触限，`1` 收盘涨停。 |
| `is_st` | `Boolean` | 历史 ST · 派生 | 19088 | `Trdsta` 为 2/3 时真，为 1 时假，为 10 或缺行时空。 |
| `observed_trade` | `Boolean` | 成交观测 · 派生 | 11919 | 源行日成交股数有限且大于零。缺行为空，停复牌状态仍需公告佐证。 |

## 数据质量与研究筛选

| 字段 | 类型 | 标签 | 空值数 | 定义与使用 |
| --- | --- | --- | ---: | --- |
| `source_row` | `Boolean` | 行来源 · 派生 | 0 | 真为 CSMAR 原行，假为日历对齐产生的缺行。 |
| `return_conflict` | `Boolean` | 含红利复权一致性 · 派生 | 12418 | 相邻源记录的 `Adjprcwd` 涨幅与 `Dretwd` 相差超过 `1e-5`。首条源记录与缺行为空。 |
| `return_ex_div_conflict` | `Boolean` | 不计红利复权一致性 · 派生 | 12418 | 相邻源记录的 `Adjprcnd` 涨幅与 `Dretnd` 相差超过 `1e-5`。首条源记录与缺行为空。 |
| `invalid_quote` | `Boolean` | 价量完整性 · 派生 | 11919 | 必需字段缺失或非有限、指定价格或价量字段非正、OHLC 关系错误，或成交均价越过高低价容差时为真。 |
| `limit_prices_missing` | `Boolean` | 限价字段完整性 · 派生 | 11919 | 源行至少缺少一个限价字段时为真。 |
| `outside_limits` | `Boolean` | 限价范围 · 派生 | 11919 | 高低报价超出源限价容差 `0.001` 元，或限价本身无效时为真。缺限价时结合 `limit_prices_missing` 判读。 |
| `limit_status_diff` | `Boolean` | 收盘限价一致性 · 派生 | 12591 | 源状态与收盘触限方向不符时为真。缺源状态、双边限价不全或缺行时为空。 |
| `one_price_day` | `Boolean` | 一字报价 · 派生 | 11919 | 日高低差不超过 `0.001` 元。可与 `LimitStatus` 联查是否一字涨跌停。 |
| `large_return` | `Boolean` | 极端收益审阅 · 派生 | 11919 | `abs(Dretwd) > 0.15`。结合板块与源限价审阅。 |
| `research_eligible` | `Boolean` | 样本筛选 · 收盘后 · 派生 | 0 | 有成交、报价有效、限价齐备、状态可核验且一致、无已知复权冲突、无一字报价且 `Trdsta = 1` 时为真。适合在当日数据可用后筛选研究样本，执行约束由策略另行判断。 |

## 缺行交叉核对

以 `instrument`、`Trddt` 为主键，只覆盖主表中 `source_row = false` 的 11,919 行。Qlib 报价按原字段保留，量纲见其来源口径。 [清洗与验收](CLEANING.md)

| 字段 | 类型 | 标签 | 空值数 | 定义与使用 |
| --- | --- | --- | ---: | --- |
| `instrument` | `String` | 主键 · 派生 | 0 | 同清洗日线。 |
| `Trddt` | `Date` | 主键 · 日频 | 0 | 同清洗日线。 |
| `qlib_close` | `Float32` | Qlib 对照 · 收盘价 | 11919 | 本地 Qlib `close` 原字段，沿用其复权口径。 |
| `qlib_volume` | `Float32` | Qlib 对照 · 成交量 | 11919 | 本地 Qlib `volume` 原字段，沿用其单位与处理口径。 |
| `qlib_row` | `Boolean` | Qlib 对照 · 行存在性 | 0 | 真表示 Qlib 有对应键。其他运行缺少键时可为空。 |
| `crosscheck` | `String` | Qlib 对照 · 结果枚举 | 0 | `qlib_positive_price_volume` 表示价量均有限且为正，`qlib_row_without_positive_price_volume` 表示有行但未满足价量条件，`qlib_no_row` 表示无行。本版全属第二类，公告确认结果见清洗记录。 |
