# 分钟数据最终版字段字典

2026-11-17 核对。适用版本 final-factor-data-20261116（本地 `outputs/final-factor-data-20261116`）。读取前按 manifest.json（本地 `outputs/final-factor-data-20261116/manifest.json`） 的 `output_sha256` 核验所用文件。数据范围、覆盖率和导出命令见 [最终数据说明](final-factor-data.md)。

## 表、主键与时间

| 表 | 主键 | 行 × 列 |
| --- | --- | ---: |
| `daily_inputs.parquet` | `code, date` | 1,009,083 × 52 |
| `minutes/YYYY.parquet` | `code, date, clock` | 全期 60,770,152 × 13 |
| `minute_eligibility.parquet` | `code, date` | 1,009,083 × 93 |
| `outcomes.parquet` | `code, date` | 1,009,083 × 12 |
| `calendar.parquet` | `date` | 2,430 × 1 |
| `coverage_by_date.csv` | `date` | 2,430 × 76 |

`code` 为 `String`，格式如 `002739.SZ`。`date` 在 Parquet 中为 `String`（北京时间市场交易日，`YYYYMMDD`）。读取覆盖 CSV 时也应将 `date` 指定为字符串。日线、窗口资格和标签按证券日一对一关联。分钟仅覆盖 996,232 个有成交的证券日，每键保留 61 个位置。完整保留位置并按 `lag` 降序处理，才能使前一行对应前一分钟。

## 日线与分钟

`daily_inputs.parquet` 含上游的 50 个原字段，再加入 `code` 和 `date`。原字段定义、单位与空值统计见 [配套日线字段字典](daily-fields.md)。`calendar.parquet` 的 `date` 给出市场交易日顺序，同时用于股票停牌时的标签日期推进。

| 分钟列 | 类型 | 定义 |
| --- | --- | --- |
| `code, date` | `String` | 证券、市场交易日 |
| `clock` | `String` | 源时间标签，`HH:MM:SS`，13:56:00 至 14:56:00 |
| `lag` | `UInt8` | 距 14:56 的分钟数，0 至 60 |
| `applicable` | `Boolean` | 该位置适用。熔断或已核验临停区间为 false，七个行情字段均为空 |
| `reason` | `String` | 缺口原因。为空表示该位置七字段均通过资格检查 |
| `open, high, low, close` | `Float64` | 分钟未复权实报 OHLC，元/股 |
| `vol, amount` | `Float64` | 股数、人民币元。已确认正常零成交可保留 0，未知或不合格留空 |
| `vwap` | `Float64` | 合格分钟的 `amount / vol`，元/股，零量时为空 |

`reason` 当前取值包括零成交或限价相关状态（`zero_volume`、`price_at_down_limit`、`price_at_up_limit`、`ipo_upper_after_resumption`），时段或证据缺口（`intraday_halt_notice_mirror`、`intraday_halt_primary`、`market_circuit_breaker`、`ipo_upper_notice_unavailable`、`source_timing_boundary`、`source_timing_gap`）和均价冲突（`vwap_ohlc_conflict`）。一个原因可以对应部分字段缺失，计算时以各字段实际空值及对应资格为准。逐键证据见 分钟验收目录（本地 `artifacts/minute-cleaning/20261116T182000+0800`） 的年度 `gaps_YYYY.parquet`。

## 窗口资格

`N ∈ {1, 5, 10, 20, 30, 60}`，窗口含 `lag < N` 的固定位置。下表中的 `field` 为 `open, high, low, close, vol, amount, vwap`。

