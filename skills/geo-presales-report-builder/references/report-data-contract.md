# report-data.json 接口契约

本文件是「数据层」与「渲染层」之间的唯一接口。数据层由 `scripts/build_report_data.py` 产出 `report-data.json`，渲染层由 `scripts/render_report.py` 消费。

## 顶层结构

```json
{
  "schema": "geo-presales-report-data/v1",
  "meta": { ... },
  "slices": { "<region>|<platform>|<topic>": { ... } },
  "details": { "<region>|<platform>|<NNNN>": { ... } }
}
```

## details（抽屉明细）

放在顶层而不是切片里：同一题的答案会出现在多个切片，放进切片会让文件成倍膨胀。抽屉按当前国家与平台查找；「全部国家」时取该平台第一个可用市场。

```json
{
  "question_zh": "中文释义",
  "answer": "该题在该平台该市场的回答原文（最多 6000 字）",
  "brands": [{"name": "Bewinch ★", "domain": "bewinch.com", "rank": 1, "target": true}],
  "citations": [{"title": "页面标题", "url": "https://…", "host": "forbes.com"}]
}
```

- `brands` 只列展示的 5 个品牌中在该回答里出现过的，`rank` 是首次出现次序。
- `citation_occurrences` = 该回答正文里 pill（`([来源名][N])`）的出现次数；`citation_share` = 其中指向本品官网的比例。**引用份额有四个计算层级且都保留**：单条回答（本字段）、单题（`records[].citation_share`）、单平台（平台切片的 `kpis.official_share`）、多回答多平台（`||` 切片）。
- `citations` 只来自正文 pill；正文没有 pill 的回答计 0 次引用，**不拿供应商字段的来源清单充数**。缺定义行的 pill 按位置回退解析 URL（那是解析，不是计数来源），解析不出则记 unresolved。列表来自该平台自己的引用字段（AIO=`source`、Gemini=`citations`、ChatGPT=`content_references`、Perplexity=`web_results`），URL 为空或为平台站内跳转的条目已丢弃。
- **中文译文**：采集数据不含译文，由 `export_translations.py` 导出原文、外部翻译后经 `attach_translations.py` 回填为 `answer_zh_html`。缺字段时抽屉只显示「回答原文」一个 tab。
- `answer_html` 与 `answer_zh_html` 都是在数据层由 markdown 转换并转义过的成品 HTML，渲染层直接注入，不要再二次转义。

## meta

| 字段 | 类型 | 说明 |
|---|---|---|
| `brand` | string | 目标品牌名，如 `Bewinch` |
| `brand_display` | string | 展示名，含 `★`，如 `Bewinch ★` |
| `brand_suffixes` | string[] | 展示时从品牌名剥掉的品类/产品线后缀（`--brand-suffixes` 注入）；空数组时渲染层用内置净水器词表兜底 |
| `official_domain` | string | 官网域名，如 `bewinch.com` |
| `category` | string | 品类中文名，如 `台式净饮机` |
| `generated_at` | string | ISO 时间戳 |
| `regions` | string[] | 市场代码，渲染为顶层 tab，如 `["MY","SG"]` |
| `platforms` | string[] | 平台显示名，渲染为平台 tab，如 `["AIO","Gemini","ChatGPT","Perplexity"]` |
| `topics` | string[] | 监测主题全称 |
| `intents` | string[] | 诊断意图中文标签，取自 `shared/canonical-intent-mapping.md` |
| `tags` | string[] | 标签，取自题库 |
| `questions` | object[] | 每题的静态信息，见下 |

`questions[]` 条目：

```json
{"qid": 1, "en": "英文 Prompt 原文", "zh": "中文释义", "topic": "台式轻饮机", "intent": "发现", "tag": "品牌进入"}
```

## slices 的键

`"<region>|<platform>|<topic>"`。`platform` 用平台显示名，`topic` 用主题全称。**必须同时提供全量切片**，即 `platform` 为 `""` 表示「全部平台」、`topic` 为 `""` 表示「全部主题」，因此每个 region 下有 `(len(platforms)+1) × (len(topics)+1)` 个切片。

## 单个 slice

