# 输出风险画像

| 风险 | 自检 |
|---|---|
| 静默少题或机械均分 | 校验各 Topic 实际配额、聚合配额与最终题数一致，并强制整批不超过 60；10–25/Topic 只告警，不为达标凑题。 |
| 仍依赖旧属性配置 | 只消费 Edgelight 型评测集 Case 原始业务字段；不生成 Attribute Pool 或 Attribute ID。 |
| Verification 太笼统 | 每 Topic 直接按需选择 3–5 条 Case 信息，逐项要求 Yes / No / Unknown 与依据。 |
| 竞品控制变量漂移 | 每 Topic 对每个适用竞品各生成一题，多条 Competitor 除竞品名称外保持完全同构。 |
| 售前情绪范围膨胀 | 每 Topic 只保留一条目标品牌 Evaluation；竞品情绪矩阵留给售后生词。 |
| Discovery 被诊断附加题挤压 | 每个 Topic 强制 Discovery 严格超过 50%；1/2/3 个适用竞品时至少为 5/6/7 条。 |
| Verification 污染正式可见度 | `analysis_type=visibility`，同时强制 `formal_visibility_eligible=false`。 |
| Accuracy 重复联网核验 | 只复制上游已核验的三字段并做确定性校验；禁止调用 `web-access` 或自行补值。 |
| 旧字段反客为主 | v8 用自由 `tags` 承接诊断、品牌范围和 Attribute；`analysis_type + formal_visibility_eligible` 独立分流，旧 `diagnosis_intent` 只读兼容。 |
| Topic / Attribute 再次混用 | Topic 只承载独立监测机会；跨 Topic 能力进入 `attribute_plan`，逐题用 Attribute Tag 关联。 |
| Tags 变相固定枚举 | v8 只规定 Builder 的默认 Intent、Brand Scope 与 Attribute 命名空间；允许其他自由 Tags。 |
| 自由 Tags 污染指标路由 | `analysis_type` 与 `formal_visibility_eligible` 由生成角色单独确定，不随自定义 Tags 改动。 |
| 品牌范围标签失真 | 从题面实际目标品牌或竞品提及反推 Branded / Non-Branded，并做确定性校验。 |
