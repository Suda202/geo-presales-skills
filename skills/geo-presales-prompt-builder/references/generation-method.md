# 海外 GEO 售前生题方法（v8）

## 1. 冻结接口传入的评测 Case

只消费系统接口提交的评测 Case 中文业务字段：公司与品牌、业务 / 产品、业务模式、品类、垂直行业、目标客户、痛点、使用场景、产品特性、差异化优势、适用边界、1–3 个 Topic、官方域名、三组正式竞品及官网域名、补充内容。不再转写成另一套 Prompt Builder 输入。

把 `主题 1（宽泛）`、`主题 2（细分）` 一类标签解析为 Topic 顺序和文本；不要在 v8 配置或问题中保存 `topic_type`。Topic 只承载独立市场、场景或战略机会；跨 Topic 的能力、特征和评价标准进入 Attribute 规划。默认生成英文问题；中文源字段作为证据，不把翻译后的扩写当作新增事实。

## 2. 先建立 Attribute × Topic 规划

从下列来源逐项抽取可测试的买家关联，不要求 Case 提供 `target_attributes`：

| 来源字段 | 可用判断 | Edgelight 例子 |
|---|---|---|
| `品类` | product_category | LED display manufacturer and commercial display solutions provider |
| `目标客户 n` | audience | commercial AV integrators and LED display distributors |
| `痛点 n` | pain_point | matching pixel pitch, brightness, refresh rate and viewing distance to a venue |
| `使用场景 n` | use_case | fixed LED installations in corporate and commercial spaces |
| `产品特性 n` | capability / integration | structural customization and content-control integration |
| `差异化优势` | business_specific | project delivery capability backed by stated manufacturing scale and certifications |
| `适用边界` | business_specific | excludes buyers seeking only lighting, power supplies, controllers or full architectural AV services |

按 [Attribute × Topic 属性规划](attribute-planning.md) 先合并同义候选，再为每个 Topic 单独划分属性优先级：P1 为 3–5 个最高优先级属性，P2 建议 5–10 个中优先级属性，P3 为 0–10 个低优先级属性。P1 / P2 / P3 不是属性类型。低信息量目录事实和需要独立真值的精确参数分别放入 `exclude` 或 `accuracy_only`，不能降级塞入 P3。同一属性在不同 Topic 中可有不同优先级；同一 `source_field` 可被多个 Topic 复用。不生成 `attribute_pool / attribute_id / priority_attribute_ids / observed_associations` 或单独的逐题 `attributes`。

## 3. 建立统一 Tags

每题使用一个自由字符串数组 `tags`。默认写入以下常用标签：

- 一个生成角色标签：`Intent: Discovery / Competitor / Verification / Accuracy / Evaluation / Category Awareness`。
- 一个品牌范围标签：题面出现目标品牌或任何正式竞品时写 `Brand Scope: Branded`，否则写 `Brand Scope: Non-Branded`。
- 零个或多个 Attribute 标签：`Attribute: {attribute_plan 中的人类可读名称}`。一题测试多个属性时可写多个；品类基线题不测试独立属性时允许为零。

允许增加 `Lifecycle: …`、`Region: …` 等自由 Tags。常用 Intent 标签用于 Builder 的实际数量汇总与模板质检，但不携带固定配额；`tags` 字段本身没有封闭枚举，自定义 Tags 不改变 `analysis_type` 或 `formal_visibility_eligible`。

## 4. 按适用竞品数执行固定配额

先按补充内容确定当前 Topic 的适用竞品数 `n`，`n` 只能为 1–3。每 Topic 固定 25 题，六类 Intent 配额为：

| 适用竞品数 `n` | Discovery | Competitor | Verification | Accuracy | Evaluation | Category Awareness | 合计 |
|-|-:|-:|-:|-:|-:|-:|-:|
| 1 | 21 | 1 | 0 | 0 | 2 | 1 | 25 |
| 2 | 19 | 2 | 0 | 0 | 3 | 1 | 25 |
| 3 | 17 | 3 | 0 | 0 | 4 | 1 | 25 |

