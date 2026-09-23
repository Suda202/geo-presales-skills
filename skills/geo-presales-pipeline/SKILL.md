---
name: geo-presales-pipeline
description: This skill should be used when running the full overseas GEO presales flow from a raw Scrapeless crawler collection directory all the way to the customer-facing single-file HTML diagnosis report — it orchestrates the stage order and, at each pause point, invokes the dedicated skill (geo-presales-crawl-integrity, geo-presales-report-builder, geo-presales-sentiment-judge) whose contract governs that stage. Do not use it to define or re-derive any metric caliber, to audit brand mention recognition (geo-presales-report-audit), to produce the upload CSV or written conclusions (geo-presales-report-editor), or to build the Case and question bank (前期工作链).
metadata:
  author: 海外 GEO 项目
  version: "1.0.0"
---

# 售前全链路编排：采集数据 → HTML 报告

## 目标与边界

把「第三方采集目录 + Case + 题库」一路带到可交客户的单文件 HTML 报告。**本 skill 只编排、零新逻辑**：口径、校验、计算、渲染全部在被调 skill 及其脚本里，这里只回答两个问题——下一步跑什么、停下来时该请哪个 skill 出场。

- 负责：阶段顺序、断点续跑、每个暂停点的分派。
- 不负责：任何指标口径（builder/editor 的统一实现）、采集缺陷的判定规则（crawl-integrity）、Claim 判读规则（sentiment-judge）、品牌纠错与 Bad Case（report-audit）、上传 CSV 与结论（report-editor）、Case 与题库生成（eval-case-builder / prompt-builder）。
- 本 skill 只服务「从爬虫数据出完整 HTML 报告」这一个任务。其他任务不要走本 skill：只要指标数字不出报告，直接用 `geo-presales-report-builder` 的 `build_report_data.py`（同样先过 crawl-integrity）；只判情感用 `geo-presales-sentiment-judge`；改已有报告走 `geo-presales-report-audit` → `geo-presales-report-editor`。

## 前置输入

| 输入 | 缺了怎么办 |
| --- | --- |
| Case JSON | 走 `geo-presales-eval-case-builder` |
| v8 题库 CSV | 走 `geo-presales-prompt-builder` |
| 采集目录 `<collect>/scraper.<platform>/<REGION>/<NNNN>.json` | 等第三方采集完成，本 skill 不采集 |

## 主命令：一条命令跑到下一个暂停点

驾驶脚本住在 report-builder（跨 skill 调度是它的既有职责，不搬家）：

```bash
cd <skills>/geo-presales-report-builder
python3 scripts/run_pipeline.py \
  --collect <采集目录> --questions <题库.csv> --case <Case.json> \
  --lexicon assets/brand_lexicon.<品类>.json --out-dir <输出目录> \
  --brands "目标,配置1,配置2,配置3" --target <目标品牌> --brand-name <品牌> \
  [--theme-keywords <主题关键词.json>] [--regions MY,SG] [--dry-run]
```

- **退出码 3 = 暂停点**：打印缺什么文件；按下面的指挥表补齐后**重跑同一命令**续跑。
- 暂停点产物（词表、claims、聚类映射、译文）重跑不会被覆盖；要重做先删对应文件。
- 不带 `--brands`/`--target` 会跳过情感环节（报告情感板块 pending）——正式交付不允许，只用于中途查看。
- `--lexicon` 是必填、`--domain-cache` 脚本已内置：声量份额与提及率排名的分母必须是全部纳入品牌（目标 + 3 配置竞品 + 开放词表命中），否则算出来的数不成立。
- 换品类必传 `--theme-keywords` 与 `--brand-suffixes`，否则主题矩阵落空、品牌名带品类后缀。

## 暂停点指挥表

**铁律：每到语义暂停点，先用 Skill 工具 invoke 对应子 skill，让它的契约进入上下文后再产出文件。禁止凭记忆写口径，禁止关键词自动打标。**

| 停在哪 | 请谁出场 | 干什么 |
| --- | --- | --- |
| 阶段 0 采集校验退出码 2（阻断）或 1（警告） | `geo-presales-crawl-integrity` | 按缺陷目录逐条定位到平台+文件，修采集或显式降级口径后续跑；不许带伤算指标 |
| 阶段 1 词表不存在 | 人工（Suda 或授权人） | 已挖掘候选 CSV；人工冻结成 `brands[].name/aliases/type`。机器分不清品牌名与品类词，**这步不能自动化** |
| 阶段 2 数据生成失败 | `geo-presales-report-builder` | 读数据接口契约排障；不要绕过 build_report_data 手搓数据 |
| 阶段 3b Claim 抽取 | `geo-presales-sentiment-judge` | 按 Claim 层契约逐单元拆原子 Claim；拿不准的进 review-queue 交 Suda 裁决 |
| 阶段 3d / 3f 两趟聚类 | `geo-presales-sentiment-judge` | claim→attribute、attribute→theme，维度>极性、theme 必须中性；输入是去重清单，同一 claim 只判一次 |
| 阶段 4 译文批次未齐 | 翻译（语义工作） | 补齐 `<批次>-zh.json`；确需部分交付走 `attach_translations.py --allow-partial` |
| 阶段 6 渲染完成 | 浏览器验证 | 逐个切国家/平台/主题，确认各模块有数、无空白、无变形；判据见 report-builder 的渲染规范 |

阶段 3 的机器工序（3a 抽取、3c/3e 去重清单、3g 回装、3h 统计、3i 接入）由脚本自动跑，不需要分派；3h 与 3i 之间有 `--expected-metrics` 对账门禁，两处实现不一致会报错，报错时回 sentiment-judge 排口径，不许改数硬过。

## 完成与出口

- 完成标准：HTML 渲染成功 + `verify_report_data.py` 通过 + 浏览器逐切片检查无空白变形。不以「命令跑完」为完成。
- 报告数字有疑点（品牌识别错、排名不对）→ `geo-presales-report-audit`，改完从阶段 2 重跑。
- 要交上传 CSV 与客户结论 → `geo-presales-report-editor`，输入是本链产出的已确认数据。
- 替换已交付报告或修复抽取器后重跑 → 先读 report-builder 的《重跑与产物卫生》，隔离重跑，不许原地覆盖。
