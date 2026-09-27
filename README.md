# Stock Trend Lab

## 从这里开始

- 第一次使用或金融零基础：阅读 [人类使用说明书](docs/USER_GUIDE_CN.md)。
- 更换账号/电脑，或让新的 AI 接手：先阅读 [AI 接手说明书](AI_HANDOFF.md)。
- 只想快速完成账号迁移：先阅读 [账号迁移摘要](docs/ACCOUNT_MIGRATION_BRIEF.md)，再按完整交接书核对细节。
- 导入外部行情：使用 `scripts/convert_market_data.py`，它会生成标准 OHLCV CSV 和可追溯的 `.meta.json` 审计文件。
- 股票运动模型：阅读 [股票运动模型（生产网络映射版）](docs/STOCK_MOTION_MODEL.md)。外部 OHLCV 需要再转换为内部运动数据流，才进入新的状态建模链路。
- 当前建设顺序：以 [人的需求—资源—生产网络](docs/HUMAN_NEED_RESOURCE_NETWORK.md) 为主干，先建立需求、满足方式、转化过程和资源约束，再把企业与股票作为下游承载/金融映射。旧 [A 股产业网络](docs/A_SHARE_INDUSTRY_NETWORK.md) 保留为历史实验分支，不再作为根节点。
- 网络对象已增加独立的 [信息素式信号覆盖层](docs/NETWORK_SIGNAL_MODEL.md)：支持按知识时点计算直接信号、独立证据、衰减、显式规则传播和可视化浓度；当前有生命周期与已审核“生猪”生产活动两条直接信号，传播规则仍为空。
- 资金控制概率模型：阅读 [A 股资金控制与运动概率模型](docs/CAPITAL_CONTROL_MODEL.md)。成交额与主体身份分开保存，无法解释的概率保留为 `CONTROLLER_UNKNOWN`。
- 需求资源网络：阅读 [人的需求—资源—生产网络](docs/HUMAN_NEED_RESOURCE_NETWORK.md)。资源丰富度必须按资源 × 地理单元 × 时间观察，候选依赖不会自动升级为事实。
- A 股产业网络：阅读 [A 股产业网络模型](docs/A_SHARE_INDUSTRY_NETWORK.md)。企业身份、证券上市阶段、行业归属和上市退市事件分开保存，但在新主干中只作为下游映射层。
- 当前研究结果不构成投资建议；历史样例模型的 ROC AUC 约为 0.509，接近随机，只能证明流程曾跑通。

这是一个以股票市场为第一批验证场景的世界模型项目。项目目标不是给出投资建议，而是建立一套可记录、可计算、可迭代的世界模型：用“物质”和“从物质中诞生的意识”作为粗略顶层分类，初始拆分为自然环境模型和社会模型，逐步记录物质约束、资源分配、市场意识和价格反馈之间的关系。

鉴于个人资源、数据来源和算力有限，第一版会保持简陋：先使用表格台账、低维字段、人工关系和轻量模型跑通最小闭环，再逐步扩展复杂度。

当前代码层仍先从股票市场跑通一条低成本实验流程：

1. 准备股票历史行情数据
2. 生成技术指标特征
3. 用时间序列方式训练分类模型
4. 输出上涨/下跌概率与简单回测结果

整体框架、世界模型目标、模块边界和阶段规划见：[框架呈现书](docs/framework_presentation.md)。

## 项目结构

