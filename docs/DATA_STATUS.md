# 数据状况呈现书

本文件是本项目的数据导入台账。接下来本对话专注于数据导入时，凡是发生数据源接入、字段口径、落盘路径、抓取脚本、数据文件或导入流程的更新，都需要同步修改本文件。

最后更新：2026-09-11 Asia/Shanghai

## 2026-09-10 迁移前本地核验

本次只核对项目文件、实际代码、数据清单和本地测试，没有抓取、刷新或改写任何外部数据、模型结果和历史原始文件。

- `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` 于 2026-09-11 复跑 66 项，全部通过。
- 当前需求网络实际包含 42 个需求节点、6 条过程—资源候选依赖、6 条数量为空的 `not_yet_observed` 占位观察，`source_observations.csv` 仍为空，企业/证券承载映射仍为 0 条。
- 当前 `stock_motion_event_v2` 牧原股份合并流仍为 10028 条；其中 10022 条行情事件、2 条已审核生产活动观察、4 条匿名集中度代理。
- 当前网络信号快照仍为 71052 行（11842 个对象 × 6 类信号），只有 2 条直接信号非零，传播规则仍为 0 条。
- 当前资金控制目录仍有 6 个资金池、120 条持仓观察、22 条控制关系，但 `flow_events.csv` 和 `controller_probability_distribution.csv` 均为空。
- `data/realtime/a_share_spot.csv` 的快照时间仍为 `2026-07-20T10:45:28`，已经过期，不能作为 2026-09-11 的当前市场数据。
- 迁移时应复制整个项目目录；部分 `data/raw/*.csv`、`data/processed/*.csv`、`data/minute/**/*.csv`、`models/*.joblib` 和 `reports/*.csv/png` 被 `.gitignore` 排除，不能只迁移代码或聊天记录。

## 2026-08-18 方向切换：需求—资源—生产主干

当前主网络不再以 A 股上市公司为根节点。需求契约升级为 `human_need_resource_network_v2`：以“人类生物种群持续存在与发展”为唯一根节点，下分物质稳态、繁衍照护、神经心理、社会协作、符号精神五个系统和 40 余个需求节点。需求节点的生物基础与剥夺反应明确标为模型结构/待核验机制，不把人视为脱离身体的独特个体。生产试点仍是“基本营养需求 → 蛋白质供给 → 动物蛋白 → 生猪及猪肉供给过程”。资源候选包括饲料粮、水、土地、能源、生物条件和物流；6 条过程—资源关系均为 `candidate_needs_evidence`，没有数量、单位或企业采购事实。资源占位观察按“资源 × 地理单元 × 观察时间”保存，数量为空时为 `not_yet_observed`，不代表零。

文件：`data/human_need_network/`、`stock_model/human_need_network.py`、`data/contracts/human_need_resource_network_v2.schema.json`、`docs/HUMAN_NEED_RESOURCE_NETWORK.md`、`reports/human_need_resource_network.html`。企业/证券承载者映射表目前为空；旧 `data/industry_network/a_share/` 保留并标记为历史 `legacy_equity_first_experiment` 分支。默认快照过滤候选依赖，显式 `include_candidates=True` 才显示候选关系。

## 当前目标

- 主网络先建立人的需求、满足功能、转化过程与资源约束；企业和证券只作为下游过程承载/金融映射。
- 以低成本方式建立 A 股行情数据导入流程。
- 优先使用免费数据源 AkShare 和 BaoStock。
- 所有历史行情统一落为模型可读的标准 OHLCV CSV。
- 任意外部 CSV/TXT 优先经过通用转换器，并为每个输出保留 `.meta.json` 审计文件。
- 牧原股份的 BaoStock 5 分钟不复权数据采用可重复运行的增量归档；分钟档案与日线模型输入严格分离。
- 标准 OHLCV 是外部观察契约，不再直接等同于模型内部状态；进入股票运动模型前应转换为 `stock_motion_event_v2` 内部运动数据流。
- 当前行情快照单独落入 `data/realtime/`，用于观察市场状态、分层和后续盘中策略扩展。
- 历史 A 股产业网络中的产品映射必须保留原文并经过人工复核；匿名客户/供应商只能进入集中度表，不能生成公司关系边。该网络不再是新主干的根节点。
- 具名客户/供应商关系必须同时保留交易原文、独立身份依据、页面核验和报告期边界；关系可得时间不得早于来源、身份与审核三者。
- 对手方文件的后续佐证单独保存且从审核完成时起可用；身份、控股或持股证据不得升级为交易金额、方向或持续性的确认。
- 网络对象的信息素式状态使用独立 `network_signal_field_v1` 覆盖层；信号事件、传播规则和时点浓度分开保存，只有显式边与显式规则同时存在时才传播。
- 资金控制模型将资金运动事实、资金池、受益所有人、投资决策人、执行人和托管/名义持有人分开；主体概率无法解释的部分必须保留为 `CONTROLLER_UNKNOWN`。

## 数据源状态

| 数据源 | 类型 | 成本 | 当前用途 | 接入状态 | 说明 |
|---|---|---:|---|---|---|
| AkShare | 免费第三方 Python 数据接口 | 低 | A 股当前快照、A 股历史日线、公募基金概况与季度持仓 | 已接入并验证 | 当前主力低成本数据源，公募基金资料经 Eastmoney 页面获取；受目标站点稳定性影响 |
| BaoStock | 免费 Python 数据接口 | 低 | A 股历史日线、分钟线、沪深上市基础信息与证监会行业分类 | 日线、分钟样例和产业网络首批数据已验证 | 基础/行业表当前不覆盖北交所；分钟档聚合不能逐日完全复现同来源日线高低价和成交量 |
| 同花顺导出文件 | 手动导出 CSV/TXT | 低 | 本地同花顺历史数据导入 | 已有导入脚本和样例 | 稳定但需要人工导出 |
| 同花顺 iFinD / Quant API | 官方数据接口 | 较高或需权限 | 实时行情、专业数据 | 预留接口，未接通 | 当前机器未发现 `iFinDPy` |
| yfinance | 免费第三方接口 | 低 | 美股或部分市场数据 | 保留 | 非 A 股主路径 |
| 巨潮资讯 CNINFO | 上市公司信息披露与公司资料 | 免费 | 发行人 `orgId`、公司概况、公告/年报证据 | 发行人注册表、牧原股份及华域汽车/上汽集团 2025 年报已接入 | `orgId` 覆盖沪深京；官方公告、来源首次可得、身份首次可得和关系审核时间分开保存 |

## 当前数据文件

