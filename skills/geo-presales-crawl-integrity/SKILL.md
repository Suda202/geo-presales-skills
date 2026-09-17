---
name: geo-presales-crawl-integrity
description: This skill should be used before computing any overseas GEO presales metric, to verify that a raw crawler collection directory (Scrapeless scraper.<platform>/<REGION>/<NNNN>.json) is trustworthy input — detecting field-layer mixing, lost reference definitions, empty citation fields and failed answers, and naming the exact platform + file for each. Do not use it to compute visibility or citation metrics, to correct brand rankings, or to judge sentiment.
metadata:
  author: 海外 GEO 项目
  version: "1.0.0"
---

# 采集数据可信性前置校验

## 目标与边界

在算任何指标之前回答一个问题：**这份采集能不能当输入用**，不能的话是哪几条记录、错在哪一层。

- 只做校验与分层，**不算提及率、声量、排名、引用份额，不判情绪，不纠品牌**。指标走 `geo-presales-report-builder`，品牌纠错走 `geo-presales-report-audit`，句级情绪走 `geo-presales-sentiment-judge`。
- 只读采集文件，**不修改任何采集数据**。产出是缺陷清单，不是修好的数据。
- 检测结果必须能指到具体平台和文件；不接受「品牌实体识别」这类无法定位环节的笼统归因。
- 不把第三方模型的正常输出差异当缺陷，不为凑数量找问题。

## 开始前读取

1. [数据分层契约](references/layer-contract.md)——四层数据定义、每平台字段映射、两个计数单位、缺失状态约定。判读任何一条前先读这个。
2. [已知缺陷目录](references/defect-catalog.md)——D1–D7 的现象、一手证据、检测方法与影响范围。
3. [平台字段契约](references/platform-contract.json)——**平台会持续扩展**：新增平台在这里加一条即可，不必改脚本；有平台没登记时脚本报 `UNKNOWN_PLATFORM_CONTRACT` 阻断，不静默跳过。

## 为什么必须先跑这一步

采集器的字段会把不同层的数据混在一起，混用不会报错，只会静默产出错误的对外数字。已实测的两个例子：

- `mentioned_<brand>` 标记把检索结果当成回答正文，Botslab 的报告口径写 4.44% 提及率，按正文口径实际是 **0/89**。
- ChatGPT 某条回答的 `content_references` 是空数组，而正文有 3 条引用定义、4 次标记——直接取字段会让该条被判成「无引用」。

两个错误都不会抛异常，只有分层核对才能发现。

## 执行流程

1. **确认输入**：采集目录、目标品牌名。目标品牌用于分层统计（正文命中 vs 检索层命中）。

2. **跑校验**：

   ```bash
   python3 scripts/audit_crawl_integrity.py \
     --collect-dir <采集目录> --target <品牌名> --out <输出>/crawl-integrity.json
   ```

3. **读退出码**：

   | 退出码 | 含义 | 处理 |
   |---|---|---|
   | `0` | 无缺陷、无警告 | 可进入指标计算 |
   | `1` | 只有警告（D2/D3/D6） | 按缺陷目录的修复规则补齐后再算指标 |
   | `2` | 有阻断缺陷（D1/D5/D7） | **先修采集或显式降级口径，不得直接算指标** |

   D4（`CITATION_UNITS` 计数单位说明）只进 `infos`，不影响退出码。脚本的判定规则：有任何 defect 即 `2`，否则有任何 warning 即 `1`，否则 `0`。

4. **按缺陷码分派**：
   - `MENTION_FLAG_LAYER_MIXING`、`FAILED_ANSWER`、`EMPTY_ANSWER` → 阻断。提及率与分母必须改用正文口径重算，并在交付里写明原始标记与真实口径的差异。
   - `MISSING_REFERENCE_DEFINITION` → 按 `citations[N-1]` 位置回退补齐，回退项必须在产出里标注 `mapping_method`，不与前向匹配混同。
   - `EMPTY_CITATION_FIELD` → 改用正文解析作为该条的引用来源。
   - `CITATION_FIELD_BODY_MISMATCH` → 逐条看方向：正文更全还是字段更全。两个方向都存在过，不能固定信一侧。
   - `TEXT_CORRUPTION` → 警告。受影响条目的**原文与译文不得直接交付客户**，须先校正或在报告里标注采集异常。新损坏词追加进 `KNOWN_TEXT_CORRUPTION` 清单，不要改成启发式匹配。
   - `PLATFORM_MARKUP_IN_BODY` → 不是缺陷。平台自带标记（`<Elicitation>`、`<FollowUp>`）混在正文里属正常输出形态，下游做句子切分、翻译与引用解析前要先剥掉。
   - `UNKNOWN_PLATFORM_CONTRACT` → **阻断**。有平台目录没登记契约，该平台整批未被审计；补 `references/platform-contract.json` 后重跑，不得据此宣称采集可信。
   - `TARGET_OUTSIDE_BODY_ONLY` → 不是缺陷。这是「被检索但未被提及」的内容机会，单独统计并交给内容侧。

5. **交下游前对齐口径**：品牌分母、引用计数单位（次数 vs 去重来源）的唯一权威实现是 `geo-presales-report-editor/scripts/geo_presales_core/`（`geo-presales-report-builder` 复用该实现），本 skill 不另立一套。两处不一致时以 core 的定义为准。

## 交付门槛

- `audit_crawl_integrity.py` 的退出码与结论一致；退出码非 0 时不得宣称采集可信。
- 每类缺陷都给出完整的 `平台 + 文件` 清单，不得只报数量或少量示例。
- 阻断缺陷必须在结论里给出「原始口径 → 修正口径」的前后数字。
- 缺陷报告归档到 `10-售前诊断报告/评测数据/<品牌名>/` 对应任务目录，与指标产出并列。
- 若把缺陷反馈给采集供应商，附上可复跑命令与该条记录的字段证据，不复述推测。

## 已知边界

- 字段映射按 2026-09-11 的四平台 HTML 核验结果；平台改版或供应商改字段需重新核验后更新 `references/layer-contract.md`。
- 正文引用标记的语法识别依赖 `([来源名][编号])` / `[编号]: url` 约定。标记缺失但正文有普通超链接时，本 skill **不判断**该链接是否算引用——按契约由业务规则决定，不替爬虫猜。
- 没有原始 HTML 时不能断言平台页面真实展示结构；`result_html`（aimode）可用于 DOM 核验，其余三平台只能以交付字段为准。
- 检索层字段只有 ChatGPT 明确暴露（`search_result`、`links`、`sse_data`）；Gemini 与 Overview 未公开独立检索结果字段，不得用来源面板或 `related_queries` 冒充。
