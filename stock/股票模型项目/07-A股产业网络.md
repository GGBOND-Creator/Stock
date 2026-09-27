# A 股产业网络模型

更新时间：2026-08-18（Asia/Shanghai）

## 1. 目标

本模型以 A 股上市公司为生产网络的起始单位，记录企业与行业、供应商、客户、竞争者、替代者和资本市场之间的连接。第一版先建立“公司—行业”双层网络和上市生命周期；有独立证据后再增加公司之间的真实生产关系。

这里必须区分企业与证券：企业是生产组织，证券是企业连接资本市场的一段上市关系。退市终止或改变证券连接，但不会把企业及其历史生产关系从数据库中删除；上市增加一种可交易权益连接，也不等于企业在上市当天才开始生产。

## 2. 网络对象

| 对象 | 含义 | 文件 |
| --- | --- | --- |
| 企业节点 | 持久存在的生产组织注册表 | `companies.csv` |
| 上市阶段 | 企业与交易所之间的一段证券连接 | `listings.csv` |
| 行业节点 | 版本化行业分类 | `industries.csv` |
| 行业归属边 | 企业在某时点所属行业 | `industry_memberships.csv` |
| 企业关系边 | 供应、客户、竞争、替代等有证据关系 | `company_relations.csv` |
| 具名关系证据 | 交易原文、页码、金额、身份依据和分离的可得时间 | `named_counterparty_relation_evidence.csv` |
| 具名关系佐证 | 对手方文件中的身份或集团关系交叉证据；不升级交易事实 | `named_relation_corroborations.csv` |
| 经营活动证据 | 主营业务、经营范围及后续产品/服务解析 | `business_activities.csv` |
| 产品/服务词表 | 统一名称的产品与服务节点；节点本身不代表某公司实际生产 | `products.csv` |
| 活动—产品映射审核 | 从经营原文到产品、角色的候选及审核结果 | `activity_product_candidates.csv` |
| 对手方集中度 | 年报只匿名披露客户/供应商时保存的聚合敞口 | `counterparty_concentrations.csv` |
| 生命周期事件 | 上市、停牌、风险警示、退市、重新上市等 | `lifecycle_events.csv` |

当前优先使用巨潮资讯 `orgId` 构造持久 `company_id`。首轮 5,884 条证券记录中有 5,880 条匹配成功，归并为 5,870 个巨潮发行人节点；10 组历史代码/重新上市证券因此合并到同一企业。另有 4 条旧证券代码未匹配，继续使用临时身份。`orgId` 比证券代码稳定，但仍属于来源机构标识，后续可再与统一社会信用代码或交易所发行人标识交叉核验。

## 3. 时间语义

所有生命周期事件保留三种时间：

| 字段 | 含义 |
| --- | --- |
| `event_time` | 外部事件发生时间 |
| `available_time` | 本系统最早知道该事实的时间 |
| `effective_time` | 该事件正式改变网络状态的时间 |

例如，退市决定在 6 月 1 日公布、6 月 15 日生效：6 月 1 日后模型可以记录“已宣布、待生效”，但上市节点要到 6 月 15 日才从网络中退出。训练时只能使用 `available_time` 不晚于决策时点的数据。

BaoStock 当前接口给出了历史上市日和退市日，却没有给出这些历史记录当年的首次可得时间。因此第一批历史事件统一标记为 `historical_availability_unknown`：可用于构建当前状态，默认不进入历史市场影响回测。后续每日刷新中新出现的上市/退市事件会标记为 `first_observed_after_previous_refresh`，最早从本次抓取时间开始使用。

具名公司关系另行保留 `source_available_time`、`identity_available_time`、`reviewed_at` 和 `relation_available_time`。只有交易原文、独立身份依据和页面核验都已完成后，关系才可进入模型，`relation_available_time` 不得早于前三者。年报金额对应报告期观察，不证明每天连续交易，也不得自动延续到后续年份。

后续佐证也有独立 `reviewed_at` 和 `available_time`，不能回填到关系最初可得时间。佐证必须写明它确认的范围；身份、持股或控股关系不能冒充采购/销售金额与方向的第二来源。

## 4. 生命周期状态

```text
unknown
  → pre_listing
  → active
  ↔ suspended
  → delisting_risk
  → delisting_announced
  → delisted
  → relisted / active
```

旧快照只能产生 `observed_active_candidate` 或 `observed_delisted_candidate`，不能自动升级成权威状态。默认网络只纳入：

