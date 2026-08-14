# 后端统计输入契约

## 当前文件适配器

生产脚本接受一个 JSON 文件。公共字段与当前 Dify 总结工作流保持一致：

| 字段 | 类型 | 是否必填 | 说明 |
|---|---|---:|---|
| `brand_name` | string | 是 | 本品品牌名 |
| `corp_name` | string | 是 | 客户或企业名称 |
| `product_name` | string/null | 否 | 产品或业务名称 |
| `core_topic` | string | 是 | 本次唯一诊断主题 |
| `market` | string | 是 | 市场代码，例如 `US` |
| `language` | string | 是 | 采集语言，例如 `en-US` |
| `task_id` | string | 是 | 诊断任务 ID |
| `batch_id` | string | 否 | 后端统计批次；未提供时使用 `task_id` |
| `overview` | object 或 JSON string | 是 | 数据总览与已算好的竞争差距 |
| `competitor` | object 或 JSON string | 是 | 竞品提及、声量和排名数据 |
| `citation` | object 或 JSON string | 是 | 来源类型、官网引用页面和热门来源 |
| `brand_expression` | array 或 JSON string | 是 | 后端逐回答分析后的本品表达证据 |
| `category_actions` | object 或 JSON string | 是 | 后端已经分好的 `p0/p1/p2` 问题 |
| `question_details` | array 或 JSON string | 是 | 去除回答全文的问题明细 |
| `action_context` | object 或 JSON string | 推荐 | 后端已经确定的行动方向、状态、证据和动作模板 |

六个原 Dify 模块字段既支持 JSON string，也支持直接 JSON 对象或数组。规范化后全部保存为直接 JSON。

## `action_context`

```json
{
  "directions": [
    {
      "direction_id": "ACT-001",
      "direction": "品牌进入机会",
      "state": "缺席型",
      "posture": "补齐",
      "key_evidence": "优先改进问题共8条",
      "action_template": "围绕真实比较场景检查并完善事实信息入口",
      "actual_themes": ["企业选型比较"]
    }
  ]
}
```

报告侧只负责把这些已确定方向写成人话，不重新计算状态。未提供时 M06 明确降级为空行动。

## 后端归属

公司后端是正式事实拥有者，应在传入前完成：

- 单条回答有效性、对象提及、情绪和引用处理；
- 提及率、声量占比、平均排名、引用占比等统计；
- 问题机会分档；
- 如需行动建议，生成稳定 `action_context`。

报告脚本只校验批次、结构、引用和文案一致性，不重算上述内容。

搜索团队传入的是逐条爬虫结果，字段包括 `answer_raw`、`job_id`、`keyword_id`、`query`、`references` 和 `search_results` 等；这些数据先经过逐回答分析与后端聚合，不直接进入本报告 Skill。

## HTTP 适配口

未来 HTTP 适配器只需返回与本文件完全相同的 JSON 对象：

```text
fetch_report_payload(task_id) -> backend-payload.json 对象
```

`base_url`、路由、鉴权、超时、重试和密钥由公司后端规范决定并从运行环境注入。当前版本只实现文件适配器，不声称已经接入真实 HTTP 接口。