通用公式为 Discovery `23 - 2n`、Competitor `n`、Verification `0`、Accuracy `0`、Evaluation `1 + n`、Category Awareness `1`。Competitor 为每个适用竞品各一条；Evaluation 为目标品牌一条，再为每个适用竞品各一条。Discovery 先覆盖全部 P1，再按增量购买价值选择 P2/P3 补足到配额。信息不足以产生相互独立的 Discovery 时停止并报告输入不足，不得写泛化、重复或无购买价值的问题。1–3 个 Topic 的整批题量分别为 25/50/75。

把生成前规划出的实际数量写入 `quotas`。`per_topic` 是未单列 Topic 共用的实际基线，不是系统默认值；题量不同的 Topic 写入 `topic_overrides`。聚合配额必须等于各 Topic 实际配额之和，并与最终问题数一致。

### Discovery × `23 - 2n`

全部要求具体品牌、制造商、供应商、平台或产品候选，且不得出现目标品牌或正式竞品名称。题面必须包含候选触发名词（provider、manufacturer、supplier、tool、platform、solution、brand 等品类对应词）；缺少触发词的问句会得到操作建议而不是品牌清单，属于格式错误而非语义偏好。

Discovery 的规划顺序：

1. 1 题无附加条件的品类候选。Case 字段（品类、业务 / 产品名称、垂直行业）提供多个既有买家称呼时（如通用叫法、技术叫法、买家口语叫法），可为每个称呼各保留一题基线候选：同一问题只换品类称呼，各平台可见度可能相差数十个百分点，不同称呼测的是不同的市场入口。称呼变体只能来自 Case 字段中实际出现的术语，不得自造同义词。
2. 让全部 P1 至少各被一题覆盖；每题只突出一个主要购买条件。
3. 为能形成不同候选集合、比较边界或决策结果的 P2 增题；目标客户和场景只有在会改变答案时才单独成题。
4. 适用边界、交付限制或项目约束能改变候选结果时，可各形成一题。
5. 只有 P1/P2 已充分覆盖且仍有明确增量价值时才使用 P3。
6. 题量有余量且不挤占 P1/P2 覆盖时，可为入围权重最高的 P1 增加一条换法不换条件的表述变体，降低单一措辞对该属性读数的干扰；变体仍写同一 Attribute Tag，且不得用变体凑题量或维持多数。

不同来源字段若会得到相同候选集合或相同决策结论，应合并为一题，不按字段数量逐项凑题。品类称呼变体是该规则的唯一例外：称呼本身就是变量，即使预期候选集合相似也各自保留。每条条件题写入实际测试的 Attribute Tag；整批 Discovery 的 Attribute Tags 必须覆盖当前 Topic 全部 P1。

单条 Prompt 的结果读数天然不稳定，同一属性的判断应在 Attribute Tag 层汇总解读；生题时的覆盖目标是"每个 P1 的读数可信"，不是穷举所有可能问法。

每题最多一个主要购买条件。宽泛 Topic 保持品类和供应商发现视角；细分或场景 Topic 锚定具体空间、项目任务和使用要求。不得只问定义、标准清单、材料差异或采购流程。

### Competitor × 当前 Topic 的适用竞品数

固定一个中性的一对一比较模板，优先选择双方都能合理比较的 P1 和高优先 P2 维度，只代入当前 Topic 的适用竞品。模板必须同时具备三要素：具体使用场景或买家条件、两个具名品牌、明确要求给出选择或推荐结论；只写 `Compare X and Y` 而不要求结论的软比较会得到"各有所长"式回避，无法形成决胜回答，视为格式错误。每个适用竞品恰好一题；不得跨 Topic 使用竞品，也不得重复同一竞品补足三题。当前 Topic 有两条以上 Competitor 题时，除竞品名称外，英文 `user_question` 与 Attribute Tags 必须完全同构；不能为不同竞品增删条件、改维度或预设胜者。每条只出现目标品牌和一个竞品，且该竞品必须有官网域名。

