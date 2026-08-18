# 海外 GEO 售前问题库契约

## 默认模式

`presales_diagnostic` 默认生成恰好 50 条问题：Generic 40 条、Branded 10 条。调用方提供其他总题量或问题类型配额时以调用方为准，但必须在生成前冻结并在交付时复核。

### 商业意图不设数量配额

`funnel_intent` 只允许 `recommendation / comparison / decision`，整批三类都必须出现，但不限制各自数量，也不要求 Generic × 三意图、Branded × 三意图的六格数量。意图按答案终点分：Recommendation 要候选，Comparison 要候选间差异与取舍，Decision 要最终选择具体候选。Generic 不出现配置品牌实体，但答案必须命名具体品牌/供应商/产品候选。

总数为 49、Generic/Branded 数量不符、任一商业意图完全缺失、用重复题补齐或生成失败后静默少题，整批均不得进入采集。

### 六种组合的答案目标

- Generic Recommendation：给具体品牌/供应商/产品候选名单或推荐，不能只给定义、标准或采购知识。
- Generic Comparison：先命名具体候选，再给候选间差异和明确取舍；只比较材料、品类或方案不合格。
- Generic Decision：从具体候选中给明确品牌/供应商/产品选择或最终适配结论。
- Branded Recommendation：判断品牌在具体场景是否值得纳入候选，并说明理由、条件或风险。
- Branded Comparison：与正式竞品做中性、有边界的比较。
- Branded Decision：询问是否应该选择、购买或采用本品牌。

这些是生成和语义 review 规则，不是六格配额，也不新增字段或统计维度。

`funnel_intent` 的正式值为 `recommendation / comparison / decision`。`awareness / informational / 了解` 只属于 v2 历史题库；新生成的 v3 题库不得使用。

## Generic 与 Branded

`generic`：

- 不出现客户品牌、产品名、已配置 aliases 或竞品名
- 可以使用 `brands / manufacturers / suppliers / platforms / products` 等通用候选词；禁止的是具体品牌实体，不是“品牌”这个类别词
- 测试 AI 是否自然提及具体品牌及竞品；合理答案必须命名品牌/供应商/产品候选
- 必须出现可识别的目标品类或品类下产品词，可以包含角色、场景和约束
- 只会回答材料差异、是否值得采用、评估标准或购买流程的题不合格，即使标成 Comparison 或 Decision

`branded`：

- 必须明确出现客户品牌
- 用于品牌认知、适用性、比较、价格、风险和采购验证
- 竞品比较保持中性；不得把品牌题天然放在答案顺序第一等同于推荐胜出

### 每 Topic 一条品牌总体评价基准题

标准化基准题直接放在 `branded`，不新增第四种意图或新角色字段。每个 Topic 恰好 1 条：

- 公司：`Evaluate the {品类} company {品牌名} on {主题}`
- 产品：`Evaluate the {品类} product {品牌名} on {主题}`

固定填写：`question_type=branded`、`funnel_intent=decision`。它计入 Branded 和 Decision 的实际数量；同批仍须另外覆盖 Recommendation 与 Comparison。该基准题不是唯一情绪样本：其余 Branded 商业题仍可形成品牌评价，下游情绪指标使用全部入选有效且提及监控对象的回答。`category_label` 应是自然品类名，不要把 `manufacturer/supplier` 再与 `company` 叠成 `manufacturer company`。例如：

- `Evaluate the CRM software company HubSpot on small business sales management`
- `Evaluate the men's fragrance product Bleu de Chanel on fragrance gift shopping`
- `Evaluate the rechargeable battery company BPI on Rechargeable battery manufacturers for OEM/ODM procurement`

这条是固定监测句式，不受普通问句开头规则限制；除此之外不能用 `Evaluate the...` 伪装成普通商业题。校验时除大小写和连续空格外逐字匹配，不自行加问号或句号。若 Topic 数超过 Branded 配额，配置本身失败，不能静默少生成。

实际生成 5 条 Branded Comparison 时，3 条分别覆盖三个正式竞品，每个竞品至少一条独立一对一题；另外 2 条围绕 Topic 关键选型因素，或同时比较两个及以上正式竞品。不得用五条近义一对一问题机械填满数量。少于 5 条时不为了凑 3+2 而增加比较配额，但仍遵守竞品比较边界。

