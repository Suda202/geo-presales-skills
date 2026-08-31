# Case Builder 与竞品研究的交接规则

## 何时调用

| 输入状态 | 处理 |
|---|---|
| 3 个竞品、官网完整，且已有同一购买集合核验 | 直接写入 Case，不重复研究。 |
| 1–2 个候选 | 调用 `overseas-geo-competitor-research`，把已提供项放入 `known_competitors` 进行核验并补足到 3 个。 |
| 3 个名称但官网不完整，或未核验购买集合 | 调用竞品研究；通过者优先保留，未通过者自动替换。 |
| 0 个竞品 | 调用竞品研究，传入空 `known_competitors`，从零发现并冻结 3 个。 |

Topic-only 模式不补齐竞品，除非用户同时要求完成整个 Case。

## 输入映射

- `target.name` ← 品牌名称
- `target.official_domain` ← 官方域名
- `target.product_name` ← 业务 / 产品名称；没有则使用品牌名称
- `target.description` ← 品类、痛点、使用场景、产品特性、差异化优势和适用边界的简洁合并
- `target.target_users` ← 目标客户
- `topic` ← “主题”字段中的第一个主题；主题尚未生成时不得先运行竞品研究
- `market`、`current_date` ← 系统固定参数和运行日期，不写入最终 Case
- `known_competitors` ← 用户已提供的 0–3 个名称、官网和别名

## 输出写回

只读取成功冻结结果中的 `formal_competitors`：

- `name` → `竞品 N`
- `official_domain` → `竞品 N 官网域名`，统一补 `https://`

同时在来源说明中保留 `source`、`same_purchase_set_eligible`、`limitations`、`comparison_policy` 和对应证据 URL；另行保留 `provided_competitor_rejections`。不得把候选池、未选中项或未经冻结的研究建议直接写入正式竞品字段。

若结果不是 `status=frozen`、正式竞品不等于 3 个，或任何正式竞品没有通过同一购买集合硬门槛，停止最终 Case 交付并返回竞品研究错误；不得猜测、编造或用相邻产品凑数。
