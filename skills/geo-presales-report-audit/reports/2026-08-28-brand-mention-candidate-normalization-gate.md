# 品牌候选保留与批次规范名门禁

日期：2026-08-28

## 本轮规则修正

- 品牌提及忠实抽取回答已经列出的候选、备选和比较对象，不再根据审计者对题目核心需求符合度的二次判断删除品牌。
- 同一品牌跨回答使用批次词典中的统一规范名；官网全小写、全大写或特殊字形只作参考，不单独触发改名。
- 母品牌、子品牌和产品线不因隶属关系自动互换；按回答实际作为购买候选或品牌标题使用的名称保留。

## Task 175 纠正记录

| 记录 | 纠正前 | 纠正后 |
|-|-|-|
| `chatgpt + #8175` | `Sure Petcare #1` | `SureFeed #1` |
| `chatgpt + #8176` | `Sure Petcare #3, Catit #4` | `Catit #3, Sure Petcare #4` |
| `gemini + #8167` | `PETKIT #1, CATLINK #2` | 恢复 `PETLIBRO #3, Litter-Robot #4` |
| `gemini + #8173` | `Sure Petcare #2` | `SureFeed #2` |
| `gemini + #8179` | `oneisall #4` | `Oneisall #4` |
| `gemini + #8186` | `oneisall #3` | `Oneisall #3` |
| `gemini + #8187` | `oneisall #3` | `Oneisall #3` |
| `gemini + #8188` | `Sure Petcare #3` | `SureFeed #3` |

## 最终品牌排名差异

相对原始文件，最终只保留 12 条成立的品牌排名修改：

- 首次出现顺序：`gemini + #8139`、`chatgpt + #8140`、`gemini + #8141`、`chatgpt + #8145`、`gemini + #8159`、`gemini + #8163`。
- 批次规范名：`gemini + #8140`（`Petpivot → PetPivot`）、`gemini + #8143`（`Catlink → CATLINK`）、`gemini + #8178`（`Catlink → CATLINK`）、`chatgpt + #8179`（`Instachew → INSTACHEW`）、`gemini + #8179`（`oneisall → Oneisall`）、`chatgpt + #8186`（`WOpet → WOPET`）。
- `gemini + #8139` 同时包含首次出现顺序修正和 `Catlink → CATLINK` 规范名修正。

## 门禁结果

- Task 175：120 条记录，`platform + wordid` 120/120 唯一。
- 最终差异：品牌排名 12 条、情绪 84 条，共 85 条记录发生 96 个目标字段变化。
- 非 `brand_rankings / sentiment` 字段与顶层字段逐值一致。
- 所有最终排名中的品牌均能在去引用正文中找到，排名与首次出现顺序一致。
- 批次内同一品牌无仅大小写不同的规范名冲突。
- `python3 scripts/run_structured_result_evals.py`：17/17 通过。
- `python3 -m unittest discover -s tests -v`：20/20 通过。
- `quick_validate.py`：Skill 校验通过。
