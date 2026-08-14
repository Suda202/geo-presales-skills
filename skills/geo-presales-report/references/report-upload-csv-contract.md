# 报告分析结论上传 CSV 契约

## 文件格式

- 编码：UTF-8 BOM。
- 换行：CRLF。
- 表头与顺序：`module,path,index,field,value`。
- 一行表示一个后台允许回填的叶子字段。
- `path` 表示数组字段；`index` 使用从 0 开始的字符串索引。根字段的 `path` 和 `index` 留空。
- 空的 `p0/p1/p2` 仍保留对应行，`value` 留空。

## 行顺序

1. `summary_overview.title`
2. `summary_category_actions.p0/p1/p2`
3. `summary_overview.points[].text`
4. `summary_competitor_performance.items[].text`
5. `summary_brand_expression.positive_evidence[]`、`risk_evidence[]`、`analysis_items[]`
6. `summary_citation_sources.items[].text`
7. `summary_priority_opportunities.actions[]`

数组按实际结论数量动态展开。行动字段顺序固定为 `source_module`、`title`、`evidence`、`action`、`expected_impact`。

## 不上传的字段

当前后台导出样例未包含以下字段，因此 CSV 不擅自添加：

- `summary_overview.conclusion`
- `summary_priority_opportunities.summary`
- `summary_final`
- 内部证据引用、task digest、输入哈希和审计状态

这些字段继续保留在内部 JSON 或审计产物中。若后台 CSV 契约发生变化，先用新的后台导出文件更新本契约和回归测试，再修改导出器。
