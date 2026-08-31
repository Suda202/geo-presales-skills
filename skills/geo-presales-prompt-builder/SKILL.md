---
name: geo-presales-prompt-builder
description: Use when generating, rewriting, auditing, or validating an English AI-search Prompt bank from an overseas GEO evaluation Case, including Attribute-by-Topic planning and free Tags for diagnostic intent, Branded or Non-Branded scope, Attributes, and custom analysis. Do not use it to create Topics, select competitors, crawl answers, calculate metrics, or write report conclusions.
metadata:
  author: Overseas GEO Project
  version: "4.5.0"
---

# GEO Presales Prompt Builder

## 目标

直接读取评测集 Case 的业务字段，生成 `overseas-geo-question-bank/v8` 英文监测 Prompt。Topic 是 Prompt 集合的主组织单元；生题前必须派生独立的 `Attribute × Topic` P1/P2/P3 规划，再把每题实际分析的 Attribute 写为自由 Tags。诊断意图、Branded / Non-Branded 品牌范围与 Attribute 统一进入逐题 `tags`，不再使用固定 `diagnosis_intent` 字段。不得要求 Case 或销售另填 `target_attributes`，不生成 Attribute ID 或单独的逐题 `attributes` 字段。

Edgelight 表中的原始 Case 字段就是评测集字段，也是 Builder 的直接输入。不要把“评测集字段”误解为需要避开的下游字段，也不要另造 `target_audiences / pain_points / use_cases` 等平行输入合同。

## 开始前读取

1. 读取 [属性规划](references/attribute-planning.md)。
2. 读取 [生成方法](references/generation-method.md)。
3. 读取 [v8 产物契约](references/presales-contract.md)。
4. 质检时读取 [质量门](references/quality-gates.md)。
5. 需要正反例时读取 [Edgelight 示例](references/examples.md)。

## 唯一输入合同

从目标评测集 Case 读取以下中文字段；编号字段支持 `1…n`：

- `公司名`、`业务 / 产品名称`、`品牌名称`、`业务模式`、`品类`、`垂直行业`
- `目标客户 1…n`、`痛点 1…n`、`使用场景 1…n`、`产品特性 1…n`
- `差异化优势`、`适用边界`
- `主题 1…n（宽泛/细分）`：只接受 1–3 个已确认 Topic；括号标签是输入提示，但 v8 不输出 `topic_type`
- `官方域名`
- 恰好三组 `竞品 n` 与 `竞品 n 官网域名`
- `补充内容`，字段必须保留但允许为空；非空时可包括 Topic 局部竞品边界，例如“竞品 1 仅用于主题 1，竞品 2–3 仅用于主题 2”

Accuracy 默认配额为 0，不读取或要求上游事实包。不得从旧评测集复制 `target_attributes`，不得新增 `attribute_pool / attribute_id / priority_attribute_ids`。`attribute_plan` 只能由 Builder 从当前 Case 字段派生。缺少品牌、品类、至少一个 Topic、官方域名、三组竞品名称及官网域名，或任一 Topic 缺少足以支持 3–5 个 P1 属性的业务字段时，停止并列出缺项。

## Topic、Attribute 与 Tags

- Topic 回答“这批 Prompts 属于哪个长期独立监测的市场、场景或战略机会”，每题只回指一个 `topic_id`。
- Attribute 回答“这题在测试 AI 如何认识品牌的哪项能力、特征或评价标准”。同名 Attribute 可跨 Topic 复用，但在每个 Topic 内可有不同优先级。
- Tags 是统一的自由字符串数组。默认使用 `Intent: …`、`Brand Scope: …`、`Attribute: …` 三个命名空间；可以增加阶段、区域或项目自定义 Tag。Tags 不决定 `analysis_type` 或 `formal_visibility_eligible`。分号 `;` 是 CSV 的 Tag 分隔符，不得出现在单个 Tag 内部。

## 执行流程

