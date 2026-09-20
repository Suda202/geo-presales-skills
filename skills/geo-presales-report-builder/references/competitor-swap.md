# 客户中途换竞品:聚合板块与逐回答两条路径

客户在报告生成后要求把某个展示竞品换掉(例如「Philips 出、Coway 进」)是常见返工。**聚合板块和逐回答详情走两条不同规则,不能一刀切**——这是 2026-09-18 在 Bewinch 上定的口径。

## 规则

| 位置 | 换品牌怎么做 | 理由 |
|---|---|---|
| 聚合板块(04 情感的主题矩阵、品牌占比条) | 可以整体换成新品牌的判读数据 | 它是全批次的整体统计,换品牌只改聚合口径 |
| 抽屉里的逐回答情感(`details[key].sentiment`) | **必须按「这条回答有没有提到该品牌」门禁**,不能硬塞 | 回答里没出现过的品牌,给它挂情感就是编造 |

Suda 原话:**「只有情感板块的展示可以这么搞,因为是整体的数据。但是每个回答详情还是得看有没有品牌提及再识别情感哦。」**

## 正确做法:恢复全品牌判读数据后重跑 `attach_sentiment`,不要手写补丁

`attach_sentiment.py` **不是重跑判读**——它只把磁盘上已经判好的标签(`<品牌>-labels.json`)合并进 `report-data.json`,没有任何模型调用。它的逐回答逻辑(`build_answer_sentiment`)本身就是上述门禁:按 `(question_id, region, platform)` 匹配,只有该回答真的被判出过该品牌的句子(即回答确实提到了它)才会挂情感。

所以换品牌的顺序是:

1. 确认新品牌有完整判读产物:units 抽取 → `sentiment-batches/<品牌>-labels.json` → `<品牌>-claims.json`(claims 过 `prep_sentiment_handoff.py check-claims`,退出码 0)。
2. 把这些判读文件放进报告目录的 `sentiment-claims/`(注意 `judged-sentences.json` 要含新品牌的 `positive`/`negative` 数组)。
3. 用新的 `--brands` 列表重跑 `attach_sentiment.py`(纯数据合并),再 render。
4. 复核:新品牌在有提及的回答里有情感、无提及的回答里为 `—`;聚合板块的新品牌数字与 `check-claims` 对账一致。

**不要手写数据补丁改 `details[key].sentiment`**:那等于把 `build_answer_sentiment` 的门禁逻辑重新实现一遍,更容易把没提及的品牌塞进去。

## 换品牌常用伴随动作

- 品牌展开词表:新品牌的别名要补进 `assets/brand_lexicon.<品类>.json`(当地语言转写别漏,漏了会系统性漏提),词表该冻结前仍要人工过一遍。
- 展示名精简:数据层的 key 可能带品类后缀(如 `Waterdrop Water Purifier`),渲染层用 `displayBrand()` 剥掉后缀让榜单读品牌本身;**别名匹配仍用全称**——精简只发生在展示层,不要在数据层改 key。
- 品牌 logo 取不到时渲染层显示首字母占位块(保持行对齐),不要留空白框。
