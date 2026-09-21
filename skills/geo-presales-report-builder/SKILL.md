---
name: geo-presales-report-builder
description: This skill should be used when generating a customer-facing overseas GEO presales diagnosis report (single-file HTML, V4.0 prototype styling) directly from Scrapeless crawler collection data plus a Case record, covering visibility, citations, sentiment, content planning and per-question detail with country / platform / topic filtering. Do not use it to compute the upload CSV (that is geo-presales-report-editor), to audit brand mention recognition, or to write report conclusions by hand.
metadata:
  author: Overseas GEO Project
  version: "2.0.0"
---

# 海外 GEO 售前诊断报告生成

## 负责什么

把「采集目录 + Case 记录」变成一份可直接给客户看的单文件 HTML 售前诊断报告，视觉与信息结构对齐 `售前报告V4.0原型`。

负责：读取 Scrapeless 采集 JSON、按国家/平台/主题切分、复用后端指标管线算全部指标、渲染 HTML。

不负责：采集数据的可信度校验（走 `geo-presales-crawl-integrity`，本 skill 的前置步骤）、上传用 CSV 的生成与结论撰写（走 `geo-presales-report-editor`）、品牌提及识别的纠错（走 `geo-presales-report-audit`）、句级情绪判读的规则制定（走 `geo-presales-sentiment-judge`）。

## 开始前读取

1. [数据接口契约](references/report-data-contract.md)——数据层与渲染层之间唯一的接口，改动任何一侧前必须先读。
2. [渲染规范](references/render-spec.md)——正文/pill/表格/商品卡的渲染规则、部署体积陷阱与验证方式,改 `report.js`、`report-extra.css` 或 markdown 转换前必读。
3. [重跑与产物卫生](references/rerun-and-artifact-hygiene.md)——修复抽取器/清洗器/渲染器或替换已交付报告时必读；规定隔离重跑、labels 安全迁移、残留扫描、旧新对账与快照验收。
4. [客户中途换竞品](references/competitor-swap.md)——换展示竞品时聚合板块与逐回答的两条规则,客户中途提出换品牌时先读。
5. [跨 skill 规范映射](../shared/canonical-intent-mapping.md)——诊断意图与客户标签的唯一权威词表。
6. `geo-presales-crawl-integrity` 的校验产出（前置步骤，见执行流程第 0 步）。

## 输入

| 输入 | 必需 | 说明 |
|---|---|---|
| 采集目录 | 是 | `<collect>/scraper.<platform>/<REGION>/<NNNN>.json`。区域目录名不限，按实际存在的读 |
| 题库 CSV | 是 | 至少含 `query / question_zh / topic / diagnosis_intent / tags / question_types`，行序即题号 |
| Case 记录 | 是 | 品牌、官网域名、3 个配置竞品及其域名、品类 |
| 品牌词表 | 建议 | 开放品牌集，决定声量份额分母的覆盖度 |
| 域名类别缓存 | 建议 | 引用来源分类，缺省时未登记域名会落到「其他」 |

**Case 记录必须以客户确认后的最新版本为准。** 同一品牌的磁盘上可能同时存在多份 Case（初版与客户核对版），竞品集可能不同——取错会让整份报告的竞品对比失去意义，用之前先确认哪份是当前版本（实例见 [案例备注](references/case-notes.md)）。

## 执行流程

整条链可用驾驶脚本一条命令跑到下一个暂停点(词表冻结、情感判读、观点归纳、翻译是语义/人工环节,脚本会停下并打印缺什么、按什么格式补,补齐后重跑同一命令续跑):

```bash
python3 scripts/run_pipeline.py --collect <采集目录> --questions <题库.csv> \
  --case <Case.json> --lexicon assets/brand_lexicon.<品类>.json --out-dir <输出> \
  --brands "目标,配置1,配置2,配置3,开放1" --target <目标品牌> --brand-name <品牌> [--dry-run]
```

退出码:`0` 跑完到渲染、`3` 停在暂停点、其余为某步失败。它只调度不实现,各步口径以下列分步定义为准;单独重跑某一步时直接用该步命令。

0. **先校验采集数据可信度**：用 `geo-presales-crawl-integrity` 检查采集目录，它会逐平台报出字段层混用、参考定义丢失、引用字段为空、答案失败等问题，并指名具体文件。**跳过这一步会把采集缺陷当成品牌表现**——实测中单个任务出现过数十到上百条空答案、空 URL 占位与题面缺失（规模实例见 [案例备注](references/case-notes.md)）。校验结论要写进报告的可用性说明。

