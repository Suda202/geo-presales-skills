# 参考扫描摘要

- 外部基准：Profound AEO Guide；Profound 101 Topics and Prompts。
- 借用：Topic 是相关 Prompt 的主容器；品类认知、竞品、情绪和准确性仍作为常用诊断视角。
- 本地适配：直接消费 Edgelight 型评测集 Case 字段，先建立独立的 Attribute × Topic 规划，再用自由 Tags 统一承接默认诊断意图、Branded / Non-Branded、Attribute 和其他横向分析；不派生 Attribute Pool 或 ID。支持 1–3 个 Topic，按各 Topic Attribute 信息量弹性分配题数且整批不超过 60；Discovery 在每个 Topic 内严格超过 50%，10–25/Topic 只作常见规划参考；同名 Attribute 可跨 Topic 聚合；每 Topic 用一条批量 Verification 覆盖 3–5 个 P1；每个适用竞品各有一条 Competitor；Evaluation 只评价目标品牌，竞品情绪矩阵留给售后生词。
- 路由适配：Tags 用于过滤和聚合，不控制 `analysis_type` 或 `formal_visibility_eligible`，避免用户自由改 Tag 时污染正式指标。
- 不借用：Profound 的界面、品牌语言、商业化配置上限与未公开评分实现。
