# 问题质量门

## 硬门：逐题

每条 `user_question` 必须同时满足：

1. `Natural`：是清楚、可成立的购买请求，不是 SEO 标题、标签或关键词堆叠。无需猜测用户逐字说法，但不得为了制造题目差异编造低频条件；每 Topic 固定品牌总体评价基准题是明确例外，按规定的 `Evaluate...` 请求式模板生成。
2. `Standalone`：脱离前文仍能确定对象、任务和必要约束。
3. `Answerable`：AI 可以直接开始回答，不必先索要公司名、预算、地区或 “GT 是什么”。
4. `Single intent`：只有一个主要购买任务；目标用户、评估标准、约束和比较对象可以单独使用，也可以复合使用，但所有条件必须共同限定同一个候选集合、比较或适配判断，不能把两道题拼在一起。
5. `Topic aligned`：体现所属 Topic 的具体意图，并保持同一购买集合。题目要求 AI 选择的对象必须仍是 Topic 中那一类候选；例如 OEM/ODM 电池制造商不能偷换成热管理厂商、集装箱式储能系统商或大型储能项目合作伙伴。
6. `Category visible`：独立看问题时，能从品类原词、自然变体或品类下产品词认出品类；`specialized product suppliers` 等占位词不合格。
7. `Commercial intent`：提问者在选购，不是在学习。Generic 的题目措辞必须明确要求具体品牌/供应商/平台/产品候选、候选间比较，或最终候选选择；不能只因为 AI 回答可能或通常会顺带举品牌就判定合格。答案候选可包含监控品牌、已配置竞品或未配置的同类品牌。只比较材料/品类、只问是否值得采用，或只给概念、标准清单、购买流程的题不合格。Branded 则必须形成监控品牌的候选适配、比较或选择判断。

   Generic 使用“无品牌答案测试”：尝试在不写任何具体候选名称的情况下完整回答。若仍可完整回答，说明品牌只会偶然出现，该题 `commercial_intent=false`。
8. `Category aligned`：明确属于目标品类，没有漂到排除品类、上下游供应商或更大的项目交付对象。只出现 battery、energy storage 等相关词不代表对象对齐。
9. `Neutral premise`：不预设品牌领先、最受欢迎、便宜、可靠或存在缺陷。
10. `Field valid`：监测 Prompt 来自 `user_question`；追问回放来自 `standalone_rewrite`。
11. `Brand boundary`：Generic 不含客户品牌、产品 aliases、竞品或其他任何具体品牌实体，但可以使用 `brands / manufacturers / suppliers / platforms / products` 等通用候选词；Branded 必含客户品牌。程序对已配置实体做确定性拦截，未配置实体由语义 review 检查。
12. `Term clarity`：专业缩写单独出现时必须有品类语境；不得用含义不明的 `GEO tools`、`AEO platform` 作为独立问题。
13. `Chinese translation`：必须提供非空字符串 `zh_translation`，且至少含一个汉字；准确等义、数字/币种保真与合理本地化由语义 review 确认。
14. `Competitor policy`：竞品题必须使用冻结集合中的等级与比较边界。`direct` 可做标准中性比较；`adjacent/fallback` 只能使用 `allowed_dimensions`；维度为空时只澄清品类或场景，禁止谁更好、全面优劣、绝对排名或全面替代性问法。

## 硬门：整批

- 总题量及 Generic/Branded 问题类型配额精确相等；不校验三类意图的精确数量或六格交叉数量。
- v3 商业意图只允许 `recommendation / comparison / decision`；出现 `awareness / informational / 了解` 直接失败。
- v3 不允许 `geo_intent` 或角度配额。信息题直接淘汰；价格、限制、风险和替代对象只能作为改变选择的条件，问题仍按答案终点归入 Recommendation、Comparison 或 Decision。
- Recommendation、Comparison、Decision 整批各至少 1 条。
- 每个 Topic 恰好 1 条 Branded 品牌总体评价基准题，严格匹配 `Evaluate the {品类} company/product {品牌} on {主题}`；固定归入 `decision`，不增加情绪意图字段。Topic 数不得超过 Branded 配额。
- 每题 `topic_id` 必须命中 `config.topics`；`decision_stage` 不得再使用 `awareness`。
- 正式售前链路的 `competitor_selection` 为冻结状态且恰好包含 3 个 formal competitors，题库未重选或遗漏销售填写/系统补足项。
- 当实际 Branded Comparison 数不少于 3 时，三个正式竞品各至少有一条只命中该竞品的一对一题；实际达到 5 条时，另外至少 2 条必须是关键因素题或多品牌综合比较，不能继续重复一对一模板。
- `question_id` 唯一；规范化后的 `user_question` 无完全重复。
- 一题一意图：按规范化条件集合去重。条件集合完全相同、只换英文措辞或条件顺序的题不得重复占配额；条件取值变化，或增删一个真正改变答案边界的条件，可以是不同意图。
- 多子品类或多产品广度 Topic 的覆盖按整批检查；单题只需命中一个合法子品类、具体产品或组合场景，不得因追求逐题全覆盖而生成罕见购买任务。
- `best / top / most / reviews` 等问法可用；集中出现只发软警告，复核是否掩盖了意图重复。
- 满足风险、角色、场景与约束覆盖。价格不设固定最低配额，只在本次选型确实需要时生成。
- `required_term_coverage` 中每个术语满足总量、Generic、Branded、全称与缩写最低覆盖；未配置的术语不强制出现。
- v3 题库必须配置 `category_expression_set` 并标记 `professional_term_assessment.status=completed`；评估为 `required` 的概念与 `required_term_coverage` 一一对应，无必覆盖概念时也要填 `no_required_terms_reason`。
- 所有被淘汰或重写的问题保留原因，不静默删除后少题。

