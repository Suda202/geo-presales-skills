# 参考扫描摘要

- 外部基准：Profound AEO Guide；Profound 101 Topics and Prompts。
- 借用：Topic 是相关 Prompt 的主容器；品牌有当前关联和目标属性；属性优先级考虑重要性、当前认知差距与可改变性；品类认知、竞品、情绪和准确性可作为诊断视角。
- 没有借用：Profound 没有定义 P1 / P2 / P3，也没有“入围属性”“比较属性”“补充属性”等分类。
- 本地适配：直接消费系统接口提交的评测 Case 字段，先建立独立的 Attribute × Topic 规划。P1 / P2 / P3 是 Attribute 在当前 Topic 下的优先级，用于安排售前首批问题覆盖。生成前没有监测回答，只按客户决策影响和 Case 证据充分程度分级，不虚构当前认知差距。再用自由 Tags 统一承接默认诊断意图、Branded / Non-Branded、Attribute 和其他横向分析；不派生 Attribute Pool 或 ID。支持 1–3 个 Topic，按各 Topic Attribute 信息量弹性分配题数且整批不超过 60；Discovery 在每个 Topic 内严格超过 50%，10–25/Topic 只作常见规划参考；同名 Attribute 可跨 Topic 聚合；每 Topic 用一条批量 Verification 覆盖 3–5 个 P1；每个适用竞品各有一条 Competitor；Evaluation 只评价目标品牌，竞品情绪矩阵留给售后生词。
- 路由适配：Tags 用于过滤和聚合，不控制 `analysis_type` 或 `formal_visibility_eligible`，避免用户自由改 Tag 时污染正式指标。
- 不借用：Profound 的界面、品牌语言、商业化配置上限与未公开评分实现。