| 文件 | 来源 | 行数 | 字段数 | 日期范围 | 用途 | 状态 |
|---|---|---:|---:|---|---|---|
| `data/realtime/a_share_spot.csv` | AkShare 当前 A 股快照 | 5879 | 18 | 快照时间 `2026-07-20T10:45:28` | 当前全市场行情、分层分析 | 已验证 |
| `data/raw/000001.SZ.csv` | AkShare 历史日线 | 615 | 6 | 2024-01-02 至 2026-07-20 | 平安银行历史训练数据 | 已验证并训练 |
| `data/raw/600519.SH.csv` | BaoStock 历史日线 | 614 | 6 | 2024-01-02 至 2026-07-17 | 贵州茅台历史样例数据 | 已验证 |
| `data/raw/002714.SZ.csv` | AkShare（东方财富接口）前复权日线 | 634 | 6 | 2024-01-02 至 2026-08-14 | 牧原股份模型输入 | 已与 BaoStock 同区间交叉核验；有审计元数据 |
| `data/raw/SAMPLE.csv` | 本项目生成样例 | 900 | 6 | 2020-01-01 至 2023-06-13 | 流程演示 | 已验证 |
| `data/raw/THS_SAMPLE.csv` | 同花顺导出样例标准化 | 3 | 6 | 2024-01-02 至 2024-01-04 | 同花顺导入演示 | 已验证 |
| `data/ths_exports/THS_SAMPLE.csv` | 同花顺导出样例 | 3 | 6 | 未标准化日期列 | 导入源样例 | 已验证 |
| `data/minute/002714.SZ/5m_baostock.csv` | BaoStock 5 分钟、不复权 | 30432 | 7 | 2024-01-02 09:35 至 2026-08-14 15:00 | 牧原股份分钟原始观察档案 | 634 天均为 48 行；有审计元数据；暂不进入模型 |
| `data/industry_network/a_share/` | BaoStock + CNINFO + 旧 AkShare 北交所候选 | 5874 个企业、5884 个上市阶段 | 10 张主表 + 2 张具名关系侧车 | 网络主体抓取于 2026-08-16；具名关系及佐证审核于 2026-08-18 | A 股产业网络、发行人身份、产品映射、匿名集中度、具名关系、上市退市生命周期 | 1 个产品、2 条已审核产品映射、2 条集中度、2 条 2025 关系、2 条身份/控股佐证 |
| `data/external/a_share_industry_network/cninfo_named_relations/` | CNINFO 官方年报与公告查询 | 2 份 PDF、2 组查询响应、2 条关系证据、2 条佐证 | 原始文件、SHA-256、原文抽取和视觉核验 | 2026-08-18 首次归档及反向核验 | 华域汽车与上汽集团具名关系身份、交易和集团关系证据 | 第 4、178、179、1、17、170 页核验；上汽年报不交叉确认交易金额 |
| `reports/named_relation_crosscheck.md` | 上汽集团 2025 年报 | 2 条佐证 | 对手方文件反向核验 + `.meta.json` | `as_of=2026-08-18T07:55:10+00:00` | 核对华域法定名称、代码、控股标签和直接持股 | 确认 58.32% 直接持股；交易金额、方向和连续性未交叉确认 |
| `data/network_signals/a_share/` | 生命周期观察、深交所核验、已审核生产映射 | 6 个信号类型、2 个事件、2 条独立证据、0 条传播规则 | `signal_types.csv`、`signal_events.csv`、`signal_event_evidence.csv`、`transmission_rules.csv` | 2026-08-18 更新 | 网络对象的可衰减/可传播显示信号 | 生产数量未披露；原始原文、显示强度与证据质量分开 |
| `data/processed/network_signal_snapshot/signal_state_snapshot.csv` | A 股 v2 网络对象 + 信号覆盖层 | 71052 行（11842 对象 × 6 类型） | 时点浓度快照 | `as_of=2026-08-18T12:00:00+08:00` | 后续颜色、光晕、流向和强度显示输入 | 2 行直接信号非零，传播贡献全部为 0 |
| `reports/network_signal_inspector.html` | 时点快照 + 信号事件/证据 + 产业网络对象表 | 2 条非零信号、1 个产品节点 | 数据驱动只读报告 + `.meta.json` 输入哈希审计 | 快照 `2026-08-18T12:00:00+08:00` | 核对直接信号、证据质量、原始事实和传播状态 | 0 条传播规则；1 条深交所证据晚于快照，标为后续核验 |
| `reports/counterparty_relation_eligibility.md` | 牧原股份年报客户/供应商集中度 | 2 条可得披露 | 具名公司关系准入审计；另有 CSV 明细和 `.meta.json` | `as_of=2026-08-18T16:00:00+08:00` | 防止匿名或未完成身份核验的对手方生成公司关系 | 牧原两条均为 `anonymous_aggregate_only`；本次新建 0，主表另有 2 条合格历史关系 |
| `data/external/a_share_industry_network/szse/20260818T063927Z/` | 深圳证券交易所官方 A 股列表接口 | 1 条精确匹配记录 | 原始 JSON + 请求元数据 | 2026-08-18 获取 | 牧原股份生命周期信号交叉核验 | 确认清单存在，不证明全天连续可交易 |
| `data/external/public_fund/normalized/` | AkShare 经 Eastmoney 公募基金资料 | 6 个产品、498 条报告索引、120 条季度持仓、71 条相邻期变化 | 产品、公告索引、持仓与区间变化观察 | 首次抓取 2026-08-17 10:38；公告日期已回填 | 公募基金产品、管理人、基金经理、托管人、报告期持仓、披露集合变化 | 持仓使用报告索引公告日终作为可得时间；管理关系仍为本地首次观察；2 个样本存在份额/组合范围警告 |
| `data/external/public_fund/report_pdfs/` | Eastmoney 公募基金报告 PDF 镜像 | 6 份 2026 年二季报 PDF、6 份逐份审计、2 份汇总审计 | 原报告镜像、SHA-256、文本与视觉核验 | 归档及核验 2026-08-17 | 季末持仓与产品身份的原文证据 | 6/6 文档身份和报告期匹配，60/60 持仓文本匹配；封面和完整前十大表视觉核验通过；尚未从基金管理人官方主机交叉取得 |
| `data/capital_control/a_share/` | 本项目字段契约 + 公募基金样例 | 1 个系统未知主体、6 个公募产品、120 条持仓、71 条变化、22 条控制关系 | 6 张主表 | 契约建立于 2026-08-17；样例已扩展至 10:57 首次观察 | 资金池、控制关系、持仓观察与主体条件概率 | 未生成交易主体概率；`controller_probability_distribution.csv` 仍为空 |

## 标准字段口径

历史日线模型输入必须统一为：

```text
date, open, high, low, close, volume
```

字段说明：

