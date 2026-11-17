# Alpha158 分钟版因子说明

2026-11-17 核对。ITA 使用 Qlib 0.9.8 的 Alpha158 表达式，按同一证券、同一市场交易日的分钟位置计算。公式版本由归档审计脚本及资格验收清单（本地 `outputs/alpha158-minute-fit-20261116/manifest.json`）固定。下表从验收结果的公式列生成。逐因子完整表达式及精确字段、偏移见 158 项公式与资格明细 CSV（本地 `outputs/alpha158-minute-fit-20261116/factor_coverage.csv`）。

## 计算口径

- **输入。** 从[分钟最终版](final-factor-data-fields.md)取未复权 `open, high, low, close, vol, vwap`。表达式中的 `$volume` 映射至 `vol`（股），`$vwap` 为合格分钟成交额除以股数。`amount` 仅通过 `vwap` 间接进入这些表达式。
- **时间。** 每个证券日只取 14:56 输出，位置按 13:56 至 14:56 顺序排列。所有窗口限定在当天。`Ref($close,N)` 取源 14:56 向前第 N 个固定位置。CSV 偏移的 `0` 为 14:56，`60` 为 13:56，与分钟表的 `lag` 一致。
- **资格与结果。** 逐公式检查所有必需字段及偏移，保留空分钟位置。仅当输入资格为真且计算值有限时保留数值。信号截面按当日 `research_eligible` 建立，未来标签只在训练或评价时连接。训练、验证和测试边界按标签实际到期日 d+2 剔除越界样本。
- **特殊依赖。** `ROCN` 仅需 `lag=0,N` 两个收盘价，值为历史价除以当期价。`MAXN`、`MINN`、`RSVN` 的收盘价只取当期。`CORDN` 的滞后成交量分母须大于 0。`WVMAN`（如 `WVMA60`）需要 N+1 个收盘位置及 N 个成交量位置。`VMA/VSTD` 原式允许当期量为零，可能得到极端有限值。
- **研究状态。** 已完成 158 项全期输入资格核验和六日有限性抽检。现有资格 Parquet 的列为布尔值。正式全期因子值表、模型及收益验证待跑。 [验收结果](minute-alpha158-fit.md)

## 公式目录

13 个单点表达式加 29 个滚动表达式族。滚动式用 `N = 5, 10, 20, 30, 60` 展开，共 158 项。`Rank` 是同一证券窗口内的时间序列排名。公式保留 Qlib 原始算子、比值方向和 `1e-12` 项。

- `K*` 描述当期 K 线实体、全幅、上下影及收盘位置。`OPEN0/HIGH0/LOW0/VWAP0` 是当期字段与收盘价的比值。
- `ROC/MA/STD/BETA/RSQR/RESI` 描述价格相对位置、均值、波动与线性趋势。`BETA` 是窗口内收盘价对时间的回归斜率除以当期收盘价。
- `MAX/MIN/QTLU/QTLD/RANK/RSV/IMAX/IMIN/IMXD` 描述区间极值、分位数、当期相对位置和极值出现位置。
- `CORR/CORD` 描述价量联动，`CNT*` 与 `SUM*` 描述价格变化的方向频率及变动幅度占比。
- `VMA/VSTD` 是相对当期量的成交量均值及波动，`WVMA` 衡量绝对收益乘成交量序列的相对离散度，`VSUM*` 衡量成交量增减幅度占比。

