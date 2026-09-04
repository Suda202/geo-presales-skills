---
name: geo-presales-prompt-builder
description: Use when generating, rewriting, auditing, or validating an English AI-search Prompt bank from an overseas GEO evaluation Case, including Attribute-by-Topic planning and free Tags for diagnostic intent, Branded or Non-Branded scope, Attributes, and custom analysis. Do not use it to create Topics, select competitors, crawl answers, calculate metrics, or write report conclusions.
metadata:
  author: Overseas GEO Project
  version: "4.7.0"
---

# GEO Presales Prompt Builder

## 目标

直接读取系统接口传入的评测 Case 业务字段，生成 `overseas-geo-question-bank/v8` 英文监测 Prompt。Topic 是 Prompt 集合的主组织单元；生题前必须派生独立的 `Attribute × Topic` P1/P2/P3 规划，再把每题实际分析的 Attribute 写为自由 Tags。P1/P2/P3 是 Attribute 在当前 Topic 下的优先级，不是 Attribute 类型或 Prompt 优先级。诊断意图、Branded / Non-Branded 品牌范围与 Attribute 统一进入逐题 `tags`，不再使用固定 `diagnosis_intent` 字段。不得要求 Case 或销售另填 `target_attributes`，不生成 Attribute ID 或单独的逐题 `attributes` 字段。

接口中的原始 Case 业务字段就是 Builder 的直接输入。不要另造 `target_audiences / pain_points / use_cases` 等平行输入合同。

## 开始前读取

1. 读取 [售前与售后共用的监测问题生成原则](../shared/prompt-generation-principles.md)。
2. 读取 [属性规划](references/attribute-planning.md)。
3. 读取 [生成方法](references/generation-method.md)。
4. 读取 [v8 产物契约](references/presales-contract.md)。
5. 质检时读取 [质量门](references/quality-gates.md)。
6. 需要正反例时读取 [Edgelight 示例](references/examples.md)。
7. 读取 [跨 skill 规范映射](../shared/canonical-intent-mapping.md)；意图 Tag、问题类型与字段名以本文件为准。

## 唯一输入合同

从系统接口提交的目标评测 Case 读取以下中文业务字段；编号字段支持 `1…n`，合并字段也按相同语义解析：

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
- Tags 是 JSON 内部的统一自由字符串数组。默认使用 `Intent: …`、`Brand Scope: …`、`Attribute: …` 三个命名空间；可以增加阶段、区域或项目自定义 Tag。Tags 不决定 `analysis_type` 或 `formal_visibility_eligible`。JSON 保留完整 Tags；上传 CSV 也带 `tags` 列，但它只用于上传适配，允许留空，且单元格必须短于 200 字符；若填写，使用英文逗号、中文逗号或换行分隔的简短标签，不把完整 Attribute 列表塞进 CSV。品牌范围、Attribute 与其他自由 Tags 仍保留在 JSON 中。

## 执行流程

1. 归一化中英文名称、品类、业务边界、1–3 个 Topic 和三组正式竞品；只把输入中的“宽泛/细分”当作理解提示，不保存为字段。读取补充内容中的 Topic 局部竞品边界，为每个正式竞品写入适用的 `topic_ids`；未提供局部边界时，三者默认适用于全部 Topic。不得把 Case 中可跨 Topic 的能力重新升级为 Topic。
2. 先抽取候选属性，再按 `Attribute × Topic` 完成 `attribute_plan`：每 Topic 有 3–5 个 P1、建议 5–10 个 P2、0–10 个 P3，以及可为空的 `excluded`。这是属性优先级分档，不是三种属性类型。生成前只能依据客户决策影响和 Case 证据是否充分来分级，不得虚构尚未采集的“当前 AI 认知差距”；采集后的差距与可改变性由售后分析使用。同一属性在不同 Topic 可有不同优先级，同一 Case 字段也可跨 Topic 复用。P3 仍必须有购买参考价值；纯目录事实进入 `exclude`，需要独立真值的单款 SKU 精确数值进入 `accuracy_only`。
3. 根据当前 Topic 适用竞品数 `n`（1–3）使用固定配额：Discovery `23 - 2n`、Competitor `n`、Verification `0`、Accuracy `0`、Evaluation `1 + n`、Category Awareness `1`，每 Topic 合计恰好 25 题。Competitor 为每个适用竞品各一条；Evaluation 为目标品牌一条，再为每个适用竞品各一条。Discovery 必须覆盖全部 P1，再按购买价值选择 P2/P3 补足到配额；信息不足以支撑相互独立的问题时停止并报告 Case 过薄，不得用伪重复凑题。1–3 个 Topic 的整批题量分别为 25/50/75，同时保存并校验 Topic 配额，失败不得静默少题。
4. 按生成方法编写自然英文根问题及等义中文。Discovery 和 Category Awareness 不出现任何具体品牌；Competitor、Evaluation 遵守各自品牌边界。按题面实际品牌提及写入唯一品牌范围 Tag：出现目标品牌或正式竞品为 `Brand Scope: Branded`，否则为 `Brand Scope: Non-Branded`。逐题守住四条写作规则：意图与格式匹配（Discovery 含候选触发名词，Competitor 具备场景、双具名品牌和明确推荐要求，Evaluation 明确评价任务）、不引导答案、缩写和跨品类歧义在题面内消解、买家语境只来自 Case 字段。Case 字段提供多个既有品类称呼时，基线候选题可按称呼各留一题，称呼变体不得自造。
5. Discovery 必须覆盖当前 Topic 全部 P1，其余单属性题优先覆盖 P2；只有 P1/P2 已充分覆盖时才使用 P3。每题把实际测试的属性写为一个或多个 `Attribute: {attribute}` Tag；无独立属性条件的品类基线题允许不写 Attribute Tag。Competitor 优先使用双方都能合理比较的 P1 和高优先 P2，只覆盖当前 Topic 的适用竞品，每个适用竞品恰好一题。当前 Topic 有两条以上 Competitor 题时，除竞品名称外，英文问题的字符、条件、任务、比较维度和 Attribute Tags 完全同构。
6. 不生成 Verification 与 Accuracy 问题。保留 Verification 作为意图定义（批量验证 AI 是否正确认知目标品牌与多个关键 Attribute 的关联，适用阶段为售后），P1 的属性级正确性核查并入 Accuracy 合同；只有用户明确要求售后验证或事实核验时，才在独立合同下单独确认产物，不得从 Case 或模型记忆临时补真值，也不在默认售前题库中生成 `validation_items` 或 `fact_value / official_source_url / fact_checked_at`。
7. 使用固定 Evaluation 与品类优先 Category Awareness 模板，不自由改写任务结构。每个 Topic 为目标品牌和当前 Topic 的每个适用竞品各生成一条 Evaluation；每题只出现一个品牌，不得混入其他竞品或不适用竞品。Evaluation 只把 Topic 当作语义约束，将其转写为客户可理解的具体业务范围或场景。英文 Prompt 正文（JSON `user_question / monitoring_prompt`、CSV `query`）不得出现独立单词 `topic`；不限制中文翻译、CSV `topic` 列或其他元数据。
8. 为每题写入一个默认诊断 Tag：`Intent: Discovery / Competitor / Verification / Accuracy / Evaluation / Category Awareness`。这些角色的数量必须满足第 3 步固定配额；Tags 字段仍允许增加其他自由 Tags。完成独立二遍语义 review，先确认 Topic 路由、属性分级与 Tags，再检查题面和翻译。保存 v8 JSON 后运行 validator 与回归测试。