1. **确认口径与输入**：目标品牌、配置竞品（3 个）、官网域名、市场列表、平台列表。平台与市场从采集目录结构推断，不要写死。

2. **确认或生成开放品牌词表**：

   ```bash
   python3 scripts/mine_brand_lexicon.py --collect-dir <采集目录> --out build/brand-candidates.csv
   ```

   词表落 `assets/brand_lexicon.<品类>.json`，正式结构为 `brands[].name/aliases/type`；也兼容 `geo-presales-report-audit` 的「标准名 → 别名 list」dict 词表（别名会保留，`_` 开头的键按元数据跳过）。跨 skill 复用同一份词表时优先 `brands[]` 结构。新品类首次运行时，挖掘出的候选需要人工过一遍再冻结——机器无法可靠区分品牌名与品类词/技术缩写。

3. **补判未登记的引用域名**（不是封闭集合）：

   ```bash
   python3 scripts/collect_domain_candidates.py --collect <采集目录> --case <Case.json> \
     --cache assets/domain-categories.json --out build/domain-candidates.json
   ```

   逐条读域名与其页面标题判读类别，写回 `assets/domain-categories.json`。该文件随每次运行生长，判过的域名下次直接命中。

4. **生成数据**：

   ```bash
   python3 scripts/build_report_data.py --collect <采集目录> --questions <题库.csv> \
     --case <Case.json> --lexicon assets/brand_lexicon.<品类>.json \
     --domain-cache assets/domain-categories.json --out <输出>/report-data.json
   ```

5. **情感判读（Claim 层，可选；缺省时情感板块显示「待接入」）**：

   走 `geo-presales-sentiment-judge` 的四层结构 `answer → evidence_text → Claim → Attribute → Theme`（契约见该 skill 的 [Claim 层契约](../geo-presales-sentiment-judge/references/claim-layer-contract.md)，**不必再读本 skill 的句级交接契约**）。

   ```bash
   J=../geo-presales-sentiment-judge/scripts/sentiment_sentences.py
   # 1) 抽取单元（evidence_text 候选，确定性）
   python3 $J extract --bank <题库.csv> --crawl-dir <采集目录> \
     --lexicon assets/brand_lexicon.<品类>.json --output <输出>/sentiment-units.json
   # 2) 语义暂停：抽取只出 claim → claims-raw.json（unit_index/brand/claim/sentiment）
   # 3) 聚类 1：claim → attribute（在去重清单上做，写 claim-attributes.json）
   python3 $J claims-cluster-list --input <输出>/claims-raw.json --key claim \
     --output <输出>/cluster-claims.json
   # 4) 聚类 2：attribute → theme（写 attribute-themes.json）
   python3 $J claims-cluster-list --input <输出>/claim-attributes.json --key attribute \
     --output <输出>/cluster-attributes.json
   # 5) 回装校验 + 统计（确定性）
   python3 $J claims-assemble --units <输出>/sentiment-units.json --claims <输出>/claims-raw.json \
     --claim-attributes <输出>/claim-attributes.json --attribute-themes <输出>/attribute-themes.json \
     --output <输出>/claims.json
   python3 $J claims-metrics --claims <输出>/claims.json \
     --brands "目标,配置1,配置2,配置3,开放1" --out-metrics <输出>/claims-metrics.json
   ```

   三层各由一趟工序产出:**抽取只出 claim;attribute 是相近 claim 的聚类,theme 是 attribute 的再聚类**。聚类必须分开做且在去重清单上做,否则同一 attribute 会被各回答各起一个名字。

   接入（脚本按 Claim 信号口径聚合，并与 `claims-metrics` 逐品牌对账，不一致直接报错）：

   ```bash
   python3 scripts/attach_sentiment.py --report <输出>/report-data.json \
     --units <输出>/sentiment-units.json --labels-dir <输出>/sentiment-batches \
     --brands "目标,配置1,配置2,配置3,开放1" --target <目标品牌> \
     --claims <输出>/claims.json --expected-metrics <输出>/claims-metrics.json \
     --out <输出>/report-data.json
   ```

   - **Claim 层是推荐路径**：统计单位是 Claim 信号（同回答同品牌同 semantic claim 只计 1 次，同 Attribute 下不同 Claim 各计一次，跨回答分别计数），跨平台对有信号的平台等权平均。输出 `sentiment.metric_basis = "claim_signals"`；前端读字段前先看它。
   - `--theme-keywords` 只在**不传 `--claims` 的句级降级路径**下才需要（它把自由标签归到主题）；Claim 层自带 `theme` 字段，不依赖关键词表。
   - **同一份报告只能用一种口径**：走了 Claim 层就不要混用句级 `compute` 的数字，两者不可比。