| 字段 | 类型 | 说明 |
|---|---|---|
| `date` | 日期 | 交易日期，导入后按升序排列并去重 |
| `open` | 数值 | 开盘价 |
| `high` | 数值 | 最高价 |
| `low` | 数值 | 最低价 |
| `close` | 数值 | 收盘价 |
| `volume` | 数值 | 成交量，保持来源口径 |

当前行情快照字段以 `data/realtime/a_share_spot.csv` 为准，当前包含：

```text
fetched_at, symbol, name, price, pct_change, change, open, high, low,
prev_close, volume, amount, turnover_rate, volume_ratio, pe_dynamic,
pb, total_market_value, free_float_market_value
```

分钟档案使用独立契约 `ohlcv_minute_v1`：

```text
datetime,open,high,low,close,volume,amount
```

- `datetime` 是带 `+08:00` 偏移的 Asia/Shanghai K 线结束时间；第一根 5 分钟线为 09:35。
- 元数据记录 `frequency=5m`、`timestamp_meaning=bar_end`、`availability_policy=available_after_bar_end`、复权和单位。
- 当前牧原股份档案为不复权；BaoStock 的成交量和成交额单位仍为 `unknown`。
- 机器可读契约：`data/contracts/ohlcv_minute_v1.schema.json`。
- 该契约目前只负责外部观察归档，尚未映射到 `stock_motion_event_v2`，也未授权现有日线训练器读取。

## 内部运动数据流契约

外部标准 OHLCV、已审核生产活动和匿名集中度代理通过 `stock_model/motion.py` 转为长表事件流 `stock_motion_event_v2`。核心字段为：

```text
schema_version,event_id,entity_id,source_schema,source_record_id,
source_entity_id,dimension_id,dimension_name,event_time,available_time,
availability_policy,channel,value,unit,evidence_kind,method,
source,market,adjustment,volume_unit,quality_status
```

内部通道分三类：

- `observation`：来源直接观察到的开高低收和成交量；
- `derived`：只使用当日及历史数据计算的收益、波动、相对位置等；
- `proxy`：带有明确假设、不能等同于真实原因的代理量。

OHLCV 不会被转换器解释为产能、权益价值锚、预期、情绪或大资金净流入。这些未解决通道记录在输出审计元数据中。完整定义见 `docs/STOCK_MOTION_MODEL.md`。

机器可读字段契约：`data/contracts/stock_motion_event_v2.schema.json`。旧 v1 契约仍保留用于历史兼容。

当前已生成内部流：

| 文件 | 来源输入 | 事件数 | 交易日数 | 日期范围 | 状态 |
|---|---|---:|---:|---|---|
| `data/processed/motion/002714.SZ.motion.csv` | `data/raw/002714.SZ.csv` + A 股产业网络 v2 | 10028 | 635 | 市场 2024-01-02 至 2026-08-14；网络证据事件时间至 2026-08-16 | 已生成并通过审计；包含 10022 条行情事件、2 条已审核活动观察、4 条匿名集中度代理 |

## 人的需求—资源—生产网络契约

`human_need_resource_network_v2` 的根节点是人类生物种群连续性，不是股票。需求树已覆盖物质稳态、繁衍照护、神经心理、社会协作、符号精神五个系统和 40 余个节点；当前生产试点仍是“基本营养—动物蛋白—生猪及猪肉供给过程”，并把饲料粮、水、土地、能源、生物条件和物流记录为候选依赖。资源丰富度接口要求 `resource_id + geographic_unit_id + observation_time + available_time`，数量、单位、范围、可获得性和质量状态分开保存；空数量不能补零。

本轮增加资源来源准入：`source_registry.csv` 登记 3 个饲料粮候选来源（FAOSTAT 作物生产、FAOSTAT 食物平衡、中国国家统计局），状态均为 `candidate_source`，尚未导入任何数量。`source_observations.csv` 是空的标准输入模板；`scripts/import_resource_observations.py` 只允许 `imported`/`verified` 来源、完整单位/地理/时间字段和不早于观察时间的 `available_time` 生成观察。

| 文件 | 当前状态 |
|---|---|
| `data/human_need_network/needs.csv`、`satisfaction_functions.csv`、`transformation_processes.csv` | 物种/群体需求树与生产结构定义，`accepted_model_structure`；生物机制仍待逐项核验 |
| `data/human_need_network/process_resource_dependencies.csv` | 6 条候选依赖，全部 `candidate_needs_evidence` |
| `data/human_need_network/resource_endowment_observations.csv` | 6 条占位观察，数量为空，全部 `not_yet_observed` |
| `data/human_need_network/process_carrier_mappings.csv` | 0 条，尚未接入企业或证券 |
| `reports/human_need_resource_network.html` | 数据驱动只读网络图；虚线表示候选依赖 |

模块与测试：`stock_model/human_need_network.py`、`tests/test_human_need_network.py`。默认快照不包含候选依赖，只有显式 `include_candidates=True` 才显示。未来资源观察按 `available_time` 过滤，不能提前进入历史网络。

## 资金控制与运动概率契约

`capital_control_distribution_v1` 将观察到的资金运动与“谁控制资金”的概率归因分开保存。首个目录为 `data/capital_control/a_share/`，包含控制主体、资金池、控制关系、持仓观察、资金运动事件和主体概率分布六张表。

同一资金事件的主体概率必须合计为 1；无法由公开证据解释的概率质量必须分配给 `CONTROLLER_UNKNOWN`。受益所有、投资决策、交易执行、托管和名义持有是不同控制角色。成交额、价格方向和大单分类不能单独识别具体主体。

机器契约：`data/contracts/capital_control_distribution_v1.schema.json`；公募基金证据契约：`data/contracts/public_fund_evidence_v1.schema.json`。完整说明：`docs/CAPITAL_CONTROL_MODEL.md`。

当前已接入六个公募基金的产品、管理人、基金经理、托管人、报告索引和 2026 年一、二季度持仓观察，并生成 71 条相邻披露集合变化。六份 2026 年二季报 PDF 已从 Eastmoney 镜像归档：基金代码、基金名称、报告期和每份 10/10 披露持仓均通过文本核验，封面及完整前十大持仓表通过视觉核验；汇总见 `report_pdf_verification_2026-06-30.json` 和 `report_pdf_visual_verification_2026-06-30.json`。这些 PDF 尚未从基金管理人官方主机交叉取得。没有接入股东持仓变化、订单身份或席位归属，因此不得把基金经理名字写成具体交易主体概率。交易概率表仍为空。部分份额类别的净资产口径与组合持仓市值可能不一致，已在抓取元数据中记录警告；五位港股代码已按 `.HK` 保存。

## A 股产业网络契约

产业网络使用 `a_share_industry_network_v2` 多表契约，将企业身份与证券上市阶段分开，并把产品候选、匿名集中度与公司关系事实分表保存。主表为：

