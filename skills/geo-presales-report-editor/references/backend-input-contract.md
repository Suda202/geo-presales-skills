# 后端统计输入契约（v2）

## 输入原则

生产脚本接受一个 `overseas-geo-backend-report-input/v2` JSON。后端是指标、分母、诊断状态和证据范围的事实拥有者；编辑侧只校验和表述，不从逐条回答重新聚合。

## 公共字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `schema_version` | string | 是 | 固定 `overseas-geo-backend-report-input/v2`。 |
| `brand_name / corp_name` | string | 是 | 目标品牌与客户主体。 |
| `product_name` | string/null | 否 | 产品或业务名称。 |
| `topics` | array | 是 | 恰好 3 项；每项含内部字段 `topic_id / topic_type / topic`，客户文案统一称“主题”。 |
| `tags` | array | 推荐 | 正在新增的 Tag 字段；每项含 `tag_id / tag / topic_ids`，用于在主题下承载更细的分析分组。缺失时继续只用主题。 |
| `target_attributes` | array | 是 | 来自评测集同一 Case；每项至少含 `attribute_id / attribute`，并通过 `topic_ids`、`tag_ids` 或两者关联。只是采集前目标，不是客户可见一等字段。 |
| `market / language / task_id` | string | 是 | 市场、语言和任务 ID。 |
| `batch_id` | string | 否 | 未提供时使用 `task_id`。 |
| `overview` | object/JSON string | 是 | 后端已算好的总览。 |
| `competitor` | object/JSON string | 是 | Discovery 范围内的提及、声量与平均提及排名。 |
| `citation` | object/JSON string | 是 | 引用聚合；必须含 Discovery 主样本范围。 |
| `brand_expression` | array/JSON string | 是 | Sentiment 回答中的目标品牌表达证据。 |
| `category_actions` | object/JSON string | 是 | 后端已经分档的问题。 |
| `question_details` | array/JSON string | 是 | 不含回答全文的问题明细。 |
| `attribute_diagnostics` | array/JSON string | 是 | 基于 Validation 与配对 Discovery 得出的属性结果。 |
| `comparison_outcomes` | array/JSON string | 是 | Competitor 的逐题胜者、平局、强度与证据。 |
| `competitor_comparison_summary` | object/JSON string | 推荐 | 按正式竞品汇总的决胜回答胜率、胜负/平局/无法判断计数及有正面对比证据的优劣势；缺失时 M02 不生成胜率和优劣势结论。 |
| `market_perception` | array/JSON string | 是 | 各主题的选择标准与品类框架。 |
| `market_perception_diagnostics` | object/JSON string | 推荐 | 购买框架与预设关键差异点的正式对齐结果；缺失时 M08 降级，报告侧不重新分析原始回答。 |
| `accuracy_findings` | array/JSON string | 是 | 官方真值、回答主张、准确性状态与错误来源。 |
| `platform_consistency` | object/JSON string | 推荐 | 后端基于同市场、同语言、同采集窗口和匹配 Discovery Prompt 形成的跨平台一致性正式结果；缺失时 M07 降级，报告侧不重算。 |
| `page_opportunities` | object/JSON string | 推荐 | 后端先按主题/Tag 扫描官网相关页面，再结合 Attribute/Prompt Gap、Citation、AI Gap 严重度和页面价值形成的正式页面机会；缺失时不从引用页面补推全站机会。 |
| `action_context` | object/JSON string | 推荐 | 后端确定的行动路由、目标载体、责任分工和复测信号；缺失时报告行动降级为空。 |

### Citation 样本范围

```json
{
  "sample_scope": {
    "primary_diagnostic_intent": "discovery",
    "included_question_ids": ["Q-COV-D01"],
    "included_answer_ids": ["A-COV-D01-01"]
  }
}
```

`average_first_position` 是后端内部兼容字段；客户文案、CSV 字段说明和校验统一显示为“平均提及排名”。

主要引用生态必须用 Discovery。其他意图的引用如需展示，另建有明确 label 的分组，不能混进主要百分比。

### Attribute 诊断

