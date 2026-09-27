# A 股资金控制与运动概率表

本目录是 `capital_control_distribution_v1` 的首个空白注册表。它建立了数据语言和验证约束，但目前没有足以识别实际交易控制人的外部证据，因此不能生成真实主体概率。

文件用途：

- `controllers.csv`：自然人、法人或无法细分的主体类别；当前只有系统保留的 `CONTROLLER_UNKNOWN`。
- `capital_pools.csv`：基金、保险账户、企业自有资金、个人账户集合等资金池。
- `control_relations.csv`：资金池与主体之间的受益所有、投资决策、交易执行、托管或名义持有关系。
- `capital_positions.csv`：资金池在报告期末公开披露的持仓观察；它不是交易流水。
- `flow_events.csv`：独立观察到的买入、卖出、持仓变化、申赎或其他资金运动事件。
- `controller_probability_distribution.csv`：在当时可用证据条件下，每个运动事件由各主体或主体类别控制的概率；同一 `flow_event_id` 的概率必须合计为 1。

无法识别的概率质量必须分配给 `CONTROLLER_UNKNOWN`。托管行、券商席位、沪深港通名义持有人和中央结算机构不能仅凭通道身份写成受益所有人或投资决策人。
