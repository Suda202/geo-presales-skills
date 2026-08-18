# Overseas GEO 问题生成方法

## 1. 先定义对象边界

每次生成前明确：

- 监测对象：品牌、产品、规范名称与 aliases
- 品类定义：客户究竟购买和比较什么
- 排除品类：容易被同一术语带入、但不属于本次诊断的市场
- 市场与 locale：国家、语言、拼写、币种、监管语境
- 用户：角色、团队规模、行业、使用场景、预算/集成/合规约束
- 竞品：仅作为边界和品牌题输入；通用题禁止出现配置品牌名
- 事实状态：已验证、用户提供、推断、待确认

例如 `brand tracking` 在海外可能指 social listening、media monitoring、SERP rank tracking 或 AI-answer visibility。目标若是 GEO，问法应使用 `AI search visibility`、`visibility in AI-generated answers`、`LLM visibility` 等清晰限定；不能单独依赖歧义短语。

### 1.1 建立品类表达集合

先把品类整理成 `category_expression_set`，再出题：

- `core_terms`：品类原词和目标市场常用自然变体，例如 `rechargeable battery manufacturers`、`battery suppliers`。
- `product_terms`：只属于该品类、用户会直接采购的产品词，例如 `LiPo cells`、`LiFePO4 battery packs`、`custom battery packs`。
- `placeholder_blacklist`：跨品类占位词，例如 `specialized product suppliers`、`product providers`、`solution vendors`。这些词不能代替真实品类。

每条问题独立看时必须能认出品类。命中 `core_terms` 或 `product_terms` 即可，不要求机械复述 Topic 原词。`Which suppliers offer low-MOQ custom LiPo cells?` 能看出电池品类；`Which specialized product suppliers offer low MOQs?` 不能。

品类可见不等于 Topic 对齐。同一品类下有多个 Topic 时，每题还要体现所属 Topic 的具体意图，不能用泛品类题跨 Topic 补量。

广度 Topic 含多个子品类或产品词时，覆盖单位是整批而不是单题。先在意图矩阵记录各子品类的批内覆盖，再让单题自然落到品类大盘、某个子品类、具体产品或组合场景。不得要求每题重复完整品类范围，也不得为了同时出现多个产品词，发明“一个全品类品牌还是多个专业品牌”之类罕见购买任务。

## 1.5 专业术语与用户自然语言双层覆盖

自然用户不只使用白话，也可能直接输入 GEO、AEO、LLM visibility 等行业术语。生成前必须建立专业术语清单，不能因为追求自然度而把输入中的规范术语全部同义改写掉。新题库先输出 `professional_term_assessment`：对 Topic、受众和品类中的每个候选概念记录 `required / excluded`、来源和理由，再为所有 `required` 概念建立配额。即使结果为空，也必须标记评估已完成并写 `no_required_terms_reason`。

术语来源按优先级判断：

1. Topic、受众或补充背景明确出现的术语：默认列为必覆盖。
2. 与购买品类直接等价、且目标市场稳定使用的规范术语：列为品类核心术语。
3. 只有厂商自称、含义不稳定或与购买任务弱相关的词：只作候选，不设硬覆盖。

AI Search Visibility 品类常见的双层表达包括：

| 用户自然语言 | 专业术语 |
|-|-|
| AI search visibility、visibility in AI-generated answers | generative engine optimization (GEO) |
| AI answer optimization、answer visibility | answer engine optimization (AEO) |
| visibility across AI platforms | LLM visibility、generative search visibility |

对默认 50 题题库：

- 输入明确出现的专业术语，建议至少 3 条，其中 Generic 至少 1 条、Branded 至少 1 条。
- 相关但未在输入中出现的品类核心术语，确认适用后建议至少 2 条；不适用时说明理由，不为配额硬塞。
- 每个必覆盖缩写至少有 1 条使用“全称（缩写）”；其余问题可用缩写，但必须带 AI search、AI-generated answers、generative search 等消歧语境。
- 专业术语题仍须改变答案边界，可覆盖定义、比较、选型、实施、指标或品牌适用性；不得只替换 `AI search visibility` 为 `GEO` 制造伪变体。

将专业术语作为意图矩阵中的 `term_slot` 预先分配，而不是问题写完后再插入关键词。没有被 `required_term_coverage` 选中的自然问题不必包含术语，整批应同时代表普通用户与专业买家的表达。

## 1.75 消费冻结竞品集合

