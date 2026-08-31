---
name: geo-presales-eval-case-builder
description: Use when creating, completing, normalizing, auditing, or maintaining a brand Case in the overseas GEO presales diagnostic input evaluation set, including generating or revising one to three monitoring Topics, writing the result to the project Feishu Base, and delegating missing competitor discovery to overseas-geo-competitor-research. Also use for Topic-only maintenance of an existing Case. Do not use for competitor-only research, Prompt generation, answer collection, metric calculation, or report writing.
metadata:
  author: 海外 GEO 项目
  version: "1.5.0"
---

# GEO 售前诊断输入评测集 Case 生成器

把品牌资料整理为一个完整 Case，并默认创建或更新到项目指定的飞书多维表格。每个 Case 对应一条 Record；以业务字段识别记录，不生成 Case 序号。

## 开始前

- 读取 [字段合同](references/field-contract.md)。
- 读取 [飞书目标与写入合同](references/lark-base-target.md)，并使用 `lark-base` Skill 执行 Base 操作。
- 读取 [主题生成规则](references/topic-generation-reference.md)；只有拆分存在歧义时再看 [主题拆分示例](references/topic-examples.md)。
- 读取 [竞品研究交接规则](references/competitor-handoff.md)。竞品名称或官网不足 3 组时，调用 `overseas-geo-competitor-research`；完全未提供竞品时也必须从零研究，不把缺失竞品退回给用户补填。
- 目标市场、语言和 AI 平台是系统固定参数，不写入 Case。

## 执行

1. 归一化公司、业务 / 产品、品牌、官网、业务模式及输入证据，保留来源冲突和待人工确认项。公司名保留可识别主体名，按字段合同省略无区分度的法律实体后缀。业务模式按当前 Case 的主要购买路径选择 `B2B` 或 `B2C`；只有企业和个人均为核心买方，且购买标准、场景和竞品基本重合时才使用 `B2B / B2C`。两类购买决策差异明显时拆分 Case。
2. 提取品类、垂直行业、目标客户、2–5 条痛点、2–5 条使用场景、2–5 条产品特性、1–5 条差异化优势和适用边界。纯 `B2C` Case 的“垂直行业”保持为空；只有 `B2B` 和 `B2B / B2C` 填写。目标客户只写会改变购买判断的核心角色或人群，不写“关注什么”；关注点分别归入痛点、使用场景、产品特性或主题。同一字段的多个值合并为一行，值之间用 `，` 分隔；单个值内部尽量用“和”“或”或“；”连接并列要素。适用边界用一句话写清主要适用条件或排除范围，不罗列产品卖点。不得用空泛营销话术补齐。
3. 从第 2 步字段生成主题候选，先按 [主题、属性与标签边界](references/topic-generation-reference.md#主题属性与标签边界) 判断候选是否足以成为 Prompt 集合的主组织单元，再按 `目标客户 × 核心任务 × 评价标准 × 候选品牌 × 优化动作` 合并或拆分。选择 1–3 个正式中文主题，合并写入同一个“主题”字段并用 `，` 分隔。Topic 名通常使用 2–5 个词，优先 2–4 个词，只表达一个核心主题；宽泛 Coverage Topic 应更短，细分 Depth Topic 仅在受众或任务确实改变购买判断时增加一个必要限定。将横跨 Topic 的能力、特征和评价标准保留在原 Case 字段，供下游派生 Attribute；将诊断意图、品牌范围和其他横向分类留给下游 Tags。只写主题名称，不输出宽泛或细分标签，不为凑数编造机会，也不分配 Prompt 数量。
4. 处理竞品：已有 3 组经过同一购买集合核验的名称与官网时直接使用；只有 0–2 组、官网缺失或尚未核验购买集合时，调用 `overseas-geo-competitor-research`。已提供项作为优先核验候选，未通过时记录淘汰并自动替换；只将 3 个通过硬门槛的 `formal_competitors` 写回 Case。研究无法冻结时保留错误与证据缺口，不用相邻产品凑数。
5. “补充内容”默认留空。只有当信息无法归入其他字段，且能明确说明会改变哪类问题设计时才填写；与品类、目标客户、痛点、使用场景、产品特性、差异化优势或适用边界重复时保持为空。补充内容不得替代必填字段。
6. 按 [飞书目标与写入合同](references/lark-base-target.md) 定位目标表，先读取真实 Field schema，再读取现有 Records。以 `品牌名称 + 业务 / 产品名称 + 主题` 判断记录归属：同一 Case 的补全或维护更新已有 Record；新品牌或新的明确业务颗粒度创建 Record。Topic-only 模式只更新“主题”及确需同步的 Topic 边界说明。
7. 创建使用 `record-batch-create`，维护使用 `record-batch-update`。新增 Record 按飞书默认位置自然追加，不置顶、不倒序，也不移动已有记录。只提交真实 schema 中存在的业务字段，不写 `Case序号`，不维护编号。认证或权限失败时按 `lark-shared` 以原身份修复，不静默切换 Bot 身份或改交 Markdown。
8. 写入后读回目标 Record，至少核对品牌名称、主题、官方域名、三组竞品及官网、补充内容；确认记录存在且本轮提交字段一致后交付。

## 本地 Markdown 分支

仅当用户明确要求本地 Markdown、离线交付或评测集导出时，读取 [输出模板](references/output-template.md) 生成无序号标题的两列表，并运行：

```bash
python3 scripts/validate_case.py <case.md>
```

校验失败先修复再交付。该分支不自动追加项目历史 Markdown 评测集，也不重排旧 Case。

## 输出

- 默认输出飞书目标 Record 的创建或更新结果，以及必填项完整性结论和必要的待人工确认项。
- 提供使用过的资料来源简表；若调用竞品研究，同时保留竞品选择证据和可比性限制。来源只支撑输入假设，不把厂商自述写成报告结论。
- Topic-only 模式附候选合并或淘汰原因。

不在本 Skill 内复制竞品研究逻辑；竞品不足时委托专用 Skill。也不生成 Prompt、AI 回答、可见度或情绪指标，不撰写售前报告。