### Verification × 0

默认不生成 Verification 题。保留 Verification 作为意图定义：批量验证 AI 是否正确认知目标品牌与当前 Topic 下多个关键 Attribute 的关联，逐项输出 `Yes / No / Unknown + 判断依据`，适用阶段为第二轮售前（高意向/定向验证）和售后。P1 的属性级正确性核查并入 Accuracy 合同。只有用户明确要求时，才在独立合同下单独确认产物，不得从 Case 或模型记忆临时补真值，也不在默认售前题库中生成 `validation_items`。

### Accuracy × 0

默认不生成 Accuracy 问题，不读取或要求 `fact_value / official_source_url / fact_checked_at`。如用户明确要求 Accuracy，先停止默认生题流程并确认独立的事实核验输入与产物合同；不得从 Case 声明、模型记忆或第三方页面临时补值。

### Evaluation × `1 + n`

对目标品牌和每个适用竞品使用同一固定模板：

`Evaluate the {category_label} {company|product} {brand_name} on {evaluation_scope}`

`company|product` 由 `brand_object_type` 决定。`evaluation_scope` 由当前 Topic 转写而来，只表达具体业务范围或场景，不把 Topic 当成英文 Prompt 词汇。目标品牌和当前 Topic 的每个适用竞品各生成一题；每题只替换品类、对象类型、当前被评价品牌与评价范围，只出现一个品牌，不加标点、追问或额外评价维度。英文 `user_question / monitoring_prompt / query` 不得出现独立单词 `topic`；中文翻译和元数据不受此规则限制。

### Category Awareness × 1

不出现任何品牌，使用品类优先固定模板：

`What is a {category_label}, and how should I evaluate one for {topic}?`

先确认购买品类，再询问评价标准；它描述市场认知，不衡量目标品牌主动提及。

## 5. 逐题写作规则

按题面自查以下四条，任何一条不满足都属于写作错误，不是风格问题：

- **意图与格式匹配**：Discovery 缺候选触发词会得到建议清单；Competitor 缺场景或缺明确推荐要求会得到骑墙回答；Verification 写成开放题会得到清单而非逐项判断；Evaluation 缺明确评价任务会得到品牌罗列。发现格式漂移时按对应题型的修复动作改写：补触发词、补使用场景、改成逐项判断、改成明确评价。
- **不引导答案**：题面不得预设目标品牌的优点、期望结论或"为什么 X 很好"式前提。问题测量的是意图本身，不是希望看到的答案；带引导的题产生的读数没有诊断价值。
- **消除歧义**：缩写首次出现必须展开成 Case 字段支持的全称；跨品类歧义的称呼（同一词在不同行业指不同产品）必须补品类限定。监测 Prompt 没有第二轮澄清机会，歧义必须在题面内解决。
- **买家语境具体化**：条件题的角色、企业类型和使用场景只能来自 `目标客户 n / 使用场景 n / 垂直行业` 等 Case 字段；具体买家语境会显著改变候选集合，但不得从输入外补造行业、规模或地域。

## 6. 二遍 review

第一遍先检查 `attribute_plan`：每 Topic 的优先级是否有决策依据、P1 是否真正决定入围、P3 是否混入应排除事实、每项是否精确溯源。第二遍逐题检查自然、独立、可回答、单意图、Topic 对齐、品牌边界、中性前提、意图与格式匹配、无引导、无歧义缩写、中英文等义和 Tags；整批检查 1–3 Topic、每 Topic 是否恰好 25 题、是否按 `23-2n / n / 0 / 0 / 1+n / 1` 配额、配额与最终题数一致、P1 在 Discovery 中的覆盖、品类称呼变体是否都来自 Case 字段、品牌范围 Tag 与题面一致、适用竞品逐一覆盖、Competitor 三要素齐备且控制变量、Evaluation 是否对目标品牌与每个适用竞品各一条、固定模板和无伪重复。
