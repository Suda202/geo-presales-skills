# 情感判读交接契约(extract → 判读 → 归纳 → attach)

`sentiment-units.json`(judge extract 产出)与 `attach_sentiment.py`(builder 接入)之间有四个中间产物。此前只有口头惯例,2026-09-17 起以本文件为准;`scripts/prep_sentiment_handoff.py` 提供其中确定性环节的生成与校验,`scripts/run_pipeline.py` 会按序驱动。语义判读与观点归纳本身是语义工作,不得脚本化(禁止关键词自动打标)。

目录布局(均在报告输出目录下):

```
sentiment-units.json            judge extract 产出,全局单元表(下标即"全局 idx")
sentiment-batches/
  <品牌>.json                   拆批视图(split 生成,只读,给判读代理看)
  <品牌>-labels.json            判读结果(语义判读写)
  review-queue.md               判读待裁决清单(语义判读写,交 Suda 裁)
sentiment-claims/
  judged-sentences.json         判读句子表(assemble 确定性生成,勿手写)
  <品牌>-claims.json            观点归纳(语义归纳写,check-claims 校验)
```

## 1. `sentiment-batches/<品牌>.json` — 拆批视图

由 `prep_sentiment_handoff.py split --units --brands --out-dir` 生成。数组,每条:

```json
{"idx": 189, "brand": "Bewinch", "region": "MY", "platform": "chatgpt",
 "question_id": "0017", "intent": "Discovery", "sentence": "…"}
```

`idx` 是**全局 units 下标**。判读代理只读本品牌批次,不改此文件。

## 2. `sentiment-batches/<品牌>-labels.json` — 判读结果

语义判读按 `geo-presales-sentiment-judge/references/judgment-rules.md` 逐句判定后手写:

```json
{"positive": [200, 431, ...], "negative": [822, ...]}
```

- 索引是**全局 idx**(与拆批视图的 `idx` 字段一致,不是批次内序号)。
- 每个品牌一个文件;`attach_sentiment.py` 合并时校验跨品牌不重复、正负不重叠。
- 拿不准且影响正向率的单元记入 `review-queue.md`(格式:问题分组 + 例句 + 待裁决点),Suda 裁决后只改本文件重跑,不重新抽取。

## 3. `sentiment-claims/judged-sentences.json` — 判读句子表

由 `prep_sentiment_handoff.py assemble --units --labels-dir --brands --out` **确定性生成,不要手写**(2026-09-17 前靠人肉整理,Bewinch 案例已验证脚本输出与人肉版集合一致):

```json
{"<品牌>": {"positive": [{"idx":200,"region":"MY","platform":"chatgpt",
  "question_id":"0018","intent":"Competitor","sentence":"…"}, ...],
  "negative": [...]}}
```

每品牌每方向按全局 idx **升序**排列;观点归纳的 `indices` 指向这里的数组下标。

## 4. `sentiment-claims/<品牌>-claims.json` — 观点归纳

语义归纳:把该品牌判读句子归成 4–8 组「标签 + 成员」:

```json
{"brand": "Bewinch",
 "positive": [{"label": "免安装零管线", "count": 37, "indices": [0, 5, 6, ...],
   "evidence": {"sentence": "<原文整句>", "region": "MY", "platform": "chatgpt",
                "question_id": "0012"}}],
 "negative": [...]}
```

- `indices` 指向 judged-sentences.json 里该品牌**同方向数组的下标**(0..N-1),**不是全局 idx**——Bewinch 案例中 Coway 曾把全局 idx 写进来,导致该品牌观点组在报告切片时被静默丢弃。
- 每个方向的各组 indices 必须**互斥且穷尽**(并集 = 全部句子),`count` 必须等于 `indices` 长度。
- 写完必须跑门禁,退出码非 0 不得进入 attach:

```bash
python3 scripts/prep_sentiment_handoff.py check-claims \
  --judged <输出>/sentiment-claims/judged-sentences.json \
  --claims-dir <输出>/sentiment-claims
```

`attach_sentiment.py` 按切片过滤成员并重算计数;它**没有 `--claims-dir` 参数**,claims 目录固定从 `--labels-dir` 的父目录找 `sentiment-claims/`(即上面布局中的兄弟目录),不可配置。缺 claims 文件时回落到「句子前 24 字当标签」的旧行为,不报错——所以门禁必须在此前拦住格式问题。当前版本只消费**目标品牌**的 claims(竞品情感矩阵只用计数);竞品 claims 仍须过门禁,它们是归档产物,未来消费方会依赖契约合规。
