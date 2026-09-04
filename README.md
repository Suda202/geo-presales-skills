# GEO 售前 Skills

这是海外 GEO 售前诊断的四个 Skill 包，覆盖从品牌资料整理、监测问题设计，到报告产出和结果审计的流程。

```text
品牌资料
  -> Case Builder
  -> Prompt Builder
  -> 外部采集和后端统计（不在本仓库）
  -> Report Audit
  -> Report Editor
  -> 客户报告和 CSV
```

## 选哪个 Skill

| Skill | 什么时候用 | 产出 | 不做什么 |
| --- | --- | --- | --- |
| `geo-presales-eval-case-builder` | 有品牌资料，需要构建售前诊断报告的标准输入字段，或把 Case 积累到飞书 Base | 规范化 Case、1–3 个监测主题、已核验竞品，写入飞书 Base | 不出题、不采集回答、不写报告 |
| `geo-presales-prompt-builder` | 已有 Case，需要生成英文 AI 搜索监测题库 | `overseas-geo-question-bank/v8` 题库、属性规划、质量报告 | 不创建主题、不选竞品、不计算指标 |
| `geo-presales-report-editor` | 底层品牌提及、排序与情绪结果已确认，需要修改报告分析结论并生成上传 CSV | 更新后的客户分析结论、可上传 CSV | 不重算底层结果，不修改 HTML 或页面 |
| `geo-presales-report-audit` | 需要审核或修正品牌提及识别、正文首次出现排序或情绪分类结果 | 修正后的结构化结果、安全补丁、可复现的问题说明与必要的 Bad Case 草稿 | 不修改客户报告分析结论，不做竞品研究或出题 |

先用 `geo-presales-report-audit` 修正品牌提及识别、首次出现排序与情绪分类等底层结果；再用 `geo-presales-report-editor` 基于已确认的结果修改分析结论并生成上传 CSV。两者处理报告的不同层次，可以连续使用。

## Prompt Builder 的关键约束

- 每个 Topic 都要先做独立的 P1、P2、P3 属性规划。
- 题数按 Topic 的有效属性覆盖分配，整批最多 60 题，不为凑数重复提问。
- 每个 Topic 内，发现类问题必须严格多于其他问题类型之和。
- 发现类和品类认知类问题不出现具体品牌。竞品类问题只比较目标品牌和一个适用竞品。
- 每题都用自由 `tags` 标记诊断意图、品牌范围和实际测试的属性。详细字段和校验规则见该 Skill 的 `SKILL.md`。

## 本地验证

在仓库根目录运行：

```bash
python3 -m unittest discover -s skills/geo-presales-eval-case-builder/evals -p 'test_*.py'
python3 -m unittest discover -s skills/geo-presales-prompt-builder/evals -p 'test_*.py'
python3 -m unittest discover -s skills/geo-presales-report-audit/tests -p 'test_*.py'
python3 -m unittest discover -s skills/geo-presales-report-editor/scripts/tests -p 'test_*.py'
```

测试不调用外部 AI 平台。