- `active`
- `suspended`
- `delisting_risk`
- `delisting_announced`

`delisted` 从当前资本市场节点中退出，但企业注册表和历史边仍保留。使用 `--include-unverified` 才会把旧快照候选节点纳入实验快照。

## 5. 上市与退市的市场影响通道

### 可核算的结构变化

- `market.structure.listed_security_count_change`：上市 `+1`，退市 `-1`。
- `market.structure.pending_listing_count_change`：已公布但尚未生效的上市数量变化。
- `market.structure.pending_delisting_count_change`：已公布但尚未生效的退市数量变化。
- `market.structure.primary_fundraising_amount`：若有独立募资额数据，记录一级市场资金转移。
- `market.structure.free_float_value_entry_exit`：若有生效时流通价值，记录可交易权益供给进入或退出。

### 明确标为代理的影响

- `proxy.market.forced_reallocation_exposure`：退市前流通价值的绝对量，只表示可能需要重新配置的风险敞口，不等同于实际流向其他股票的资金。

### 暂不直接计算的机制假设

- 新股募资和新增流通权益可能形成资金吸收压力；
- 退市可能引发同产业风险重估、被动组合移除和资金重新分配；
- 影响强度可能沿供应链、行业归属、指数成分和共同持仓网络传播。

这些是待检验机制。没有资金流、指数调整、基金持仓和真实产业边时，不能从“发生退市”直接推断其他股票必然上涨或下跌。

## 6. 第一版真实数据状态

2026-08-16 通过免费 BaoStock 接口抓取并本地归档：

| 内容 | 数量 | 状态 |
| --- | ---: | --- |
| 证券上市阶段 | 5,884 | 5,545 条 BaoStock 沪深记录，加 339 条旧 AkShare 北交所候选 |
| 企业发行人节点 | 5,874 | 5,870 个巨潮 `orgId` 节点，4 个临时证券代码节点 |
| 当前正式网络上市节点 | 5,208 | BaoStock 状态映射，需继续交叉核验 |
| 历史退市节点 | 337 | 保留在注册表，当前网络不纳入 |
| 北交所候选节点 | 339 | 来自 2026-07-20 旧快照，默认不纳入正式网络 |
| 行业节点 | 83 | 证监会行业分类 |
| 公司—行业边 | 5,206 | BaoStock 更新日为 2026-08-10 |
| 缺行业的正式上市节点 | 2 | 保留 `unknown`，不猜测 |
| 公司—公司生产关系边 | 2 | 华域汽车与上汽集团 2025 年双向交易观察；均有报告期边界 |
| 具名关系证据 | 2 | 交易原文、页面、金额及独立身份年报均已视觉核验 |
| 具名关系佐证 | 2 | 上汽集团年报确认华域名称、代码、控股标签和 58.32% 直接持股；不确认交易金额 |
| 经营活动原文证据 | 2 | 牧原股份主营业务和经营范围，尚未自动解析产品关系 |
| 产品词表节点 | 1 | “生猪”；词表定义不等于公司活动事实 |
| 已审核活动—产品映射 | 2 | “生猪”的养殖/生产、销售角色，均为 `approved` |
| 客户/供应商集中度 | 2 | 牧原股份 2025 年报前五大客户、供应商聚合披露 |

原始抓取归档：`data/external/a_share_industry_network/baostock/20260816T135051Z/`。

巨潮身份与公司概况归档：`data/external/a_share_industry_network/cninfo/20260816T140638Z/`。

牧原股份 2025 年报归档：`data/external/a_share_industry_network/cninfo_reports/20260817T021821Z/`。公告编号 `1225042507`，PDF SHA-256 为 `aa44a1f4244a6efbc6e54e7dbd4307235d39117bb4ff4d9590f386b02b0d9a04`。

年报第 30–31 页经文本抽取和页面渲染交叉核验：前五名客户合计销售额 `11,937,999,760.19` 元，占年度销售总额 `8.28%`；前五名供应商合计采购额 `20,149,948,693.01` 元，占年度采购总额 `19.48%`。名称仅为“第一名”至“第五名”，无法确认法律实体，因此只生成两条集中度记录，不生成公司关系边。官方公告时间为 `2026-03-28T00:00:00+08:00`；为防止回测泄漏，本地数据默认从首次归档时间 `2026-08-17T02:18:21+00:00` 起可用。

