# Top N 展示误报纠偏门禁

日期：2026-08-14
Skill 版本：1.1.1

## 已确认产品规则

- 官网引用页面模块固定展示 Top 8。
- 底层存在超过 8 个 URL 时，不能据此判定页面“把 Top 8 当成总数”。
- 原始引用记录数、唯一 URL 数、引用该域名的回答覆盖数和 Top 8 列表长度是不同单位，不能直接混算。
- 只有页面或产品字段明确声称“共 N 个”或“全部 N 个”，且同口径底层结果不一致时，才创建数量错误 Case。

## 规则修改

- 在 `references/audit-workflow.md` 增加“区分总数、覆盖数和 Top N 展示”。
- 在引用审计规则中明确 Top N 只核对入选、排序、链接和来源归类。
- 在 `evals/execution_cases.json` 增加“官网引用页面固定只展示 Top 8”反误报样例。
- 在输出风险清单中增加“把产品设计误报成统计错误”。

## 门禁结果

- 触发评测：18/18 通过，false positives = 0，false negatives = 0，precision = 1.0，recall = 1.0。
- 执行样例结构校验：6/6 通过，包含 Top 8 反误报样例。
- 确定性脚本测试：3/3 通过。
- JSON 结构校验：`manifest.json`、`execution_cases.json`、`output-risk-profile.json` 通过。

## 本次审计结论纠正

Task 96 的“官网页面总数把 Top 8 当成全部”不成立，应从确定性问题清单中删除。底层 URL 多于 8 只能说明候选引用页面更多，不能推导产品页面声称的总数错误。