正式售前模式以竞品研究 Skill 的 `competitor-selection.json` 为唯一正式竞品输入：

- 只消费 `status=frozen`、`selection_count=3` 且恰好包含 3 个 `formal_competitors` 的集合。
- 保留销售填写与系统补足的全部三个竞品；Intent Miner 不重新挑选、不删除降级候选，也不发起业务复核。
- 将每个 formal competitor 的 `name + aliases` 加入 Generic 品牌边界。
- `direct`：可在证据支持的产品、用户、采购与能力维度做标准中性比较，仍不预设领先。
- `adjacent / fallback`：只能在 `comparison_policy.allowed_dimensions` 内中性比较，禁止全面优劣、绝对排名、“谁更好”或全面替代结论。
- `allowed_dimensions=[]`：只生成品类关系或使用场景澄清题，不询问功能、效果、价格或综合强弱。

竞品的可比级别是题库边界，不是市场事实结论。问题仍须保持中性，并由回答采集与后续证据分析确定实际差异。

## 2. 商业意图与决策阶段

通用 `yao-geo-intent-miner` 需要同时服务拓词、内容、FAQ 和监测，因此使用信息、价格、风险、替代、交易和品牌验证等 GEO 操作意图。本 Skill 只服务售前品牌可见度诊断，不照搬这层分类。

v3 删除 `geo_intent`。`funnel_intent` 是唯一意图分类，只允许 `recommendation / comparison / decision`：

- 信息题直接淘汰；它会把回答带到概念、机制或评估清单。
- 价格、风险、约束、替代对象只是选购条件，根据回答终点归入 Recommendation、Comparison 或 Decision。
- “有哪些替代方案”属于 Recommendation；“原方案还是另一类方案”只有在回答还会命名对应的具体候选品牌/产品时才可作为 Generic Comparison。Generic 不点任何具体品牌实体，但题目本身必须要求具体品牌、供应商、产品或平台候选；点名监控品牌时属于 Branded。答案候选不受配置名单限制，可以自然出现监控品牌、已配置竞品或未配置的同类品牌。
- “是否应试用、购买或采用”属于 Decision；“去哪买、怎么注册”不生成。
- 固定 `Evaluate...` 品牌总体评价基准题由模板确定性识别，归入 Branded + Decision，不增加额外标签。

决策阶段可使用 `shortlist / evaluation / purchase / implementation / review`。售前报告的商业意图只使用 `recommendation / comparison / decision`；不再生成 `awareness`、了解、概念科普或纯教育型问题。

### 售前商业意图的答案终点

售前 50 题只使用 `recommendation / comparison / decision`，三类均须出现，但不设数量或六格交叉配额，也不新增弱、中、强或 `answer_goal` 字段。三类都必须服务选购。Generic 题不出现具体品牌实体，但题目措辞必须把回答任务锁定到具体候选；只给材料差异、选购标准或品类取舍不合格，即使 AI 可能顺带举出品牌也不能通过：

| 类型组合 | 问题应把回答带到哪里 |
|-|-|
| Generic Recommendation | 给品牌/供应商候选名单或推荐；不能只给标准清单 |
| Generic Comparison | 先带出具体品牌/供应商/产品候选，再比较关键差异并给取舍 |
| Generic Decision | 从具体品牌/供应商/产品候选中给最终选择或适配结论 |
| Branded Recommendation | 说明品牌在具体场景是否值得纳入候选，并给理由或适用条件 |
| Branded Comparison | 将本品牌与正式竞品做中性、有边界的比较 |
| Branded Decision | 判断是否应该选择、购买或采用本品牌 |

Recommendation、Comparison 与 Decision 的区别是回答任务，不是购买强度：Recommendation 要候选，Comparison 要候选间差异与取舍，Decision 要对具体候选作最终适配判断。三类都可以带人群、用途、预算和场景；Branded 可以使用会引出理由、条件或风险的 Yes/No 题。Generic 若只问某种材料、方案或品类是否值得采用，而不要求命名候选品牌，不算商业监测题；“回答通常会出现品牌”不等于“问题要求品牌答案”。

### 商业问题的构成

`商业意图 = 品类基础词 + 0 至多个可选条件`。不加条件可测品类大盘；加条件可测更具体的购买意图。四类条件既可单独使用，也可复合使用：

- 目标用户：谁在选。
- 评估标准：买家关心的能力。
- 约束：预算、集成、地区、合规、MOQ 等。
- 比较对象：品类或方案。Generic 问题不得写任何具体品牌实体，但必须要求回答命名对应的品牌/供应商/产品候选。

