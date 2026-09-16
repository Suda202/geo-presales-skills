# 原始爬虫层品牌抽取

适用对象：采集目录里的原始响应（`<collect>/scraper.<platform>/<REGION>/<NNNN>.json`），**还没有** `wordid` / `brand_rankings`。报告 JSON 层的审计见 [结构化结果审计](structured-result-audit.md)。

本文件只覆盖「把原始回答变成可排名品牌序列」这一段。指标计算不在这里。

## 为什么是两步而不是一步

去引用是确定性的，品牌判断是语义性的，混在一起做会两者都不可靠：

```
原始响应 ──de_cite_crawl.py（确定性）──▶ 去引用正文
                                          │
                              品牌抽取（语义判断，可并行分片）
                                          │
                              verify_brand_extraction.py（确定性）
                                          │
                              归一标准名 → 按首现位置排名
```

## 一、去引用（确定性）

```bash
python3 scripts/de_cite_crawl.py \
  --collect-dir <采集目录> --question-bank <题库.json> \
  --out <输出>/normalized-answers.jsonl
```

规则：

- 回答正文按平台取：`chatgpt`/`gemini` → `result_text`；`aimode` → `result_md`；`overview` → `content`。其余字段（`search_result`、`links`、`sse_data`、`products`、`ads`、`citations`、`source`、`web_source`）是别的层级，**不进入正文**。
- 删除正文尾部的 `[编号]: url "标题"` 定义行、行内 `([来源名][编号])` 标记、普通 markdown 超链接（保留可见文字）、图片与 HTML 标签。
- **商品卡表格**（`| id | goods | price | rating | merchants | picture |`）：
  - `goods` 列是可见产品名，**保留**，其中的品牌计入；
  - `merchants` 列是销售渠道（Best Buy，或品牌自营店），**整体清空**。产出里 `body_markdown` 保留原样，`body_ranking` 是清空后的版本——**排名一律用 `body_ranking`**。
- 模型失败页（"I encountered an error…" 之类，去引用后 < 200 字符）标 `answer_status = unavailable`，不进任何分母。

## 二、品牌抽取（语义判断，按分片并行）

按 [结构化结果审计 §3](structured-result-audit.md) 的两遍法，落到原始层时：

**分片契约**：按 `平台 × 顺序` 切 15 条一片，每片一个 Subagent。每片只读自己的分片文件，**只写自己的 `extract-<platform>-<n>.json`**，不碰别的分片、不改采集数据。

每片产出：

```json
[{
  "answer_id": "chatgpt:BOT-T1-D01:0001",
  "brands": [{"brand": "VIOFO", "evidence": "首次出现处的正文片段"}],
  "excluded_entities": [{"name": "Best Buy", "reason": "商品卡 merchants 列渠道"}],
  "new_entities": [],
  "uncertainties": []
}]
```

- `brands` **按首次出现顺序**排列，不写排名数字；顺序即排名。
- 每个品牌名必须能在该条正文中检索到。
- 清单外的新品牌照常计入并在 `new_entities` 单独列出，**不擅自并入**其他品牌。
- 拿不准的写 `uncertainties`，不硬判。

**编排方（主 Agent）必须做的**：分片全部回收后，先建立全批次标准词典并归一，再算任何排名。不要等排完名再改名——那会造成名次漂移和同一品牌重复占位。

## 三、独立校验（确定性）

```bash
python3 scripts/verify_brand_extraction.py \
  --normalized <normalized-answers.jsonl> \
  --extractions <抽取目录> \
  --lexicon assets/brand_lexicon.<case>.json \
  --out <输出>/verification.json
```

退出码非 0 不得进入指标计算。四项检查：

| 检查 | 抓什么 |
|---|---|
| 1 名称在正文中 | 记录的品牌名在正文里找不到（凭印象写的） |
| 2 首现顺序 | 记录顺序 ≠ 正文首次出现先后（凭榜单印象排序） |
| 3 标准名一致性 | 同一品牌被写成多种大小写，即将占两个名次 |
| 4 召回 | 标准词典命中的品牌在记录中缺失 |

第 3 项是硬性前置。**已实证**：分片抽取时两个分片各写了一种大小写，未归一直接算排名，`Lamtto`/`LAMTTO` 与 `Wolfbox`/`WOLFBOX` 各被拆成两行、各占一个名次，品牌总数从 20 虚增到 22。

第 4 项需要 `--lexicon`；不给则跳过。词典是每个 Case 的资产，放 `assets/brand_lexicon.<case>.json`，键是标准名、值是正文里出现过的写法；下划线开头的键视为元信息。

## 已知陷阱（均有一手证据）

- **merchants 列的品牌名不是品牌首现**。品牌自营店（"$149.99 - eufy"、`VIOFO Direct`）属销售渠道，不计入首现位置。若改用「计入」，受影响回答的首现顺序会变。
- **goods 列无品牌前缀的纯型号行不计入**（"Nexus 5"、"DR970X-2CH Plus II"）。
- **正文引用标记是否等于原站 citation pill 无法从 JSON 证实**，需原始 HTML。按项目既有口径把交付的 Markdown 标记作为回退证据。
- **回答正文比供应商引用字段更完整**：实测过字段为空而正文有 4 次标记的回答，也实测过正文丢定义行而字段完整的回答。两个方向都存在，不能固定信一侧。
- **采集器的 `mentioned_*` 标记不可作为提及依据**——它扫的是整个响应体（含检索结果、原始流、购物卡片）。检测与处理见 `geo-presales-crawl-integrity`。