## 默认覆盖要求

- v3 不生成额外的角度意图字段。价格、预算、总成本、限制、风险和替代对象只有在改变购买选择时才作为条件进入 Recommendation、Comparison 或 Decision；不设任何角度配额。
- 多子品类或多产品广度 Topic 按整批建立覆盖矩阵；单题可只命中一个子品类、具体产品或组合场景，不要求逐题复述 Topic 的全部范围。
- 自然度不要求复刻用户逐字问法，只要求形成真实、可回答的购买请求。不得为制造题目差异编造低频条件。
- `user_question` 不设固定词数上下限；长度只接受自然度、单意图和必要条件约束。
- 至少 3 个用户角色、3 个使用场景、2 类约束条件。
- `best / top / recommended / which / how to choose` 都是允许的商业问法，不设硬比例；整批过度集中时只提醒复核是否重复测量同一意图。
- 每个问题簇原则上不超过 3 条；超过时必须证明答案边界不同。
- `target_audiences` 是条件来源，不设每个受众的题数下限；覆盖情况由整批意图多样性复核。
- 价格条件不设固定最低配额。有公开价格时可问价格、套餐和预算适配；定制报价时问收费方式、报价因素或总成本；无法校准预算量级时不写具体金额。

## JSON 输入契约

### 冻结竞品集合

正式售前链路将竞品研究产出原样放入 `config.competitor_selection`。该对象必须 `status=frozen`、`selection_count=3`，且恰好包含 3 个 `formal_competitors`：

```json
{
  "status": "frozen",
  "selection_count": 3,
  "formal_competitors": [
    {
      "name": "Profound",
      "aliases": ["Profound AI"],
      "comparability_tier": "direct",
      "comparison_policy": {
        "mode": "standard_evidence_based",
        "allowed_dimensions": ["AI answer monitoring", "reporting"]
      }
    },
    {
      "name": "Adjacent Example",
      "aliases": [],
      "comparability_tier": "adjacent",
      "comparison_policy": {
        "mode": "neutral_shared_dimensions_only",
        "allowed_dimensions": ["AI answer monitoring"]
      }
    },
    {
      "name": "Fallback Example",
      "aliases": [],
      "comparability_tier": "fallback",
      "comparison_policy": {
        "mode": "neutral_shared_dimensions_only",
        "allowed_dimensions": []
      }
    }
  ]
}
```

`direct` 可做标准中性比较。`adjacent/fallback` 的比较题只能使用 `allowed_dimensions`；列表为空时只做品类关系或使用场景澄清。任何低可比候选都禁止“谁更好”、全面优劣、绝对排名或全面替代性问法。`competitors` 字符串列表只为旧题库兼容；有冻结对象时以 `formal_competitors` 为正式集合。

校验脚本接受：

```json
{
  "schema_version": "overseas-geo-question-bank/v3",
  "config": {
    "brand_name": "Peec AI",
    "product_name": "Peec AI Platform",
    "brand_object_type": "company",
    "category_label": "AI search visibility",
    "aliases": ["Peec"],
    "topics": [
      {
        "topic_id": "ai-search-visibility-platforms",
        "topic": "AI search visibility platforms for marketing teams"
      }
    ],
    "target_audiences": ["seo_agency", "enterprise_marketing"],
    "competitors": ["Profound", "Otterly AI"],
    "expected_total": 50,
    "quotas": {
      "question_type": {"generic": 40, "branded": 10}
    },
    "category_expression_set": {
      "core_terms": [
        "AI search visibility",
        "AI visibility",
        "generative engine optimization"
      ],
      "product_terms": [
        "GEO platform",
        "AI answer monitoring"
      ],
      "placeholder_blacklist": [
        "specialized product suppliers",
        "product providers",
        "solution vendors"
      ]
    },
    "min_distinct_counts": {"audience_roles": 3, "scenarios": 3, "constraints": 2},
    "professional_term_assessment": {
      "status": "completed",
      "decisions": [
        {
          "concept": "geo",
          "source": "input_explicit",
          "decision": "required",
          "reason": "The audience explicitly includes GEO agencies."
        }
      ]
    },
    "required_term_coverage": {
      "geo": {
        "label": "generative engine optimization (GEO)",
        "terms": ["generative engine optimization", "GEO"],
        "expanded_form": "generative engine optimization",
        "acronym": "GEO",
        "context_terms": ["AI search", "AI-generated answers", "generative search"],
        "min_total": 3,
        "min_generic": 1,
        "min_branded": 1,
        "min_expanded": 1,
        "min_acronym": 1
      }
    },
    "excluded_categories": ["social listening", "media monitoring", "SERP rank tracking"]
  },
  "questions": []
}
```