1. 归一化中英文名称、品类、业务边界、1–3 个 Topic 和三组正式竞品；只把输入中的“宽泛/细分”当作理解提示，不保存为字段。读取补充内容中的 Topic 局部竞品边界，为每个正式竞品写入适用的 `topic_ids`；未提供局部边界时，三者默认适用于全部 Topic。不得把 Case 中可跨 Topic 的能力重新升级为 Topic。
2. 先抽取候选属性，再按 `Attribute × Topic` 完成 `attribute_plan`：每 Topic 有 3–5 个 P1、建议 5–10 个 P2、0–10 个 P3，以及可为空的 `excluded`。同一属性在不同 Topic 可有不同优先级，同一 Case 字段也可跨 Topic 复用。P3 仍必须有购买参考价值；纯目录事实进入 `exclude`，需要独立真值的单款 SKU 精确数值进入 `accuracy_only`。
3. 按各 Topic 的 Attribute 信息量规划实际题量，不设置统一的每 Topic 默认配额。每个适用竞品保留一条 Competitor；Verification、目标品牌 Evaluation 与 Category Awareness 各保留一条；Accuracy 保持 0。售前不生成竞品 Evaluation，竞品情绪矩阵留给售后生词。Discovery 必须是每个 Topic 的严格多数，即 `Discovery > 该 Topic 全部其他题型之和`，不能用其他 Topic 的 Discovery 抵消。Discovery 必须覆盖全部 P1，再为能形成独立购买问题的 P2 增题，P3 只在仍有明显增量价值时使用。每 Topic 10–25 题只作为常见规划区间，不是硬门；不同 Topic 可以有不同题量，信息不足以支撑 Discovery 严格多数时停止并报告 Case 过薄，不得用伪重复凑题。整批不得超过 60 题；超过时不得削减到 Discovery 失去多数，应减少 Topic、缩小竞品适用范围或重新确认诊断范围，同时保存并校验实际 Topic 配额，失败不得静默少题。
4. 按生成方法编写自然英文根问题及等义中文。Discovery 和 Category Awareness 不出现任何具体品牌；Competitor、Verification、Accuracy、Evaluation 遵守各自品牌边界。按题面实际品牌提及写入唯一品牌范围 Tag：出现目标品牌或正式竞品为 `Brand Scope: Branded`，否则为 `Brand Scope: Non-Branded`。逐题守住四条写作规则：意图与格式匹配（Discovery 含候选触发名词，Competitor 具备场景、双具名品牌和明确推荐要求，Verification 逐项判断，Evaluation 明确评价任务）、不引导答案、缩写和跨品类歧义在题面内消解、买家语境只来自 Case 字段。Case 字段提供多个既有品类称呼时，基线候选题可按称呼各留一题，称呼变体不得自造。
5. Discovery 必须覆盖当前 Topic 全部 P1，其余单属性题优先覆盖 P2；只有 P1/P2 已充分覆盖时才使用 P3。每题把实际测试的属性写为一个或多个 `Attribute: {attribute}` Tag；无独立属性条件的品类基线题允许不写 Attribute Tag。Competitor 优先使用双方都能合理比较的 P1 和高优先 P2，只覆盖当前 Topic 的适用竞品，每个适用竞品恰好一题。当前 Topic 有两条以上 Competitor 题时，除竞品名称外，英文问题的字符、条件、任务、比较维度和 Attribute Tags 完全同构。
6. 将 Verification 写成一条批量验证题，当前 Topic 的 P1 必须按 `attribute_plan` 顺序全部进入 `validation_items`，并按同一顺序写为 Attribute Tags；其 `source_field / source_value / statement` 分别等于 P1 的溯源字段、原值和 `verification_statement`。固定要求逐项返回 `Yes / No / Unknown + 判断依据`；不生成 `attribute_id / priority_attribute_ids / paired_discovery_ids`。
7. 不生成 Accuracy 问题，也不要求 `fact_value / official_source_url / fact_checked_at`。如用户明确要求 Accuracy，停止默认流程并先确认独立的事实核验输入与产物合同，不得临时从 Case 或模型记忆补真值。
8. 使用固定 Evaluation 与品类优先 Category Awareness 模板，不自由改写任务结构。每个 Topic 只为目标品牌生成一条 Evaluation，不生成竞品 Evaluation；竞品情绪矩阵属于售后生词范围。Evaluation 只把 Topic 当作语义约束，将其转写为客户可理解的具体业务范围或场景。英文 Prompt 正文（JSON `user_question / monitoring_prompt`、CSV `query`）不得出现独立单词 `topic`；不限制中文翻译、CSV `topic` 列或其他元数据。
9. 为每题写入一个默认诊断 Tag：`Intent: Discovery / Competitor / Verification / Accuracy / Evaluation / Category Awareness`。该集合是 Builder 的常用生成角色，不代表固定配额，也不是 Tags 字段的全局枚举；允许同时增加其他自由 Tags。完成独立二遍语义 review，先确认 Topic 路由、属性分级与 Tags，再检查题面和翻译。保存 v8 JSON 后运行 validator 与回归测试。