6. **中文译文**（可选；不跑则抽屉只显示原文）：

   采集数据不含译文，需要外翻一轮：

   ```bash
   python3 scripts/export_translations.py --collect <采集目录> --regions MY,SG      --batch-size 40 --out-dir <输出>/translation-batches
   ```

   分批翻译成 `<批次>-zh.json`，格式 `{"<key>": "<中文 markdown>"}`。翻译要求：保留 markdown 结构、品牌名与型号保留英文、URL 与数值原样、商品清单表格照原样不填空单元格、不增删信息。派翻译子代理时让它**每翻完一条立即落盘**（一次性写大 JSON 失败过）。回填：

   ```bash
   python3 scripts/attach_translations.py --report <输出>/report-data.json      --batches <输出>/translation-batches --out <输出>/report-data.json
   ```

   缺条目会直接报错，确需部分交付加 `--allow-partial`。回填时会做**截断门禁**：长回答的译文/原文长度比显著低于全批中位时列出疑似截断条目（Bewinch 案例：8 条 5-7.5K 字符回答被翻译代理截到约六成、键齐全静默入库），默认警告并写入 `meta.translation_length_suspects`，加 `--strict-length` 升级为阻断；疑似条目重翻后重跑本命令覆盖。**译文体积大致翻倍**，加入后单文件 HTML 会明显变大。

7. **校验**：

   ```bash
   python3 scripts/verify_report_data.py --report <输出>/report-data.json --collect <采集目录>
   ```

   退出码非 0 不得交付。校验会独立复算每个切片并与产物对账，同时跑突变测试确认能发现错误。

8. **渲染**：

   ```bash
   python3 scripts/render_report.py --data <输出>/report-data.json --out <品牌>-售前诊断报告.html
   ```

   渲染前会做 JavaScript 语法检查；语法错误会直接中断，不产出白页。

9. **浏览器验证**：打开产物，逐个切国家 / 平台 / 主题，确认各模块有数、无空白、无变形。改了 JS 或 CSS 后必须重做这一步。脚本化遍历的已知坑：tab 按钮每次切换都被 `buildTabs()` 用 innerHTML 重建，**开头缓存的按钮引用第一次点击后即失效、后续点击静默无效**（Bewinch 案例两轮「45 切片全通过」实际只反复测了一个切片）——每次点击前必须重新 querySelector。

## 指标口径

口径全部复用 `geo-presales-report-editor/scripts/geo_presales_core` 的 `prepare_answers` 与 `compute_metrics`，本 skill 不另写指标。

**该目录归 `geo-presales-report-editor` 所有，本 skill 只读。** 发现口径不对时改在 owner 那边，不在本 skill 复制一份实现；本 skill 的 `verify_report_data.py` 是对它的独立复算，两者口径必须一致——不一致时以 owner 的定义为准，并把差异报出来，不要单方面对齐（2026-09-16 就出过一次：生产侧口径被静默改动，复算侧没跟，门禁报出的差异最终证明是生产侧的问题）。

| 指标 | 口径 |
|---|---|
| 提及率 | 目标品牌出现的回答数 ÷ 该切片全部 Discovery 可用回答数 |
| 提及率排名 | 按提及率在全部纳入品牌中的位置 |
| 声量份额 | 目标品牌提及量 ÷ **全部纳入品牌**提及量之和 |
| 平均提及位置 | 被提及时在全部纳入品牌中的首次出现次序均值 |
| 引用次数 | **只计正文 pill（`([来源名][N])`）的出现次数**，同一编号出现 N 次计 N 次，不做回答内去重；正文没有 pill 即 0 次，不拿供应商字段的来源清单充数 |
| 引用份额 | 指向官网的引用次数 ÷ 全部引用次数。**四个层级都保留**：单条回答（抽屉）、单题（明细表）、单平台（平台切片）、多回答多平台（全量切片） |
| 正向情感占比 | 正向 Claim 信号 ÷（正向 + 负向 Claim 信号），**排除中性**（句级降级路径按句数计） |