```text
companies.csv
listings.csv
industries.csv
industry_memberships.csv
company_relations.csv
business_activities.csv
products.csv
activity_product_candidates.csv
counterparty_concentrations.csv
lifecycle_events.csv
```

具名公司关系使用独立侧车 `named_counterparty_relation_evidence.csv`，由 `named_counterparty_relation_evidence_v1` 约束。侧车保留交易原文、页码、法定名称、独立身份年报、报告期、公告时间、来源首次可得时间、身份首次可得时间、审核时间和最终关系可得时间。

对手方文件的后续佐证保存在 `named_relation_corroborations.csv`，由 `named_relation_corroboration_v1` 约束。当前两条记录链接到原两条交易证据，结论固定为 `corroborates_identity_and_control_link_not_transaction_amount_or_direction`，避免把集团关系当作交易复核。

生命周期事件同时记录 `event_time`、`available_time` 和 `effective_time`。企业节点不会因退市被删除；退市只让对应证券连接退出当前资本市场网络。历史上市/退市日期若没有当年的首次可得时间，会标为 `historical_availability_unknown`，默认不得用于历史影响回测。

机器契约：`data/contracts/a_share_industry_network_v2.schema.json`。v1 仍保留为历史契约。完整说明见 `docs/A_SHARE_INDUSTRY_NETWORK.md`。

发行人身份审计：`data/industry_network/a_share/issuer_identity_map.csv`。首轮 5884 条上市记录中 5880 条匹配巨潮 `orgId`，归并后为 5874 个企业节点；4 条旧代码仍保留临时身份。

首批生产活动证据：`business_activities.csv` 中保存牧原股份的“主营业务”和“经营范围”两条巨潮原文。主营业务原文“生猪的养殖与销售”生成“生猪”词表节点及 `producer`、`seller` 两条映射；用户按推荐于 `2026-08-17T02:37:23+00:00` 授权复核，两条均为 `approved`。经营范围里的饲料、屠宰、食品许可没有升级为实际生产事实。

牧原股份 2025 年报：公告编号 `1225042507`，PDF 归档在 `data/external/a_share_industry_network/cninfo_reports/20260817T021821Z/`，SHA-256 为 `aa44a1f4244a6efbc6e54e7dbd4307235d39117bb4ff4d9590f386b02b0d9a04`。第 30–31 页披露前五名客户销售额 `11,937,999,760.19` 元、占比 `8.28%`，前五名供应商采购额 `20,149,948,693.01` 元、占比 `19.48%`。名称只有“第一名”至“第五名”，因此只写入 `counterparty_concentrations.csv`，未写入 `company_relations.csv`。官方公告时间为 2026-03-28，本地模型可得时间从 2026-08-17 首次归档起算。

华域汽车/上汽集团具名关系试点：华域汽车 2025 年报公告编号 `1225052214`，上汽集团独立身份年报公告编号 `1225071780`。华域汽车第 4、178、179 页和上汽集团第 1 页完成文本与视觉核验，确认 2025 年华域汽车向上汽集团采购商品及材料 `153,169,367.40` 元、向上汽集团销售商品 `5,438,818,642.01` 元。主表写入两条定向 `supplies` 观察，`valid_to=2026-01-01` 为报告期结束的排他边界；关系从 `2026-08-18T07:28:24+00:00` 起可得，不自动延续。按 `2026-08-18T16:00:00+08:00` 重建的当前有效关系快照为 0。

2026-08-18 进一步检查上汽集团年报全部“华域汽车”命中页。第 17 页确认华域法定名称、代码 `600741` 和“下属控股子公司”标签；第 170 页企业集团构成表确认直接持股 `58.32%`。两页视觉核验后生成 2 条佐证，最早从审核完成时间 `2026-08-18T07:55:10+00:00` 使用。该年报未逐笔披露可与华域两笔交易对应的金额，所以 `transaction_amount_or_direction_cross_confirmed=false`，关系主表保持 2 行不变。

## 网络信息素信号覆盖层

网络信号使用独立 `network_signal_field_v1` 契约，详细定义见 `docs/NETWORK_SIGNAL_MODEL.md`。`signal_types.csv` 是受控展示词表；`signal_events.csv` 当前有 2 条直接状态，`signal_event_evidence.csv` 有 2 条独立证据，`transmission_rules.csv` 仍为空。证据表新增 `raw_numeric_value`、`raw_unit`、`raw_text` 和维度字段，将来源事实与事件的标准化显示强度分开。计算器要求事件、关系边和传播规则均满足 `available_time <= as_of`，并把直接贡献和传播贡献分开；证据不重复增加浓度。

生命周期事件来自 `STATUS_3de54a4d161756b9047b`：BaoStock 在 `2026-08-16T13:48:42+00:00` 抓取时观察牧原股份上市阶段为 active。2026-08-18 深交所官方 A 股列表通过代码 `002714` 和简称“牧原股份”精确匹配，信号增加 `official_listing_presence_confirmed`；该记录不证明当天每一时刻均可交易。

生产事件来自已审核映射 `ACTIVITY_PRODUCT_e68171883dc3330a1a29`：角色为 `producer`，产品为“生猪”，证据原文为“生猪的养殖与销售”，审核时间 `2026-08-17T02:37:23+00:00`。来源未披露产量，所以证据记录 `raw_numeric_value=空`、`raw_unit=not_reported`、`raw_text=生猪的养殖与销售`；公司对象上的 `production.activity=+1` 仅为二元活动存在显示编码。当前正式快照共 71,052 行，生命周期和生产活动各 1 行非零，所有传播贡献为零。

2026-08-18 完成数据驱动只读报告：生成器直接读取快照、事件、证据、规则和产业网络表，同一视图展示两条直接信号、证据来源与质量、原始事实、未披露数值和零传播状态，并输出输入文件 SHA-256 审计。报告发现深交所证据的可得时间晚于快照，已标为“后续核验”，不会回填更早状态。报告不写回存储、不改变数据契约或来源状态，也未增加传播规则。

## 导入脚本状态