```text
stock/
  data/
    inbox/               # 外部数据原件（本地保留，不进入版本控制）
    raw/                 # 原始行情 CSV
    minute/              # 带时区的分钟行情增量档案（独立于日线模型）
    realtime/            # 当前行情快照
    ths_exports/         # 同花顺导出的 CSV/TXT，可临时放这里
    processed/           # 处理后的特征数据
      motion/            # stock_motion_event_v2 内部股票运动流
      industry_network_snapshot/  # 按知识时点生成的正式产业网络
    industry_network/    # 企业、上市阶段、行业、产品证据、关系与生命周期主表
    capital_control/     # 资金池、控制关系、持仓观察、资金运动与主体概率分布
    external/            # 外部数据原始归档
  models/                # 训练出的模型文件
  reports/               # 训练指标、预测结果、回测图表
    natural_environment_map.html  # 全球自然环境模型可视化
    human_need_resource_network.html  # 需求根节点网络可视化
  scripts/
    build_natural_environment_visualization.py  # 生成自然环境模型可视化
    build_human_need_network_report.py  # 生成需求—资源—生产网络可视化
    make_sample_data.py  # 生成演示数据
    convert_market_data.py  # 任意外部 CSV/TXT 转换为标准 OHLCV 并生成审计元数据
    build_stock_motion_stream.py  # 标准 OHLCV 转换为内部运动数据流
    fetch_a_share_industry_network.py  # 抓取并维护企业/行业/上市退市网络
    build_a_share_network_snapshot.py  # 生成无未来泄漏的时点网络
    enrich_a_share_issuer_identity.py  # 接入 CNINFO 发行人身份与公司概况原文
    import_cninfo_annual_report_evidence.py  # 归档年报并导入产品候选和匿名集中度
    import_named_counterparty_relations.py  # 归档、核验并导入具名公司关系
    crosscheck_named_counterparty_relations.py  # 用对手方文件核验身份和集团关系
    review_activity_product_candidates.py  # 记录产品映射的显式人工审核
    build_combined_stock_motion_stream.py  # 合并行情与产业网络内部事件
    fetch_public_fund_evidence.py  # 归档公募基金概况、管理关系和季度持仓
    fetch_a_share_spot.py     # 免费抓取 A 股当前行情快照
    fetch_a_share_history.py  # 免费抓取 A 股历史日线
    fetch_a_share_minutes.py  # 免费抓取并增量归档 BaoStock 分钟线
    audit_minute_archive.py   # 分钟聚合与同来源日线核验
    import_ths.py        # 导入同花顺导出的行情文件
    fetch_realtime.py    # 通过本机同花顺/iFinD接口抓取实时行情
  stock_model/
    converter.py         # 通用本地数据转换与质量校验
    a_share.py           # A 股免费数据源接入
    minute.py            # 分钟契约、BaoStock 接入、增量合并和审计
    data.py              # 数据读取与可选下载
    realtime.py          # 实时行情接入
    features.py          # 特征工程
    motion.py            # 股票运动流契约、后向派生与来源审计
    capital_control.py   # 资金控制关系与主体概率分布验证
    public_fund.py       # 公募基金产品、管理人和持仓标准化
    industry_network.py  # 产业网络契约、生命周期状态机与市场影响流
    train.py             # 训练与评估
    predict.py           # 单只股票预测
  requirements.txt
```

## 全球自然环境数据库

自然环境模型的第一版数据库位于：

```text
data/natural_environment/
```

当前包含：

```text
global_environment_units.csv
natural_environment_dimensions.csv
```

生成本地可视化：

```powershell
.\.venv\Scripts\python.exe scripts\build_natural_environment_visualization.py
```

输出：

```text
reports/natural_environment_map.html
```

当前记录是 `seed_unverified` 种子数据，只用于验证字段结构和可视化流程。

## 安装

建议在另一台电脑上复制整个文件夹后，进入该目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

如果不能联网，可以先在有网络的电脑上下载依赖 wheel 包，或只使用已有 CSV 数据，安装依赖仍然需要本地 Python 包来源。

## CSV 数据格式

把原始数据放到 `data/raw/`，文件名建议用股票代码，例如：

```text
data/raw/000001.SZ.csv
data/raw/AAPL.csv
```

CSV 至少包含这些列，大小写不限：

```text
date, open, high, low, close, volume
```

示例：

```csv
date,open,high,low,close,volume
2024-01-02,10.20,10.50,10.10,10.42,12345600
```

外部文件无需先手工改成这些列。可先放到 `data/inbox/`，再按 [人类使用说明书](docs/USER_GUIDE_CN.md) 使用通用转换器。转换时需要记录数据源、复权口径和成交量单位；未知信息应写 `unknown`，不能猜测。

## 低成本接入 A 股行情

数据导入状态统一记录在：

```text
docs/DATA_STATUS.md
```

后续本对话中凡是更新数据源、导入脚本、落盘文件或字段口径，都需要同步更新这份数据状况呈现书。

成本优先时，建议先使用免费数据源：

1. AkShare：抓当前 A 股全市场快照，也可抓单股历史日线。
2. BaoStock：免费历史日线备选。

安装依赖：

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

抓取当前 A 股全市场快照：

```powershell
python scripts/fetch_a_share_spot.py
```

