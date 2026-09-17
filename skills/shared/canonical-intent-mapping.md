# 跨 Skill 共享：诊断意图规范映射表

本文件是售前 skill 家族的唯一权威词表。消费方共六个：geo-presales-eval-case-builder / geo-presales-prompt-builder / geo-presales-report-editor / geo-presales-report-audit / geo-presales-report-builder / geo-presales-sentiment-judge，各自的"开始前读取"均指向本文件。各 skill 内部不得另行定义同概念的别名。

## 完整映射

（下列 Intent: … 标签为当前默认值，后续将迁移为自定义 Tags，枚举不固定）

| Prompt Builder Intent Tag | 后端 diagnostic_intent | 中文客户标签 | analysis_type | formal_visibility_eligible | 报告模块归属 |
|---|---|---|---|---|---|
| `Intent: Discovery` | `discovery` | 发现（发现类问题） | `visibility,sentiment` | `true` | M01 数据总览、M02 竞品表现、M03 引用来源、M05 品牌进入、M07 平台一致 |
| `Intent: Competitor` | `competitor` | 竞品（竞品类问题） | `sentiment` | `false` | M02 竞品表现 |
| `Intent: Verification` | `validation` | 验证（验证类问题） | —（空） | `false` | 无独立模块；作为属性诊断输入 M04 品牌表达与 M01 数据总览 |
| `Intent: Accuracy` | `accuracy` | 准确性（准确性类问题） | `accuracy` | `false` | 无独立模块；作为准确性输入 M05 品牌进入 |
| `Intent: Evaluation` | `sentiment` | 评价（评价类问题） | `sentiment` | `false` | M04 品牌表达 |
| `Intent: Category Awareness` | `market_perception` | 品类认知（品类认知类问题） | —（空） | `true` | M08 购买框架（品类认知 / Market Perception） |

**报告模块按事实来源划分，不按诊断意图划分，两者不是一一对应。** 一个模块可以消费多种意图的样本（M02 同时用 Discovery 的竞争位置与 Competitor 的决胜结果），一种意图也可能不进任何模块（验证与准确性只作为诊断输入）。下表的模块归属只说明「该意图的样本最终进入哪些模块」，不要把它读成「该意图等于某个模块」。

*重要：`formal_visibility_eligible = true` 表示进入后端可见度处理管线，**不等于**进入正式 Visibility 指标（品牌进入率、平均提及位置、声量、问题机会）。报告侧正式 Visibility 指标和主要引用生态**只使用 Discovery（`Intent: Discovery`）**；Competitor 只统计情感并进入独立的 M02 竞品表现，不再进入可见度题集；Category Awareness 进入独立的 M08 购买框架。

情绪适用范围与 Discovery 独立判断：后端已标记为 Sentiment 的样本必须进入 M04 品牌表达聚合，不得因为该记录不属于 Discovery 或同时带有其他诊断意图而删除；它仍不得进入正式 Visibility。

> **迁移说明**：`Intent: Discovery`、`Intent: Competitor` 等诊断意图 Tag 当前作为默认枚举使用，计划迁移为项目自定义 Tags（不再是固定枚举）。迁移完成前，仍以本表为默认对照；迁移后，`analysis_type` 和 `formal_visibility_eligible` 的推导规则须在自定义 Tag 的定义文件中重新声明，不得依赖本表 Intent Tag 列自动推导。

## 问题类型（后端枚举）

后端问题类型只有两个值：`visibility`、`sentiment`。
- `accuracy` 是 diagnostic_intent 值，不是问题类型。
- 任何 intent 的 `analysis_type` 如为 `accuracy`，对应后端问题类型仍按分析处理（当前售前默认配额为 0）。

## `target_attributes` 来源

Report Editor 的后端输入字段 `target_attributes` 由**后端摄入层**从 v8 Prompt Bank 的 `attribute_plan` 字段和逐题 `Attribute: {attribute}` Tags 自动派生，并补充 `attribute_id`。Prompt Builder 不直接产出 `target_attributes`、`attribute_id` 或独立的逐题 `attributes` 字段。这一派生步骤由后端完成，不属于任何单个 skill 的职责范围。

## 字段名称互查

| 概念 | Case Builder（飞书 Base 字段） | Prompt Builder（输入合同） | Report Editor（后端字段） |
|---|---|---|---|
| 多值痛点 | `痛点`（单字段合并，`，`分隔） | `痛点 1…n`（编号兼容，合并单字段也接受） | — |
| 多值使用场景 | `使用场景`（单字段合并） | `使用场景 1…n`（编号兼容） | — |
| 多值产品特性 | `产品特性`（单字段合并） | `产品特性 1…n`（编号兼容） | — |
| 主题 | `主题`（单字段合并，`，`分隔，不标注类型） | `主题 1…n`（编号兼容，括号仅理解提示，不输出） | `topic_id`（英文 slug） |

## 报告模块代码

| 代码 | 含义 | 事实来源 |
|---|---|---|
| M01 | 数据总览（综合主诊断、跨模块关系与优先级） | M02–M05、M07–M08 |
| M02 | 竞品表现 | `competitor`、`competitor_comparison_summary` |
| M03 | 引用来源 | `citation`、`page_opportunities` |
| M04 | 品牌表达（品牌被认可与被质疑的表达证据） | `brand_expression` |
| M05 | 品牌进入（后端已分档的缺口覆盖哪些需求与阶段） | `category_actions` |
| M06 | 下一步行动 | `action_context` |
| M07 | 平台一致 | `platform_consistency` |
| M08 | 购买框架（品类认知 / Market Perception） | `market_perception_diagnostics` |
| M10 | 最终摘要 | M01–M08 |

模块编号按事实来源分配，与诊断意图编号无关。**M09 是未使用的编号**（后端从未定义过该模块，编号从 M08 直接跳到 M10），不是本表遗漏。验证、准确性没有对应模块：它们只作为诊断输入进入上表模块（验证 → M04 与 M01，准确性 → M05）。完整职责与依赖见 `geo-presales-report-editor/references/backend-report-task-contract.md`。
