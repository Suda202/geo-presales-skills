# 海外 GEO Skills

海外 GEO 的 10 个 Skill。**售前诊断** 9 个：前期工作建 Case 和题库，之后主线一条命令从爬虫数据跑到 HTML 报告，另有「只要指标」和「改已有报告」两条支线。**售后** 1 个：签约后不重新生词，而是在售前诊断的基础上验证、补全、排序、固化正式监测词组。

## 售后：签约后的正式建库

售前负责发现候选机会；售后把售前的前半段做成正式台账——补齐客户内部数据（销售、客服、成交流失记录）、把诊断主题转成交付主题、锁定 Prompt 版本后建正式基线。

| Skill | 什么时候用 | 产出 | 不做什么 |
| --- | --- | --- | --- |
| `geo-after-sales-prompt-builder` | 已签约，要在售前诊断基础上建成正式监测词组 | 属性 × 意图的交叉主表、v8 监测词组、排期文件、输入差异清单 | 不做售前覆盖，不采集，不算指标，不判情感，不自行发现或冻结竞品（竞品核验走 `overseas-geo-competitor-research`） |

## 前期工作：建 Case 和题库

主线和两条支线都依赖两份输入——Case（品牌归一化档案）和 v8 题库。没有就先走这条链：

```text
品牌资料
  -> Eval Case Builder    品牌资料归一成 Case（含 2 个监测主题），写飞书 Base
  -> Prompt Builder       Case -> v8 英文监测题库
```

竞品核验可以单独跑（`overseas-geo-competitor-research`），也常在 Eval Case Builder 里一并完成：正式竞品不足 3 个或候选待核验时，Case Builder 会内部委派它联网核验并冻结 3 个同一购买集合的正式竞品。

## 对号入座

前期工作完成后，按手上的活选一条路径：**大多数情况走主线**——从采集数据一路跑到给客户看的 HTML 报告；只要指标数字、或改已有报告，才走另外两条。

### 主线 · 从爬虫数据到 HTML 报告

前置：已完成前期工作，手上有 Case 和题库。
输入：第三方采集目录（`<collect>/scraper.<platform>/<REGION>/<NNNN>.json`）+ 题库 + Case。
输出：单文件 HTML 售前诊断报告（支持国家 / 平台 / 主题三层筛选），内含全部可见度、引用与情感指标。

一条命令跑到下一个暂停点，补齐后重跑同一命令续跑：

```bash
cd skills/geo-presales-report-builder
python3 scripts/run_pipeline.py --collect <采集目录> --questions <题库.csv> \
  --case <Case.json> --lexicon assets/brand_lexicon.<品类>.json --out-dir <输出> \
  --brands "目标,配置1,配置2,配置3,开放1" --target <目标品牌> --brand-name <品牌>
```

`run_pipeline.py` 串起采集校验、词表冻结、指标计算、情感判读接入、翻译、渲染；确定性步骤自动跑，语义环节（词表冻结、Claim 判读、翻译）停下并提示补什么。链上各环节归属：

| 环节 | 谁负责 | 说明 |
| --- | --- | --- |
| 采集校验 | `geo-presales-crawl-integrity` | 先确认这份采集能不能用：分不清「正文明说品牌」和「只是被检索到」，提及率就会失真；有阻断缺陷不许往下算 |
| 指标 + 报告数据 + 渲染 | `geo-presales-report-builder` | 复用全库统一口径算可见度与引用类指标，渲染 HTML；不自己判情感，只把判读结果按切片汇总 |
| 情感判读 | `geo-presales-sentiment-judge` | 判读只有它做（Claim 抽取与聚类的规则都在它那里）；不提供 `--brands`/`--target` 时跳过，报告情感板块为 pending，正式交付不允许 |

要让 Agent 全程自动接管（到暂停点自动请对应 Skill 出场），用编排 Skill `geo-presales-pipeline`：它只定阶段顺序和暂停点分派，口径与实现仍全部在上面三个 Skill 里。

### 支线一 · 只要指标数字，不出报告

主线的前半段单独跑：只算可见度与引用类指标（提及率、提及率排名、声量份额、平均提及位置、可见度、引用次数），产出报告数据文件，不渲染 HTML。

```bash
cd skills/geo-presales-report-builder
python3 scripts/build_report_data.py --collect <采集目录> --questions <题库.csv> \
  --case <Case.json> --out <输出>/report-data.json
```

