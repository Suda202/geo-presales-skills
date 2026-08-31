# 输出风险画像

## 主要风险

- 把选填字段当必填，尤其强行填写公司名、业务 / 产品名称、第二或第三个主题、补充内容。
- 用“补充内容”掩盖品类、痛点、场景、特性、差异化优势或适用边界缺失。
- 保留中英文镜像列，或把公司、业务 / 产品、品牌、竞品名称翻成中文。
- 使用场景只是主题名复写，没有表达客户实际完成的任务。
- 为凑满三个竞品编造名称，或使用功能相似但不进入同一次购买决策的品牌。
- 没有收到竞品时直接退回待补项，没有调用专用竞品研究从零发现并冻结三个。
- 把竞品研究逻辑复制进 Case Builder，造成证据、分级和选择规则漂移。
- 仍依赖已经弃用的 Topic Builder，导致主题规则存在两个事实源。
- 把受众，场景，评价标准和限制条件全部塞进 Topic，导致 Topic 变成完整 Prompt；或把 2–5 个词误当中文字符数硬限制。
- 把可跨 Topic 的能力或评价标准升级为 Topic，或反过来把完整市场 / Use Case 降为 Attribute，导致监测主组织失真。
- 把诊断意图、Branded / Non-Branded 等下游 Tags 当成 Topic。
- 把官网或客户自述直接写成已核验报告结论。

## 自检路径

1. 运行 `scripts/validate_case.py` 检查字段、数量、语言与 URL。
2. 确认主题只按 `references/topic-generation-reference.md` 生成，没有调用或复制旧 Topic Builder 的规则；每个 Topic 都能独立承载一组 Prompts，跨 Topic 能力留给 Attribute，诊断意图与品牌范围留给 Tags；Coverage 名称更短，Depth 最多增加一个必要限定。
3. 竞品输入不足 3 组或尚未核验购买集合时，确认已经调用 `overseas-geo-competitor-research`，且只把 `same_purchase_set_eligible=true` 的冻结 `formal_competitors` 写回 Case。
4. 人工确认每条使用场景是任务表达，每条差异化优势是具体输入假设。
5. 若保留补充内容，逐句回答：这条信息为何不能写入已有字段，它会改变哪类问题设计？回答不出则删除。
