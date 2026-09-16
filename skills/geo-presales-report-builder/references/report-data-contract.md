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
| `official_domain` | string | 官网域名，如 `bewinch.com` |
| `category` | string | 品类中文名，如 `台式净饮机` |
| `generated_at` | string | ISO 时间戳 |
| `regions` | string[] | 市场代码，渲染为顶层 tab，如 `["MY","SG"]` |
| `platforms` | string[] | 平台显示名，渲染为平台 tab，如 `["AIO","Gemini","ChatGPT","Perplexity"]` |
| `topics` | string[] | 监测主题全称 |
| `intents` | string[] | 诊断意图中文标签，取自 `shared/canonical-intent-mapping.md` |
| `tags` | string[] | 标签，取自题库 |
| `grade_names` | object | `{"P0":"优先改进","P1":"持续优化","P2":"保持稳定"}` |
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
      "pos": [{"text":"多场合适配","claim":"中文论断句","evidence":"英文原句"}],
      "neg": [{"text":"留香与扩散争议","claim":"…","evidence":"…"}]
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
      "citation_share": "6.0%", "sentiment": "90.9%", "grade": "P0"
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

- `summary.pos_rate` 与 `neg_rate` 的分母是 `pos+neg`，**排除中性**，且两者相加为 100%。
- `claims.pos` / `claims.neg` 各最多 3 条，来自目标品牌的句级情感判读。
- `matrix` 是**品牌情感对比表**，不是「属性 × 品牌」矩阵：判读按整句给方向、没有逐句属性标注，按关键词把长句切进属性格会同时错配品牌与方向，给客户看会误导。
- `rows[].values` 与 `columns` 同序；`target` 为真的行是本品。末列「代表证据」要求句子明确点名该品牌且不含其他展示品牌，并优先取 60 字以上的完整句（标题式短句说明不了问题）。

**records**

- 每题一行，`grade` 取值 `P0`/`P1`/`P2`：未提及 → `P0`；提及位置 ≥4 → `P1`；1–3 → `P2`。
- `sentiment` 仅情绪题有值，其余为 `null`。
- `mention_rate`/`share`/`citation_share` 是该题在该切片下的值。

## 口径来源

- 可见度、声量、平均提及位置、引用、机会分档：复用 `geo-presales-report-editor/scripts/geo_presales_core` 的 `prepare_answers` 与 `compute_metrics`。
- 正式可见度只用 Discovery 意图。情绪样本用 `analysis_type` 含 sentiment 的题。
- 声量份额分母 = 全部纳入对象的提及次数之和；纳入对象 = 目标品牌 + 3 个配置竞品 + 开放品牌词表命中的品牌。
- 空答案（正文为空）不进入任何分母。
