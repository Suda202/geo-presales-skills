# 智能体语义任务契约

每个结果都使用以下统一信封。字段名和枚举是程序接口，必须保持英文；说明和报告内容全部使用中文。

```json
{
  "protocol_version": "1.0",
  "run_id": "从 task 原样复制",
  "task_id": "从 task 原样复制",
  "kind": "从 task 原样复制",
  "task_digest": "从 task 原样复制",
  "status": "completed",
  "output": {},
  "issues": []
}
```

`status` 只允许 `completed`、`partial` 或 `cannot_complete`。仅当任务中 `blocking=false` 时允许使用 `cannot_complete`。

## `sentiment_batch`：情绪批处理

只处理任务中列出的 item ID。打开每个 `answer_ref` 对应的资源文件，返回回答原文中的精确子串。

```json
{
  "items": {
    "q01-r01": {
      "label": "positive",
      "score": 0.6,
      "confidence": 0.88,
      "evidence": [
        {"quote": "回答原文中的精确片段"}
      ],
      "flags": []
    }
  }
}
```

执行规则：

- `label` 只允许 `positive`、`neutral`、`negative`。
- `score` 范围为 `-1..1`：大于 `0.1` 为正向，`[-0.1, 0.1]` 为中性，小于 `-0.1` 为负向。
- 判断回答对监测对象的总体评价，不使用提问语气代替回答情绪。
- 不把“竞品在某方面更强”“仍需核验”或“独立证据不足”单独当作目标品牌负向；结合全文主导评价判断正向、中性或负向。
- 禁止在该任务中处理顺序、提及、竞品、来源、翻译、指标或报告文案。
- 如果脚本生成 review task，只重新判断其中列出的 item ID。

## `source_classification_batch`：未知来源分类

根据 host、示例 URL、标题和摘要，对同一个稳定 host 只分类一次。

```json
{
  "items": {
    "S-001": {
      "source_type": "media_review",
      "confidence": 0.84,
      "basis_fields": ["host", "title"],
      "flags": []
    }
  }
}
```

禁止返回 `brand_official` 或 `competitor_official`，官网分类由程序负责。证据不足时优先返回 `other`，禁止强猜。置信度低于任务阈值时，脚本会自动降级为 `other`。

## `brand_expression_themes`：品牌表达主题

只使用任务中提供的证据编号。

```json
{
  "positive": [
    {
      "label": "上手门槛较低",
      "summary": "多条已校验证据认可其配置和使用过程较清晰。",
      "evidence_ids": ["E-q01-r01-01", "E-q08-r01-01"],
      "confidence": 0.87
    }
  ],
  "risk": []
}
```

禁止填写 `support_count`，该值由程序根据不同回答编号计算。正向主题只能引用正向证据；风险主题只能引用负向或中性证据。证据不足时返回空数组，禁止补写主题。

## `report_module`：报告模块分析

先读取 `fact_pack_ref`。输出一至五条分析观点，所有数字必须使用 fact token。

```json
{
  "module_id": "M01",
  "title": "数据总览",
  "points": [
    {
      "text_template": "监测对象在有效发现类问题回答中的提及率为 {{fact:overview.target.mention_rate}}。",
      "refs": ["fact:overview.target.mention_rate"]
    }
  ],
  "conclusion": {
    "text_template": "共有 {{fact:coverage.valid_answers}} 条有效回答，结论适用于当前统计范围。",
    "refs": ["fact:coverage.valid_answers"]
  }
}
```

执行规则：

- `text_template` 中的 token 必须与 `refs` 完全一致。
- token 之外禁止直接写数字。
- 禁止从“未观察到引用”推断页面不存在，也禁止推断市场需求、搜索量、流量、转化或保证提升。
- M02 必须使用“平均提及位置”等统一表达，禁止称为语义推荐排名；只有后端决胜回答胜率可称为竞品胜率，不得另写总体胜率，优劣势只引用正面对比证据。
- M03 页面机会只使用后端 `page_opportunities`：候选必须来自主题/Tag 相关官网页面扫描；页面相关性与 Citation 状态分开表达，具体修改落到能力、Claim 或问题缺口，不把 Attribute/Prompt Gap 暴露为客户字段。
- M05 只描述脚本提供的分档，禁止重新分类。
- M07 只解释后端 `platform_consistency` 中的整体与主题结果，禁止拼接不同市场、语言、采集窗口或 Prompt 的结果，也禁止自行计算一致率、共识阈值和平台原因；Attribute 只作其他模块或跨模块解释证据，不单独输出跨平台状态。
- M08 只解释后端 `market_perception_diagnostics`，分析主题下的选择标准是否覆盖问题关键属性、是否与品牌预设差异点契合；禁止从原始回答重判购买标准或写成品牌提及、排名、Visibility、竞品输赢原因和归因。

## `next_actions`：下一步行动

为脚本给出的每个 `direction_id` 恰好生成一条行动，并保持 `source_module` 不变。

任务资源中的 `route_type`、`verification_signals`、`page_opportunity_ids`、`target_surfaces`、`geo_team_delivery`、`client_action`、`client_inputs` 与 `confirmed_client_owner` 是内部控制字段，不原样暴露给客户。它们分别约束问题路由、复测信号、页面机会、内容载体和责任分工。

```json
{
  "summary": {
    "text_template": "优先处理统计证据明确支持的薄弱方向。",
    "refs": []
  },
  "actions": [
    {
      "direction_id": "D-citation-evidence",
      "source_module": "M03",
      "title": "补强可引用的官网证据",
      "evidence_template": "品牌官网引用份额为 {{fact:citations.official_share}}。",
      "expected_impact_template": "同口径复测时观察目标页面是否进入引用，以及品牌提及是否变化。",
      "action": "我方生成官网 Blog 与第三方比较内容并提供产品页修改清单；客户相关团队确认产品事实并修改上线产品页。",
      "refs": ["fact:citations.official_share"]
    }
  ]
}
```

禁止新增行动方向、渠道、发布数量、频率、期限或效果承诺。所有数字证据必须使用 fact token。不得看到低指标就自行判断内容不足；不得把非 Blog 官网写成我方直接修改；不得把产品规格、价格、政策、集成或服务承诺全部塞进 Blog。`expected_impact_template` 只写可见度、引用、品牌表达或事实准确性复测信号，不写 AI Referral Traffic、线索或成交归因。