```json
{
  "attribute_id": "PEC-A01",
  "status": "strength | opportunity | objection | unknown",
  "validation_question_ids": ["Q-COV-V01"],
  "paired_discovery_question_ids": ["Q-COV-D01"],
  "evidence_refs": ["A-COV-V01-01", "A-COV-D01-01"]
}
```

`target_attributes` 不能直接转成结论。只有 `attribute_diagnostics` 能描述实际关联：知道且主动推荐为 Strength，知道但不主动推荐为 Opportunity，否定或错误关联为 Objection，证据不足为 Unknown。Attribute 通过主题或 Tag 承载；客户报告可按主题/Tag 组织，但不新增独立 Attribute 模块、上传字段或跨平台状态。

### 竞品与准确性

`comparison_outcomes.outcome` 只允许 `target_wins / competitor_wins / tie / unclear`，并保存 `decisiveness` 与证据。不得映射成 Sentiment。

正式竞品比较汇总使用：

```json
{
  "sample_scope": {"primary_diagnostic_intent": "competitor"},
  "pairs": [
    {
      "comparison_id": "CMP-001",
      "competitor_name": "Leader",
      "total_valid_answers": 50,
      "decisive_answers": 39,
      "target_wins": 29,
      "competitor_wins": 10,
      "ties": 7,
      "unclear": 4,
      "target_decisive_win_rate": 0.7435897436,
      "advantage_themes": [
        {
          "theme_id": "CMP-ADV-001",
          "dimension": "reporting",
          "finding": "目标品牌的报告更容易使用",
          "support_count": 2,
          "evidence_refs": ["A-C01", "A-C02"]
        }
      ],
      "disadvantage_themes": []
    }
  ]
}
```

- 唯一正式胜率为 `target_wins / (target_wins + competitor_wins)`；`decisive_answers` 必须等于双方胜场之和。
- `total_valid_answers` 必须等于双方胜场、`ties` 与 `unclear` 之和。平局和无法判断保留为样本边界，但不进入胜率分母。
- 没有决胜回答时 `target_decisive_win_rate` 必须显式为 `null`，不能写 0。
- 不传总体胜率字段。正式汇总的竞品集合必须与 `comparison_outcomes` 中的正式竞品集合一致。
- `advantage_themes / disadvantage_themes` 只保存明确正面对比主题；每项必须有维度、结论、正整数支持样本和非空回答证据引用。

`accuracy_findings` 应保存 `official_truth / answer_claim / status / error_source / official_source_url`；编辑侧不自行检索真值。

### 品类认知/购买框架

```json
{
  "sample_scope": {"primary_diagnostic_intent": "market_perception"},
  "findings": [
    {
      "finding_id": "MP-001",
      "topic_id": "coverage",
      "attribute_id": "ATTR-001",
      "alignment_status": "included | missing | conflicting | insufficient",
      "intended_differentiator": "multi-engine visibility measurement",
      "market_criteria": ["reporting", "pricing"],
      "finding": "当前购买框架未把多平台覆盖作为主要标准",
      "support_count": 2,
      "evidence_refs": ["A-MP01", "A-MP02"]
    }
  ]
}
```

- `topic_id` 与 `attribute_id` 必须引用同一 Case 中已有且相互映射的主题对象和 Attribute。
- `included / missing / conflicting` 必须有市场标准、正整数支持样本和非空证据，支持样本数不得超过唯一证据引用数；`insufficient` 可为零样本与空证据。
- 状态由后端根据 Market Perception 样本正式给出。报告侧不得从 `market_perception` 原始结果重新归纳、匹配或自判。
- 该对象只回答市场购买框架是否包含品牌预设差异点，不回答品牌 Visibility、直接竞品输赢或任何流量/成交归因。

### 跨平台一致性