## 软警告：整批

- 题量不少于 10 时，如超过 50% 的问题所属 `cluster` 只出现 1 次，警告可能用唯一标签伪造多样性；超过 80% 标为高风险。需语义复核簇是否真正可复用。
- 题量不少于 10 时，如超过 75% 的问题以 `How / What / Which` 开头，警告句式过度集中；超过 90% 标为高风险。任一单一开头超过 50% 也发出警告。这些都不直接判错，但要复核是否存在跨品牌模板化。
- `scenario / constraint` 单例题占比达到 80% 时警告元数据颗粒可能过细。聚类、场景和约束统计前统一大小写、空格、连字符与下划线。
- 裸 `most / review` 的低置信命中只输出待看上下文的提示。

软警告不代替语义审查，也不应为了降低比例而机械换句式或合并不同意图簇。

句式重复和 Yes/No 都不是硬门：句式相同但条件取值不同可以保留；Yes/No 题只要会引出理由、适用条件或风险就合格。需要判断的是答案是否重复、是否有商业价值，不是表面句型。

## 自然度判定

允许：

- 标准疑问句：`Which AI visibility tools work best for small SEO agencies?`
- 自然对话请求：`Compare Peec AI and Profound for a mid-sized marketing team.`
- 第一人称需求：`I'm looking for an AI visibility tool for a small SEO agency.`
- 简短但完整的问题：`Which CRM is best?`
- Yes/No 决策题：`Is Peec AI suitable for a small SEO agency that needs weekly reporting?`

拒绝：

- 关键词：`AI search visibility tool pricing`
- 标题：`Best AI Search Visibility Tools for 2026`
- 裸动作：`Buy AI brand tracking tool subscription`
- 缺上下文：`Which one is better?`
- 预设断言：`Why is Peec AI the most reliable option?`

问题不因词数本身通过或失败；过长、堆条件或重复表达分别由 Natural 与 Single intent 判断。七项布尔 `quality_checks` 必须在初稿之后的独立二遍语义 review 生成，不得与问题初稿同步默认填 `true`。程序脚本只能捕获确定性错误和高风险模式；自然度、单意图、Generic 是否会产出具体品牌候选、中性前提、术语是否机械塞入、译文等义和跨品牌语义模板重复必须由 review 确认。

专业术语覆盖也不能覆盖自然度门：术语必须在问题意图中有作用，不得把已完成的问题批量替换同义词或追加 `(GEO/AEO)` 凑数量。整批既要覆盖普通用户常用的 `AI search visibility`，也要覆盖专业买家会使用的规范术语。

二遍语义 review 必须逐条填写 `topic_aligned / category_visible / commercial_intent`，并先回答三问：问题要求 AI 选择的对象，是否仍是 Topic 的同一购买集合；Generic 的题目是否明确要求品牌/供应商/平台/产品候选，而非只可能在回答中顺带出现；使用的条件是否来自输入或有业务依据。然后检查 Recommendation、Comparison、Decision 的答案终点：给候选、比较候选并取舍、从候选中给最终选择。脚本只拦截确定性词面错误和明显科普/购买流程模式，不能凭正则判断 AI 的完整回答。

## 品类防漂移

- `brand tracking`、`brand monitoring` 单独出现时视为歧义表达，必须同时出现 `AI search`、`AI-generated answers`、`generative search`、`LLM` 或等价限定。
- 如果问题专门解释 GEO 与 social listening 的区别，可标记 `boundary_question: true`，允许出现排除品类。
- 不用 `rank tracking` 指代 AI 答案可见性；需要排名时写清 `brand position in AI-generated answers`。
- 不用 `specialized product suppliers / product providers / solution vendors` 等跨行业占位词代替真实品类。

## 修复顺序

1. 保留原始问题与失败原因。
2. 回到意图矩阵确认问题目标，而不是只润色句子。
3. 重新生成 `user_question`，再分别生成其余四个字段。
4. 重跑逐题门、语义去重、总题量与 Generic/Branded 配额、三类意图及逐 Topic 情绪题覆盖。
5. 修复后仍不通过则淘汰，并从缺失矩阵单元补生成新题。