2026-08-18 增加具名关系准入审计。审计只查看指定 `as_of` 时已经可得的集中度记录，并明确区分两种拒绝：`anonymous_aggregate_only` 表示来源未披露名称；`aggregate_table_has_no_resolved_counterparty_identity` 表示即使来源称已披露名称，集中度表本身仍没有可核验的目标公司身份。两种情况都不会写入 `company_relations.csv`。当前客户、供应商两条记录均因匿名汇总被拒绝，合格关系和新建关系都是 0。

同日完成第一组具名关系试点。华域汽车 2025 年报第 4 页把“上汽集团”定义为“上海汽车集团股份有限公司”；第 178 页披露华域汽车向上汽集团采购商品及材料 `153,169,367.40` 元，第 179 页披露华域汽车向上汽集团销售商品 `5,438,818,642.01` 元。上汽集团 2025 年报第 1 页独立确认公司代码 `600104`、简称“上汽集团”和法定名称。四页均完成文本与页面布局核验。

因此主表新增两条 `supplies` 边：上汽集团到华域汽车的商品及材料供应观察，以及华域汽车到上汽集团的商品供应观察。两条边的 `valid_from=2025-01-01`、`valid_to=2026-01-01`，其中 `valid_to` 为报告期结束日次日的排他边界；它们不是 2026 年仍持续交易的声明。关系在本地完成来源、身份和视觉审核后，即 `2026-08-18T07:28:24+00:00` 才可用于模型。按 `2026-08-18T16:00:00+08:00` 重建的“当前有效关系”快照仍为 0，历史观察保留在主表和证据侧车中。

归档目录：`data/external/a_share_industry_network/cninfo_named_relations/20260818T072351Z_600741_1225052214_600104_1225071780/`。华域汽车年报公告编号 `1225052214`、SHA-256 `19d879f380cc042f4f5d91cb952c939f95b4e953366e8045da1e3a58760065f4`；上汽集团年报公告编号 `1225071780`、SHA-256 `aca3b701a1d6c2d59c8063801c579c0b1a589fd7d183e13146e4790cce3d0874`。

对手方年报反向核验显示：上汽集团年报第 17 页将华域汽车系统股份有限公司（`600741`）列为“下属控股子公司”，第 170 页企业集团构成表披露直接持股 `58.32%`。两页经文本与渲染页面核验后生成 2 条佐证记录，从 `2026-08-18T07:55:10+00:00` 起可用。上汽年报没有逐笔列示与华域对应的采购、销售金额，因此该佐证只确认身份和集团关系，不能交叉确认原两条供应观察的金额、方向、连续性或重要性。结果见 `reports/named_relation_crosscheck.md`。

内部网络：`data/industry_network/a_share/`。

正式时点快照：`data/processed/industry_network_snapshot/`。

含旧候选节点的实验快照：`data/processed/industry_network_snapshot_with_candidates/`。

## 7. 运行方式

抓取并更新网络：

```powershell
.\.venv\Scripts\python.exe scripts\fetch_a_share_industry_network.py
```

从已归档原始文件重建，不联网：

```powershell
.\.venv\Scripts\python.exe scripts\fetch_a_share_industry_network.py `
  --archive-dir data\external\a_share_industry_network\baostock\20260816T135051Z
```

抓取牧原股份最新完整年报并导入产品候选、客户/供应商集中度：

```powershell
.\.venv\Scripts\python.exe scripts\import_cninfo_annual_report_evidence.py `
  --symbol 002714 --org-id 9900022995
```

从本次归档离线复建：

```powershell
.\.venv\Scripts\python.exe scripts\import_cninfo_annual_report_evidence.py `
  --archive-dir data\external\a_share_industry_network\cninfo_reports\20260817T021821Z `
  --announcement-id 1225042507
```

按知识时点生成网络：

```powershell
.\.venv\Scripts\python.exe scripts\build_a_share_network_snapshot.py `
  --as-of 2026-08-16T22:00:00+08:00
```

审计当前客户/供应商披露是否具备公司关系建边条件：

```powershell
.\.venv\Scripts\python.exe scripts\audit_counterparty_relation_eligibility.py `
  --as-of 2026-08-18T16:00:00+08:00
```

输出为 `reports/counterparty_relation_eligibility.csv`、同名 `.meta.json` 和 Markdown 摘要。该命令是只读审计，不修改产业网络主表。

从本次具名关系归档离线复建：

```powershell
.\.venv\Scripts\python.exe scripts\import_named_counterparty_relations.py `
  --archive-dir data\external\a_share_industry_network\cninfo_named_relations\20260818T072351Z_600741_1225052214_600104_1225071780
