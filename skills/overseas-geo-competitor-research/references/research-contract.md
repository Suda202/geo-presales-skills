# 竞品研究结果契约

## 输入

```json
{
  "topic": "AI 搜索可见性监测平台",
  "market": "US",
  "current_date": "2026-07-24",
  "target": {
    "name": "Peec AI",
    "product_name": "Peec AI",
    "official_domain": "peec.ai",
    "description": "面向营销团队的 AI 搜索可见性平台",
    "target_users": ["品牌营销团队", "SEO 团队"],
    "buying_motion": "SaaS 订阅",
    "market_position": "peer"
  },
  "known_competitors": [
    {
      "name": "Profound",
      "official_domain": "tryprofound.com",
      "aliases": ["Profound AI"]
    }
  ]
}
```

`known_competitors` 允许为空或包含一至三个用户候选。已提供项至少包含 `name`；官网未知时可留空，由自动研究补齐。为空时系统从零发现三个正式竞品。固定集合只有三个位置，超过三个应由上游表单阻止。

用户候选不是正式竞品结论：只有通过同一购买集合硬门槛的候选才能保留。未通过项进入 `provided_competitor_rejections`，系统自动搜索替代项，不要求业务补充。

## 研究结果

`research.json` 必须包含冻结输入的 `input_hash`、检索日期、证据池和候选池。

```json
{
  "input_hash": "从 input.json 原样复制",
  "researched_at": "2026-07-24",
  "evidence": [
    {
      "evidence_id": "EV-001",
      "url": "https://example.com/product",
      "title": "页面标题",
      "source_type": "official",
      "published_at": null,
      "accessed_at": "2026-07-24",
      "claims": ["候选仍在提供该产品", "产品面向企业营销团队"]
    }
  ],
  "candidates": [
    {
      "canonical_name": "Example",
      "official_domain": "example.com",
      "aliases": ["Example AI"],
      "source": "discovered",
      "activity_status": "active",
      "direct_substitute": true,
      "same_purchase_set": true,
      "market_position": "peer",
      "dimensions": {
        "sub_track": 5,
        "product_form": 5,
        "target_users": 4,
        "core_job": 5,
        "buying_motion": 4,
        "status_similarity": 4,
        "specialty_fit": 3
      },
      "evidence_bindings": {
        "activity_status": ["EV-001"],
        "direct_substitute": ["EV-001", "EV-002"],
        "same_purchase_set": ["EV-001", "EV-002"],
        "market_position": ["EV-002"],
        "sub_track": ["EV-001", "EV-002"],
        "product_form": ["EV-001"],
        "target_users": ["EV-001", "EV-002"],
        "core_job": ["EV-001", "EV-002"],
        "buying_motion": ["EV-001"],
        "status_similarity": ["EV-002"],
        "specialty_fit": ["EV-001", "EV-002"]
      },
      "evidence_ids": ["EV-001", "EV-002"]
    }
  ]
}
```

## 字段说明

`source_type` 只允许：

- `official`：候选官网、产品页、定价页或官方文档。
- `independent_review`：独立评测或用户评测平台。
- `market_report`：市场报告、分类榜单或研究机构材料。
- `news`：近期新闻或融资、产品状态报道。
- `directory`：可信产品目录，只能作为补充证据。

`market_position` 只允许：

- `leader`：有近期独立证据支持的同赛道头部。
- `peer`：市场成熟度、客户层级和购买方式与监测对象相近。
- `challenger`：在本次 Topic 或垂直场景中高度可替代的挑战者。
- `unknown`：证据不足，不能依靠该字段进入组合角色。

`dimensions` 每项使用 0–5 分。评分必须由证据支持：

- `sub_track`：细分赛道一致性。
- `product_form`：产品或服务形态一致性。
- `target_users`：目标用户与决策者重叠程度。
- `core_job`：核心任务和直接替代关系。
- `buying_motion`：价格层级、销售方式和采购路径相似度。
- `status_similarity`：公司或产品成熟度、客户层级和市场地位接近程度。
- `specialty_fit`：候选在本次 Topic 或垂直场景中的针对性。

`evidence_bindings` 必须把每个评分维度、当前活跃状态、直接替代关系、同一购买集合判断和市场地位绑定到候选自己的证据 ID。`same_purchase_set` 证据必须支持买家会在同一次选型中比较双方，不能只证明功能相似。市场地位绑定的证据必须是近 18 个月独立来源；当前活跃状态必须绑定近 30 天实际访问的候选官网证据。脚本只验证证据链是否闭合，智能体仍需确保页面内容确实支持对应判断。

`source` 可写 `user_provided` 或 `discovered`，但它只是研究提示。脚本以冻结输入中的名称、官网域名和别名重新识别来源，防止研究结果漏标或错标。来源不会绕过购买集合硬门槛。

## 同一购买集合硬门槛

候选只有同时满足以下条件，`same_purchase_set_eligible` 才为 `true`：

- `same_purchase_set=true` 且绑定了候选自己的证据。
- `activity_status=active` 且绑定近 30 天访问的候选官网证据。
- `sub_track >= 4`、`core_job >= 4`、`product_form >= 3`、`target_users >= 3`、`buying_motion >= 3`，并且每项有证据绑定。
- 候选不是目标品牌自身，名称和官网域名有效且不重复。

缺少字段或证据时按未通过处理；已提供但格式非法或超出 0–5 仍属于契约错误。未通过项可以保留在候选审计中，但不得进入 `formal_competitors`。合格候选少于三个时，研究智能体应自动扩大检索并再次执行 `finalize`，不能降级到相邻购买集合或返回业务复核状态。

## 自动选择顺序

通过硬门槛的用户候选先按输入顺序保留。剩余位置仅从其他 `same_purchase_set_eligible=true` 的候选中选择：

1. `leader_representativeness_verified=true` 的细分头部优先。
2. 其余按综合得分降序。
3. 名称只用于稳定打破同分。

头部是本 Topic 和目标市场下、且已通过同一购买集合门槛的细分品类头部，不按大行业知名度判断。市场地位永远不能覆盖购买集合门槛。

## 冻结输出

`competitor-selection.json` 在成功时固定包含三个 `same_purchase_set_eligible=true` 的 `formal_competitors`，且 `status` 固定为 `frozen`。每个正式竞品包括：

- `source`：`user_provided` 或 `discovered`。
- `same_purchase_set_eligible`：固定为 `true`。
- `limitations`：未达到更高等级的原因。
- `comparison_policy.mode`：`standard_evidence_based`。
- `comparison_policy.allowed_dimensions`：可生成比较题的共同且有证据维度。
- `comparison_policy.prohibited_claims`：禁止无证据的全面优劣、绝对排名和领先结论。

`provided_competitor_rejections` 保存未通过购买集合门槛的用户候选及原因。它们不能进入 Prompt 的正式竞品范围。

顶层 `selection_strategy` 必须明确输出：购买集合硬门槛、用户候选通过后优先保留、自动位置先按已验证细分头部再按分数的策略，以及 `from_scratch / verify_and_fill` 模式。

每个正式竞品和候选审计项同时输出 `leader_representativeness_verified`。研究文件自报 `market_position=leader` 但缺少合格近期独立证据时，该值为 `false`，不能获得头部优先级。
