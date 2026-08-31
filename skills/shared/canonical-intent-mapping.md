# 四 Skill 共享：诊断意图规范映射表

本文件是 geo-presales-eval-case-builder / geo-presales-prompt-builder / geo-presales-report-editor / geo-presales-report-audit 的唯一权威词表。四个 skill 的"开始前读取"均指向本文件。各 skill 内部不得另行定义同概念的别名。

## 完整映射

（下列 Intent: … 标签为当前默认值，后续将迁移为自定义 Tags，枚举不固定）

| Prompt Builder Intent Tag | 后端 diagnostic_intent | 中文客户标签 | analysis_type | formal_visibility_eligible | 报告模块 |
|---|---|---|---|---|---|
| `Intent: Discovery` | `discovery` | 发现（发现类问题） | `visibility` | `true` | M01 发现 |
| `Intent: Competitor` | `competitor` | 竞品（竞品类问题） | `visibility` | `true`* | M02 竞品 |
| `Intent: Verification` | `validation` | 验证（验证类问题） | `visibility` | `false` | M03 验证 |
| `Intent: Accuracy` | `accuracy` | 准确性（准确性类问题） | `accuracy` | `false` | M04 准确性 |
| `Intent: Evaluation` | `sentiment` | 评价（评价类问题） | `sentiment` | `false` | M05 评价 |
| `Intent: Category Awareness` | `market_perception` | 品类认知（品类认知类问题） | `visibility` | `true`* | M08 品类认知 |

*重要：`formal_visibility_eligible = true` 表示进入后端可见度处理管线，**不等于**进入正式 Visibility 指标（品牌进入率、平均提及排名、声量、问题机会）。报告侧正式 Visibility 指标和主要引用生态**只使用 Discovery（`Intent: Discovery`）**；Competitor 和 Category Awareness 分别进入独立的 M02 竞品模块和 M08 品类认知模块。

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

| 代码 | 含义 |
|---|---|
| M01 | 整体 Visibility（发现类样本） |
| M02 | 竞品比较 |
| M03 | 验证 |
| M04 | 准确性 |
| M05 | 评价/情绪 |
| M06 | 行动建议 |
| M07 | 平台差异 |
| M08 | 品类认知（Market Perception） |