| 名称或名称模式 | Qlib 表达式 |
| --- | --- |
| `KMID` | `($close-$open)/$open` |
| `KLEN` | `($high-$low)/$open` |
| `KMID2` | `($close-$open)/($high-$low+1e-12)` |
| `KUP` | `($high-Greater($open, $close))/$open` |
| `KUP2` | `($high-Greater($open, $close))/($high-$low+1e-12)` |
| `KLOW` | `(Less($open, $close)-$low)/$open` |
| `KLOW2` | `(Less($open, $close)-$low)/($high-$low+1e-12)` |
| `KSFT` | `(2*$close-$high-$low)/$open` |
| `KSFT2` | `(2*$close-$high-$low)/($high-$low+1e-12)` |
| `OPEN0` | `$open/$close` |
| `HIGH0` | `$high/$close` |
| `LOW0` | `$low/$close` |
| `VWAP0` | `$vwap/$close` |
| `ROC{N}` | `Ref($close, N)/$close` |
| `MA{N}` | `Mean($close, N)/$close` |
| `STD{N}` | `Std($close, N)/$close` |
| `BETA{N}` | `Slope($close, N)/$close` |
| `RSQR{N}` | `Rsquare($close, N)` |
| `RESI{N}` | `Resi($close, N)/$close` |
| `MAX{N}` | `Max($high, N)/$close` |
| `MIN{N}` | `Min($low, N)/$close` |
| `QTLU{N}` | `Quantile($close, N, 0.8)/$close` |
| `QTLD{N}` | `Quantile($close, N, 0.2)/$close` |
| `RANK{N}` | `Rank($close, N)` |
| `RSV{N}` | `($close-Min($low, N))/(Max($high, N)-Min($low, N)+1e-12)` |
| `IMAX{N}` | `IdxMax($high, N)/N` |
| `IMIN{N}` | `IdxMin($low, N)/N` |
| `IMXD{N}` | `(IdxMax($high, N)-IdxMin($low, N))/N` |
| `CORR{N}` | `Corr($close, Log($volume+1), N)` |
| `CORD{N}` | `Corr($close/Ref($close,1), Log($volume/Ref($volume, 1)+1), N)` |
| `CNTP{N}` | `Mean($close>Ref($close, 1), N)` |
| `CNTN{N}` | `Mean($close<Ref($close, 1), N)` |
| `CNTD{N}` | `Mean($close>Ref($close, 1), N)-Mean($close<Ref($close, 1), N)` |
| `SUMP{N}` | `Sum(Greater($close-Ref($close, 1), 0), N)/(Sum(Abs($close-Ref($close, 1)), N)+1e-12)` |
| `SUMN{N}` | `Sum(Greater(Ref($close, 1)-$close, 0), N)/(Sum(Abs($close-Ref($close, 1)), N)+1e-12)` |
| `SUMD{N}` | `(Sum(Greater($close-Ref($close, 1), 0), N)-Sum(Greater(Ref($close, 1)-$close, 0), N))/(Sum(Abs($close-Ref($close, 1)), N)+1e-12)` |
| `VMA{N}` | `Mean($volume, N)/($volume+1e-12)` |
| `VSTD{N}` | `Std($volume, N)/($volume+1e-12)` |
| `WVMA{N}` | `Std(Abs($close/Ref($close, 1)-1)*$volume, N)/(Mean(Abs($close/Ref($close, 1)-1)*$volume, N)+1e-12)` |
| `VSUMP{N}` | `Sum(Greater($volume-Ref($volume, 1), 0), N)/(Sum(Abs($volume-Ref($volume, 1)), N)+1e-12)` |
| `VSUMN{N}` | `Sum(Greater(Ref($volume, 1)-$volume, 0), N)/(Sum(Abs($volume-Ref($volume, 1)), N)+1e-12)` |
| `VSUMD{N}` | `(Sum(Greater($volume-Ref($volume, 1), 0), N)-Sum(Greater(Ref($volume, 1)-$volume, 0), N))/(Sum(Abs($volume-Ref($volume, 1)), N)+1e-12)` |

## 验收产物字段

| 文件 | 字段与含义 |
| --- | --- |
| `input_eligibility.parquet` | `code,date` 为证券日键。`eligible_count`（UInt16）为输入合格的因子数，158 个因子名列为 Boolean。覆盖全部日线键，无分钟窗口的因子资格为 false。 |
| `native_sample_validity.parquet` | 六日抽检证券日键，158 个 Boolean 列表示同时输入合格且 Qlib 输出有限。 |
| `factor_coverage.csv` | `factor, expression, family, window, required_fields_and_lags` 记录公式身份、窗口及精确依赖。`window=0` 表示单点；同一字段的必需偏移以逗号分隔，多字段以分号分隔。 |
| 同上 | `traded_rows, traded_input_eligible` 为成交证券日分母和合格数。`matched_rows, matched_input_eligible, matched_input_coverage` 为日线研究合格且标签非空的分母、逐因子输入合格数与比例。`matched_input_eligible_at_zero_current_volume` 为其中当期量为零的逐因子合格数。 |
| 同上 | `native_sample_rows, native_sample_input_eligible, native_sample_strict_finite, native_sample_finite_with_bad_inputs` 依次表示抽检行数、输入合格数、合格且有限数、输入不合格但原生输出有限数。 |
| `by_date.csv`、`by_year_market.csv`、`by_turnover_market.csv` | 分别按信号日、年份和市场、市场和日成交额组汇总匹配样本。`rows, all_158_inputs, any_inputs, median_eligible` 分别为分母、158 项输入全齐数、至少一项合格数、逐行输入合格数的中位数。因子同名列为各自的输入合格数。 |