单一条件示例：`适合医疗设备厂商的充电电池制造商`，只使用目标用户/用途条件。复合条件示例：`适合需要低起订量和医疗认证的初创医疗设备公司的充电电池制造商`，同时使用目标用户、评估标准和约束。

复合条件必须共同限定**同一个购买判断**，并实际改变候选集合、比较维度或最终适配结论；不能用 `and` 把两道独立问题拼在一起。只保留有业务意义且有输入或证据支持的条件，避免为追求复杂度堆叠人群、预算、场景和能力。

四类条件不是四种意图，也不和三类意图一一绑定。目标用户、评估标准或约束都可以进入 Recommendation、Comparison 或 Decision；比较对象通常进入 Comparison，也可作为“替代什么”的 Recommendation 条件。完成具体问题后按答案终点硬分配：

- 回答需要给候选品牌/供应商名单 → `recommendation`
- 回答需要命名候选并比较差异、作取舍 → `comparison`
- 回答需要从具体候选中给最终适配判断 → `decision`

常见问法包括 `best / top / recommended / which / how to choose / what should we use instead of`，但不按句式配额。`How to choose` 只有在回答会比较或推荐具体候选时才合格；`What should I look for...` 这类只产出标准清单的题不合格。

自然度不是逐字复刻真实用户，而是保证问题像一个可成立的购买请求。先保留真实意图与答案终点，再选择清楚、自然的表达；不得为了让 50 题表面不同而编造输入中没有、也不会显著改变候选集合的条件，例如“当钻石的闪耀最重要时”。问题长度不设固定上下限，冗余条件照样按单意图和自然度门删除。

不生成：

- 概念科普：`What is CRM software?`
- 只解释差异：`What is the difference between CRM and ERP?`
- 教育型评估框架：`What should I look for in a CRM?`
- 购买流程：`Where can I buy CRM software?`

## 3. 先场景和因素，再矩阵与措辞

生成顺序固定为：

`Topic + 产品范围 + 目标受众 + 补充背景 → 品类边界、核心任务、核心场景、选型因素 → 意图矩阵 → 问题`

每类受众先提取 1–2 个最重要的任务。选型因素按以下顺序获取：

1. 补充背景明确提出的关注点。
2. 目标受众、Topic 和产品范围直接支持的品类因素。
3. 正式竞品研究中得到的共同维度。
4. 模型补充的合理候选，但不得编造产品能力、法规或合规要求。

先为每个问题分配：

`question_type × funnel_intent × decision_stage × role × scenario × constraint × evidence_need × term_slot`

然后再生成英文。禁止先列 `best/top/pricing/reviews` 关键词模板，再替换品牌或角色凑题量。

Branded 中先为每个 Topic 占用 1 个品牌总体评价基准题位置，再生成其余商业题。固定模板为：

- 公司：`Evaluate the {category_label} company {brand_name} on {topic}`
- 产品：`Evaluate the {category_label} product {brand_name} on {topic}`

该题是每 Topic 的品牌总体评价基准题，硬归 `question_type=branded`、`funnel_intent=decision`；它计入 Branded 与 Decision，不新增任何意图或角色标签。它不代表只有这一题参与情绪统计：其余 Branded 商业题仍应从具体适配、比较和选择里采样品牌评价；下游报告对所有入选有效且提及监控对象的回答计算情绪，不按这条模板限定统计范围。`brand_object_type` 只允许 `company / product`。`category_label` 写自然品类，如 `CRM software`、`men's fragrance`、`rechargeable battery`，不要生成 `rechargeable battery manufacturer company` 这类叠词。

一题一意图按“规范化条件集合”判断，不按英文句式判断。条件集合包含本题实际使用的全部 `条件类型=条件取值`，生成 `intent_key` 时按稳定顺序排列，使同一组条件不因语序不同产生不同键：

- 同一条件类型换取值，可以是不同意图，例如小企业销售团队与房地产中介。
- 增加或删除一个真正改变候选集合、比较维度或结论的条件，可以是不同意图。
- 条件集合完全相同，只换 `best / recommended / which`、改写语序或调换条件顺序，仍是同一意图，不能重复占配额。
- 句式重复但人群、场景、约束或比较对象的条件集合不同，不机械判错；二遍 review 要判断答案是否仍会高度雷同。
- 多个条件共同限定一个购买任务，仍是一题一意图；如果回答必须分别完成两个可独立成立的任务，就是复合问题，必须拆分。