默认输出：

```text
data/realtime/a_share_spot.csv
```

抓取单股历史日线，输出为模型可直接使用的标准 OHLCV：

```powershell
python scripts/fetch_a_share_history.py 000001.SZ --source akshare --start 20180101
```

输出：

```text
data/raw/000001.SZ.csv
```

如果 AkShare 当天接口不稳定，可以切换 BaoStock：

```powershell
python scripts/fetch_a_share_history.py 000001.SZ --source baostock --start 2018-01-01
```

抓完历史数据后直接训练：

```powershell
$env:MPLBACKEND='Agg'
$env:MPLCONFIGDIR=(Join-Path $PWD ".matplotlib")
python -m stock_model.train --csv data/raw/000001.SZ.csv --symbol 000001.SZ
```

免费数据源适合研究、预演和早期建库；如果后续需要更高稳定性、分钟级别、逐笔、Level-2 或商用权限，再考虑 Tushare Pro 高权限、同花顺 iFinD 或交易所授权数据。

## 牧原股份 5 分钟增量档案

当前已建立 BaoStock 5 分钟、不复权档案：

```text
data/minute/002714.SZ/5m_baostock.csv
```

日常更新命令：

```powershell
.\.venv\Scripts\python.exe scripts\fetch_a_share_minutes.py 002714.SZ `
  --frequency 5 --adjustflag 3 --volume-unit unknown --amount-unit unknown