| 脚本 | 作用 | 输出 | 状态 |
|---|---|---|---|
| `scripts/fetch_a_share_spot.py` | 抓取当前 A 股全市场快照 | `data/realtime/a_share_spot.csv` | 已验证 |
| `scripts/fetch_a_share_history.py` | 抓取单股历史日线，支持 AkShare / BaoStock | `data/raw/{symbol}.csv` | 已验证 |
| `scripts/fetch_a_share_minutes.py` | 抓取并增量合并 BaoStock 5/15/30/60 分钟线 | `data/minute/{symbol}/{frequency}m_baostock.csv`、同名 `.meta.json` | 牧原股份 5 分钟线已验证 |
| `scripts/audit_minute_archive.py` | 将分钟线聚合后与同来源、同复权日线交叉核验 | `reports/data_validation/*_5m_*.csv`、`*.json`、`*.md` | 已用于牧原股份 |
| `scripts/import_ths.py` | 导入同花顺导出 CSV/TXT | `data/raw/{symbol}.csv` | 已验证样例 |
| `scripts/convert_market_data.py` | 将常见中英文外部 CSV/TXT 转为标准 OHLCV，并校验价格关系 | `data/raw/{symbol}.csv`、同名 `.meta.json` | 2026-08-16 本地测试通过 |
| `scripts/build_stock_motion_stream.py` | 将标准日线 OHLCV 转为内部股票运动事件流 | `data/processed/motion/{symbol}.motion.csv`、同名 `.meta.json` | 2026-08-16 本地测试通过 |
| `scripts/compare_ohlcv_sources.py` | 比较两个标准日线文件的交易日、OHLC、收益率和成交量尺度 | `reports/data_validation/*.csv`、`*.json`、`*.md` | 已用于牧原股份双来源核验 |
| `scripts/fetch_realtime.py` | 通过同花顺 iFinD / Quant API 抓实时行情 | `data/realtime/latest_quotes.csv` | 已预留，缺 `iFinDPy` |
| `scripts/segment_a_share_spot.py` | 对 A 股当前快照做市场分层 | `reports/a_share_segments.csv`、`reports/a_share_segments.md` | 已有脚本和报告 |
| `scripts/fetch_a_share_industry_network.py` | 抓取/归档 BaoStock 企业基础与行业表，增量维护上市退市历史 | `data/external/a_share_industry_network/`、`data/industry_network/a_share/` | 2026-08-16 首批全量运行通过 |
| `scripts/build_a_share_network_snapshot.py` | 按知识时点生成正式或含候选节点的产业网络快照 | `data/processed/industry_network_snapshot*/` | 2026-08-16 本地验证通过 |
| `scripts/enrich_a_share_issuer_identity.py` | 用 CNINFO `orgId` 迁移企业身份，并导入指定公司的概况原文 | `issuer_identity_map.csv`、`business_activities.csv`、CNINFO 原始归档 | 2026-08-16 首轮运行通过 |
| `scripts/import_cninfo_annual_report_evidence.py` | 下载/离线重建完整年报，核验匿名客户供应商集中度并生成待审核产品映射 | `products.csv`、`activity_product_candidates.csv`、`counterparty_concentrations.csv`、年报原始归档 | 2026-08-17 牧原股份 2025 年报验证通过 |
| `scripts/import_named_counterparty_relations.py` | 归档/离线重建具名关系年报，校验交易原文、金额、方向、独立身份和可得时间 | `named_counterparty_relation_evidence.csv`、`company_relations.csv`、官方原始归档 | 2026-08-18 两条 2025 年关系验证通过，重复运行保持 2 行 |
| `scripts/crosscheck_named_counterparty_relations.py` | 用对手方年报核验身份和集团关系，并限制结论范围 | `named_relation_corroborations.csv`、`reports/named_relation_crosscheck.md`、归档审计 | 2026-08-18 两条佐证验证通过；供应关系主表未变化 |
| `scripts/audit_counterparty_relation_eligibility.py` | 按知识时点审计集中度披露是否具备具名公司关系建边条件；不写网络主表 | `reports/counterparty_relation_eligibility.csv`、`.meta.json`、`.md` | 2026-08-18 两条匿名汇总均拒绝；不影响另有证据的 2 条历史关系 |
| `scripts/review_activity_product_candidates.py` | 记录产品映射的显式人工审核决定，防止重建年报时覆盖审核状态 | `activity_product_candidates.csv`、`network.meta.json` | 2026-08-17 两条“生猪”映射已授权通过 |
| `scripts/build_combined_stock_motion_stream.py` | 合并 OHLCV、已审核生产活动和匿名集中度代理为 `stock_motion_event_v2` | `data/processed/motion/002714.SZ.motion.csv`、同名 `.meta.json` | 2026-08-17 10028 条事件验证通过 |
| `scripts/build_human_need_network_report.py` | 读取需求—资源—生产契约并生成需求根节点网络图 | `reports/human_need_resource_network.html` | 2026-08-18 本地生成；候选资源依赖用虚线显示 |
| `scripts/import_resource_observations.py` | 对归档资源观察执行来源、单位、地理与时间准入 | `data/human_need_network/resource_endowment_observations_imported.csv`、`.meta.json` | 2026-08-19 已用拒绝/通过 fixture 测试；尚无真实观察写入 |
| `scripts/initialize_network_signal_store.py` | 初始化受控信号词表、事件/证据/规则表；已有存储只补缺失文件，不覆盖核验元数据 | `data/network_signals/a_share/` | 2026-08-18 幂等性验证通过 |
| `scripts/import_lifecycle_signal_event.py` | 将可得时间明确的抓取时点上市状态观察幂等转换为直接生命周期信号 | `data/network_signals/a_share/signal_events.csv` | 2026-08-18 牧原股份 1 条事件验证通过 |
| `scripts/verify_lifecycle_signal_with_szse.py` | 用深交所官方 A 股列表精确匹配代码和简称，归档响应并关联独立证据 | `signal_event_evidence.csv`、`data/external/a_share_industry_network/szse/` | 2026-08-18 牧原股份核验通过 |
| `scripts/import_approved_production_signal.py` | 将已审核 `producer` 映射转换为直接生产活动信号，分开保存原文、原始数值和显示强度 | `signal_events.csv`、`signal_event_evidence.csv` | 2026-08-18 牧原股份“生猪”生产活动导入通过 |
| `scripts/build_network_signal_snapshot.py` | 将 A 股网络对象与信号覆盖层按知识时点合并 | `data/processed/network_signal_snapshot/signal_state_snapshot.csv` | 2026-08-18 11842 对象、71052 行；2 行直接信号非零 |
| `scripts/build_network_signal_report.py` | 从快照、事件、证据、规则和产业网络对象表生成只读报告，并区分快照时证据与后续核验 | `reports/network_signal_inspector.html`、同名 `.meta.json` | 2026-08-18 牧原股份报告生成及宽窄屏、浅深主题核验通过 |

## 已验证命令

抓取当前 A 股快照：

```powershell
.\.venv\Scripts\Activate.ps1
python scripts/fetch_a_share_spot.py
```

抓取 AkShare 历史日线：

```powershell
python scripts/fetch_a_share_history.py 000001.SZ --source akshare --start 20240101
```

抓取 BaoStock 历史日线：

```powershell
python scripts/fetch_a_share_history.py 600519.SH --source baostock --start 2024-01-01
```