品牌边界使用完整的配置名单：`brand_name + product_name + aliases + competitors + formal competitor aliases`。Generic 问题不得出现任一名称，也不得另行写入未配置的具体品牌；不能只检查主品牌名而遗漏产品名或缩写别名。程序会兼容驼峰、空格、连字符和下划线的机械变体；语义简称仍由品牌/竞品研究显式写入 aliases，未配置品牌实体由二遍语义 review 拦截。

同一问题簇只保留真正改变答案边界的变体，例如角色、预算、市场、团队规模、证据类型或决策阶段发生变化；只替换 `best/top/leading` 不算新意图。

实际有 5 条 Branded Comparison 时使用“3+2”结构：三个正式竞品各有至少一条只命中该竞品的独立一对一题；另外两条询问 Topic 关键选型因素，或同时比较两个及以上正式竞品。少于 5 条时不人为补足比较数量。低可比竞品始终受 `allowed_dimensions` 限制。

`target_audiences` 是可用条件来源，不设每个受众的最低题数或占比。整批应避免明显只服务单一受众，但不能为了平均覆盖而生成弱商业意图题；`audience_role` 使用规范化标识，便于二遍 review 看实际分布。

初稿完成后启动独立二遍 review，再填写 `quality_checks`。逐题确认 `topic_aligned / category_visible / commercial_intent`：先检查问题要求 AI 选择的对象是否仍属于 Topic 的同一购买集合，再检查 Generic 的题目是否明确要求具体品牌/供应商/平台/产品候选，而不是只可能在回答中顺带出现。只命中宽泛相关词不代表对齐：OEM/ODM 电池制造商不能漂成热管理厂商、集装箱式储能系统商或大型储能项目合作伙伴。品牌总体评价基准题还要逐 Topic 检查恰好 1 条、严格匹配模板，并且只出现监控品牌。二遍还要同时查批内与近期其他品牌题库：实体归一后完全重复可直接修复；词面相似只用于召回候选，不得脱离条件取值硬删。

## 4. 五段式字段隔离

| 字段 | 用途 | 可进入监测 |
|-|-|-|
| `user_question` | 真实用户会直接向 AI 提出的自然问题 | 是，根问题唯一来源 |
| `standalone_rewrite` | 消解指代和上下文后的独立问题 | 仅用于追问回放 |
| `retrieval_rewrite` | 搜索或检索使用的短语 | 否 |
| `evidence_query` | 查询价格、案例、合规、评价等证据 | 否 |
| `title_seed` | 内容选题或标题输入 | 否 |

不得把检索短语或标题通过加问号伪装成 `user_question`。

每条 `user_question` 同时生成准确、非空的 `zh_translation`，供销售和业务快速复核意图。中译不进入海外 AI 平台采样，不代替英文自然度判定。

## 5. 海外平台适配

- 默认用同一条 canonical `user_question` 跨平台采样，保证 ChatGPT、Perplexity、Gemini、Google AI Mode/AI Overviews 和 Copilot 可比。
- 仅当用户明确研究平台措辞差异时生成 `platform_variant`；变体不得改变核心意图、实体或约束。
- Perplexity 的证据倾向不等于每题都追加 “with sources”；只有引用研究场景才显式要求来源。
- Google AI Mode/AI Overviews 问题保持可独立检索；ChatGPT/Gemini/Copilot 仍需自然对话，不写系统指令。
- 按 `en-US / en-GB / en-AU` 等 locale 处理拼写和市场术语；价格、法规和可用性没有证据时不写具体断言。

## 6. 购买动作、风险与价格条件

试用、购买或采用只作为 Decision 的选择动作，不能要求 AI 执行现实操作：

- 可用：`Which AI visibility tool should I choose for a small SEO agency?`
- 不可用：`Buy AI visibility tool subscription.`

限制或风险条件必须中性，不预设品牌有缺陷：

- 可用：`What are the main limitations of Peec AI for enterprise teams?`
- 不可用：`Why is Peec AI unreliable?`

价格不设固定题量。只有价格、采购或预算确实影响本次选型时才生成：

- 有公开价格或订阅套餐：可问价格、套餐和预算适配。
- 定制报价或必须联系销售：改问收费方式、报价影响因素或总成本。
- 无法确认目标市场的合理预算量级：不写具体金额，只询问预算适配或成本结构。