```

脚本会从档案最后一个交易日重新抓取并替换重叠时间戳，所以周末重复运行也不会制造重复数据。当前档案每个交易日有 48 根 K 线，但聚合后不能逐日完全复现 BaoStock 日线的最高价、最低价和成交量；它目前只作为带审计的原始观察保存，不进入日线模型或 `stock_motion_event_v2`。

## 接入本机同花顺数据

当前项目采用“同花顺导出文件 -> 标准 CSV -> 模型训练”的方式接入。这个方式最适合预演和迁移：不绑定同花顺安装目录，也不依赖另一台电脑的本地数据库结构。

在同花顺中导出日线行情为 CSV 或 TXT，建议包含这些字段：

```text
日期, 开盘, 最高, 最低, 收盘, 成交量
```

常见的 `开盘价/最高价/最低价/收盘价/成交量(手)` 也可以识别。导出后可以把文件放到：

```text
data/ths_exports/
```

导入单个文件：

```powershell
python scripts/import_ths.py --input data/ths_exports/000001.csv --symbol 000001.SZ
```

批量导入一个目录：

```powershell
python scripts/import_ths.py --directory data/ths_exports --pattern *.csv
```

导入后会生成标准行情文件，例如：

```text
data/raw/000001.SZ.csv
```

然后就可以直接训练：

```powershell
python -m stock_model.train --csv data/raw/000001.SZ.csv --symbol 000001.SZ
```

如果你后续希望直接读取同花顺安装目录里的缓存/本地数据文件，需要先确认本机同花顺实际保存格式。不同版本和不同数据类型可能是加密、二进制或专用格式，稳定性不如导出 CSV。

## 接入本机同花顺远航版实时资料

实时行情不建议直接解析远航版本地缓存文件，因为缓存格式会随版本、账号权限和行情类型变化。当前项目预留了更稳定的“本机同花顺数据接口/iFinD Python 模块 -> 标准 CSV”的入口。

前提：

1. 本机已安装并启用同花顺数据接口/iFinD Quant API 环境。
2. 当前 Python 环境能 `import iFinDPy`。
3. 账号具备相应实时行情权限。

设置账号密码后抓取实时行情：

```powershell
.\.venv\Scripts\Activate.ps1
$env:THS_USERNAME="你的账号"
$env:THS_PASSWORD="你的密码"
python scripts/fetch_realtime.py 000001.SZ 600519.SH
```

如果你的 iFinD 环境已经在外部完成登录，可以跳过登录：

```powershell
python scripts/fetch_realtime.py 000001.SZ 600519.SH --no-login
```

如果 `iFinDPy` 不在当前虚拟环境里，但你知道它所在目录，可以直接指定：

```powershell
python scripts/fetch_realtime.py 000001.SZ --ifind-path "C:\path\to\iFinDPy"
```

默认输出：

```text
data/realtime/latest_quotes.csv
```

默认指标为：

```text
open, high, low, latest, volume, amount
```

也可以自定义 `THS_RQ` 指标：

```powershell
python scripts/fetch_realtime.py 000001.SZ --indicators open,high,low,latest,volume,amount
```

如果运行时报 `Cannot import iFinDPy`，说明当前虚拟环境还没有接入同花顺的数据接口模块。需要从同花顺/iFinD 安装目录或官方安装包中，把接口模块安装到 `.venv`，或改用同花顺接口自带的 Python 环境运行脚本。

## 快速预演

先生成一份演示数据：

```powershell
python scripts/make_sample_data.py
```

训练模型：

```powershell
python -m stock_model.train --csv data/raw/SAMPLE.csv --symbol SAMPLE
```

预测最近一天之后的走势概率：

```powershell
python -m stock_model.predict --csv data/raw/SAMPLE.csv --model models/SAMPLE_model.joblib
```

## 可选：联网下载数据

如果安装了 `yfinance` 且电脑能联网，可以直接下载美股或部分市场数据：

```powershell
python -m stock_model.train --download AAPL --start 2018-01-01 --symbol AAPL
```

下载后的原始 CSV 会保存到 `data/raw/`，便于迁移。

## 4.1 随机技巧

这个项目里有两类随机性：一类来自演示数据生成，另一类来自模型训练算法本身。为了让实验可复现，默认都固定为 `42`：

- `scripts/make_sample_data.py` 默认使用 `--seed 42`
- `stock_model.train` 默认使用 `--random-state 42`

如果想生成一份不同走势的演示数据，可以换一个种子：

```powershell
python scripts/make_sample_data.py --seed 7
```

如果想检查模型结论是否依赖某一次随机初始化，可以在同一份真实数据上换几个 `random-state` 重跑：

```powershell
python -m stock_model.train --csv data/raw/000001.SZ.csv --symbol 000001.SZ --random-state 7
python -m stock_model.train --csv data/raw/000001.SZ.csv --symbol 000001.SZ --random-state 21
python -m stock_model.train --csv data/raw/000001.SZ.csv --symbol 000001.SZ --random-state 42
```

观察重点不是某一次准确率最高，而是多次结果是否大体稳定。若换种子后测试集准确率、ROC AUC 或回测曲线大幅跳动，通常说明样本量偏小、特征不够稳，或策略阈值过于贴合当前数据。

## 模型说明

### 人的需求—资源—生产网络

当前主干使用 `human_need_resource_network_v2`：把人类作为具有共同生物基础、通过群体和文化实现差异化满足的种群，唯一根节点下分物质稳态、繁衍照护、神经心理、社会协作、符号精神五个系统。企业和证券只允许在过程之后映射。第一条试点为“基本营养需求 → 蛋白质供给 → 动物蛋白 → 生猪及猪肉供给过程 → 饲料粮/水/土地/能源/生物条件/物流”。六条过程—资源关系目前都是待核验候选，资源数量为空且明确标记 `not_yet_observed`，不能解释为零。饲料粮来源登记与导入闸门见 [流程与契约](docs/HUMAN_NEED_RESOURCE_NETWORK.md)。查看 [流程与契约](docs/HUMAN_NEED_RESOURCE_NETWORK.md) 或运行：

```powershell
.\.venv\Scripts\python.exe scripts\build_human_need_network_report.py
```

输出为 `reports/human_need_resource_network.html`。默认事实快照不会纳入待核验依赖；显示候选必须显式使用 `include_candidates=True`。

### A 股产业网络

该网络现在标记为 `legacy_equity_first_experiment`，保留已有事实和上市/退市能力，供以后映射到需求—资源主干。第一版网络已经把企业生产组织与证券上市关系分离。5,884 个证券上市阶段中有 5,880 条匹配到巨潮 `orgId`，归并后形成 5,874 个企业节点、83 个行业节点和 5,206 条公司—行业边。默认正式时点网络只纳入 5,208 个 BaoStock 当前上市阶段；337 个历史退市阶段保留，339 个过期北交所候选默认排除。

```powershell
.\.venv\Scripts\python.exe scripts\fetch_a_share_industry_network.py
.\.venv\Scripts\python.exe scripts\enrich_a_share_issuer_identity.py `
  --profile-symbol 002714
.\.venv\Scripts\python.exe scripts\import_cninfo_annual_report_evidence.py `
  --symbol 002714 --org-id 9900022995
