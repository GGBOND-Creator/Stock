# 股票运动模型（生产网络映射版）

更新时间：2026-08-17（Asia/Shanghai）

## 1. 模型目的

本模型把股票市场看作社会生产网络在金融系统中的一个有噪声观察窗口。企业组织人员、设备、能源、知识、供应链和销售渠道进行生产；股票则是对企业剩余权益的可交易权利。股票不是生产线本身，但可以把一家企业或其中一个业务单元抽象为“生产单元”，把一只股票视为该企业生产网络与金融索取权在特定制度和市场环境下的具体实例。

模型的第一目标不是直接预测涨跌，而是先把外部世界转换为统一的内部运动数据流，使不同来源的数据都表达为：哪个对象、在什么时间、哪个状态通道发生了怎样的变化、这个变化何时可知、证据是事实还是代理量。

## 2. 当前认识的分层

### 可作为框架事实使用

- 股票代表企业剩余权益，而不是对一条物理生产线的直接所有权。
- 企业经营、未来现金分配、利率和风险会影响人们愿意支付的价格。
- 情绪、注意力、流动性、持仓集中、制度约束和大额交易会影响价格形成过程。
- 价格是相对于计价货币、利率、其他资产和市场状态形成的，不是脱离参照系的绝对价值。
- 仅凭 OHLCV 无法唯一分离生产价值、预期、情绪和大资金净流动。

### 当前研究假设

- 在生产能力、单位经济性、利率、风险和制度状态相近时，企业剩余权益可能存在一个缓慢移动的价值锚。
- 市场价格相对价值锚的偏离，可能部分由预期修正、情绪、流动性和资本压力解释。
- 所谓“脱去情绪与大资金影响后的固定区间”更适合表述为“条件价值带”：它依赖生产状态、资本结构、利率、风险和制度，可能移动、变宽或失效。
- 若能得到独立的生产、财务、预期、情绪和资金证据，模型可能把价格运动分解为更稳定的状态变化和短期扰动。

这些假设必须通过样本外数据检验，不能由概念定义直接证明。

## 3. 相对价值表达

企业权益的长期价值锚可以先用概念式表达：

```text
价值锚 V(t)
  = 对未来可分配现金流的折现期望
  + 经营选择权、网络位置、控制权等其他可识别价值
```

股票市场观察到的是相对于某个计价参照 `N(t)` 的价格：

```text
P(t) / N(t)
  = V(t) / N(t)
  × exp(情绪状态 + 流动性/资本压力 + 制度约束 + 未解释误差)
```

这只是状态分解框架，不表示各分量能从价格序列中被唯一求出。生产状态通过收入能力、成本、产能利用率和风险影响未来可分配现金流；新信息改变未来期望；情绪和资本压力影响市场价格围绕价值锚的运动。

## 4. 内部状态层

| 层 | 内部含义 | 典型通道 | 当前 OHLCV 能否直接提供 |
| --- | --- | --- | --- |
| L0 对象与参照 | 企业、股票、行业、市场、计价货币 | `entity.*`、`reference.*` | 只能提供部分标识 |
| L1 生产运动 | 产能、投入、产出、库存、单位经济性、供应链约束 | `production.*` | 不能 |
| L2 权益价值 | 可分配现金流、资本结构、折现率、价值锚 | `claim.*` | 不能 |
| L3 预期运动 | 对未来生产和分配的预期及其修正 | `expectation.*` | 不能唯一识别 |
| L4 市场意识与资本 | 情绪、注意力、持仓、订单与净资金流 | `sentiment.*`、`capital.*` | 成交量只能产生代理量 |
| L5 制度和环境约束 | 利率、政策、交易制度、停牌、涨跌停、自然约束 | `constraint.*` | 不能 |
| L6 市场观察 | 价格、成交量、收益、波动、相对位置 | `market.*` | 可以 |

第一版转换器只生成 L6 观察和明确标注的代理通道。它不会用价格上涨反推“生产改善”，也不会把成交量直接命名为“大资金流入”。

## 5. 内部运动数据流契约

内部流采用长表事件格式 `stock_motion_event_v2`。一条记录表示一个对象在一个事件时间上的一个通道值；市场行情、已审核生产活动和匿名集中度代理可以在同一流中共存。

机器可读契约位于 `data/contracts/stock_motion_event_v2.schema.json`。旧的 `stock_motion_daily_v1` 文件和契约保留作历史兼容参考。

| 字段 | 含义 |
| --- | --- |
| `schema_version` | 内部契约版本 |
| `event_id` | `对象|事件日期|通道|来源口径指纹` 组成的确定性标识 |
| `entity_id` | 股票或后续其他对象标识 |
| `source_schema` | 外部来源或上游内部表的契约版本 |
| `source_record_id` | 原始记录或审核映射的稳定标识 |
| `source_entity_id` | 上游企业、证券或其他来源对象标识 |
| `dimension_id` / `dimension_name` | 产品、匿名对手方组等维度；市场行情为空 |
| `event_time` | 变化在外部世界中发生的日期 |
| `available_time` | 该值最早可被当前模型使用的日期 |
| `availability_policy` | 当前日线统一为收盘后可用 |
| `channel` | 内部状态通道 |
| `value` / `unit` | 数值及单位 |
| `evidence_kind` | `observation`、`derived` 或 `proxy` |
| `method` | 转换方法，避免同名指标口径不明 |
| `source` / `market` | 来源和市场 |
| `adjustment` / `volume_unit` | 复权与成交量口径 |
| `quality_status` | 当前记录的数据质量状态 |

