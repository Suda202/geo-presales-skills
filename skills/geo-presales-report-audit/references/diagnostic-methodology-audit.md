# 问题类型与诊断意图口径审计

## 单一配置源与结果层

评测集同一 Case 保存 `target_attributes`、Topic 和正式竞品。`target_attributes` 是采集前目标；采集后才能生成 `observed_associations`。报告或 JSON 若把目标属性直接当成已观察到的品牌认知，记录方法口径错误。

## 两个独立维度

不要再使用“通用问题 / 品牌问题”或“购买意图”分流。每个问题同时检查两个维度：

1. **问题类型**：只有 `visibility`、`sentiment`。按集合处理，允许只含一个，也允许同时包含两个。
2. **诊断意图**：描述该问题要诊断什么。

> **迁移说明**：当前六个诊断意图值（`discovery / competitor / validation / accuracy / sentiment / market_perception`）对应 Prompt Builder 的 `Intent: …` 默认 Tag 枚举。诊断意图后续将改为自定义 Tags，枚举将不再固定；届时本节的值列表须同步更新。

当前数据兼容 `discovery / competitor / validation / accuracy / sentiment / market_perception` 六个值；后续字段变为标签时允许自由命名和多选，不把旧六值继续当封闭枚举。

问题类型决定核心指标样本：

| 问题类型集合包含 | 进入结果 | 不代表 |
|---|---|---|
| `visibility` | Visibility、正文首次出现位置、声量、主要引用生态 | 情绪一定为中性 |
| `sentiment` | 目标品牌正/中/负及表达证据 | 不可同时进入 Visibility |

同一问题同时含 `visibility` 与 `sentiment` 时，分别进入两个模块的样本和分母；分别保存各模块的证据，不复制成两道问题，也不强迫二选一。

当前六个诊断意图仍可触发专项结果核对：`competitor` 核对比较结果，`validation` 核对属性关联，`accuracy` 核对事实准确性，`market_perception` 核对品类认知；这些结果与可见度、情绪的样本资格并不互斥。`discovery` 和 `sentiment` 只作为当前标签保留，不能用它们替代问题类型字段。

## 字段兼容与冲突

优先读取报告实际保存的问题类型字段；标量先规范成单元素集合，数组按集合去重。诊断意图同样同时兼容当前标量和未来标签数组。

- 遇到旧 `generic / brand / brand_related` 分类，不再据此决定是否计算情绪。
- 遇到 `purchase_intent / funnel_intent`，不得把它当作现行字段或分母依据。
- 遇到用 `diagnostic_intent` 反推问题类型的实现，记录配置或聚合错误。
- 遇到未知诊断标签，保留原值并核对其是否有明确结果契约；不因它不在旧六值中直接判错。
- 字段冲突时不得猜测，追溯题库版本、配置源和实际入选 ID。

## Attribute 诊断

Validation 必须：

1. 指向当前 Case 的具体 `attribute_id`；
2. 绑定同 Topic、共享 Attribute 且问题类型包含 `visibility` 的样本；
3. 分开回答“AI 是否知道此属性”和“AI 是否会在无品牌提示时主动推荐品牌”。

可输出：`strength`（知道且自然推荐）、`opportunity`（知道但不主动推荐）、`objection`（出现否定或错误关联）、`unknown`（证据不足）。这些状态必须由回答证据产生，不能从 Case 自述直接派生。

## 引用样本范围

主要引用生态只聚合问题类型包含 `visibility` 的回答，回答客户“哪些来源影响品牌进入候选”。其他问题的引用如有展示，必须独立标注样本范围。检查 citation 结果是否保存实际入选的 question/answer IDs；不要再要求 `primary_diagnostic_intent=discovery`。

## 竞品、情绪与准确性

- Competitor：诊断意图标签包含 `competitor` 时，逐题核对比较对象、共同条件、结论方向、是否明确胜者、理由是否支持。平衡叙述不自动等于平局；必须看最终比较判断。
- Sentiment：问题类型集合包含 `sentiment` 时，判断目标品牌的直接表达，按正/中/负三档；竞品赢不自动等于目标品牌负面。
- Accuracy：诊断意图标签包含 `accuracy` 时，并列保存官方真值、回答具体主张和差异。错误来源区分题面前提、模型生成、过时信息、实体混淆、解析/结构化错误和官方来源不足。

## 对账顺序

先按 Topic 对账问题明细总数，再分别统计 `visibility`、`sentiment` 以及两者交集；三项相加不能用来反推总题数。再按诊断意图标签统计样本分布，但不预设标签互斥或数量合计等于总题数。最后核对每个聚合模块的 `included_question_ids / included_answer_ids`。`0/N` 是有样本零结果，`0/0` 是无样本，必须展示为无数据。

## 跨 Skill 可见度范围校验

**校验点**：`formal_visibility_eligible = true` 在 Prompt Builder 中标记了 Discovery、Competitor、Category Awareness 三类。报告侧正式 Visibility 指标（品牌进入率、声量、平均提及排名、问题机会、主要引用生态）**只使用 Discovery**；Competitor 进 M02 竞品模块，Category Awareness 进 M08 品类认知模块。

审计时须核对：
- 正式 Visibility 分母不得包含 Competitor 或 Category Awareness 样本。
- M02 声量只使用 Discovery 范围内对竞品的提及，不包含 Competitor 题本身的提及。
- M08 结果来自后端正式 `market_perception_diagnostics`，不进入品牌 Visibility 聚合。

如报告 CSV 中出现 Visibility 指标引用了非 Discovery 样本，判为 **scope_violation**，输出原因和受影响字段路径。

**关于 `accuracy` 的问题类型**：后端问题类型只有 `visibility`、`sentiment`。含 `Intent: Accuracy` 的问题 `analysis_type = accuracy`，审计时若发现其 `question_type` 字段被写为 `accuracy` 而非 `visibility` 或 `sentiment`，判为类型枚举错误。当前售前 Accuracy 配额为 0，实际无样本；若未来引入，先更新本文件的枚举定义再生成。