首次回补并建立牧原股份 5 分钟档案：

```powershell
.\.venv\Scripts\python.exe scripts\fetch_a_share_minutes.py 002714.SZ `
  --frequency 5 --start 2024-01-01 --end 2026-08-14 `
  --adjustflag 3 --volume-unit unknown --amount-unit unknown
```

以后增量更新时不传 `--start`；脚本会从档案最后一个交易日开始重抓，以最后返回值替换重叠时间戳，不会追加重复行：

```powershell
.\.venv\Scripts\python.exe scripts\fetch_a_share_minutes.py 002714.SZ `
  --frequency 5 --adjustflag 3 --volume-unit unknown --amount-unit unknown
```

使用真实 A 股数据训练：

```powershell
$env:MPLBACKEND='Agg'
$env:MPLCONFIGDIR=(Join-Path $PWD ".matplotlib")
python -m stock_model.train --csv data/raw/000001.SZ.csv --symbol 000001.SZ
```

将标准 OHLCV 转为内部运动数据流：

```powershell
.\.venv\Scripts\python.exe scripts\build_stock_motion_stream.py `
  --input data\raw\002714.SZ.csv `
  --output data\processed\motion\002714.SZ.motion.csv
```

将市场观察、已审核生产活动和匿名集中度代理合并为一个内部流：

```powershell
.\.venv\Scripts\python.exe scripts\build_combined_stock_motion_stream.py `
  --input data\raw\002714.SZ.csv `
  --output data\processed\motion\002714.SZ.motion.csv `
  --network-dir data\industry_network\a_share `
  --symbol 002714.SZ