## 分析与指标边界

> **注意**：下表中的 `Intent: …` Tag 为当前默认枚举。诊断意图后续将迁移为自定义 Tags，迁移后需在自定义 Tag 定义中重新声明 `analysis_type` 与 `formal_visibility_eligible` 的推导规则。

| 默认诊断 Tag | analysis_type | formal_visibility_eligible |
|---|---|---|
| `Intent: Discovery` | `visibility,sentiment` | `true` |
| `Intent: Competitor` | `sentiment` | `false` |
| `Intent: Verification` | 空 | `false` |
| `Intent: Accuracy` | `accuracy` | `false` |
| `Intent: Evaluation` | `sentiment` | `false` |
| `Intent: Category Awareness` | 空 | `true` |

把 `analysis_type` 用于分析模块分流，把 `formal_visibility_eligible` 用于正式可见度题集资格。两者由 Prompt 生成角色确定，不从可自由修改的 Tags 自动推导；增删自定义 Tag 不得改变路由。Discovery 同时承担可见度与情感分析；Competitor 与 Evaluation 只进入情感模块；Verification 与 Accuracy 只在独立合同下使用，不进入默认售前题库的可见度或情感指标；Category Awareness 不分流进任何标准分析模块，由售前报告作为认知标准与品牌属性对比输入直接消费。正式 Visibility、声量、排名、Share of Voice 与聚合引用指标的分子与分母只统计 `formal_visibility_eligible = true` 的 Discovery 与 Category Awareness，Competitor 不再计入。旧 `metric_scopes` 只可由兼容适配器生成，不是 v8 核心字段，也不得覆盖上述两个字段。

不生成或保留 `topic_type`、`question_type`、`funnel_intent`、`decision_stage`。旧 `overseas-geo-question-bank/v5` 仅允许只读验证或迁移，不得作为新题库默认输出。

## 输出与验证

- 每 Topic 固定输出 25 条 Prompt，按适用竞品数 `n` 执行 `23-2n / n / 0 / 0 / 1+n / 1`配额；同时输出 `attribute_plan`、实际 Topic 配额、Case 字段覆盖、按 Topic 的竞品 Competitor 与 Evaluation 覆盖、Tags 汇总和失败/重写原因。
- 每题包含 `question_id / topic_id / tags / analysis_type / formal_visibility_eligible / intent_key / user_question / zh_translation / monitoring_prompt / quality_checks`；不包含 `diagnosis_intent` 或单独的 `attributes`。
- 默认题库不含 Verification 题与 `validation_items`、Accuracy 题或事实包字段；上传 CSV 固定字段顺序为 `query,question_zh,topic,diagnosis_intent,tags,question_types,purchase_intent,persona_name,scene_name`。`diagnosis_intent` 从 JSON 唯一默认 Intent Tag 转写为 `discovery / competitor / verification / accuracy / evaluation / category_awareness`。`tags` 为上传适配列：允许留空；如果填写，必须是短于 200 字符的字符串，并使用英文逗号、中文逗号或换行分隔，优先保留可上传的最小化摘要，不要把 JSON 里的完整 Attribute 列表直接搬进来。`question_types` 按上传合同填写：Discovery、Verification、Accuracy 与 Category Awareness 为 `visibility,sentiment`，Competitor 与 Evaluation 为 `sentiment`。`purchase_intent / persona_name / scene_name` 没有可靠来源时留空，不臆造。JSON 仍不生成独立 `diagnosis_intent` 或 `question_type` 字段；这两个 CSV 字段只由上传适配器导出。

```bash
python3 scripts/validate_question_bank.py /absolute/path/question-bank.json
python3 -m unittest discover -s evals -p 'test_*.py'
```

新题库默认生成 v8；validator 仍可只读旧 v7/v6/v5。不创建 Topic，不选择或补齐竞品，不重新核验官网事实，不采集回答，不生成 `observed_associations`，不计算任何诊断指标，不直接写售前报告。