`schema_version` 是新产物必填项。v3 必须提供 `category_expression_set`、`professional_term_assessment` 和 `required_term_coverage`（术语配额可为空对象）。每个 `required` 决策必须对应一个配额概念；不适用的候选用 `excluded` 并写明理由。`decisions=[]` 时必须写 `no_required_terms_reason`。v2 和无 schema 的历史题库仍可校验，但会显式返回 legacy warning；它们不是新题生成模板。

v3 同时必须提供 `brand_object_type=company|product` 和 `category_label`。`category_label` 必须能命中 `category_expression_set` 的品类表达，用于确定性生成每 Topic 的固定品牌总体评价基准题。

`category_expression_set` 是逐题品类落地的确定性词表：

- `core_terms` 放品类原词与自然变体。
- `product_terms` 放无需再重复品类原词也能明确归类的产品词。
- `placeholder_blacklist` 放跨行业空占位词；命中即失败，即使同题还出现了品类词也要删掉占位表达。

不要把只表示采购动作的 `OEM/ODM`、`supplier`、`manufacturer` 单独当作品类词；它们无法告诉读者采购的是什么。

`aliases` 为可选字符串数组，用于配置品牌缩写、产品别名或常见写法。程序将 `brand_name / product_name / aliases / competitors / formal competitor aliases` 作为 Generic 品牌边界硬门，并自动兼容驼峰、空格、下划线和连字符变体，如 `CreativeHit / Creative Hit`。语义简称如 `Peec` 仍必须显式写入 aliases，避免把普通英文词误判为品牌。

`target_audiences` 为规范化后的目标受众字符串数组。程序汇总各受众覆盖供二遍 review 使用，但不设置逐受众最低题数或最高占比。

`required_term_coverage` 只配置输入明确出现或经品类判断确认适用的专业术语。它检查规范词面是否真实进入问题，不把 `AI search visibility` 等自然同义表达自动算成 GEO/AEO 覆盖。默认 50 题中，输入明确出现的术语建议 `min_total=3`；相关但未明确输入的核心术语建议 `min_total=2`。每个问题仍必须自然、单意图，不能为了达标堆叠术语。

如果使用容易歧义的缩写，配置 `expanded_form / acronym / context_terms`：

- 至少一条问题同时出现全称与缩写。
- 其他缩写问题必须出现任一 `context_terms`，确保独立采样时不会把 GEO 理解成 geography、把 AEO 理解成其他行业缩写。
- 术语覆盖必须同时分布到 Generic 与 Branded；只在解释性通用题出现术语，不能验证品牌与品类的关联。

每条问题至少包含：

- `question_id`
- `topic_id`：必须命中 `config.topics`，供逐题检查是否围绕所属 Topic
- `intent_key`：由所属 Topic 和规范化条件集合组成的稳定意图标识；条件集合可为空、单一或复合，多条件按稳定顺序编码；同一组条件不得因措辞或顺序不同生成不同键，相同 `intent_key` 不得重复占配额
- `question_type`
- `funnel_intent`
- `decision_stage`：v3 只允许 `shortlist / evaluation / purchase / implementation / review`，不再使用 `awareness`
- `cluster`
- `audience_role`
- `scenario`
- `constraint`
- `evidence_need`
- `user_question`
- `zh_translation`：`user_question` 的准确非空中译，仅用于人员理解与复核
- `standalone_rewrite`
- `retrieval_rewrite`
- `evidence_query`
- `title_seed`
- `monitoring_prompt`
- `quality_checks`

v3 的 `quality_checks` 必含并全部为 `true`：`natural / standalone / answerable / single_intent / category_aligned / neutral_premise / monitoring_field_valid / topic_aligned / category_visible / commercial_intent`。后三项必须在独立二遍语义 review 后填写，不能随初稿默认置真。品牌总体评价基准题虽然是固定探测句，也按 Decision 处理并保留 `commercial_intent=true`，不另造例外字段。
