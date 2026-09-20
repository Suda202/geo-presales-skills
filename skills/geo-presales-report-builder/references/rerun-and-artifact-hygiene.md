# 重跑、情感判读迁移与交付物卫生

本规范用于已经交付过、但需要修复数据清洗器、抽取器或渲染器的报告。核心原则是：**先在隔离输出验证，再替换正式产物；索引变化时按内容迁移判读，不能按旧数组位置硬套。**

**与 Claim 层路径的关系**：

- 若报告已升级到 Claim 层（`sentiment.metric_basis = "attribute_signals"`），判读产物的索引基座是 `claims.json` 的 `unit_index`。重抽 units 后旧 claims 会整体失效——**不能改索引硬套**，应重新走 Claim 抽取（`claims-assemble` 会校验索引越界与品牌不符），再按下方第 2 节的内容键规则做人工核对。
- 若仍在句级降级路径，按本文档第 2 节的 `(platform, region, question_id, brand, 规范化句子)` 内容键迁移 labels 与 `judged-sentences.json`。
- 两条路径的共同底线：**确定性清洗不得改变任何人的语义判断**；清洗只应让同一判断落到相同的句子/观点上。

## 1. 先保留旧交付物，隔离重跑

1. 记录正式报告目录、当前 HTML、`report-data.json`、`sentiment-units.json`、labels、claims 和译文批次的时间戳与文件大小。
2. 在新的临时输出目录重跑，不直接覆盖客户已看到的 HTML 或数据。
3. 先重新生成 `report-data.json`，再重新抽取情感单元；不要因为只是清洗正文就复用旧 `sentiment-units.json`。
4. 如原始采集校验出现阻断缺陷，保留 `crawl-integrity.json` 并明确记录降级原因；不得修改原始采集数据、伪造校验通过或把采集缺陷写成品牌表现。只有在本次变更目标是确定性的下游清洗、且用户已接受沿用既有降级口径时，才可继续生成；最终交付仍须通过 `verify_report_data.py`。

## 2. 抽取器改变后的 labels 安全迁移

`sentiment-units.json` 的数组位置是全局索引；任何抽取器清洗、去重、排序或字段修复都可能改变索引。**禁止直接把旧 labels 的整数索引写进新 units。**

只有同时满足以下条件时，才允许自动迁移旧的人工判读：

- 用 `(platform, region, question_id, brand, 规范化后的完整句子)` 建立内容键；规范化只处理确定性噪声和多余空白，不改变语义。
- 旧 units 的每一条都能在新 units 中找到唯一对应项；重复键必须按原出现顺序逐个配对并记录。
- 旧 units 在新 units 中保持有序子序列；若顺序变化、缺句、重复无法消歧或品牌归属变化，立即停止并重新判读，不猜索引。
- 每个展示品牌的 positive / negative labels 全部成功映射；迁移前后正负数量、品牌集合和方向互斥性一致。

迁移后必须重新执行：

```bash
python3 scripts/prep_sentiment_handoff.py split \
  --units <新输出>/sentiment-units.json \
  --brands "目标,配置1,配置2,配置3,开放1" \
  --out-dir <新输出>/sentiment-batches

python3 scripts/prep_sentiment_handoff.py assemble \
  --units <新输出>/sentiment-units.json \
  --labels-dir <新输出>/sentiment-batches \
  --brands "目标,配置1,配置2,配置3,开放1" \
  --out <新输出>/sentiment-claims/judged-sentences.json

python3 scripts/prep_sentiment_handoff.py check-claims \
  --judged <新输出>/sentiment-claims/judged-sentences.json \
  --claims-dir <新输出>/sentiment-claims
```

`check-claims` 即使只输出多属性句警告也要确认 `problems` 为空；有越界、未归组、重复方向或 count 不一致时不得接入。

完成 `attach_sentiment.py` 后，对旧/新数据按每个切片比较目标品牌与展示品牌的 `pos`、`neg`、`pos_rate`；确定性清洗不应悄悄改变原有判读统计。若新增内容本来未被人工判读，不得自动标正或负，只能保留为未判读。

## 3. 翻译、证据与残留文案的联合门禁

- 译文按 detail key 迁移可以独立于情感 units，但仍必须重新运行 `attach_translations.py --strict-length`；检查 `meta.translation_length_suspects` 是空数组。
- 平台 UI 残留必须同时扫三处：`report-data.json` 的原文/译文、`details[*].sentiment` 的证据句、最终 HTML。只扫 HTML 不足以保证下次重跑不会把脏数据重新带回。
- Scrapeless 商品查看器残留 `Go to product viewer dialog for this item.` 必须在生成层和情感抽取层都清洗；替换为空格而不是删除，避免相邻商品名粘连。
- 翻译批次中的原始输入备份可以保留作追溯，但它不属于客户交付物；交付扫描只针对 report-data、HTML 和实际被 attach 的情感证据。历史/非展示品牌中间文件若含旧噪声，应标明为归档或隔离，不能让后续流水线误把它们当当前交接产物。

## 4. 替换正式产物前的完整验收

在临时输出目录完成以下顺序：

1. `attach_sentiment.py`。
2. `attach_translations.py --strict-length`。
3. `verify_report_data.py`：45 切片不是固定要求，必须以实际 `meta` 为准；要求每个切片与独立复算一致、退出码 0。
4. `render_report.py` 生成 canonical HTML；不要手改 HTML。
5. 扫描：客户可见 `report-data.json` / HTML / 明细译文 / 情感证据中的平台残留为 0，翻译疑似清单为空。
6. 比较旧/新 KPI 和情感 summary；确定性清洗修复不得产生未解释的指标漂移。
7. 浏览器打开**正式文件名**而不是临时副本，验证模块数量、筛选 tab、明细抽屉、citation pill、正文链接、商品卡和主题矩阵。临时预览文件删除后不要刷新旧 URL，否则 404 不能代表正式报告失败。
8. 通过后再复制 `report-data.json` 与 HTML 到正式目录，并同步带日期的快照；用 `cmp` 确认快照与正式 HTML 相同。

## 5. 最小可复核记录

在任务记录或交接文档中保留：

- 原始采集校验结果及是否采用降级口径；
- 旧/新 units 数量、成功映射数量、未映射数量；
- 每个展示品牌的 labels 正负数量；
- claims 校验的 problems/warnings；
- `verify_report_data.py` 的切片数和退出码；
- 残留文案、翻译疑似清单和最终 HTML 字节数；
- 正式文件与快照的路径及字节一致性结果。

这些记录用于证明“清洗修复了什么”与“没有偷偷改变什么”，不能只以“重新渲染成功”作为验收。