```

用对手方年报反向核验身份与集团关系：

```powershell
.\.venv\Scripts\python.exe scripts\crosscheck_named_counterparty_relations.py `
  --reviewed-at 2026-08-18T07:55:10Z
```

机器契约：`data/contracts/a_share_industry_network_v2.schema.json`。具名关系证据与佐证侧车分别由 `data/contracts/named_counterparty_relation_evidence_v1.schema.json`、`data/contracts/named_relation_corroboration_v1.schema.json` 约束。

## 8. 当前边界与下一步

- 行业边仍只是分类关系；当前真实公司关系仅有华域汽车与上汽集团这一组 2025 年交易观察。
- BaoStock 当前基础表未覆盖北交所；旧 AkShare 北交所名单仅作候选，不能当作 2026-08-16 当前事实。
- 绝大多数企业已切换为巨潮 `orgId`；`689009.SH`、`810014.BJ`、`810013.BJ`、`810011.BJ` 仍未匹配。
- 每日增量刷新已经保留生命周期历史，并能识别本系统两次刷新之间首次出现的上市/退市；行业分类变更的完整双时态版本链仍需增强。
- 牧原股份主营业务原文已映射为“生猪”的 `producer`、`seller` 两条记录；用户于 `2026-08-17T02:37:23+00:00` 指示按推荐复核，两条均更新为 `approved`。经营范围中的饲料、屠宰、食品等许可内容没有升级为实际生产事实。
- 牧原股份 2025 年报的前五大客户和供应商均匿名，当前只能用于集中度/依赖度代理，不能用于识别具体上下游公司。
- 具名关系准入门已把当前两条集中度记录判定为 `anonymous_aggregate_only`；只有披露原文中的法定名称、独立公司身份依据和经过审核的可得时间同时存在时，才进入后续关系审核。
- 第一组具名关系证明了建边流程可运行，但关联交易金额不等于对手方依赖度、利润贡献、未来订单或股票价值信号；没有后续报告时也不能外推到 2026 年。
- 对手方年报已确认身份、控股标签和持股比例，但没有给出可与华域披露逐笔对应的交易表；关系金额目前仍只有华域年报这一项交易来源。
- 两条已审核活动和四条匿名集中度代理已转换到 `stock_motion_event_v2` 内部流。下一步接入确实披露法定名称或能由独立证据确认的对手方；只有身份、来源和时间戳可信时才建立公司关系。
- 当前项目建设顺序已明确为“先补强 A 股产业网，再建立其下位自然模型”。自然模型从已审核产品/经营活动向下连接资源、能源、水、土地、气候、生物条件和物流地理约束，不再优先扩展脱离产业用途的全球资源种子表。
- “下位”是数据库组织关系，不是现实因果方向。自然约束可以先于并影响产业生产；任何具体影响仍需独立数据和时间安全的验证。

## 9. 变更记录

| 日期 | 变更 |
| --- | --- |
| 2026-08-16 | 建立 A 股产业网络、公司/证券分离、生命周期状态机、上市退市市场影响流和首批 BaoStock 公司—行业网络。 |
| 2026-08-16 | 接入巨潮 `orgId` 发行人身份，完成 5,880 条上市记录映射；以牧原股份主营业务和经营范围作为首批生产活动原文证据。 |
| 2026-08-17 | 升级为 v2：建立“生猪”产品词表和两条待审核角色映射；归档并核验牧原股份 2025 年报，保存客户/供应商集中度，因对手方匿名保持公司关系边为 0。 |
| 2026-08-17 | 用户授权复核“生猪”的生产、销售两条映射并更新为 `approved`；审核结果可重复导入且不会被后续年报重建覆盖。 |
| 2026-08-17 | 确定后续路线：产业网络作为建模入口，从已审核产业活动向下建立产业锚定的自然依赖模型。 |
| 2026-08-18 | 增加客户/供应商关系准入审计；当前两条匿名汇总均被拒绝，合格关系和新建关系为 0，产业网络主表未改动。 |
| 2026-08-18 | 归档并视觉核验华域汽车、上汽集团 2025 年报；建立具名关系证据契约和两条仅覆盖 2025 报告期的双向供应观察，离线重建保持幂等。 |
| 2026-08-18 | 用上汽集团年报第 17、170 页反向核验华域法定名称、代码、控股标签和 58.32% 直接持股；新增两条范围受限的佐证，不修改供应关系事实。 |