两条注意事项与主线相同：先跑 `geo-presales-crawl-integrity` 确认采集能用；必须补上 `--lexicon assets/brand_lexicon.<品类>.json --domain-cache assets/domain-categories.json`——**口径要求声量份额与提及率排名的分母是全部纳入品牌（目标 + 3 个配置竞品 + 开放词表命中），省略时开放品牌不进指标，算出来的数不成立，不能当正式指标交付**。这两个文件用 `mine_brand_lexicon.py` 和 `collect_domain_candidates.py` 生成（见 [SKILL.md](skills/geo-presales-report-builder/SKILL.md) 步骤 2–3）。需要「正向情感占比」时另跑 `geo-presales-sentiment-judge`。

### 支线二 · 已有报告要改

| 要改什么 | 用哪个 Skill |
| --- | --- |
| 品牌提及识别 / 正文首现排序有问题 | `geo-presales-report-audit`（先修底层） |
| 客户结论要改、要出上传 CSV | `geo-presales-report-editor`（在修好的底层上改结论） |

先用 Report Audit 把底层结果改对，再用 Report Editor 改结论；两者处理同一份报告的不同层次，可连用。

> 指标口径全库只有一份实现：Report Builder、Report Audit、Crawl Integrity 都直接引用它算数，自己不另写。位置和改动方式见文末「开发与维护」。

## 完整清单（10 个 Skill）

| Skill | 路径 | 什么时候用 | 产出 | 不做什么 |
| --- | --- | --- | --- | --- |
| `geo-presales-pipeline` | 主线（编排） | 有采集目录 + Case + 题库，要一路跑到 HTML 报告，让 Agent 在每个暂停点自动请对应 Skill 出场 | 阶段顺序 + 暂停点分派；产物即主线各 Skill 的产物 | 零新逻辑：不定义口径、不校验、不判读、不审计、不出上传 CSV |
| `geo-presales-crawl-integrity` | 主线 | 算任何指标之前，先确认这份采集能不能用：每条回答是正文明说了品牌，还是只是被检索到 | 分层判定 + 问题清单，指明涉及的平台和文件 | 不算提及率、声量、排名、引用份额，不判情绪，不纠品牌 |
| `geo-presales-report-builder` | 主线 | 有采集目录 + 题库 + Case，要一份能给客户看的报告 | 可见度与引用类指标 + 单文件 HTML 报告，支持国家 / 平台 / 主题三层筛选 | 不做情感判读（归 sentiment-judge，只汇总其结果），不另写指标口径（复用全库统一实现），不出上传 CSV，不纠品牌识别，不做采集校验 |
| `geo-presales-sentiment-judge` | 主线 | 需要句级正负句和正向情感占比 | 逐句 CSV + 正向情感占比，按品牌、意图、平台分层 | 只算「正向情感占比」一个指标；不改后端已有的情绪字段，不判竞品胜负，不算可见度 |
| `geo-presales-report-audit` | 支线二（跨路径） | 品牌提及识别或正文首现排序需要审核和修正 | 修正后的品牌提及识别与首现排序、安全补丁、可复现的问题说明与 Bad Case 草稿 | 不改客户结论，不审情绪，不做竞品研究或出题 |
| `geo-presales-report-editor` | 支线二 | 底层结果已确认，要改客户结论并出上传件 | 更新后的客户结论、可上传 CSV | 不重算底层，不渲染 HTML，不操作报告页面 |
| `overseas-geo-competitor-research` | 共用 | 正式竞品不足 3 个，或用户填的候选需要核验 | 3 个通过同一购买集合硬门槛的正式竞品 + 选择证据 | 不建 Case、不出题、不采集 |
| `geo-presales-eval-case-builder` | 共用 | 有品牌资料，要构建监测输入或积累到飞书 Base | 规范化 Case、2 个监测主题、已核验竞品，写入飞书 Base | 不出题、不采集、不写报告 |
| `geo-presales-prompt-builder` | 共用 | 已有 Case，要生成英文 AI 搜索监测题库 | `overseas-geo-question-bank/v8` 题库、属性规划、质量报告 | 不建主题、不选竞品、不算指标 |
| `geo-after-sales-prompt-builder` | 售后 | 已签约，要用售前诊断建正式监测词组 | 属性 × 意图交叉主表、v8 监测词组、排期文件、输入差异清单 | 不做售前覆盖、不采集、不算指标、不判情感、不自选竞品 |

