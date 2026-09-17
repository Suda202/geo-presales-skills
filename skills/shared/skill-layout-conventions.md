# 售前 Skill 目录布局约定

适用于 `.agents/skills/` 下的售前 skill 家族。目的:让后续维护者不用猜测试和用例放在哪、该跑哪条命令。

## 目录职责

| 目录 | 放什么 | 怎么跑 |
|---|---|---|
| `tests/` | Python unittest(`test_*.py`)与测试 fixture | `python3 -m unittest discover -s tests -p 'test_*.py'` |
| `evals/` | 语义评估用例 JSON(`trigger_cases.json`、`quality_cases.json` 等,由 Agent 语义执行)以及少数历史上放这里的 unittest | 用例 JSON 按各 SKILL.md 的说明执行;含 unittest 的另跑 discover |
| `scripts/` | 确定性脚本 | 见各 SKILL.md 的命令 |
| `references/` | 契约、规则、示例等按需读取的参考 | — |
| `assets/` | 词表、域名缓存等可复用数据资产 | — |
| `reports/` | 门禁结果与变更记录快照 | — |

## 现状与新增约定

- **新建 skill 一律**:unittest 放顶层 `tests/`,语义用例 JSON 放 `evals/`,两者不混放。
- 历史遗留(不强迫迁移,跑测试前先看这张表):
  - `geo-presales-prompt-builder`、`geo-presales-eval-case-builder`:unittest 在 `evals/` 下。
  - `geo-presales-report-editor`、`overseas-geo-competitor-research`:unittest 在 `scripts/tests/` 下。
  - `geo-presales-report-builder`:`tests/` 只放 fixture(`fixture_report_data.json`,被 `verify_report_data.py --self-test` 流程消费),没有 unittest。
  - `geo-presales-crawl-integrity`、`shared`:暂无 unittest。
- `unittest discover` 返回 exit 5(NO TESTS RAN)说明找错了目录,不是测试通过;按上表换目录再跑。

## 词表与共享资产

- 品牌词表命名统一下划线 `brand_lexicon.<维度>.json`;首选结构 `brands[].name/aliases/type`,dict 型「标准名 → 别名 list」为兼容格式(消费方均已适配,`_` 开头的键为元数据)。`shared/brand-lexicon.botslab.json` 是历史命名,保留不改。
- 指标口径唯一实现在 `geo-presales-report-editor/scripts/geo_presales_core/`;`shared/scripts/` 下的三个指标脚本已标记 DEPRECATED,仅只读参考。
