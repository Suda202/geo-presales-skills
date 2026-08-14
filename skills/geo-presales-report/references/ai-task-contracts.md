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
      "text_template": "监测对象在有效通用回答中的提及率为 {{fact:overview.target.mention_rate}}。",
      "refs": ["fact:overview.target.mention_rate"]
    }
  ],
  "conclusion": {
    "text_template": "本批次共有 {{fact:coverage.valid_answers}} 条有效回答，结论只代表本次限定范围。",
    "refs": ["fact:coverage.valid_answers"]
  }
}
```

执行规则：

- `text_template` 中的 token 必须与 `refs` 完全一致。
- token 之外禁止直接写数字。
- 禁止从“未观察到引用”推断页面不存在，也禁止推断市场需求、搜索量、流量、转化或保证提升。
- M02 必须使用“首次出现顺序”等准确表达，禁止称为语义推荐排名。
- M05 只描述脚本提供的分档，禁止重新分类。

## `next_actions`：下一步行动

为脚本给出的每个 `direction_id` 恰好生成一条行动，并保持 `source_module` 不变。

```json
{
  "summary": {
    "text_template": "优先处理本批次证据明确支持的薄弱方向。",
    "refs": []
  },
  "actions": [
    {
      "direction_id": "D-citation-evidence",
      "source_module": "M03",
      "title": "补强可引用的官网证据",
      "evidence_template": "品牌官网引用占原始引用的 {{fact:citations.official_share}}。",
      "expected_impact_template": "让关键一方事实更容易被识别、提取和引用。",
      "action": "检查现有官网页面，完善关键结论、证明材料和定义的表达结构。",
      "refs": ["fact:citations.official_share"]
    }
  ]
}
```

禁止新增行动方向、渠道、发布数量、频率、期限或效果承诺。所有数字证据必须使用 fact token。
