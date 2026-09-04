# 报告分析结论上传 CSV 契约

## Skill 的交付边界

该 Skill 只更新或生成 CSV 文件，不在销售后台或报告页面回填、提交、上传。用户提供现成导出 CSV 时，优先直接编辑该文件的允许回填内容；页面链接只可用于定位 Task 或只读核对已确认统计。

直接编辑时必须保留五列表头、字段路径、后台支持的叶子字段、UTF-8 BOM 与 CRLF。默认不改 `module/path/index/field`；只有结论数组确实需要增删且仍符合下述动态展开规则时，才同步调整对应数组索引。不得改写统计事实、内部 ID 或新增后台未知字段。输出为新 CSV，保留原文件供对照。

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

所有客户可见 `value` 统一使用“平均提及位置”和“引用份额”。“平均提及排名”“引用占比”“官网引用占比”视为废弃字段名或文案，上传前必须改正；内部兼容键可保留，不得原样显示给客户。

当前后台上传契约没有独立的跨平台和购买框架模块字段。M07、M08 先以内部结构化模块保存；其结论会在改变诊断可信度、范围、差异化判断或优先级时由 M01 写入 `summary_overview.points[]`，从而进入正式上传 CSV。不得擅自新增 `summary_platform_consistency` 或 `summary_market_perception` 上传行；后台契约扩展后再增加独立展示。

M02 的决胜回答胜率和正面对比优劣势仍写入现有 `summary_competitor_performance.items[].text`，不新增数值列。客户文案只把决胜回答胜率称为“竞品胜率”，不得写总体胜率。

M03 的正式页面机会仍写入现有 `summary_citation_sources.items[].text`，M06 的具体页面动作仍写入现有行动字段；不新增 Attribute、Tag、页面相关性、Citation 状态或 priority 列。Attribute 由主题/Tag 承载，内部 `page_opportunities` 只用于生成有证据的客户文案。

## 不上传的字段

当前后台导出样例未包含以下字段，因此 CSV 不擅自添加：

- `summary_overview.conclusion`
- `summary_priority_opportunities.summary`
- `summary_final`
- 内部证据引用、task digest、输入哈希和审计状态
- 独立 `summary_platform_consistency` 模块
- 独立 `summary_market_perception` 模块

这些字段继续保留在内部 JSON 或审计产物中。若后台 CSV 契约发生变化，先用新的后台导出文件更新本契约和回归测试，再修改导出器。

Skill 完成后只把 CSV 交给用户确认；确认和上传是 Skill 之外的步骤。