**Report Audit 跨两条路径。** 它既服务于支线二的修正流程，它的采集原始层脚本也被主线的 Report Builder 直接引用——去引用正文是品牌识别的入口，两边必须用同一份实现。

## 指标归属一览

| 指标 | 谁算 | 口径实现 |
| --- | --- | --- |
| 提及率、提及率排名、声量份额、平均提及位置、可见度 | `geo-presales-report-builder` | 全库统一实现（`geo_presales_core`） |
| 引用次数 | `geo-presales-report-builder` | 只计正文里带编号的引用标记出现次数，不拿供应商给的来源清单凑数 |
| 正向情感占比（判读） | `geo-presales-sentiment-judge` | 正向句 ÷（正向句 + 负向句），排除中性 |
| 正向情感占比（按切片汇总进报告） | `geo-presales-report-builder` | 复用 sentiment-judge 的判读结果，按国家 / 平台 / 主题分别统计 |

**改口径只改统一实现这一处**，其他 Skill 对它只读。位置、改动前的验证命令和影响范围见文末「开发与维护」。

## 关键约束

**Prompt Builder**

- 每个 Topic 先排属性优先级（P1 核心 / P2 次要 / P3 补充），再出题。
- 每个 Topic 固定 25 题：不点品牌的发现类问题 `23-2n` 条、每个适用竞品各 1 条竞品对比题、目标品牌与每个竞品各 1 条评价题（共 `1+n`）、品类认知 1 条；不出验证题与事实核验题（这两类留给售后）。（`n` = 该 Topic 的适用竞品数，1–3 个）
- 每个 Topic 里不点品牌的发现类问题必须覆盖该 Topic 的全部核心属性（P1）；信息不足直接报 Case 过薄，不凑题。
- 不点品牌的发现类问题与品类认知题不出现任何具体品牌；每题用 `tags` 标出它测什么、品牌范围如何（`tags` 只是标注，不参与指标口径）。
- 正式可见度只统计 Discovery（不点品牌的发现类问题）这一类，品类认知等其他类型都不进分子分母。

**Report Builder**

- 引用次数只计正文里带编号的引用标记的出现次数，不拿供应商字段的来源清单充数。
- 正文为空的答案不进任何分母，也不计为「未提及」。
- 声量份额、平均提及位置与提及率排名的分母 / 比较范围都是全部纳入品牌（目标 + 3 个配置竞品 + 开放词表命中），前端只展示 5 行是为了可读性。
- 交付前必须做一次独立复算校验（`verify_report_data.py`）并全部通过，不通过不出报告。

## 开发与维护（同事可跳过）

以下面向改脚本、跑测试的人。

### 指标口径实现

统一实现在 `skills/geo-presales-report-editor/scripts/geo_presales_core/`，其他 Skill 只读。改动前先跑：

```bash
python3 -m unittest discover -s skills/geo-presales-report-editor/scripts/tests
```

并在改动说明里写明受影响的下游 Skill。

### 跨 Skill 路径

脚本按自身位置定位兄弟 Skill：每个脚本都在 `<skills>/<skill>/scripts/` 下，用 `Path(__file__).resolve().parents[2]` 找到 skills 根目录。整套放在一起时，从任意工作目录调用都可以。

单独部署某个 Skill、兄弟目录不在同一层时，用环境变量指定：

```bash
export GEO_PRESALES_SKILLS_ROOT=/path/to/skills
```

### 本地验证

在仓库根目录运行：

```bash
python3 -m unittest discover -s skills/geo-presales-eval-case-builder/evals -p 'test_*.py'
python3 -m unittest discover -s skills/geo-presales-prompt-builder/evals -p 'test_*.py'
python3 -m unittest discover -s skills/geo-presales-report-audit/tests -p 'test_*.py'
python3 -m unittest discover -s skills/geo-presales-report-editor/scripts/tests -p 'test_*.py'
python3 -m unittest discover -s skills/geo-presales-sentiment-judge/tests -p 'test_*.py'
python3 -m unittest discover -s skills/overseas-geo-competitor-research/scripts/tests -p 'test_*.py'
python3 -m unittest discover -s skills/geo-after-sales-prompt-builder/scripts -p 'test_*.py'
```

测试不调用外部 AI 平台。

### 不随仓库分发

各 Skill 的 `assets/` 下按客户生成的品牌词表与引用域名缓存、`build/` 运行产物都不入库，`.gitignore` 已排除。需要时按对应 `SKILL.md` 在自己的 `assets/` 下生成。