**引用伪拆分折叠只针对旧格式采集**：gemini/overview 平台按 `_citation_keep_mask` 折叠伪拆分（每个 canonical 保留出现次数最多的编号，同编号真重复保留）。供应商 2026-09-18 起的新格式批次来源列表已去重并带 `cited_count`（代数判别见 `geo-presales-crawl-integrity` 的数据分层契约与缺陷 D8），对新格式数据折叠应为无操作——若折叠改变数字,先查是否判错了代数。

**正式可见度只用 Discovery 意图**，Evaluation / Competitor / Category Awareness 不进可见度分母。

### 品牌集合与展示规则

参与计算的品牌 = 目标品牌 + 3 个配置竞品 + 开放品牌词表命中的品牌（单品类通常在几十到上百个）。声量份额与平均提及位置的分母都是这一整集，**不是只有展示的几个**。

前端每个榜单**只展示 5 行**：目标品牌 + 3 个配置竞品 + 1 个按提及率降序取到的开放竞品（已在前面出现则顺延）。其余品牌在环形图里合并为「其他品牌」段。情感矩阵同样只展示这 5 个品牌。

### 空答案

正文为空（strip 后为空串）的答案不进入任何分母，也不计为「未提及」。各平台的分母因此可能不等（实例见 [案例备注](references/case-notes.md)）。

## 切片与交互

切片键为 `<region>|<platform>|<topic>`，`""` 表示该维度不筛选，因此每个市场有 `(平台数+1) × (主题数+1)` 个切片，另需一组 `region=""` 的合并国家切片。

前端三层 tab：国家（首个选项为「全部国家」）→ 平台 → 主题。国家与平台是单选，主题可再次点击取消。

## 交付门槛

- **源码真相在本 skill,客户 HTML 只是产物**:任何修订都改 `scripts/` 与 `assets/` 后完整重跑数据层链路(build → attach_sentiment → attach_translations → verify → render),不得手改已渲染的单页 HTML——手改产物会在下次重渲染时被静默覆盖,且让产物与 `report-data.json` 脱钩。若修改了抽取器/清洗器或替换已交付报告,必须先在隔离输出目录重跑并按 [重跑与产物卫生](references/rerun-and-artifact-hygiene.md) 迁移 labels、对账旧新指标,通过后才替换正式文件。
- `verify_report_data.py` 退出码为 0，且突变测试全部检出。
- 在浏览器里逐层切过 tab，确认没有空白模块或错位。
- **正文不得带平台残留文案**:逐条扫 `Go to product viewer dialog for this item.`(明细与情感证据两处都要,详见 [渲染规范](references/render-spec.md))。
- **商品卡逐条核查**:客户会直接问「所有涉及商品卡的回答详情渲染都正常了吗」,交付前把含商品表的回答全部过一遍(中英文两版),不只抽查一条。
- 报告里出现的每个数字都能在 `report-data.json` 里定位到，不得有前端临时计算的指标。
- `meta.questions` 每题必须带 `intent`(从题库 `diagnostic_intent` 映射的中文标签):明细表的情感列、切片过滤都靠它,缺失时明细正向情感列会整列显示「—」(Bewinch 实例)。
- 情感板块若尚无判读数据，必须在 `meta.sentiment_claims_status` 标 `pending`，不允许用占位数字冒充。
- 产物归档到 `10-售前诊断报告/评测数据/<品牌名>/` 对应任务目录，与可见度统计并列。

## 已知边界

- **引用来源的展示类别固定 7 类**：自有网站 / 竞品网站 / 社交平台 / 媒体网站 / 新闻稿平台 / 机构网站 / 其他。以《引用来源分类》定义为准，不得增删。两条最容易搞错的边界：**只有本批已监测竞品的官网进「竞品网站」，回答里额外识别出的开放竞品官网不自动进这一类**；**未命中默认类别的企业网站（含其他厂商官网）归「其他」**。旧版的 `corporate_site`（企业网站）已取消，遇到历史值按「其他」处理。
- 引用来源类别依赖 `assets/domain-categories.json` 的判读覆盖度；未判读的域名回落「其他」。新品类首次运行时「其他」占比偏高属正常，补判后下降。
- 开放品牌集是词表驱动的，词表没收录的品牌不会进入声量分母。补充词表要重新跑数据层。
- 前端展示 5 行是为了可读性，不代表其余未展示品牌不影响结论；需要完整分布时看 `report-data.json` 的 `competition` 与 `matrix`。