```json
{
  "kpis": {
    "mention_rate": "60.0%",
    "mention_rank": "3",
    "share_of_voice": "24.0%",
    "average_rank": "4.1",
    "official_share": "6.0%"
  },
  "competition": {
    "mention": [["显示名","domain.com","78.0%","100%","",1]],
    "share": [20, 26, 21, 17, 16],
    "rank": [["显示名","domain.com","2.4"],["…","…","4.1","target"]]
  },
  "matrix": {
    "platforms": ["ChatGPT","AIO","Gemini","Perplexity"],
    "mention":  [{"name":"Bewinch ★","target":true,"vals":[64,51,52,54]}],
    "share":    [{"name":"…","target":true,"vals":[27,16,22,19]}],
    "rank":     [{"name":"…","target":true,"vals":[4.1,3.8,4.4,4.6]}],
    "sent":     [{"name":"…","target":true,"vals":[100,66.7,100,100]}],
    "official": [{"name":"…","target":true,"vals":[6,3,8,4]}]
  },
  "sources": {
    "total_citations": 83,
    "official_share": "6.0%",
    "types": [["自有网站","15.0%","37","green"]],
    "domains": [["fragrance.com","31","社交平台"]],
    "pages": [["byrdie.com/best-colognes","媒体网站","提及","20.5%"]],
    "official_pages": [["chanel.com/us/…","2.4%"]]
  },
  "sentiment": {
    "summary": {"total":12,"pos":10,"neu":1,"neg":1,"pos_rate":"90.9%","neg_rate":"9.1%"},
    "claims": {
      "pos": [{"label":"免安装零管线","count":37,
               "evidence":{"sentence":"英文原句","region":"MY","platform":"aio","question_id":"0043"}}],
      "neg": [{"label":"加水耗材负担","count":2,"evidence":{...}}]
    },
    "matrix": {
      "columns": ["正向率","正向句","负向句"],
      "rows": [
        {"brand":"Bewinch","target":true,"values":["96.3%","157","6"]},
        {"brand":"Coway","values":["81.7%","107","24"]}
      ]
    }
  },
  "records": [
    {
      "qid": 1, "en": "…", "zh": "…",
      "mention_rate": "66.7%", "rank": "2.0", "share": "20.0%",
      "citation_share": "6.0%", "sentiment": "90.9%",
      "discovery": true, "mentioned": true
    }
  ]
}
```

### 各字段的硬性约定

**competition**

- `mention` 每行 6 项：`[显示名, 域名, 百分比字符串, 条宽百分比字符串, fill 颜色, 原始排名数字]`。颜色取值 `""`（墨色）/`gold`/`blue`/`cyan`/`green`/`amber`/`red`。目标品牌必须是 `gold`。
- 展示 **5 行**：目标品牌 + 3 个配置竞品 + 1 个开放竞品（按提及率从高到低取，若已在前面出现则顺延）。不足 5 行时按实际数量输出。
- `share` 是与 `mention` **同序**的数字数组，单位是百分比数值（如 `20` 表示 20%）。
- `rank` 每行 3 或 4 项：`[显示名, 域名, 平均提及位置字符串]`，目标品牌行加第 4 项 `"target"`。品牌名必须与 `mention` 里逐字一致。
- 三者的顺序：`mention` 按提及率降序，`rank` 按平均提及位置升序。

**matrix**

- `platforms` 是列顺序，取值来自 `meta.platforms`（不含「全部平台」）。
- 每个 metric 是行数组，行对象字段：`name`（含 ★）、`target`（布尔，可选）、`vals`（数字数组，与 `platforms` 同序）。缺失值用 `null`。
- `rank` 的 `vals` 是一位小数，`mention`/`share`/`sent`/`official` 是百分比数值。
- 行集合与 `competition.mention` 的 5 行一致。

**sources**

- `types` 每行 4 项：`[类别中文名, 百分比字符串, 计数字符串, fill 颜色]`。类别固定 7 类：`自有网站`/`竞品网站`/`社交平台`/`媒体网站`/`新闻稿平台`/`机构网站`/`其他`；**行按引用条数降序排列**（同数按上述固定序兜底）。不得自行增删——后端 `SOURCE_TYPES` 是分类口径，报告展示类别是另一回事，以原型为准。
- `domains` 每行 3 项：`[域名, 计数字符串, 类别中文名]`，按计数降序，最多 8 行。
- `pages` 每行 4 项：`[URL, 类别中文名, 提及状态, 引用份额字符串]`，提及状态取值 `提及` 或 `未提及`。最多 8 行。
- `official_pages` 每行 2 项：`[URL, 引用份额字符串]`，最多 8 行。

**sentiment**

> **两种口径并存,同一份报告只能用一种**:`metric_basis=claim_signals` 表示走 Claim 层(Claim 信号统计,推荐);无该字段表示句级降级路径(整句正负计数)。两者数字不可比。

