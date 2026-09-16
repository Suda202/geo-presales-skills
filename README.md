# GEO 售前 Skills

海外 GEO 售前诊断的 8 个 Skill，分两条链。

- **链 A（自产报告）**：输入是第三方爬虫采集的 JSON，一路算到单文件 HTML 诊断报告。
- **链 B（修订报告）**：输入是已经生成的诊断报告或后端统计包，只改结果和结论，不重算、不渲染。

两条链共用一组输入准备 Skill，把品牌资料变成可监测的 Case 和题库。

## 两条链

### 链 A · 从第三方采集数据自产 HTML 报告

采集目录形态为 `<collect>/scraper.<platform>/<REGION>/<NNNN>.json`。

```text
采集目录（第三方 JSON）
  -> Crawl Integrity     校验这份采集能不能当输入用
  -> Sentiment Judge     抽句级正负句，算正向率
  -> Report Builder      算全部指标 + 渲染单文件 HTML
  -> 客户诊断报告 HTML
```

### 链 B · 基于已生成的诊断报告做修正

```text
已有诊断报告 / 后端统计包
  -> Report Audit        修正品牌提及识别与正文首次出现排序
  -> Report Editor       按确认后的结果改客户结论
  -> 可上传结论 CSV
```

先用 Report Audit 把底层结果改对，再用 Report Editor 改结论。两者处理同一份报告的不同层次，可以连着用。

### 共用输入准备

```text
品牌资料
  -> Competitor Research    联网冻结 3 个同一购买集合的正式竞品
  -> Eval Case Builder      品牌资料归一成 Case 字段，写飞书 Base
  -> Prompt Builder         Case -> v8 英文监测题库
```

## 选哪个 Skill

| Skill | 链条 | 什么时候用 | 产出 | 不做什么 |
| --- | --- | --- | --- | --- |
| `geo-presales-crawl-integrity` | A | 算任何指标之前，先确认采集能不能当输入用 | 缺陷清单 + 退出码（`0` 可用 / `1` 警告 / `2` 阻断） | 不算提及率、声量、排名、引用份额，不判情绪，不纠品牌 |
| `geo-presales-sentiment-judge` | A | 需要句级正负句和正向率 | 逐句 CSV + 正向率，按品牌、意图、平台分层 | 不回写后端 `sentiment` 字段，不判竞品胜负，不算可见度 |
| `geo-presales-report-builder` | A | 有采集目录 + 题库 + Case，要一份能给客户看的报告 | 单文件 HTML 报告，支持国家 / 平台 / 主题三层筛选 | 不出上传 CSV，不纠品牌识别，不做采集校验 |
| `geo-presales-report-audit` | B（跨链） | 品牌提及识别或正文首现排序需要审核和修正 | 修正后的 `brand_rankings`、安全补丁、可复现的问题说明与 Bad Case 草稿 | 不改客户结论，不审情绪，不做竞品研究或出题 |
| `geo-presales-report-editor` | B | 底层结果已确认，要改客户结论并出上传件 | 更新后的客户结论、可上传 CSV | 不重算底层，不渲染 HTML，不操作报告页面 |
| `overseas-geo-competitor-research` | 共用 | 正式竞品不足 3 个，或用户填的候选需要核验 | 3 个通过同一购买集合硬门槛的正式竞品 + 选择证据 | 不建 Case、不出题、不采集 |
| `geo-presales-eval-case-builder` | 共用 | 有品牌资料，要构建监测输入或积累到飞书 Base | 规范化 Case、2 个监测主题、已核验竞品，写入飞书 Base | 不出题、不采集、不写报告 |
| `geo-presales-prompt-builder` | 共用 | 已有 Case，要生成英文 AI 搜索监测题库 | `overseas-geo-question-bank/v8` 题库、属性规划、质量报告 | 不建主题、不选竞品、不算指标 |

**Report Audit 跨两条链。** 它的报告 JSON 层服务于链 B 的修正流程；它的采集原始层脚本（`de_cite_crawl.py`、`verify_brand_extraction.py`）被链 A 的 Report Builder 直接引用——去引用正文是品牌识别的入口，两边必须用同一份实现。

## 指标口径只有一个实现

`geo-presales-report-editor/scripts/geo_presales_core/` 是四个 Skill 共用的指标口径实现，Report Builder、Report Audit、Crawl Integrity 都直接引用它。

**其他 Skill 对这个目录只读。** 需要改口径就改在 owner 这边，不在下游复制一份。改之前先跑 `python3 -m unittest discover -s skills/geo-presales-report-editor/scripts/tests`，并在改动说明里写明受影响的下游 Skill 与指标——同一个函数改了，多份报告的同一列数字会一起变。

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

脚本按自身位置定位兄弟 Skill：每个脚本都在 `<skills>/<skill>/scripts/` 下，用 `Path(__file__).resolve().parents[2]` 找到 skills 根目录。所以整套放在一起时，从任意工作目录调用都可以。

单独部署某个 Skill、兄弟目录不在同一层时，用环境变量指定：

```bash
export GEO_PRESALES_SKILLS_ROOT=/path/to/skills
```

## 本地验证

在仓库根目录运行：

```bash
python3 -m unittest discover -s skills/geo-presales-eval-case-builder/evals -p 'test_*.py'
```

```bash
python3 -m unittest discover -s skills/geo-presales-prompt-builder/evals -p 'test_*.py'
```

```bash
python3 -m unittest discover -s skills/geo-presales-report-audit/tests -p 'test_*.py'
```

```bash
python3 -m unittest discover -s skills/geo-presales-report-editor/scripts/tests -p 'test_*.py'
```

```bash
python3 -m unittest discover -s skills/geo-presales-sentiment-judge/tests -p 'test_*.py'
```

```bash
python3 -m unittest discover -s skills/overseas-geo-competitor-research/scripts/tests -p 'test_*.py'
```

测试不调用外部 AI 平台。

## 不随仓库分发

各 Skill 的 `assets/` 下按客户生成的品牌词表与引用域名缓存、`build/` 运行产物都不入库，`.gitignore` 已排除。需要时按对应 `SKILL.md` 在自己的 `assets/` 下生成。
