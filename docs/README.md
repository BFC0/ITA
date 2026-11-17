# ITA 文档导航

首次使用请从[项目首页](../README.md)确认当前进度、数据源、因子口径和运行命令。项目内的文档及本地证据从本页查找。

## 项目计划与协作

- [现行五周计划与五人分工](project/中证500指数增强项目_5周计划.md)
- [项目执行约定](../AGENTS.md)
- [团队 PR 练习](<project/pull request小练习.txt>)
- [模型训练与交付公共要求](../shared/model_training_requirements.md)
- [行情缺失判定与补数规范](../shared/market_data_quality.md)

## 数据与因子

| 文档 | 内容 |
| --- | --- |
| [分钟数据最终版](local/final-factor-data.md) | 唯一研究数据集的文件、字段资格、标签及复现命令 |
| [分钟最终版字段字典](local/final-factor-data-fields.md) | 六类数据表的键、字段类型、值域、缺失语义和版本清单 |
| [Alpha158 分钟版因子说明](local/minute-alpha158.md) | 158 项公式、固定窗口、字段依赖和验收产物字段 |
| [Alpha158 分钟版输入验收](local/minute-alpha158-fit.md) | 覆盖率、全期输入资格和六日有限性抽检 |
| [分钟字段与清洗上游](local/minute-fields.md) | 整日分钟分片、修订和审计读取入口 |
| [配套日线字段字典](local/daily-fields.md) | 日线上游、复权、收益口径和字段定义 |
| [交易所公开日行情试查](local/exchange-pilot.md) | 公开接口的试查范围、证据和复现入口 |

## 清洗与验收

- [分钟行情清洗与验收规则](local/minute-plan.md)
- [分钟行情清洗执行计划与完成状态](local/minute-execution.md)
- [本地分钟行情验收与待补证清单](local/minute-audit.md)
- 本地缺口试查记录见 分钟缺口（本地 `outputs/20160620-minute-gap-pilot/report.md`）、公开网页（本地 `outputs/20160620-web-gap-pilot/report.md`）和 Investing 试查（本地 `outputs/20160620-investing-pilot/report.md`）。

## 历史与冻结证据

- [TRD_Dalyr 上游公开发布说明](trd-dalyr/RELEASE_NOTES.md) · [公开数据字典](trd-dalyr/TRD_Dalyr_数据说明与字段字典.md)

- [原八周计划](archive/中证500指数增强项目_8周计划.md)
- 迁移报告（本地 `artifacts/migration/report.md`）
- 冻结证据见 分钟验收（本地 `artifacts/minute-cleaning/20261116T182000+0800/report.md`）和 TRD_Dalyr 发布说明（本地 `artifacts/releases/trd-dalyr/20261111T174544799547+0800/RELEASE_NOTES.md`）。
- 历史副本见 早期项目备份（本地 `history`）和 数据源、GitHub 发布与项目整理记录（本地 `artifacts/history`）。

## 文件结构

```text
ITA/
├── README.md      项目入口、正式数据与因子、运行命令
├── AGENTS.md      项目执行约定
├── requirements.txt
├── docs/
│   ├── README.md  文档导航
│   ├── project/   现行计划和团队协作材料
│   ├── local/     数据字典、清洗、验收与因子说明
│   └── archive/   已退役计划
├── shared/        共用训练、交付和行情质量规范
├── scripts/       读取、验收、导出、回读和试查脚本
├── data/
│   └── snapshots/ 上游日线、分钟分片、日历及证据
├── artifacts/     冻结运行、发布和迁移证据
├── history/       早期项目备份
└── outputs/       已登记最终数据、资格验收及新运行产物
```

数据清洗和复现从 `data/snapshots/` 及原清单所列证据读取。研究从 分钟数据最终版（本地 `outputs/final-factor-data-20261116`） 读取，因子资格验收产物见 alpha158-minute-fit-20261116（本地 `outputs/alpha158-minute-fit-20261116`）。新运行写入 `outputs/<运行名>/`。`data/`、`artifacts/`、`history/` 和 `outputs/` 是本地目录，复现前需将获准使用的文件放入这些位置。
