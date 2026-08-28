# 问题质量门（v8）

## 输入硬门

- 输入字段来自同一 Edgelight 型评测集 Case：公司与品牌、业务 / 产品、业务模式、品类、垂直行业、目标客户、痛点、使用场景、产品特性、差异化优势、适用边界、1–3 个 Topic、官方域名、三组正式竞品及官网域名、补充内容。
- `补充内容`字段必须存在但允许为空；为空或未声明 Topic 局部竞品边界时，三组正式竞品均适用于全部 Topic。
- 纯 `B2C` Case 的垂直行业可为空；`B2B` 与 `B2B / B2C` 仍需非空。
- 不要求或读取旧 `target_attributes` 作为 v8 输入；不存在根据未采集回答预写的 `observed_associations`。
- `config` 只包含 v8 合同声明的字段；拒绝 `target_audiences / pain_points / use_cases` 等平行输入合同和未声明配置。
- `attribute_plan` 对每 Topic 恰好一项；P1 为 3–5 个，P2 建议 5–10 个且不超过 10，P3 为 0–10 个。每项精确回指 Case 原字段；同一 Case 字段允许跨 Topic 复用。
- P3 仍必须影响购买认知；纯目录事实与无决策价值文案进入 `excluded.route=exclude`，非具体型号 Topic 下的单款 SKU 精确值进入 `excluded.route=accuracy_only`。
- Topic 标签中的“宽泛/细分”不成为 `topic_type`；Case 级正式竞品恰好三个且各有官网域名。存在 Topic 局部竞品边界时，每个竞品用 `topic_ids` 显式声明适用范围，每个 Topic 至少有一个适用竞品。
- Accuracy 默认配额为 0；输入不要求上游事实包，默认产物不包含 Accuracy 题或事实包字段。

## 逐题硬门

- `topic_id` 能回指当前 v8 配置；问题字段不依赖旧的逐题 `attribute_ids` 或单独 `attributes`。
- `tags` 是非空且归一后无重复的自由字符串数组；每题恰好一个默认 `Intent: …` 和一个 `Brand Scope: …`，允许增加其他自由 Tag。单个 Tag 不得包含 CSV 保留分隔符 `;`。
- `Brand Scope: Branded / Non-Branded` 与题面实际是否出现目标品牌或正式竞品一致。
- 每个 `Attribute: …` 都回指当前 Topic 的 `attribute_plan`；同名 Attribute 可跨 Topic，不能把其他 Topic 的属性串入当前题。
- 问题自然、独立、可回答、单一任务、品类可识别、前提中性；中英文等义。
- Discovery 明确要求具体候选，不出现目标品牌或正式竞品，每题最多一个主要购买条件。
- Competitor 题只比较目标品牌与当前 Topic 的一个适用竞品；每个适用竞品恰好一题。当前 Topic 有两题以上时，除竞品名称外英文题面完全相同。
- Verification 只出现目标品牌，包含 3–5 个仅由 `source_field / source_value / statement` 组成的 `validation_items`，并与当前 Topic 的有序 P1 属性完全一致；逐项要求 `Yes / No / Unknown + 判断依据`，中文翻译按相同顺序完整翻译每个待验证陈述。
- 默认产物不生成 Accuracy 题；如用户明确要求，先使用另行确认的事实核验合同，不临时复用默认 Builder 合同。
- Evaluation 每个 Topic 只评价目标品牌一次，不出现竞品；竞品情绪矩阵留给售后生词。它只替换固定模板的品牌与 Topic 具体范围；英文 `user_question / monitoring_prompt / query` 不出现独立单词 `topic`，中文翻译和元数据不受此限制。Category Awareness 使用品类优先固定模板且不出现品牌。
- `analysis_type` 与 `formal_visibility_eligible` 精确匹配 v8 分流表；Discovery、Competitor、Category Awareness 为 `true`，其余三类为 `false`；自由 Tags 不改变路由。
- `monitoring_prompt` 等于 `user_question`；`intent_key` 唯一；不存在 `diagnosis_intent / attributes / topic_type / question_type / funnel_intent / decision_stage / metric_scopes / attribute_pool / attribute_id / attribute_ids / priority_attribute_ids / paired_discovery_ids`。

## 整批硬门

- Topic 数为 1–3；各 Topic 实际配额可不同，聚合配额、`expected_total` 与最终题数必须一致；整批不超过 60。
- 不校验统一的每 Topic 默认题量。每 Topic 的 Competitor 等于适用竞品数，Verification / Accuracy / Evaluation / Category Awareness 为 `1/0/1/1`；Discovery 为正整数，并由 P1/P2/P3 的有效覆盖决定。
- 每个 Topic 的 Discovery 必须严格超过该 Topic 全部非 Discovery 题数之和，即占比大于 50%；不接受只在整批层面达到多数。无法用独立购买问题满足时停止，不得制造伪重复。
- 每 Topic 10–25 只作语义警告区间，不作失败条件；不得为进入区间而制造伪重复。`formal_visibility_eligible=true` 的数量按实际 Discovery、Competitor 与 Category Awareness 统计；Verification 即使 `analysis_type=visibility` 也必须为 `false`。
- 每条 Discovery 题面归一后唯一，并明确要求具体品牌、制造商、供应商、产品或解决方案候选。
- 每 Topic 的 Competitor 恰好逐一覆盖其适用竞品；两题以上时通过“仅竞品名不同”的控制变量检查。其他 Topic 的竞品出现即失败。
- 每 Topic 的 Evaluation 恰好一条且只评价目标品牌；出现竞品即失败。
- 每 Topic 的 Verification 恰好覆盖全部 P1，题面、有序 `validation_items`、有序 Attribute Tags 与 P1 的溯源和 `verification_statement` 精确一致；默认没有 Accuracy 题。
- Discovery 的 Attribute Tags 覆盖每个 P1，其余单属性题优先覆盖 P2；Competitor 的维度与 Attribute Tags 来自双方可比的 P1 和高优先 P2。P3 只补余量。
- 不存在伪重复或输入外虚构条件，也不把 Case 品牌自述直接当成已核验真值。同一 Case 字段跨 Topic 重复使用是允许行为。
- Prompt Builder 全程不调用 `web-access`，不搜索、打开或重新核验目标品牌官网。

## 语义警告

确定性 validator 通过后仍需人工复核：Topic 是否确实为完整监测机会，跨 Topic 能力是否正确进入 Attribute；P1 是否真正决定入围，P2 是否明显影响比较，P3 是否仍有购买参考价值，应排除事实是否被降级塞入 P3；中文源字段是否被英文扩写成新事实；Discovery 是否先覆盖 P1/P2；Tags 是否准确且不过度标注；Topic 局部竞品是否跨界；竞品题是否保持控制变量；Verification 是否暗示正向答案；固定模板译文是否弱化限定。