## 分析与指标边界

| 默认诊断 Tag | analysis_type | formal_visibility_eligible |
|---|---|---|
| `Intent: Discovery` | `visibility` | `true` |
| `Intent: Competitor` | `visibility` | `true` |
| `Intent: Verification` | `visibility` | `false` |
| `Intent: Accuracy` | `accuracy` | `false` |
| `Intent: Evaluation` | `sentiment` | `false` |
| `Intent: Category Awareness` | `visibility` | `true` |

把 `analysis_type` 用于分析模块分流，把 `formal_visibility_eligible` 用于正式可见度题集资格。两者由 Prompt 生成角色确定，不从可自由修改的 Tags 自动推导；增删自定义 Tag 不得改变路由。Verification 虽进入 visibility 分析模块，但不得进入正式 Visibility、声量、排名、Share of Voice 或聚合引用指标的分子与分母。旧 `metric_scopes` 只可由兼容适配器生成，不是 v8 核心字段，也不得覆盖上述两个字段。

不生成或保留 `topic_type`、`question_type`、`funnel_intent`、`decision_stage`。旧 `overseas-geo-question-bank/v5` 仅允许只读验证或迁移，不得作为新题库默认输出。

## 输出与验证

- 输出按 Attribute 信息量规划的实际 Prompt 数，不要求 Topic 等量，整批不得超过 60；同时输出 `attribute_plan`、实际 Topic 配额、Case 字段覆盖、按 Topic 的竞品覆盖、目标品牌 Evaluation 覆盖、Tags 汇总和失败/重写原因。每 Topic 10–25 只作软参考，低于或高于该区间时说明原因，不为进入区间而补写低价值题。
- 每题包含 `question_id / topic_id / tags / analysis_type / formal_visibility_eligible / intent_key / user_question / zh_translation / monitoring_prompt / quality_checks`；不包含 `diagnosis_intent` 或单独的 `attributes`。
- Verification 额外包含 3–5 个 `validation_items`，每项直接回指 Case 的 `source_field / source_value`；默认题库不包含 Accuracy 题或事实包字段。
- CSV 固定字段顺序为 `query,question_zh,topic,tags,question_types,purchase_intent,persona_name,scene_name`。`tags` 用 `; ` 连接同一题的多个 Tag；`question_types` 按产物契约填写。`purchase_intent / persona_name / scene_name` 没有可靠来源时留空，不臆造。

```bash
python3 scripts/validate_question_bank.py /absolute/path/question-bank.json
python3 -m unittest discover -s evals -p 'test_*.py'
```

新题库默认生成 v8；validator 仍可只读旧 v7/v6/v5。不创建 Topic，不选择或补齐竞品，不重新核验官网事实，不采集回答，不生成 `observed_associations`，不计算任何诊断指标，不直接写售前报告。
