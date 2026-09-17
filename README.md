# GEO 售前 Skills

海外 GEO 售前诊断的 8 个 Skill。先按你手头的任务对号入座，再查完整清单。

## 对号入座：三类任务

### 任务一 · 从第三方爬虫数据做指标统计

输入：第三方采集目录（`<collect>/scraper.<platform>/<REGION>/<NNNN>.json`）+ 题库 + Case。
输出：提及率、提及率排名、声量份额、平均提及位置、可见度、正向情感占比。

按顺序用这三个：

| 步骤 | Skill | 干什么 |
| --- | --- | --- |
| 1 | `geo-presales-crawl-integrity` | 先校验这份采集能不能当输入用，不把采集缺陷当成品牌表现 |
| 2 | `geo-presales-report-builder` | 算全部统计指标（复用 `geo_presales_core` 口径），产出 `report-data.json` |
| 3 | `geo-presales-sentiment-judge` | 需要句级正/负句和「正向情感占比」时用它 |

```bash
cd skills/geo-presales-report-builder
python3 scripts/build_report_data.py --collect <采集目录> --questions <题库.csv> \
  --case <Case.json> --lexicon assets/brand_lexicon.<品类>.json \
  --domain-cache assets/domain-categories.json --out <输出>/report-data.json
```

### 任务二 · 指标统计 + 生成 HTML 报告

在任务一的基础上多一步渲染，产出能给客户看的单文件 HTML 报告（支持国家 / 平台 / 主题三层筛选）：

```bash
cd skills/geo-presales-report-builder
python3 scripts/run_pipeline.py --collect <采集目录> --questions <题库.csv> \
  --case <Case.json> --lexicon assets/brand_lexicon.<品类>.json --out-dir <输出> \
  --brands "目标,配置1,配置2,配置3,开放1" --target <目标品牌> --brand-name <品牌>
```

`run_pipeline.py` 一条命令串起指标计算、词表冻结、情感判读接入、翻译、渲染；语义环节会停下并提示补什么，补齐后重跑同一命令续跑。

### 任务三 · 已有报告，要修改

| 要改什么 | 用哪个 Skill |
| --- | --- |
| 品牌提及识别 / 正文首现排序有问题 | `geo-presales-report-audit`（先修底层） |
| 客户结论要改、要出上传 CSV | `geo-presales-report-editor`（在修好的底层上改结论） |

先用 Report Audit 把底层结果改对，再用 Report Editor 改结论；两者处理同一份报告的不同层次，可连用。

> 指标口径只有一个实现：`geo-presales-report-editor/scripts/geo_presales_core/`。Report Builder、Report Audit、Crawl Integrity 都引用它算数，自己不另写指标。

## 输入准备（任务开始前）

| 我想做的事 | 用哪个 Skill |
| --- | --- |
| 正式竞品不足 3 个，或候选竞品要核验 | `overseas-geo-competitor-research` |
| 把品牌资料归一成 Case、写飞书 Base | `geo-presales-eval-case-builder` |
| 已有 Case，要生成英文 AI 搜索监测题库 | `geo-presales-prompt-builder` |

## 完整清单（8 个 Skill）

| Skill | 链条 | 什么时候用 | 产出 | 不做什么 |
| --- | --- | --- | --- | --- |
| `geo-presales-crawl-integrity` | A | 算任何指标之前，先确认采集能不能当输入用 | 缺陷清单 + 退出码（`0` 可用 / `1` 警告 / `2` 阻断） | 不算提及率、声量、排名、引用份额，不判情绪，不纠品牌 |
| `geo-presales-report-builder` | A | 有采集目录 + 题库 + Case，要一份能给客户看的报告 | 全部统计指标 + 单文件 HTML 报告，支持国家 / 平台 / 主题三层筛选 | 不另写指标口径（复用 `geo_presales_core`），不出上传 CSV，不纠品牌识别，不做采集校验 |
| `geo-presales-sentiment-judge` | A | 需要句级正负句和正向情感占比 | 逐句 CSV + 正向情感占比，按品牌、意图、平台分层 | 只算「正向情感占比」一个指标；不回写后端 `sentiment` 字段，不判竞品胜负，不算可见度 |
| `geo-presales-report-audit` | B（跨链） | 品牌提及识别或正文首现排序需要审核和修正 | 修正后的 `brand_rankings`、安全补丁、可复现的问题说明与 Bad Case 草稿 | 不改客户结论，不审情绪，不做竞品研究或出题 |
| `geo-presales-report-editor` | B | 底层结果已确认，要改客户结论并出上传件 | 更新后的客户结论、可上传 CSV | 不重算底层，不渲染 HTML，不操作报告页面 |
| `overseas-geo-competitor-research` | 共用 | 正式竞品不足 3 个，或用户填的候选需要核验 | 3 个通过同一购买集合硬门槛的正式竞品 + 选择证据 | 不建 Case、不出题、不采集 |
| `geo-presales-eval-case-builder` | 共用 | 有品牌资料，要构建监测输入或积累到飞书 Base | 规范化 Case、2 个监测主题、已核验竞品，写入飞书 Base | 不出题、不采集、不写报告 |
| `geo-presales-prompt-builder` | 共用 | 已有 Case，要生成英文 AI 搜索监测题库 | `overseas-geo-question-bank/v8` 题库、属性规划、质量报告 | 不建主题、不选竞品、不算指标 |