```

当前训练命令仍是旧基线接口，尚未强制消费内部运动流；不得把“内部契约已建立”误写为“生产/价值状态已经建模完成”。

## 最近一次训练验证

数据文件：`data/raw/000001.SZ.csv`

```text
Rows used: 555
CV accuracy scores: 0.568, 0.635, 0.541, 0.446, 0.419
Test accuracy: 0.541
Test ROC AUC: 0.509
Latest prediction date: 2026-07-20
Latest prob_up: 0.482093
Latest prediction: down
```

输出：

| 文件 | 说明 |
|---|---|
| `models/000001.SZ_model.joblib` | 平安银行样例模型 |
| `reports/000001.SZ_test_predictions.csv` | 样本外预测明细 |
| `reports/000001.SZ_backtest.png` | 简单回测图 |
| `reports/000001.SZ_latest_prediction.csv` | 最新预测结果 |

## 牧原股份双来源核验

核验时间：2026-08-16；标的：`002714.SZ`；请求区间：2024-01-01 至 2026-08-14。

- AkShare `stock_zh_a_hist(adjust="qfq")` 与 BaoStock `query_history_k_data_plus(adjustflag="2")` 均返回 634 个交易日，实际区间均为 2024-01-02 至 2026-08-14，没有单边缺失日期。
- 两个来源的前复权 OHLC 仅 57/634 行完全相同，最大绝对价差为 0.64594816 元；最后一个不完全相同的日期为 2026-05-26。说明两家的前复权序列不能直接拼接或互换。
- 收盘日收益率相关系数为 0.999593；绝对差中位数约 0.000265，最大值约 0.006381。高度相关不代表数值完全一致。
- BaoStock 成交量除以 AkShare 成交量的中位数约为 99.999992，缩放后的相对误差中位数低于 `0.000001`。AkShare 官方文档明确该接口成交量单位为“手”；BaoStock 当前单位文档未完成核实，仍记录为 `unknown`，不能只凭倍率把单位正式写为“股”。
- AkShare 不复权接口在补充核验时连续遭遇上游主动断开，因此本轮没有完成“不复权对不复权”的第二组比较。该失败不影响已经落盘文件的哈希和统计，但限制了对复权差异成因的判断。
- 模型输入采用 AkShare 单一来源，不与 BaoStock 价格拼接：`data/raw/002714.SZ.csv`；口径为日线、前复权、成交量单位“手”，审计文件为 `data/raw/002714.SZ.csv.meta.json`。
- 详细结果：`reports/data_validation/002714.SZ_akshare_vs_baostock.md`、同名 `.json` 和逐日 `.csv`。

## 牧原股份 5 分钟增量档案核验

建立时间：2026-08-16；来源：BaoStock；频率：5 分钟；复权：不复权。

- 首次回补得到 30432 行、634 个交易日，时间范围为 2024-01-02 09:35 至 2026-08-14 15:00。
- 每个交易日均为 48 行；没有重复时间戳、午间休市数据、零成交量行或结构缺失日。
- 第二次增量运行只抓取最后一个交易日的 48 行并替换 48 个重叠时间戳，档案仍为 30432 行，证明重复运行具有幂等性。
- 与 BaoStock 同区间不复权日线聚合比较：开盘和收盘 634/634 天完全一致；最高价 250/634 天一致，最大差 0.15 元；最低价 260/634 天一致，最大差 0.43 元；成交量 149/634 天一致，最大相对差约 2.128%。
- 事实结论：档案的日期、时段和行数结构完整。限制结论：它不能被称为逐笔完整数据，且在高低价/成交量差异原因解决或明确接受前，不进入模型训练。
- 审计报告：`reports/data_validation/002714.SZ_5m_baostock_vs_daily.md`、同名 `.json` 和逐日 `.csv`。

## 待办事项

- 建立股票池文件，例如 `data/universe/a_share_core.csv`。
- 批量抓取股票池历史日线，并记录成功、失败、缺失日期。
- 为 `data/realtime/a_share_spot.csv` 增加快照归档机制，避免每次覆盖。
- 从六只基金管理人的官方主机交叉取得已归档的 2026 年二季报，并核对文件哈希与公告时间；当前本地 PDF 来自 Eastmoney 镜像。
- 建立官方增减持、回购、融资融券、互联互通、大宗交易和龙虎榜的独立外部契约；通道身份不得冒充受益所有人。
- 在有真实后验标签以前，资金主体分布保持规则化先验和显式 `unknown`，并报告覆盖率而不是只报告最大概率。
- 继续核实 BaoStock `volume` 的官方单位说明；AkShare `stock_zh_a_hist` 已确认单位为“手”，牧原股份样本中 BaoStock 数值约为其 100 倍。
- 给每次数据导入生成机器可读日志，例如 `data/import_log.csv`。
- 用用户实际取得的外部文件验证通用转换器，并确认该来源的复权方式和成交量单位。
- 增加缺失交易日、异常跳变、零成交和跨来源口径比较报告。
- 调查 BaoStock 5 分钟聚合值与同来源日线最高价、最低价和成交量不完全一致的原因；在解决或接受限制前不把分钟档接入模型。
- 若需要无人值守每日运行，再单独建立并验证调度；当前已完成幂等增量脚本，但未创建系统定时任务。
- 为北交所接入带行业分类和上市状态的当前免费来源；2026-07-20 AkShare 快照中的 339 个北交所节点只作过期候选。
- 核实 4 个未匹配旧代码的法律实体身份，并用统一社会信用代码或交易所发行人标识继续交叉核验巨潮 `orgId`。
- 继续寻找其他披露法定名称或有独立身份依据的客户/供应商；沿用首组具名关系的原文、身份、视觉审核和时间边界门槛，不从关联背景或行业分类推断关系。
- 为行业分类变更增加完整双时态版本链；当前增量重点覆盖上市和退市生命周期。

## 更新日志

| 时间 | 变更 | 影响文件 |
|---|---|---|
| 2026-07-20 10:45 | 建立低成本 A 股数据接入，AkShare 当前快照和历史日线验证通过，BaoStock 历史日线验证通过 | `stock_model/a_share.py`、`scripts/fetch_a_share_spot.py`、`scripts/fetch_a_share_history.py`、`requirements.txt`、`README.md` |
| 2026-07-20 10:45 | 使用 `000001.SZ` 真实日线跑通模型训练和最新预测 | `data/raw/000001.SZ.csv`、`models/000001.SZ_model.joblib`、`reports/000001.SZ_latest_prediction.csv` |
| 2026-07-20 14:25 | 创建本数据状况呈现书，作为后续数据导入变更台账 | `docs/DATA_STATUS.md` |
| 2026-08-16 | 增加通用本地数据转换器、审计元数据和自动测试；建立跨账号 AI 接手说明与零基础人类说明 | `stock_model/converter.py`、`scripts/convert_market_data.py`、`tests/test_converter.py`、`AI_HANDOFF.md`、`docs/USER_GUIDE_CN.md` |
| 2026-08-16 | 建立 `stock_motion_daily_v1` 内部运动数据流契约和 OHLCV 转换器，区分观察、派生、代理与未识别潜在状态 | `stock_model/motion.py`、`scripts/build_stock_motion_stream.py`、`tests/test_motion.py`、`docs/STOCK_MOTION_MODEL.md` |
| 2026-08-16 20:48 | 用牧原股份 `002714.SZ` 对 AkShare 与 BaoStock 的同区间前复权日线进行交叉核验，保存模型输入、审计元数据和可复现比较报告 | `data/raw/002714.SZ.csv`、`data/validation/002714.SZ/`、`reports/data_validation/`、`scripts/compare_ohlcv_sources.py` |
| 2026-08-16 21:17 | 建立 `ohlcv_minute_v1` 契约和 BaoStock 分钟增量归档；回补牧原股份 5 分钟不复权数据并与同来源日线核验 | `stock_model/minute.py`、`scripts/fetch_a_share_minutes.py`、`scripts/audit_minute_archive.py`、`tests/test_minute.py`、`data/contracts/ohlcv_minute_v1.schema.json`、`data/minute/002714.SZ/` |
| 2026-08-16 21:50 | 建立 A 股产业网络与上市退市生命周期；归档 BaoStock 沪深企业/行业数据，生成 5884 节点注册表和时点网络 | `stock_model/industry_network.py`、`scripts/fetch_a_share_industry_network.py`、`scripts/build_a_share_network_snapshot.py`、`data/industry_network/a_share/`、`docs/A_SHARE_INDUSTRY_NETWORK.md` |
| 2026-08-16 22:06 | 接入 CNINFO 发行人 `orgId` 和公司概况；映射 5880 条上市记录并导入牧原股份两条经营活动原文 | `scripts/enrich_a_share_issuer_identity.py`、`issuer_identity_map.csv`、`business_activities.csv`、`data/external/a_share_industry_network/cninfo/` |
| 2026-08-17 10:18 | 产业网络升级至 v2；归档并核验牧原股份 2025 年报，建立“生猪”产品节点、两条待审核角色映射和两条匿名对手方集中度；公司关系边保持为 0 | `stock_model/industry_network.py`、`scripts/import_cninfo_annual_report_evidence.py`、`data/contracts/a_share_industry_network_v2.schema.json`、`data/industry_network/a_share/`、`data/external/a_share_industry_network/cninfo_reports/` |
| 2026-08-17 10:37 | 用户授权复核两条“生猪”映射；升级 `stock_motion_event_v2` 并将 2 条已审核活动观察、4 条匿名集中度代理与 10022 条行情事件合并 | `scripts/review_activity_product_candidates.py`、`scripts/build_combined_stock_motion_stream.py`、`stock_model/motion.py`、`data/contracts/stock_motion_event_v2.schema.json`、`data/processed/motion/002714.SZ.motion.csv` |
| 2026-08-17 | 建立 `capital_control_distribution_v1` 资金控制概率契约、空白注册表和验证函数；明确受益所有、投资决策、交易执行与托管角色，未识别概率强制保留为 `CONTROLLER_UNKNOWN` | `docs/CAPITAL_CONTROL_MODEL.md`、`data/contracts/capital_control_distribution_v1.schema.json`、`data/capital_control/a_share/`、`stock_model/capital_control.py`、`tests/test_capital_control.py` |
| 2026-08-17 10:38 | 按公募基金优先顺序接入 000001 与 110022：归档产品概况、管理人、基金经理、托管人、200 条报告索引和 2026 年一/二季度 40 条持仓；用报告公告日终回填持仓可得时间，不生成交易主体概率 | `scripts/fetch_public_fund_evidence.py`、`stock_model/public_fund.py`、`data/contracts/public_fund_evidence_v1.schema.json`、`data/external/public_fund/`、`data/capital_control/a_share/`、`tests/test_public_fund.py` |
| 2026-08-17 11:00 | 公募基金样本扩展到 6 个产品、498 条报告索引和 120 条季度持仓；发现并记录招商白酒与中欧医疗的份额净资产/组合持仓范围不一致警告，不进行跨口径资金比例计算 | `scripts/fetch_public_fund_evidence.py`、`stock_model/public_fund.py`、`data/external/public_fund/normalized/`、`data/contracts/public_fund_evidence_v1.schema.json` |
| 2026-08-17 11:10 | 生成相邻季度披露集合变化表；共同披露证券才计算持股数差，进入/离开前十大集合保留为未知；修正五位港股代码 `00700` 为 `00700.HK` | `stock_model/public_fund.py`、`scripts/fetch_public_fund_evidence.py`、`data/external/public_fund/normalized/public_fund_holding_changes.csv`、`tests/test_public_fund.py`、`reports/public_fund_control_sample.md` |
| 2026-08-17 11:35 | 归档六份 2026 年二季报 Eastmoney 镜像 PDF；完成 SHA-256、产品身份、报告期、60/60 持仓文本匹配，以及封面和完整前十大持仓表视觉核验 | `scripts/archive_public_fund_report_pdfs.py`、`data/external/public_fund/report_pdfs/`、`AI_HANDOFF.md` |
| 2026-08-17 | 增加 `network_signal_field_v1` 信息素式网络信号覆盖层；建立衰减、延迟、规则传播、循环防放大和直接/传播贡献分离；生成 11842 对象 × 6 类型的零信号快照 | `stock_model/network_signals.py`、`scripts/initialize_network_signal_store.py`、`scripts/build_network_signal_snapshot.py`、`data/contracts/network_signal_field_v1.schema.json`、`data/network_signals/a_share/`、`data/processed/network_signal_snapshot/`、`docs/NETWORK_SIGNAL_MODEL.md`、`tests/test_network_signals.py` |
| 2026-08-18 | 将牧原股份抓取时上市状态观察幂等导入为首条直接生命周期信号；拒绝历史可得时间不明记录，生效时间不早于本地可得时间；重建 1 行非零、0 行传播的正式快照 | `stock_model/network_signals.py`、`scripts/import_lifecycle_signal_event.py`、`data/network_signals/a_share/`、`data/processed/network_signal_snapshot/`、`docs/NETWORK_SIGNAL_MODEL.md`、`tests/test_network_signals.py` |
| 2026-08-18 | 用深交所官方 A 股列表交叉核验首条生命周期信号；代码、简称精确匹配，新增独立证据表并保留原始第三方质量标签；浓度和传播状态不变 | `stock_model/network_signals.py`、`scripts/verify_lifecycle_signal_with_szse.py`、`data/contracts/network_signal_field_v1.schema.json`、`data/network_signals/a_share/signal_event_evidence.csv`、`data/external/a_share_industry_network/szse/`、`docs/NETWORK_SIGNAL_MODEL.md`、`tests/test_network_signals.py` |
| 2026-08-18 | 将已审核“生猪—producer”映射导入为首条生产活动直接信号；产量未披露，原文、空数值、显示强度与证据质量分开；传播规则保持为空 | `stock_model/network_signals.py`、`scripts/import_approved_production_signal.py`、`data/contracts/network_signal_field_v1.schema.json`、`data/network_signals/a_share/`、`data/processed/network_signal_snapshot/`、`docs/NETWORK_SIGNAL_MODEL.md`、`tests/test_network_signals.py` |
| 2026-08-18 | 完成牧原股份网络信号只读显示试点；同时呈现两条直接信号、证据质量、原始事实、未披露数值和零传播，并完成宽窄屏与浅深主题核验；数据契约和传播规则未变 | `docs/NETWORK_SIGNAL_MODEL.md`、`docs/DATA_STATUS.md`、`AI_HANDOFF.md` |
| 2026-08-18 | 将网络信号显示升级为数据驱动本地报告，增加输入哈希审计和证据可得时间标记；深交所证据晚于快照，仅作后续核验，不回填更早状态 | `stock_model/network_signal_view.py`、`scripts/build_network_signal_report.py`、`tests/test_network_signal_view.py`、`reports/network_signal_inspector.html`、`docs/NETWORK_SIGNAL_MODEL.md` |
| 2026-08-18 | 增加具名客户/供应商关系准入审计；按知识时点检查当前两条匿名年报汇总，均拒绝建边，合格关系和新建关系为 0，产业网络主表未改动 | `stock_model/industry_network.py`、`scripts/audit_counterparty_relation_eligibility.py`、`tests/test_industry_network.py`、`reports/counterparty_relation_eligibility.md`、`docs/A_SHARE_INDUSTRY_NETWORK.md` |
| 2026-08-18 | 归档华域汽车与上汽集团 2025 年报，完成四页视觉核验，建立具名关系证据 v1 并写入两条仅覆盖 2025 报告期的双向供应观察；离线重建幂等，完整测试 53 项通过 | `stock_model/industry_network.py`、`scripts/import_named_counterparty_relations.py`、`data/contracts/named_counterparty_relation_evidence_v1.schema.json`、`data/industry_network/a_share/`、`data/external/a_share_industry_network/cninfo_named_relations/` |
| 2026-08-18 | 用上汽集团年报第 17、170 页反向核验华域身份、控股标签和 58.32% 直接持股；新增 2 条范围受限佐证，不改变交易关系，完整测试 56 项通过 | `stock_model/industry_network.py`、`scripts/crosscheck_named_counterparty_relations.py`、`data/contracts/named_relation_corroboration_v1.schema.json`、`reports/named_relation_crosscheck.md` |
| 2026-08-18 | 按用户方向重建产业网络主干；新增需求—资源—生产 v1 契约、基本营养—动物蛋白—生猪试点、资源时点占位观察、防未来泄漏测试和需求根节点网络图；旧 A 股网络降为历史分支 | `stock_model/human_need_network.py`、`data/human_need_network/`、`data/contracts/human_need_resource_network_v1.schema.json`、`docs/HUMAN_NEED_RESOURCE_NETWORK.md`、`scripts/build_human_need_network_report.py`、`reports/human_need_resource_network.html`、`tests/test_human_need_network.py` |
| 2026-08-19 | 按用户要求把需求网补充到物种/群体生物尺度；升级 v2 契约，覆盖物质稳态、繁衍照护、神经心理、社会协作和符号精神五个系统及 40 余个需求节点；精神需求明确为生物—认知—社会涌现假设；网络图改为需求全景 + 生猪试点双层显示 | `data/human_need_network/needs.csv`、`data/contracts/human_need_resource_network_v2.schema.json`、`stock_model/human_need_network.py`、`scripts/build_human_need_network_report.py`、`docs/HUMAN_NEED_RESOURCE_NETWORK.md`、`tests/test_human_need_network.py` |
| 2026-08-19 | 为饲料粮依赖增加来源登记与观察导入闸门；登记 FAOSTAT 与中国国家统计局候选来源，但没有伪造数量；增加来源时间语义、单位/地理完整性和未来观察隔离测试 | `data/human_need_network/source_registry.csv`、`source_observations.csv`、`data/contracts/resource_observation_source_v1.schema.json`、`stock_model/human_need_network.py`、`scripts/import_resource_observations.py`、`tests/test_human_need_network.py` |
| 2026-09-10 | 迁移前核对项目文件、数据清单和实际代码；66 项本地测试全部通过；确认未刷新外部数据，旧实时快照、空白概率表、空白资源观察和零传播规则继续保持原状态 | `AI_HANDOFF.md`、`docs/ACCOUNT_MIGRATION_BRIEF.md`、`docs/CONVERSATION_MIGRATION.md`、本地测试结果 |