| 列或列族 | 类型 | 定义 |
| --- | --- | --- |
| `code, date` | `String` | 证券日主键 |
| `observed_trade, research_eligible` | `Boolean` | 从日线带入的有成交及当日研究资格 |
| `market, board` | `String` | 交易所和板块。无分钟窗口的证券日为空 |
| `lag60_applicable`、`lag60_<field>_ok` | `Boolean` | 13:56 是否适用、对应字段是否有效。无分钟窗口时为空 |
| `wN_expected`、`wN_<field>_ok`、`wN_all` | `UInt8` | 依次为窗内适用位置数、该字段有效位置数、七字段同时有效位置数。无分钟窗口时为空 |
| `wN_close_path_ok`、`wN_ohlc_ok` | `Boolean` | 窗内收盘价全齐、四项 OHLC 全齐，均要求相关计数等于 `N` |
| `wN_turnover_ok`、`wN_vwap_path_ok` | `Boolean` | 窗内量额全齐、每分钟 VWAP 全齐，均要求相关计数等于 `N` |
| `ret60_endpoints_ok` | `Boolean` | 13:56 和 14:56 两个收盘价有效 |

无分钟窗口时，四类窗级布尔资格及 `ret60_endpoints_ok` 均为 false。整窗验证以固定长度 `N` 为分母。需要 `N` 次相邻分钟变化的因子还需检查额外的历史位置。按 Alpha158 具体公式计算时使用 [逐因子输入资格](minute-alpha158.md)。

## 收盘端点与标签

这些列用于训练标签、事后评价或执行诊断。信号日股票池与特征质量在连接这些结果前确定。

| 列 | 类型 | 定义 |
| --- | --- | --- |
| `code, date` | `String` | 证券、信号日 d |
| `d1, d2` | `String` | 市场日历上的后第 1、2 个交易日，超出冻结样本时为空 |
| `d1_raw_close, d2_raw_close` | `Float64` | 端点状态为 `priced` 时保留核验可用的未复权日收盘价，元/股 |
| `d1_status, d2_status` | `String` | 当前文件实有 `priced`（可作价格端点）、`confirmed_suspension`（确认停牌）、`outside_frozen_sample`（期末越界） |
| `forward_return_d1_d2` | `Float64` | d+1 收盘至 d+2 收盘的含红利收益率，小数。两个端点均为 `priced` 且 d+2 的 `return_total_daily_checked` 有限时写入该值 |
| `d1_auction_status` | `String` | d+1 收盘阶段证据状态，期末无 d+1 时为空 |
| `d1_independent_auction_shares, d1_independent_auction_yuan` | `Float64` | 独立收盘竞价量额，股和元。当前全列为空 |

`d1_auction_status` 实有 `nontrading`（无交易）、`circuit_breaker_day`（熔断日）、`sh_legacy_close`（沪市旧收盘机制）、`crosschecked_backfill`（对账补录）、`inferred_only`（仅推算）、`missing_eligible_1500`（缺合格 15:00 实报）、`price_matches_bucket_unverified`（价匹配、归桶待核）。这些状态用于诊断收盘成交证据。全期标签非空 994,684 条，同时满足 `research_eligible` 的有 978,561 条。

## 日截面覆盖与版本清单

| 数据 | 字段 | 定义 |
| --- | --- | --- |
| `coverage_by_date.csv` | `date` | 单个市场交易日 |
| 同上 | `observed_trade, research_eligible` | 当日对应资格为真的证券数 |
| 同上 | 其余与窗口资格表同名的 Boolean 列 | 每列在日内为真的证券数，CSV 存整数 |
| 同上 | `<flag>_matched` | 指定窗口、端点或适用标记为真、日线研究合格且标签非空的证券数 |
| 同上 | `wN_strict` | `wN_all == N` 的证券数，含该条件下全部证券 |
| 同上 | `label_count` | 全部证券中标签非空的数量 |
| `manifest.json` | `daily_snapshot, minute_snapshot, minute_audit` | 上游日线、分钟及验收批次标识 |
| 同上 | `polars, daily_rows, securities, trading_dates, minute_rows` | 导出环境版本与覆盖统计 |
| 同上 | `input_sha256, minute_partition_sha256, code_sha256, output_sha256` | 上游文件、逐日源分钟、导出关键代码及本交付文件的 SHA-256 |