.\.venv\Scripts\python.exe scripts\review_activity_product_candidates.py `
  --mapping-id ACTIVITY_PRODUCT_e68171883dc3330a1a29 `
  --mapping-id ACTIVITY_PRODUCT_d1d128a1f0a5da814cf4 `
  --decision approved --reviewer project_user_authorized_review
.\.venv\Scripts\python.exe scripts\build_a_share_network_snapshot.py `
  --as-of 2026-08-17T10:30:00+08:00
```

上市和退市事件使用发生时间、可得时间和生效时间。退市不会删除企业历史，上市退市的节点数量、募资额、流通价值变化和重新配置敞口分别记录为结构事实或代理量。v2 已建立“生猪”产品词表，并经用户授权将 `producer`、`seller` 两条映射审核通过；经营范围中的饲料、屠宰、食品没有升级为事实。牧原股份 2025 年报的客户/供应商名称匿名，因此仍只保存集中度。首组具名关系来自华域汽车与上汽集团 2025 年报：主表保存两条仅覆盖 2025 报告期的双向供应观察，不能自动延续到 2026 年。上汽年报又反向确认华域法定名称、代码、控股标签和 58.32% 直接持股，但没有逐笔交易金额，所以只增加身份/集团关系佐证，不修改原交易事实。两条牧原活动观察与四条匿名集中度代理已进入 `stock_motion_event_v2` 合并流；具名关系和佐证尚未转换为传播规则或价格信号。详细边界见 [A 股产业网络模型](docs/A_SHARE_INDUSTRY_NETWORK.md)。

### 网络信息素信号覆盖层

网络对象（企业、上市阶段、行业、产品）现在都有稳定的信号槽位，便于后续显示颜色、光晕、脉冲和流向。信号事件记录来源、事件时间、可得时间、生效时间、强度和半衰期；独立核验证据单独关联，不重复增加浓度；传播还必须同时拥有明确关系边和传播规则。当前快照为 11842 个对象 × 6 个信号类型：牧原股份上市阶段 `lifecycle.change=+1`，公司对象 `production.activity=+1`。生产证据只确认“生猪的养殖与销售”这一活动存在，产量未披露；两个 `+1` 都只是显示编码，不代表收益、价值、概率或规模，且不会传播。运行方式见 [网络信息素信号模型](docs/NETWORK_SIGNAL_MODEL.md)。

### 股票运动模型与旧基线

项目新增了“社会生产网络 → 企业权益 → 市场价格”的股票运动模型。标准 OHLCV、已审核生产活动和集中度代理进入统一的 `stock_motion_event_v2` 内部事件流：

```powershell
.\.venv\Scripts\python.exe scripts\build_stock_motion_stream.py `
  --input data\raw\002714.SZ.csv `
  --output data\processed\motion\002714.SZ.motion.csv
```

生成牧原股份合并流：

```powershell
.\.venv\Scripts\python.exe scripts\build_combined_stock_motion_stream.py `
  --input data\raw\002714.SZ.csv `
  --output data\processed\motion\002714.SZ.motion.csv `
  --network-dir data\industry_network\a_share `
  --symbol 002714.SZ
```

内部流区分直接观察、历史派生量和假设性代理量，并保留来源记录、产品维度、事件时间和可用时间。OHLCV 本身不能证明生产改善、情绪变化或大资金净流入；匿名集中度也不能识别具体对手方。详细概念、字段和边界见 [股票运动模型](docs/STOCK_MOTION_MODEL.md)。

下述分类器仍是旧的行情特征基线，尚未改成只读取内部运动流。

默认模型使用 `HistGradientBoostingClassifier`，输入特征主要包括：

- 日收益率、滚动收益率
- 均线偏离
- 波动率
- 成交量变化
- RSI
- MACD
- 布林带位置

标签默认为：未来 `horizon` 个交易日收益率是否大于 `threshold`。

例如默认设置表示预测“未来 1 个交易日收盘价是否上涨”。

## 重要提醒

这个项目只用于研究和预演。股票市场只是世界模型的一个验证窗口，受政策、流动性、公司事件、情绪、宏观环境等多重因素影响，历史数据模型可能失效。实际使用前应进行严格的样本外测试、交易成本评估和风险控制。