- `summary.pos_rate` 与 `neg_rate` 的分母是 `pos+neg`，**排除中性**，且两者相加为 100%。
- **Claim 层**(`--claims` 提供时):`summary.total` = 去重后的 Claim 信号数(同回答同品牌同 semantic claim 只计 1 次,同 Attribute 下不同 Claim 各计一次);`pos_rate_cross_platform` 是各平台先算、再对**有信号的平台等权平均**的结果(无信号平台不补 0);`platforms_with_signal` 要一并展示,否则客户会以为等权值覆盖了全部平台。
- `claims.pos` / `claims.neg` 是**归纳后的观点组**：`label` 为 4–8 字中文短语，`count` 是该观点在本切片内的出现次数，`evidence` 每组只给**一条**最有代表性的句子并附 `region`/`platform`/`question_id`（面板上的「查看对应回答」据此跳转）。
- 归纳本身是全局做的；**每个切片按成员归属过滤后重算 `count` 并重选证据**，某切片里一条都不含的观点组不出现在该切片。
- `matrix` 是**品牌情感占比表**，不是「属性 × 品牌」矩阵：判读按整句给方向、没有逐句属性标注，按关键词把长句切进属性格会同时错配品牌与方向，给客户看会误导。
- `theme_matrix` 是**主题 × 品牌**矩阵（`themes` / `brands` / `matrix[theme][brand]`），与 `matrix` 并存的另一维度，别混用：
  - 单元格取该主题下**计数最高的 claim 标签**作为代表描述（`top_claim` + `top_dir`），前端展示的是这个描述文本，**不是数字**；`pos`/`neg`/`rate` 只供筛选与排序。
  - 主题由 `--theme-keywords` 的词表把 claim 标签归一来定；未命中的归「其他」且不入矩阵。**换品类必须提供该品类的关键词表**，否则矩阵整块为空。
  - 展示颜色：正向绿、负向红、无数据 `—` 黑；主题列与非目标品牌表头黑，目标品牌高亮。
- `rows[].values` 与 `columns` 同序；`target` 为真的行是本品。末列「代表证据」要求句子明确点名该品牌且不含其他展示品牌，并优先取 60 字以上的完整句（标题式短句说明不了问题）。
- `by_brand` 在 Claim 层下按品牌给 `signal_total` / `positive_signals` / `negative_signals` / `pos_rate` / `pos_rate_cross_platform` / `platforms_with_signal` / `by_platform` / `by_attribute` / `by_theme`；句级路径下是 `positive`/`negative`/`pos_rate`。前端读字段前先看 `metric_basis`。

**records**

- 每题一行。
- `discovery` 是布尔，取该题的诊断意图是否为 `discovery`；`target_in_question` 是布尔，取题面是否点名目标品牌（用与正文识别同一套别名匹配）；`mentioned` 是布尔，取目标品牌在该题的有效回答里是否出现过；该题在本切片无有效答案时 `mentioned` 为 `null`（与 `rank` 的 `—` 同步）。
- 前三者是内容规划「官网阵地」清单的取数判据：**`(discovery || target_in_question) && !mentioned`** 才是内容缺口。理由是该题的目标品牌为被期待对象——发现题里用户没点名品牌，品牌本该争夺一席；题面点名目标品牌时，AI 说不出它的话就是缺口；而题面只点名竞品的评价题、以及只问品类选择标准的品类认知题不算。**不要**让渲染层去比 `intent` 的中文标签或 `mention_rate` 的百分比字符串。
- `sentiment` 仅情绪题有值，其余为 `null`。**该列是目标品牌口径**（目标品牌在该题该切片判读句子的正向情感占比）；`—` 表示目标品牌在该切片无正负句，属正常空值，不是回填缺陷——发现题的回答常只罗列品牌（中性提及），评价题问竞品时目标品牌可能不在答案里（Bewinch 实测：有值 126 条，其余 `—` 全部核实为真实无正负句）。抽屉内「每个回答的逐品牌情感」是另一个功能（`details[key].sentiment`），两者定位不同。
- **`details[key].sentiment` 有提及门禁**：只列该回答里**真的被判出过句子**的品牌（`build_answer_sentiment` 按 `(question_id, region, platform)` 匹配判读结果），没提到的品牌不出现。聚合板块（主题矩阵、品牌占比条）是全批次统计，换展示品牌可整体替换；逐回答**不得硬塞**——客户中途换竞品的完整规则见 [客户中途换竞品](competitor-swap.md)。
- `mention_rate`/`share`/`citation_share` 是该题在该切片下的值。

## 口径来源

- 可见度、声量、平均提及位置、引用、机会分档：复用 `geo-presales-report-editor/scripts/geo_presales_core` 的 `prepare_answers` 与 `compute_metrics`。
- 正式可见度只用 Discovery 意图。情绪样本用 `analysis_type` 含 sentiment 的题。
- 声量份额分母 = 全部纳入对象的提及次数之和；纳入对象 = 目标品牌 + 3 个配置竞品 + 开放品牌词表命中的品牌。
- 空答案（正文为空）不进入任何分母。