```json
{
  "sample_scope": {
    "primary_diagnostic_intent": "discovery",
    "comparison_unit": "matched_prompts",
    "market": "US",
    "language": "en-US",
    "collection_window": "2026-08-01/2026-08-07"
  },
  "findings": [
    {
      "consistency_id": "PC-001",
    "scope_type": "overall | topic",
      "scope_id": "overall",
      "comparable_platform_count": 3,
      "mention_consistency": "consistent_present | consistent_absent | mixed | insufficient",
      "position_consistency": "consistent | mixed | not_applicable | insufficient",
      "consensus_strength": "strong | moderate | weak | insufficient",
      "platform_results": [
        {
          "platform": "ChatGPT",
          "mention_rate": 0.35,
          "average_first_position": 2.8
        }
      ],
      "evidence_refs": ["Q-D01"]
    }
  ]
}
```

- 只比较已对齐市场、语言、采集窗口和 Prompt 的 Discovery 样本；至少两个平台可比。
- 正式分析层级只包括整体与主题：`overall` 的 `scope_id` 固定为 `overall`，`topic` 必须引用已有 `topic_id`。不接收 Attribute 级 finding。
- `mention_consistency` 与 `position_consistency` 分开统计。所有平台均未提及时，位置状态必须为 `not_applicable`。
- `consensus_strength`、一致性阈值和有效样本判断由后端负责；编辑侧不得从 `platform_results` 重新计算。
- 主题的提及或位置状态为 `mixed` 时，可正式解释为该主题的跨平台判断尚未稳定。
- Attribute 仍保留在 `attribute_diagnostics` 与 `market_perception_diagnostics`，可作为主题结论的解释证据，但不拥有独立跨平台状态。
- 一致性只说明可比平台是否给出稳定结果，不等于全网共识、长期趋势或确定因果。
- 新任务应提供该对象；为兼容已有 v2 批次，缺失时允许 M07 明确降级。

### 行动路由与责任边界

```json
{
  "directions": [
    {
      "direction_id": "ACT-001",
      "direction": "补强第三方对关键能力的独立佐证",
      "state": "品牌能力已被识别，但外部验证不足",
      "posture": "先补可信来源，再观察可见度变化",
      "key_evidence": "属性诊断与引用结构已由后端确认",
      "action_template": "形成官网 Blog 解释内容与第三方比较内容",
      "route_type": "trust_gap",
      "verification_signals": ["citation", "visibility"],
      "page_opportunity_ids": ["PAGE-001", "PAGE-002"],
      "target_surfaces": ["official_blog", "third_party_source", "non_blog_official_page"],
      "geo_team_delivery": "生成官网 Blog 与第三方比较内容，并提供产品页修改清单",
      "client_action": "修改并上线产品页",
      "client_inputs": ["最新产品能力清单", "可公开客户案例"],
      "confirmed_client_owner": "产品团队"
    }
  ]
}
```

- `route_type` 只允许 `comprehension_gap / trust_gap / accuracy_correction / objection_reframe / strength_amplification`。这是后端基于配对诊断、准确性、品牌表达与引用证据给出的正式问题类型；报告侧不得从单个低指标自行推断。
- 兼容旧 v2 批次时 `route_type` 可缺失；新方向若提供 `route_type`，必须同时提供一个或多个 `verification_signals`。验证信号只允许 `visibility / citation / brand_expression / accuracy`。
- `trust_gap` 必须包含 `third_party_source`；`accuracy_correction` 必须包含 `accuracy` 验证信号。所有正式路由都必须指向至少一个公开载体，不能只停留在内部材料。
- `target_surfaces` 只允许 `official_blog / third_party_source / non_blog_official_page / internal_material`。Blog 或第三方方向必须给 `geo_team_delivery`；非 Blog 官网方向必须给 `client_action`；依赖企业内部材料时必须列出 `client_inputs`。
- 诊断覆盖整个官网和外部信源，但我方直接交付只限官网 Blog 与约定第三方内容。非 Blog 官网正式页面由我方提供修改清单或建议文案、客户修改上线；产品规格、价格、政策、集成和服务承诺不能全部改写成 Blog。
- `confirmed_client_owner` 只有责任部门已由后端确认时才提供；未确认时客户文案统一写“客户相关团队”。
- 复测只验证行动是否在同口径可见度、引用、品牌表达或事实准确性数据中出现；不接入 AI Referral Traffic、线索或成交归因。