`event_time` 与 `available_time` 分开，是为了接入财报、政策、新闻等具有发布延迟的数据。任何训练样本只能使用 `available_time` 不晚于决策时点的事件；事件的可得策略不再强制都是收盘后。

## 6. OHLCV 第一版转换通道

### 直接观察

- `market.price.open/high/low/close`
- `market.activity.volume`

### 仅用当前及历史数据派生

- `market.motion.return_1d`
- `market.motion.log_return_1d`
- `market.motion.gap_return`
- `market.motion.intraday_return`
- `market.motion.range_ratio`
- `market.state.close_location`
- `market.activity.log_volume_change_1d`
- `market.activity.volume_ratio_20`
- `market.risk.volatility_20`
- `market.relative.price_zscore_60`

### 假设性代理量

- `proxy.directional_activity_pressure`：用涨跌方向与相对成交活跃度组合而成。它只能表示“方向与交易活跃度同时出现”的代理状态，不能解释为已观察到主力资金流。

### 产业网络映射通道

牧原股份 2025 年报和主营业务审核结果进入 `002714.SZ.motion.csv` 时，使用以下内部通道：

- `production.activity.product_role.producer`：已审核的“生猪—养殖/生产”原文映射，值为 1，属于观察事实；
- `production.activity.product_role.seller`：已审核的“生猪—销售”原文映射，值为 1，属于观察事实；
- `proxy.production.network.customer.top_five_share`、`supplier.top_five_share`：匿名前五大客户/供应商占比；
- `proxy.production.network.customer.related_party_share`、`supplier.related_party_share`：匿名披露中的关联方占比。

后四个通道的数值来自年报，但解释为产业依赖度代理，不代表具体上下游身份、实际资金流或价格方向。产品事件在人工审核完成后才可用；由于主营业务原文没有活动生效日期，其 `event_time` 使用来源观察时间而不是推测的生产起始日。年报事件以报告期末为 `event_time`，从本地首次归档时间起可用。

### OHLCV 仍未解决的潜在通道

- `production.capacity_state`
- `production.unit_economics_state`
- `claim.distributable_value_anchor`
- `expectation.revision_state`
- `sentiment.state`
- `capital.net_flow_state`
- `constraint.regime_state`

这些通道会写入审计元数据的 `unresolved_latent_channels`，提醒后续模型不要用行情数据伪造原因。

## 7. 转换流程

```text
外部来源
  → 原件与来源元数据
  → 标准 OHLCV（外部观察契约）
  → 股票运动流（内部语义契约）
  → 按决策时点截取可用状态
  → 特征/状态估计
  → 样本外验证
```

本地命令：

```powershell
.\.venv\Scripts\python.exe scripts\build_stock_motion_stream.py `
  --input data\raw\002714.SZ.csv `
  --output data\processed\motion\002714.SZ.motion.csv
```

将市场观察和产业网络证据合并到同一内部流：

```powershell
.\.venv\Scripts\python.exe scripts\build_combined_stock_motion_stream.py `
  --input data\raw\002714.SZ.csv `
  --output data\processed\motion\002714.SZ.motion.csv `
  --network-dir data\industry_network\a_share `
  --symbol 002714.SZ
```

若输入旁边存在同名 `.meta.json`，转换器会自动继承来源、市场、复权和成交量单位；否则缺失口径保留为 `unknown`。输出同时生成 `.meta.json`，记录文件指纹、通道方法、因果策略和未解决的潜在状态。

## 8. 验证顺序

1. 验证内部流能无损恢复原始 OHLCV 观察。
2. 验证修改未来数据不会改变过去已经形成的内部事件。
3. 为生产、财务、利率、行业和制度数据分别建立外部契约与内部通道映射。
4. 用独立证据估计价值锚，不允许只用价格自身定义价值后再证明价格会回归。
5. 检验“条件价值带”是否跨时间、跨公司和跨制度状态稳定。
6. 只有通过滚动样本外验证，才把内部状态用于预测实验。

## 9. 当前边界

- 当前实现是内部数据语言和行情转换层，不是已经完成的社会生产网络模型。
- 当前已接入牧原股份两条已审核主营业务角色映射和四条匿名集中度代理，但没有产量、单位经济性、可识别供应链、利率、新闻、持仓或订单流数据，因此不能估计生产价值和各类潜在原因。
- 现有涨跌分类器仍属于旧的行情特征基线。后续应改为只读取版本化的内部运动流；在完成适配前，两条链路必须明确区分。
- 所有结果用于研究，不构成投资建议。

## 10. 变更记录

| 日期 | 变更 |
| --- | --- |
| 2026-08-16 | 根据“金融是社会生产网络映射”的方向建立第一版股票运动模型、内部状态层和 `stock_motion_daily_v1` 数据流契约。 |
| 2026-08-17 | 升级为 `stock_motion_event_v2`，增加来源记录、企业/产品维度和非收盘后可得时间；将牧原股份已审核“生猪”活动与匿名年报集中度代理接入合并流。 |
