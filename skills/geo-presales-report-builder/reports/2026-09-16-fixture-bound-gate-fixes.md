# 2026-09-16 门禁脚本去 Bewinch 形态耦合

## 触发

Edgelight 案例（US / ChatGPT / 5 题 × 15 次重复）跑 `verify_report_data.py --self-test` 时，
基线报 17 项失败，但逐条核实后**没有一项是数据错误**：17 项全部来自校验器写死 Bewinch 案例的形态。

## 改了什么

`scripts/verify_report_data.py` 四处：

| 位置 | 旧 | 新 | 为什么 |
|---|---|---|---|
| `run_checks` 题数检查 | `len(meta.questions) != 50` 即报错 | 校验结构自洽：qid 应为 1..N 连续、每条有 en/topic、覆盖主题集合与 `meta.topics` 一致 | 题数由题库决定。按采集次数展开是 75 行，按真实题目是 5 行，都不是固定值 |
| `_check_slice` 空域名检查 | 展示行有任一空域名即报错 | 只有当该对象**在词表里声明了域名**、展示行却为空时才报错；`meta.objects` 缺失时回落旧行为 | 开放品牌词表允许无域名（参考词表 96 个里 43 个为空），展示行为空是正常形态 |
| `_mutations` 切片键 | 写死 `MY\|\|` / `SG\|\|` / `SG\|AIO\|` / `\|Gemini\|台式净饮机` | 从 `meta.regions` / `meta.platforms` / `meta.topics` 推导，找不到时回落实际存在的切片 | 换市场或主题的 Case 直接 `KeyError` |
| `_mutations` 矩阵越界 | 固定写 `vals[1]` | 先找 `vals` 长度足够的切片，否则回落 `vals[0]` | 单平台 Case 的 `vals` 只有一项，`vals[1]` 越界 |

## 门禁结果

Edgelight 案例：`baseline: 通过`，19 个注入错误全部检出，退出码 0。

Bewinch 形态回归：`_mutations` 在 `tests/fixture_report_data.json` 上仍产出 19 条并正确取到 `MY||` / `SG||` 键，未破坏原形态。

## 未改动（仍为已知边界）

- `Recomputer._spans` 已按数据层同口径去引用（`de_cite.strip_citations` + `blank_merchant_columns`），无需改。
- `Recomputer` 要求 `meta.objects`；`tests/fixture_report_data.json` 缺该字段，是**改动前就存在**的现象，与本次无关。
- 开放品牌域名仍可为空：需要展示域名时，从采集自带的引用域名取证（如 `usabsen.com`、`hexatrontech.com`），不凭印象补。
