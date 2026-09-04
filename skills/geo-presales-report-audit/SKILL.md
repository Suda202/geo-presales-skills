---
name: geo-presales-report-audit
description: Use when auditing or correcting brand mention recognition and first-appearance rankings in GEO presales JSON results. Delivers safe brand-ranking corrections and Bad Case evidence; does not edit customer-facing analytical conclusions or sentiment.
metadata:
  author: 海外 GEO 项目
  version: "2.3.0"
---

# GEO 售前报告质量审计

## 目标与边界

用一手证据回答三件事：历史问题是否修复、当前报告是否新增客户可见问题、每条问题能否直接交给研发修复并用同一样本回归。

- 使用本 Skill 审核并修正 `brand_rankings` 等底层结构化结果；完成后再使用 `geo-presales-report-editor` 基于已确认的结果修改分析结论并生成上传 CSV。
- 暂不审计、判断或修改 `sentiment`。当前回答级情绪口径已冻结，待句子级情绪方案与验收标准确认后，另行设计并恢复该能力；本轮必须逐值保留原 `sentiment`。
- 不在本 Skill 修改客户报告的分析结论、客户文案或结论 CSV；底层数据确认后将这些工作交给 `geo-presales-report-editor`。
- 仅在用户授权维护 Bad Case 时写入飞书；只要求检查、解释或复核时保持只读。
- 不为凑数量找问题，不把第三方模型的正常推理自动归因成系统错误，不把某个 Task、品牌或品类结论固化为规则。
- 不审计普通错别字、缺字、标点、排版和不影响数据或结论的基础页面文案。

## 开始前读取

完整读取：

1. [全面审计流程](references/audit-workflow.md)
2. [结构化结果审计](references/structured-result-audit.md)
3. [诊断方法口径](references/diagnostic-methodology-audit.md)
4. [Bad Case 交付契约](references/badcase-output-contract.md)
5. [回归状态口径](references/regression-status.md)
- 读取 [跨 skill 规范映射](../shared/canonical-intent-mapping.md)；问题类型枚举、诊断意图值与 Visibility 范围以本文件为准。

涉及网页报告时先使用 `web-access`。涉及飞书 Wiki、多维表格或文档时使用 `lark-cli` 和对应的 `lark-wiki`、`lark-base`、`lark-doc` Skill，并先确认可读写的组织、profile、应用和机器人身份。

## 审计主流程

1. 固定 Task、目标品牌、报告/JSON 版本、Topic、目标 Attribute、问题类型集合、诊断意图标签、审计时间、历史 Bad Case 表和用户指定重点。
2. 按 `Case 配置 → Topic/Attribute/问题明细 → 回答全文 → 问题类型与诊断意图标签 → 结构化结果 → 聚合页面` 建立证据链。
3. 双轨执行：逐条回归适用的历史问题，同时脱离历史清单开放式扫描新增问题。
4. 找到最早出错环节，区分问题生成、采集、正文清洗、实体或竞品归类、出现顺序排名、引用、统计聚合和报告展示；品牌排名差异必须继续拆到具体实体和具体误判，不能在交付中只写“品牌实体识别”。
5. 先做反证，排除合理限定条件、正常证据保留、第三方模型自然输出、版本混用和当前无样本。
6. 将可以独立修复、独立回归的样本拆成一条记录，按交付契约撰写并制作标注截图。
7. 按当前证据更新状态；没有对应验证样本时只能标记“待验证”，不能写“已修复”。
8. 将诊断意图与品牌提及范围分开核对：未知标签原样保留并核对配置，不因不在旧枚举中直接判错；不根据问题类型或诊断意图重判情绪。
9. 写入飞书后逐条读回标题、字段、附件、状态和来源报告；未读回不得宣称更新完成。

审计 JSON 时只执行两遍品牌处理：先建立全批次候选实体与标准品牌词典，再按统一词典逐条排除引用和非品牌实体、去重并按正文首次出现顺序排名。正文已经列为候选或比较对象的品牌保持计入，不以审计者对需求符合度的二次判断删选。跨回答统一同一品牌的输出名，但官网大小写只作参考；母品牌、子品牌和产品线不因隶属关系自动互换。`sentiment` 一律保持输入值；不得根据回答、问题类型、诊断意图或竞品胜负重新判定。

## 不可降低的交付门槛

- 标题必须说人话，写明 `Task <编号> + #<记录编号>`；报告级问题写 Task 和对不上的具体数字。
- 必须写清本来应该是什么、实际变成什么，并引用原题、回答、结构化结果或页面数字的具体例子。
- 每条必须填写现有表格中的错误类型、模块、状态和优先级。
- 一条能够独立修复和回归的 Case 单独一行。
- 每条使用自己的截图；截图画面内直接写明问题，并用红框、箭头、下划线或编号中的至少一种指向原始证据。
- 不新增独立 Task ID 或“本轮标记”字段；Task 和记录号写进 `Bad Case` 与 `复现证据`。

## 确定性辅助工具

`structured_result_audit.py` 负责引用清洗、结构校验和 `brand_rankings` 审核补丁安全写回；`prepare_badcase_draft.py` 负责 Bad Case 草稿格式；`annotate_evidence_screenshot.py` 负责确定性证据标注。参数与语义边界见结构化审计和 Bad Case 交付参考。三者都不替代开放式品牌发现、句子级情绪、竞品胜负或 Attribute 关联判断，也不直接写入飞书。

修改触发描述、审计规则或脚本后，重新运行 `evals/trigger_cases.json`、`evals/execution_cases.json`、`scripts/run_structured_result_evals.py` 和 `tests/test_scripts.py`，并把门禁结果更新到 `reports/`。

## 最终交付

先给结论，再报告输入、输出、实际修改记录数、逐条字段前后值、未修改字段、验证与备份位置。每次修改都必须按字段完整列出所有被修改记录的身份；多平台数据使用 `platform + wordid`，不得只报总数、去重后的 wordid 或少量示例。

审计差异文档必须在逐条明细前提供“错误类型—记录编号索引”，每种错误类型单独一行，完整列出对应记录身份：报告 Case 使用 `Task <编号> #<记录编号>`，多平台 JSON 使用 `platform + wordid`。至少覆盖修复失败、待修复和新增 Case；已修复与待验证如需汇总，必须另标状态，不得混入同事的待修改清单。报告级问题没有单条记录号时，写 `Task <编号>（报告级：<模块或具体数字>）`，不得编造编号。索引必须与后文逐条明细一一对应，不得只给数量或少量示例。

输出 `brand_rankings` 差异时，不得把“品牌实体识别”“品牌名称规范化”或“排名提取”单独写成错误类型。按实际原因分行，例如“研究系统/论文原型误计为品牌”“模型/产品系列名误计为品牌”“引用锚文本公司名误计为品牌”“去引用正文候选品牌漏提”“品牌别名/误拼未统一”“去引用正文首次出现顺序排名错误”。逐条明细必须列出具体名称与动作：误计项写“名称（排除）”，漏提项写“名称（补入）”，归一项写“原名 → 标准名”，排序项写校正后的首次出现顺序。不存在的原因不得凑写；只有排序变更时只写排序原因。

报告审计另列已修复、修复失败或待修复、待验证和新增 Case；每条都带 Task、记录号、错误类型、具体例子和证据位置。最后说明哪些文件或飞书记录已实际写入并验证；差异为零时明确写“没有修改数据内容”，并在索引处写“无审计差异”。
