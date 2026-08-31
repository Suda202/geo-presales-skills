# GEO 售前 Skills

这是海外 GEO 售前诊断的四个 Skill 包，覆盖从品牌资料整理、监测问题设计，到报告产出和结果审计的流程。

```text
品牌资料
  -> Case Builder
  -> Prompt Builder
  -> 外部采集和后端统计（不在本仓库）
  -> Report Editor
  -> 客户报告和 CSV
       -> Report Audit
```

## 选哪个 Skill

| Skill | 什么时候用 | 产出 | 不做什么 |
| --- | --- | --- | --- |
| `geo-presales-eval-case-builder` | 有品牌资料，需要建立或维护售前评测 Case | 规范化 Case、1 到 3 个监测主题、已核验竞品 | 不出题、不采集回答、不写报告 |
| `geo-presales-prompt-builder` | 已有 Case，需要生成英文 AI 搜索监测题库 | `overseas-geo-question-bank/v8` 题库、属性规划、质量报告 | 不创建主题、不选竞品、不计算指标 |
| `geo-presales-report-editor` | 已有后端统计和初步结论，需要生成或修改客户报告 | 有证据约束的中文结论、可上传 CSV | 不重算生产指标，不生成 HTML 或 PDF |
| `geo-presales-report-audit` | 要核对报告、JSON 结果或历史 Bad Case 是否正确 | 审计结论、可复现的问题说明、必要的 Bad Case 草稿 | 不生成客户报告，不做竞品研究或出题 |

`geo-presales-report` 是旧的合并包，已经拆成 `geo-presales-report-editor` 和 `geo-presales-report-audit`。要写报告时用 editor，要检查报告或底层结果时用 audit，两者可以连续使用。

## Prompt Builder 的关键约束

- 每个 Topic 都要先做独立的 P1、P2、P3 属性规划。
- 题数按 Topic 的有效属性覆盖分配，整批最多 60 题，不为凑数重复提问。
- 每个 Topic 内，发现类问题必须严格多于其他问题类型之和。
- 发现类和品类认知类问题不出现具体品牌。竞品类问题只比较目标品牌和一个适用竞品。
- 每题都用自由 `tags` 标记诊断意图、品牌范围和实际测试的属性。详细字段和校验规则见该 Skill 的 `SKILL.md`。

## `evals/v3` 是什么

`evals/v3/` 里有 9 份旧版 `overseas-geo-question-bank/v3` 题库样本，包含不同品牌和品类的历史输入与生成结果。

它们现在不是四个 Skill 的运行依赖，也不会被下方测试命令执行。保留它们是为了回看旧版题库结构、复盘品类漂移和“只问采购知识”等历史问题。新题库一律使用 v8，新增改动应以各 Skill 自带的 fixture 和测试为准，不要把 v3 当作当前产物合同。

## 本地验证

在仓库根目录运行：

```bash
python3 -m unittest discover -s skills/geo-presales-eval-case-builder/evals -p 'test_*.py'
python3 -m unittest discover -s skills/geo-presales-prompt-builder/evals -p 'test_*.py'
python3 -m unittest discover -s skills/geo-presales-report-audit/tests -p 'test_*.py'
python3 -m unittest discover -s skills/geo-presales-report-editor/scripts/tests -p 'test_*.py'
```

测试不调用外部 AI 平台。
