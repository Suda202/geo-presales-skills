# 实体、排名与审计边界纠偏门禁

日期：2026-08-14
Skill 版本：1.1.2

## 已确认产品规则

- 品牌排名定义为品牌实体在去引用正文中的首次出现顺序，不要求明确推荐或强弱关系。
- 品牌提及只从正文非链接文本提取；引用链接 title/锚文本不参与品牌提及和出现顺序。
- Ltd、Limited、Inc、LLC 等公司后缀不得拆成独立品牌。如历史 Bug 由引用 title 触发，title 中的完整公司名可作为回归输入。
- 普通错别字、缺字、标点、排版和不影响数据或结论的基础页面文案不纳入审计 Bad Case。

## Task 99 回归依据

- `#5161` 的 MiaDonna 只出现在引用链接 title/锚文本，去引用正文内没有 MiaDonna；该条不应计入品牌提及和排名。
- `#5170` 的正文比较集中确实按 Brilliant Earth、VRAI、Dorsey、Grown Brilliance、Angara、MiaDonna 的顺序出现；MiaDonna `#6` 符合产品排名定义。
- `#5193/#5196/#5200` 的引用 title 中有 `Chatham Inc.`，结构化结果没有独立 `Inc` 品牌；公司后缀误拆历史问题本轮已修复。
- `#5166` 中的 `Limited lifetime warranty` 是“有限终身保修”，`Limited` 不是公司后缀，不作回归样本。
- Task 99 的英文回答 HTML 有40条以 `<p>Done</p>` 结尾；客户详情抽屉滚动到英文回答底部后可见，不是网络未加载。

## 规则修改

- 在 `references/audit-workflow.md` 改写排名口径，并增加去引用正文、公司后缀和基础文案边界。
- 在 `evals/execution_cases.json` 增加四类反误报样例。
- 在输出风险清单增加对应的交付前检查。

## 门禁结果

- Skill 结构校验：通过。
- 触发评测：18/18 通过，false positives = 0，false negatives = 0，precision = 1.0，recall = 1.0。
- 执行样例结构校验：10/10 通过，包含排名口径、引用 title、公司后缀和基础文案四类回归样例。
- 确定性脚本测试：3/3 通过。
- JSON 结构校验：`manifest.json`、`trigger_cases.json`、`execution_cases.json`、`output-risk-profile.json` 通过。
