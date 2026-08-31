# Case 本地 Markdown 导出模板

只在用户明确要求本地 Markdown、离线交付或评测集导出时使用。默认交付以 [飞书目标与写入合同](lark-base-target.md) 为准。

只输出实际有值的选填行，不输出空占位符，也不生成序号。

```markdown
## <品牌名称>

| 字段 | 填写内容 |
|---|---|
| 公司名 | <English identifiable company name without a non-distinguishing legal suffix> |
| 业务 / 产品名称 | <English business or product name> |
| 品牌名称 | <English brand name> |
| 业务模式 | <B2B / B2C / B2B / B2C> |
| 品类 | <中文> |
| 垂直行业 | <中文；仅 B2B 或 B2B / B2C 保留此行> |
| 目标客户 | <中文角色或人群，中文角色或人群> |
| 痛点 | <中文痛点，中文痛点> |
| 使用场景 | <中文任务，中文任务> |
| 产品特性 | <中文硬指标或能力，中文硬指标或能力> |
| 差异化优势 | <中文具体赢单理由，中文具体赢单理由> |
| 适用边界 | <中文> |
| 主题 | <中文主题，中文主题> |
| 官方域名 | <https://official.example> |
| 竞品 1 | <English competitor name> |
| 竞品 1 官网域名 | <https://competitor.example> |
| 竞品 2 | <English competitor name> |
| 竞品 2 官网域名 | <https://competitor.example> |
| 竞品 3 | <English competitor name> |
| 竞品 3 官网域名 | <https://competitor.example> |
| 补充内容 | <仅在确有其他字段无法承接的新增重要信息时保留> |
```

公司名、业务 / 产品名称和补充内容均按需增删；其他必填行不得省略。目标客户、痛点、使用场景、产品特性、差异化优势和主题等多值字段各保留一行，不同值之间用 `，` 分隔；单个值内部尽量使用“和”“或”或“；”。主题只写名称，不标注类型。竞品名称和官网按 1–3 分组字段填写，以保持一一对应；这里的数字是字段名，不是 Case 序号。
