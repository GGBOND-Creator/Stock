# 网络信息素信号覆盖层 v1

## 目的

“信息素”在本项目中是一个可计算的网络状态信号，而不是生物学信息素的事实断言。它为公司、上市阶段、行业、产品及未来的自然单元、资金池提供统一的展示接口：信号可以在对象上出现、随时间衰减，并在获得显式授权时沿网络关系传播。颜色、光晕、脉冲和流向只是显示配置。

该层独立于 `a_share_industry_network_v2`，因此不会破坏企业、上市阶段、行业和生命周期的主契约。

## 四层数据

| 层 | 文件 | 作用 |
| --- | --- | --- |
| 词表 | `data/network_signals/a_share/signal_types.csv` | 受控信号名称、单位和显示默认值；本身不产生事实 |
| 事件 | `data/network_signals/a_share/signal_events.csv` | 有来源的直接信号，含事件时间、可得时间、生效时间、强度和衰减 |
| 证据 | `data/network_signals/a_share/signal_event_evidence.csv` | 对信号事件的独立支持或交叉核验证据，不重复增加浓度 |
| 规则 | `data/network_signals/a_share/transmission_rules.csv` | 明确允许某类信号沿某类关系传播的规则 |

当前六个词表项是：`production.activity`、`supply.constraint`、`demand.change`、`capital.pressure`、`risk.warning`、`lifecycle.change`。当前有两条牧原股份直接信号：上市阶段的生命周期状态和公司的“生猪”生产活动存在状态；每条各有一条独立证据。证据用于提高可审计性，不产生第二份浓度。传播规则仍为空，避免把行业分类、成交量或情绪解释自动伪装成信号事实。

证据表将事实与显示编码分开：`raw_numeric_value` 保存来源数值，未披露时保持为空；`raw_unit` 必须说明单位或写明 `not_reported`；`raw_text` 保存原文；`initial_strength` 只属于信号事件的标准化显示强度。

## 时间和传播语义

计算 `as_of` 时只使用 `available_time <= as_of` 的事件、规则和关系边。直接信号从 `effective_time` 开始；已知但尚未生效的记录不进入浓度。指数衰减使用：

`strength = initial_strength × 0.5 ^ (elapsed_days / half_life_days)`

传播每跳再乘 `attenuation`，到达时间加上 `delay_days`。传播必须同时满足：

1. 存在明确的网络边；
2. 存在匹配 `signal_type` 与 `relation_type` 的规则；
3. 规则方向、有效期、最大跳数和可得时间均允许。

没有规则时只保留发射对象的直接信号。循环和多路径会对每个事件、每个对象保留绝对值最大的路径，防止循环无限放大。快照同时输出 `direct_contribution` 与 `propagated_contribution`，并将后者标为 `includes_propagated_signal`。

## A 股对象与边

脚本从 v2 网络生成对象注册表：企业、上市阶段、行业和已审核产品映射均可进入展示。上市阶段—企业、公司—行业、已识别公司关系和已审核公司—产品映射会转换为带时间字段的候选边；它们不会自行传播，必须有规则授权。匿名客户/供应商集中度不会生成公司关系边。

## 运行

初始化空白信号存储：

```powershell
.\.venv\Scripts\python.exe scripts\initialize_network_signal_store.py
```

导入一条抓取时点明确的上市状态观察：

```powershell
.\.venv\Scripts\python.exe scripts\import_lifecycle_signal_event.py `
  --event-id STATUS_3de54a4d161756b9047b
```

该导入器只接受 `availability_quality=observed_at_fetch_time` 的 `status_observed_active` 或 `status_observed_delisted`。信号生效时间取 `max(effective_time, available_time)`，防止晚到历史记录回填进过去；重复执行使用稳定 ID 合并。`+1` 表示抓取时观察为上市状态，`-1` 表示抓取时观察为退市状态，它们是二元显示编码，不是收益、价值或概率。

用深交所官方 A 股列表交叉核验：

```powershell
.\.venv\Scripts\python.exe scripts\verify_lifecycle_signal_with_szse.py `
  --signal-event-id SIGNAL_LIFECYCLE_01299fa3f5dcf534e7c5 `
  --symbol 002714 --expected-name 牧原股份
