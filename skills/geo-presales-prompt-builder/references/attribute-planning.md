# Attribute × Topic 属性规划（v8）

## 目标

生成 Prompt 前，先从 Case 原始字段派生买家会用于入围、比较和选型的 Attribute，再在每个 Topic 内划分 P1 / P2 / P3。优先级是 `Attribute × Topic` 关系；同一能力可在一个 Topic 为 P1，在另一个 Topic 为 P2 或不适用。Topic 是纵向主组织，Attribute 是横向战略认知，两者不互相替代。

`attribute_plan` 是 Builder 从现有 Case 字段自动派生的中间产物，不是销售或 Case 新增的手工输入。不使用旧 `target_attributes`，不生成 Attribute ID。逐题通过 `Attribute: {attribute}` Tag 回指这里的人类可读 Attribute 名，不再创建逐题属性 ID 或单独的 `attributes` 字段。

## 与 Topic 和 Tags 的边界

- 一个候选本身代表可长期独立监测的市场、Use Case、ICP 或战略机会，并能形成完整 Prompt 集合时，它应由上游作为 Topic，不再重复派生为同名 Attribute。
- 一个候选是能力、特征或评价标准，可在多个 Topic 中复用时，将它作为 Attribute；例如 `Night Vision` 可同时属于智能行车记录仪和家庭安防摄像头。
- 诊断意图、Branded / Non-Branded、购买阶段、地区等只是 Tags，不进入 `attribute_plan`。

## 候选属性抽取

只能从 `品类 / 垂直行业 / 目标客户 n / 痛点 n / 使用场景 n / 产品特性 n / 差异化优势 / 适用边界 / 补充内容` 抽取。先合并同义和强重叠的陈述，再评估：

1. 是否对当前 Topic 的买家有意义。
2. 是否会改变供应商入围、对比、偏好或选型。
3. Case 原字段是否足以支持，英文转写是否会扩张成新事实。
4. 它是品类级能力，还是仅对单款 SKU 成立的精确值。

同一能力被多个独立 Case 字段共同支持时（例如同时出现在痛点、产品特性和差异化优势中），它比只有单一字段来源的候选更可信，定级时优先考虑 P1；`source_field` 仍只记录最能代表决策含义的那个字段。`差异化优势` 回答"品牌为什么赢"，`适用边界` 回答"品牌不适合谁"，两者是 P1 判断和竞品比较维度的高优先来源：AI 回答按情境匹配给推荐，只有品类级泛化描述的候选难以形成入围条件。

## 分级标准

| 优先级 | 每 Topic 数量 | 决策含义 | 题型用途 |
|---|---:|---|---|
| P1 | 3–5 | 决定是否进入候选集合，缺失时可能直接淘汰 | 必须逐项进入 Verification；Discovery 必须覆盖；Competitor 优先使用 |
| P2 | 建议 5–10 | 明显影响横向比较、偏好和最终选择 | 主要进入 Discovery 和 Competitor，不进入首轮 Verification |
| P3 | 0–10 | 有购买参考价值，但通常不影响首轮入围 | 只在题量有余量且 P1/P2 已充分覆盖时进入 Discovery |
| Excluded / Accuracy | 不计入属性数 | 不改变购买决策，或属于需要独立真值的精确事实 | 删除，或用 `accuracy_only` 保留给独立 Accuracy 合同 |

P2 少于 5 个时不得从输入外补齐；保留现有属性并报告 Case 信息较薄。P3 不是低价值事实的收容所；纯目录归类、公司名称、无决策意义的官网文案必须进入 `excluded`。非具体型号 Topic 下的单款 SKU 电压、电流、功率、MTBF 等精确值进入 `accuracy_only`；其中有决策价值的安全保护、可靠性或选型范围可在不扩张原文的前提下单独抽取。

## v8 `attribute_plan` 合同

`config.attribute_plan` 对每个 Topic 恰好保留一项：

```json
{
  "topic_id": "topic_1",
  "priorities": {
    "P1": [
      {
        "attribute": "视觉规格选型",
        "source_field": "产品特性 1",
        "source_value": "Case 原字段完整值",
        "decision_reason": "像素间距、亮度和刷新率决定显示屏能否匹配场馆。",
        "verification_statement": "It supports LED display selection based on pixel pitch, brightness, refresh rate, color, and image quality."
      }
    ],
    "P2": [
      {
        "attribute": "项目总成本控制",
        "source_field": "痛点 1",
        "source_value": "Case 原字段完整值",
        "decision_reason": "会明显影响供应商比较和最终选择。"
      }
    ],
    "P3": []
  },
  "excluded": [
    {
      "candidate": "官网将 LED 显示屏列为独立产品类别",
      "source_field": "差异化优势",
      "source_value": "Case 原字段完整值",
      "reason": "仅说明官网信息架构，不改变入围或选型。",
      "route": "exclude"
    }
  ]
}
```

P1 比 P2/P3 多一个 `verification_statement`。当前 Topic 的 `validation_items` 与 `Attribute: …` Tags 都必须与 P1 按顺序一一对应：`source_field` 相同、`source_value` 相同、`statement` 等于 `verification_statement`。这个强绑定保证 Verification 验证的是先完成优先级判断的核心属性，而不是生题时临时挑选的事实。

## 题型分配检查

- Verification：只用 P1，3–5 项全覆盖；Attribute Tags 按 P1 顺序完整写入，不混入 P2/P3。
- Discovery：每个 P1 至少有一道问题测试并写入对应 Attribute Tag；其余单属性题优先覆盖 P2；P3 仅补余量。
- Competitor：使用双方都能合理比较的 P1 和高优先 P2；同 Topic 多个竞品保持维度、题面和 Attribute Tags 同构。
- Category Awareness：询问品类和评价方法，语义上优先回到 P1 选型标准，不在题面罗列属性。
- Evaluation：仍只使用 Topic 具体业务范围，不把属性列表塞入固定模板。
