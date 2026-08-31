# 问题类型重叠与诊断标签迁移门禁

更新时间：2026-08-28

## 本轮口径

- 删除“通用问题 / 品牌问题”和购买意图分流。
- 问题类型只有 `visibility / sentiment`，按集合处理；同一问题允许同时属于两类，并分别进入两个指标的样本和分母。
- 将诊断意图与问题类型分开。当前兼容六个既有值，后续接受自由命名、多值标签；未知标签保留，不因旧枚举门禁失败。
- 情绪判断资格只由问题类型集合是否包含 `sentiment` 决定；`visibility` 不强制情绪为 `neutral`。

## 脚本门禁

- `question_type(s)` 同时兼容标量和数组，类型值只允许 `visibility / sentiment`。
- `diagnostic_intent(s)` 同时兼容标量和数组，允许未知自由标签。
- `metric_scopes` 必须覆盖问题类型和已知诊断标签要求的范围，同时允许未来标签增加自定义 scope。
- `sentiment_from_review` 在问题类型不含 `sentiment` 时拒绝生成情绪；在 `visibility + sentiment` 重叠时按实际正中负输出。

## 验证结果

- 结构化金标：15/15 通过。
- 单元测试：20/20 通过。
- 触发评测：21/21 通过，precision=1.0，recall=1.0。
- Skill 结构校验：通过。
- JSON 语法校验：全部通过。