```

脚本归档官方原始 JSON 和请求元数据，要求代码、简称同时精确匹配，再写入 `signal_event_evidence.csv`。2026-08-18 官方清单记录为：代码 `002714`、简称“牧原股份”、板块“主板”、上市日期 `2014-01-28`。这确认证券出现在当日官方 A 股列表，不等同于确认每一时刻都可交易，也不改变信号强度。

导入首条已审核生产活动：

```powershell
.\.venv\Scripts\python.exe scripts\import_approved_production_signal.py `
  --mapping-id ACTIVITY_PRODUCT_e68171883dc3330a1a29
```

导入器只接受 `review_status=approved`、`role=producer` 且证据引文能在活动原文中逐字找到的映射。牧原股份证据原文为“生猪的养殖与销售”，人工审核时间为 `2026-08-17T02:37:23+00:00`。来源没有披露产量，因此证据记录 `raw_numeric_value=空`、`raw_unit=not_reported`；事件的 `initial_strength=1` 只表示“已审核生产活动存在”，不能解释为产能、产量、收入或价值大小。

生成时点快照：

```powershell
.\.venv\Scripts\python.exe scripts\build_network_signal_snapshot.py `
  --as-of 2026-08-18T12:00:00+08:00
```

输出 `data/processed/network_signal_snapshot/signal_state_snapshot.csv`。当前快照为 11,842 个网络对象 × 6 个信号类型，共 71,052 行；牧原股份上市阶段的 `lifecycle.change` 和公司对象的 `production.activity` 各为 `+1`，其余 71,050 行为零。传播规则为零，因此两条信号都不会扩散到其他对象。

## 最小流程闭环

1. 外部生命周期记录先进入 `lifecycle_events.csv`，保留来源和三时间语义。
2. 专用导入器只选择可得时间明确的抓取时点状态观察。
3. 状态被编码为上市阶段对象上的直接 `lifecycle.change` 信号。
4. 独立官方来源写入证据表，增强信号质量但不重复增加浓度。
5. 快照按 `as_of` 过滤并计算浓度；没有规则时传播贡献保持为零。
6. 后续界面读取词表颜色、显示通道和浓度，但必须同时显示证据质量。

## 数据驱动只读报告

2026-08-18 已将第一版检查器升级为项目内可复现报告。`scripts/build_network_signal_report.py` 直接读取时点快照、信号类型、事件、证据、传播规则和产业网络对象表，生成 `reports/network_signal_inspector.html` 与同名 `.meta.json`。审计文件记录全部输入文件的 SHA-256、快照时点、非零信号数、传播规则数和后续证据数；报告不写回信号存储。

当前报告显示上市阶段、企业和“生猪”产品三个对象及两条结构关系。上市阶段和企业分别显示生命周期、生产活动直接信号；产品保持中性，所有关系明确显示传播贡献 `0.0`，传播规则为 `0` 条。证据区可在两条直接信号间切换，展示事件来源、独立证据来源、质量、原始事实文本、原始数值、可得时间和显示编码。

生成器按快照 `as_of` 单独判断事件和证据是否已可得。生产活动证据在快照时已经可得，原始数值显示为“未披露”。深交所官方列表证据取得于 `2026-08-18T06:39:27.684639+00:00`，晚于快照 `2026-08-18T04:00:00+00:00`，因此报告明确标为“快照后取得，仅作后续核验”，不会把它回填为快照时已知信息。生命周期信号本身仍由更早可得的 BaoStock 抓取时状态观察支持。

报告已在 736 像素和 360 像素宽度、浅色和深色主题下核验；两种信号选择均可用，没有脚本错误、节点重叠或横向溢出。生产活动的 `initial_strength=1.0` 不能代替产量，生命周期的 `+1.0` 也不解释为收益、价值、概率或交易可得性。

## 事实、代理与假设边界

- 事件的强度和半衰期必须由来源、审核或明确代理方法支持；没有证据时保留空表。
- 规则的衰减率、延迟和跳数是模型设定，除非有单独研究证据，不应称作客观产业参数。
- `capital.pressure` 不识别具体控制人；成交额、大单或价格波动不能直接变成资金主体信号。
- 快照是研究状态和可视化输入，不是投资建议，也不是未来价格预测。
