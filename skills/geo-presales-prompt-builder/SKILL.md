---
name: geo-presales-prompt-builder
description: Use when generating, rewriting, auditing, or validating English AI-search monitoring Prompts for GEO presales diagnostics, including Generic/Branded quotas, commercial intent coverage, terminology, naturalness, and category or purchasing-object drift. Do not use for crawling answers, calculating metrics, or writing report conclusions.
metadata:
  author: Overseas GEO Project
  version: "0.8.0"
---

# GEO Presales Prompt Builder

把品牌、品类、市场、人群和售前主题转换成可直接投放海外 AI 平台的自然英文问题库。核心目标是问题质量与监测可比性，不是关键词扩写数量。

## 必读规则

- 生成前读 `references/generation-method.md`、`references/presales-contract.md`；质检时再读 `references/quality-gates.md`，需要正反例时读 `references/examples.md`。
- 修改规则后，用 `evals/` 回归。

## 执行流程

1. 归一化 Topic、品牌/产品/aliases、品类、排除品类、受众、locale、平台、事实来源和题量；建立 `category_expression_set`（品类原词/自然变体、品类产品词、占位词黑名单）。正式售前原样消费冻结的 3 个 `formal_competitors`，不重选。另做 `professional_term_assessment` 和 `required_term_coverage`；事实不足就标假设，不编价格、能力或市场表现。
2. 选择 `presales_diagnostic` 或 `intent_research`。售前默认冻结 50 题、Generic 40 / Branded 10；商业意图只用 `recommendation / comparison / decision`，三类都必须有，但不设数量或交叉格子配额；不生成了解、科普或纯评估框架题。
3. 按目标用户、评估标准、约束和比较对象建立意图矩阵；条件可单用或复合，但不得拼接任务。按答案终点分类：要候选是 Recommendation，要取舍是 Comparison，要最终判断是 Decision。v3 不使用 `geo_intent`；价格、风险、替代和试用只是改变选择的条件。每题独立体现 Topic、品类与同一购买集合。
4. 一题一意图：条件取值不同，或增删会改变答案的条件，才算不同意图；条件相同、只换措辞或顺序不算。句式相同与 Yes/No 不直接判错。
5. Generic 不得出现客户品牌、产品 aliases 或竞品。每 Topic 在 Branded 中固定生成 1 条 `Evaluate the {品类} company/product {品牌} on {主题}` 品牌总体评价基准题，硬归 `branded + decision`，由模板本身识别，不新增情绪意图标签。这不是唯一情绪样本：其余 Branded 题继续探测具体人群、能力、竞品和选择下的品牌评价。Branded Comparison 达到 5 条时采用三竞品各一条，加两条关键因素或多品牌题；不越过低可比竞品的 `allowed_dimensions`。
6. 分开生成 `user_question / standalone_rewrite / retrieval_rewrite / evidence_query / title_seed`。只有 `user_question` 可作根监测 Prompt。使用目标语言的自然表达，绝对上限 30 个英文词；locale 由采集环境控制时，不把目标市场机械塞进每题。
7. 二遍逐题确认购买对象仍属于 Topic，并且答案必须给候选、推荐或明确取舍；再查单意图、品牌边界、中性前提、译文和字段隔离。整批检查配额、重复、术语、受众与竞品覆盖。
8. 保存为 `overseas-geo-question-bank/v3`，运行 `python3 scripts/validate_question_bank.py <question-bank.json>`。独立二遍 review 后才填写 `quality_checks`；程序通过不代替语义判断。

## 输出契约

- 监测题库、总题量与 Generic/Branded 配额、三类意图覆盖
- 每条 `user_question` 的非空中文译文 `zh_translation`
- 商业意图与决策阶段映射
- 冻结三竞品的可比等级、允许维度与出题边界汇总
- 每 Topic 品牌总体评价基准题覆盖、三个正式竞品的一对一覆盖、适用时的 Branded Comparison 3+2 结构与目标受众覆盖汇总
- 专业术语覆盖表：来源、全称/缩写、Generic/Branded 分布与未覆盖原因
- 五段式重写字段，明确监测字段
- 被合并/淘汰/重写的问题及原因
- 质量报告：硬门、警告、事实状态、平台与 locale

不采集 AI 回答，不计算提及率/排名/情绪/引用，不直接撰写售前报告或内容资产。