### 官网页面机会

```json
{
  "sample_scope": {
    "scan_scope": "topic_or_tag_relevant_official_pages",
    "coverage_status": "complete",
    "included_topic_ids": ["home_security"],
    "included_tag_ids": ["storage"],
    "candidate_page_count": 2
  },
  "items": [
    {
      "page_opportunity_id": "PAGE-001",
      "url": "https://example.com/support/local-storage",
      "page_type": "non_blog_official_page",
      "topic_id": "home_security",
      "tag_ids": ["storage"],
      "attribute_ids": ["ATTR-local-storage"],
      "prompt_gap_ids": ["Q-D01"],
      "relevance_status": "high",
      "citation_status": "cited",
      "citation_refs": ["CIT-001"],
      "ai_gap_severity": "high",
      "page_value": "high",
      "opportunity_state": "reinforce_cited",
      "priority": "high",
      "priority_score": 92,
      "finding": "页面已被引用，但对无需订阅和本地保存的表达仍可强化",
      "evidence_refs": ["Q-D01", "CIT-001"]
    },
    {
      "page_opportunity_id": "PAGE-002",
      "url": "https://example.com/blog/continuous-recording-guide",
      "page_type": "official_blog",
      "topic_id": "home_security",
      "tag_ids": [],
      "attribute_ids": [],
      "prompt_gap_ids": ["Q-D02"],
      "relevance_status": "high",
      "citation_status": "uncited",
      "citation_refs": [],
      "ai_gap_severity": "medium",
      "page_value": "high",
      "opportunity_state": "citation_gap",
      "priority": "medium",
      "priority_score": 78,
      "finding": "页面与持续录像问题高度相关，但尚未进入引用",
      "evidence_refs": ["Q-D02"]
    }
  ]
}
```

- `scan_scope` 只允许 `topic_relevant_official_pages / topic_or_tag_relevant_official_pages`；禁止把已引用页面子集写成官网候选范围。`coverage_status` 为 `complete / partial`，报告必须保留扫描边界。
- 主题或主题+Tag 负责划定候选页面范围；具体 `attribute_ids / prompt_gap_ids` 至少有一类非空，用于证明页面要强化哪个能力、Claim 或问题缺口。它们是内部证据，对外不展示 Attribute/Prompt Gap 字段。
- `relevance_status` 与 `citation_status` 是两条独立轴，四象限固定映射为：`high+cited → reinforce_cited`、`high+uncited → citation_gap`、`low+cited → avoid_forcing`、`low+uncited → ignore`。
- `cited` 必须有 `citation_refs`，`uncited` 必须为空。未引用不等于低相关；已引用也不等于值得为当前主题/Tag 修改。
- `ai_gap_severity / page_value / citation_status / relevance_status` 由后端综合成 `priority`，可同时提供 `priority_score`（0..100）。报告侧不手算公式或改优先级；低相关未引用必须 `none`，低相关已引用不能设为中高优先级。
- `page_type` 只分官网 Blog 与非 Blog 正式页面。行动引用页面机会时只能引用高相关页面，并且 `target_surfaces` 必须覆盖对应页面类型；执行责任继续服从前述权限边界。
- 缺失 `page_opportunities` 时，M03 仍可分析现有引用结构，但不得声称已经完成全站页面机会扫描，也不得从 `brand_official_pages` 推断未引用页面。

## v1 兼容

脚本仍可读取旧 v1 `core_topic` 输入以回放历史报告，但新任务一律使用 v2。v1 缺少独立 Attribute、竞品、品类认知和准确性结果时，报告不得补写这些结论。

## 后端归属

后端在传入前完成：有效样本筛选、六类意图分流、实体与平均提及排名、Visibility、逐竞品决胜回答胜率与正面对比主题、主题/Tag 承载的 Attribute 关联、Market Perception 对齐状态、Accuracy、Sentiment、引用样本范围、问题分档、匹配 Discovery Prompt 的整体/主题跨平台一致性状态、主题/Tag 范围内的官网页面机会，以及有证据的行动路由。编辑器不重算这些内容。