**Report Audit 跨两条链。** 它的报告 JSON 层服务于链 B 的修正流程；它的采集原始层脚本（`de_cite_crawl.py`、`verify_brand_extraction.py`）被链 A 的 Report Builder 直接引用——去引用正文是品牌识别的入口，两边必须用同一份实现。

## 指标归属一览

| 指标 | 谁算 | 口径实现 |
| --- | --- | --- |
| 提及率、提及率排名、声量份额、平均提及位置、可见度 | `geo-presales-report-builder` | `geo_presales_core`（`report-editor/scripts/` 下） |
| 引用次数 | `geo-presales-report-builder` | 只计正文 pill（`([来源名][N])`）出现次数 |
| 正向情感占比 | `geo-presales-sentiment-judge` | 正向句 ÷（正向句 + 负向句），排除中性 |

**改口径只改 `geo_presales_core` 这一处。** 其他 Skill 对它只读；改动前先跑 `python3 -m unittest discover -s skills/geo-presales-report-editor/scripts/tests`，并在说明里写明受影响的下游 Skill。

## 关键约束

**Prompt Builder**

- 每个 Topic 先做独立的 P1 / P2 / P3 属性规划，再出题。
- 每个 Topic 固定 25 题，按适用竞品数 `n` 执行 `23-2n / n / 0 / 0 / 1+n / 1` 配额。
- 每个 Topic 的 Discovery 必须覆盖全部 P1 属性；信息不足时报 Case 过薄，不凑题。
- Discovery 与 Category Awareness 不出现具体品牌；每题用自由 `tags` 标记诊断意图、品牌范围和实际测试的属性。
- 正式可见度的分子分母只统计 `Intent: Discovery` 题。

**Report Builder**

- 引用次数只计正文 pill（`([来源名][N])`）的出现次数，不拿供应商字段的来源清单充数。
- 正文为空的答案不进任何分母，也不计为「未提及」。
- 声量份额与平均提及位置的分母是全部纳入品牌（目标 + 3 个配置竞品 + 开放词表命中），前端只展示 5 行是为了可读性。
- 交付前必须跑 `verify_report_data.py` 且退出码为 0，它是对指标口径的独立复算。

## 跨 Skill 路径

脚本按自身位置定位兄弟 Skill：每个脚本都在 `<skills>/<skill>/scripts/` 下，用 `Path(__file__).resolve().parents[2]` 找到 skills 根目录。整套放在一起时，从任意工作目录调用都可以。

单独部署某个 Skill、兄弟目录不在同一层时，用环境变量指定：

```bash
export GEO_PRESALES_SKILLS_ROOT=/path/to/skills
```

## 本地验证

在仓库根目录运行：

```bash
python3 -m unittest discover -s skills/geo-presales-eval-case-builder/evals -p 'test_*.py'
python3 -m unittest discover -s skills/geo-presales-prompt-builder/evals -p 'test_*.py'
python3 -m unittest discover -s skills/geo-presales-report-audit/tests -p 'test_*.py'
python3 -m unittest discover -s skills/geo-presales-report-editor/scripts/tests -p 'test_*.py'
python3 -m unittest discover -s skills/geo-presales-sentiment-judge/tests -p 'test_*.py'
python3 -m unittest discover -s skills/overseas-geo-competitor-research/scripts/tests -p 'test_*.py'
```

测试不调用外部 AI 平台。

## 不随仓库分发

各 Skill 的 `assets/` 下按客户生成的品牌词表与引用域名缓存、`build/` 运行产物都不入库，`.gitignore` 已排除。需要时按对应 `SKILL.md` 在自己的 `assets/` 下生成。
