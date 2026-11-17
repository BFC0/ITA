# ITA

截至 2026-11-17，固定 499 股的分钟窗口和日线端点已完成全期验收，分钟最终版已交付，Alpha158 分钟版已完成全期输入资格核验和六日公式抽检。下一步是生成正式因子值并开展首轮日频验证。历史中证 500 成分及权重和独立收盘竞价量额仍待补证。

- [文档导航与文件结构](docs/README.md)
- [现行计划 · 5 周与 5 人分工](docs/project/中证500指数增强项目_5周计划.md)
- [分钟数据最终版 · 数据说明](docs/local/final-factor-data.md) · [字段字典](docs/local/final-factor-data-fields.md)
- [Alpha158 分钟版 · 因子说明与公式](docs/local/minute-alpha158.md) · [输入验收](docs/local/minute-alpha158-fit.md)

## 唯一数据源

**ITA 的新研究和重跑统一使用分钟数据最终版 final-factor-data-20261116（本地 `outputs/final-factor-data-20261116`）。** 数据集覆盖 2016-01-04 至 2025-12-31、2,430 个市场交易日和固定 499 股，包括 13:56–14:56 分钟窗口、配套日线、分钟资格、交易日历和独立收益标签。所有研究派生量从该版本生成。

- 开跑前按 数据集清单（本地 `outputs/final-factor-data-20261116/manifest.json`） 的 `output_sha256` 核验所用文件，运行清单记录数据集版本和文件哈希。TRD_Dalyr 快照 `20261111T171040402190+0800` 是配套日线的上游，清洗复现按原清单校验上游哈希。历史运行按各自清单复现。
- 分钟价格为未复权实报，配套日线和收益按各自字段口径使用。信号按 `research_eligible` 和各公式的输入资格生成，未来收盘端点只用于标签及事后核验。字段缺失保留原状态。 [配套日线字段](docs/local/daily-fields.md) · [最终版表结构](docs/local/final-factor-data-fields.md)
- 历史成分及权重、全收益指数、行业、财报、FF3、无风险利率及独立收盘竞价量额仍缺证。依赖这些输入的正式结果登记阻断。固定 499 股结果按实际样本披露。新增或更换数据源须经项目负责人授权并在此登记。

## 因子口径

**正式因子库采用 Alpha158 分钟版的严格版 158 个表达式。** 每个交易日取源 14:56 标签及同一下午的固定分钟位置，最长回溯至 13:56。逐公式检查字段与偏移，缺失输入和非有限输出留空。共同样本上的因子或模型比较另报覆盖率。

首轮日频研究采用 d 日信号、d+1 收盘执行和 d+2 收盘标签到期的口径。使用最终版 `outcomes.parquet` 中的 `forward_return_d1_d2`，按市场交易日历推进。实际模拟成交及容量需要独立的收盘阶段量额证据。 [输入验收与公式版本](docs/local/minute-alpha158-fit.md)

## 本地运行

真实数据复现需要在项目约定位置放置获准使用的行情快照及验收产物。仓库提供代码、文档和复现入口，文中标注的本地文件供有权限的成员核对。

从 ITA 根目录运行。现有环境已用 Python 3.13 验证。新环境安装 [Python 依赖](requirements.txt) 后可运行抽检。

```powershell
python -m pip install -r requirements.txt
python -B scripts/audit.py smoke-01 --smoke
```

全量复现时换一个新的运行名，去掉 `--smoke`，随后对同一运行执行独立回读。

```powershell
python -B scripts/audit.py run-01
python -B scripts/verify.py run-01
```

[交易所公开日行情试查](docs/local/exchange-pilot.md)可用 `python -B scripts/exchange_pilot.py exchange-01` 重查。该命令会联网访问公开接口。

分钟最终版导出及严格版公式资格复核的命令见 [最终数据说明](docs/local/final-factor-data.md) 和 [Alpha158 分钟版验收](docs/local/minute-alpha158-fit.md)。
