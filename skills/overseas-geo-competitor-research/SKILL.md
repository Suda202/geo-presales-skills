---
name: overseas-geo-competitor-research
description: 用于为海外 GEO 售前诊断联网发现、核验和冻结三个处于同一购买集合的正式竞品。支持未提供竞品时从零发现，也支持核验用户填写的一个至三个候选并补足；需要验证竞品名称、官网、同次购买可替代性与市场地位证据时使用。
metadata:
  author: 海外 GEO 项目
  version: "0.5.0"
---

# 海外 GEO 售前竞品研究

## 用途

使用联网研究建立候选池，再由确定性脚本完成来源识别、购买集合核验、评分、组合选择和冻结。输入允许提供零至三个候选；没有提供时从零发现，已经提供的候选也必须通过“同一次购买决策”硬门槛，不符合时记录淘汰原因并自动替换。

## 工作流程

1. 准备输入并生成检索计划。

   ```bash
   python3 scripts/competitor_research.py prepare --input /绝对路径/input.json --run-dir /绝对路径/runs/<id>
   ```

2. 读取 `research-plan.json`，按其中查询词执行联网搜索。

   - 优先调用 `network-search` Skill；当前环境没有该能力时，使用可用的搜索与网页读取工具。
   - 先搜索候选池，再读取候选官网、产品/定价页、独立评测、市场报告或近期新闻。
   - 优先为每个候选保存一条官网证据和一条独立来源证据；必须保存候选与目标品牌进入同一次购买决策的证据。
   - 头部、同层级或挑战者地位使用近 18 个月独立证据；当前活跃状态使用近 30 天实际访问的官网证据；记录检索日期。
   - 区分事实和判断。评分可以由智能体提出，但必须给出对应 evidence ID。

3. 按 [研究结果契约](references/research-contract.md) 写入 `research.json`。

4. 运行脚本分级和组合选择。

   ```bash
   python3 scripts/competitor_research.py finalize --run-dir /绝对路径/runs/<id> --research /绝对路径/research.json
   ```

5. 只有当候选池至少包含三个不同官网域名、且三个均通过同一购买集合硬门槛时，脚本才输出 `status=frozen`、`selection_count=3`。不足时继续自动检索并重跑，不得用相邻产品凑数或返回 `needs_manual_input`。

修改输入契约、分级或降级规则后，必须重跑 `scripts/tests/` 与 `evals/contract-cases.json` 中的回归场景。

## 从零发现与用户候选处理

- `known_competitors` 允许零至三个。为空时全部从零发现；有值时作为待核验候选，脚本依据名称、官网和别名识别 `user_provided`，不信任研究文件自报来源。
- 用户候选通过同一购买集合硬门槛后按输入顺序优先保留；未通过时进入 `provided_competitor_rejections`，系统自动寻找替代项，不能强行写入正式集合。
- 剩余位置只从同一购买集合候选中选择，排序为“已验证的细分头部 → 综合得分 → 名称稳定排序”。相邻产品、外围工具和不同购买决策的品牌只进入候选审计，不能补位。
- 固定集合只有三个位置，因此输入最多三个；超过三个由上游阻止，脚本也会拒绝。

## 同一购买集合硬门槛

正式竞品必须同时满足：

- `same_purchase_set=true`，且有绑定证据说明买家会在同一次选型中比较双方。
- 核心任务一致，产品或服务形态可替代，目标用户和采购角色明显重叠。
- 官网当前活跃，候选不是目标品牌自身，名称与官网域名唯一。
- `sub_track`、`core_job` 至少 4 分，`product_form`、`target_users`、`buying_motion` 至少 3 分；这些字段及 `same_purchase_set` 均有证据绑定。

市场地位、品牌规模、融资和知名度只参与门槛通过后的排序，不能让相邻品类进入正式集合。证据不足等同于尚未通过，必须继续搜索，而不是降级凑数。

## 选择顺序

- 先保留通过硬门槛的用户候选。
- 自动位置优先本 Topic 和目标市场中有近 18 个月独立证据的细分头部，再按综合得分选择 `peer` 或 `challenger`。
- 头部不足时可以选择多个合格 `peer` 或 `challenger`；不能退回相邻购买集合。

## 比较内容边界

即使同属一个购买集合，也只允许在 `comparison_policy.allowed_dimensions` 中有证据的共同维度做中性比较；禁止无证据的绝对排名、全面替代性或领先结论。

## 输出

- `research-plan.json`：检索查询和证据要求。
- `competitor-selection.json`：三个同一购买集合的正式竞品、用户候选淘汰、选择策略、比较边界、得分、证据和候选审计。

所有字段、评分和证据说明见 [研究结果契约](references/research-contract.md)。
