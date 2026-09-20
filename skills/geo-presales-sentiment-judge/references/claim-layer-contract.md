# Claim 层契约(evidence_text → Claim → Attribute → Theme)

情感分析的正式结构。2026-09-20 由 Suda 定稿;此前只有「整句判方向 + 标签归纳」两档降级形态,没有 Claim/Attribute 层。本文件是四层结构的唯一定义点。

## 为什么要拆层

一段回答常同时包含多个意思,不拆就无法判断 AI 到底在评价哪一面,同类信号也无法稳定汇总。示例:

> "Profound is powerful and easy to use once configured, but setup can be complicated and pricing isn't publicly available."

拆解后:

| AI 原文片段 | Claim | Attribute | Theme | 情感 |
|---|---|---|---|---|
| Profound is powerful | 产品能力强 | 产品能力强 | 产品能力 | 正向 |
| easy to use once configured | 配置后容易使用 | 易用性好 | 易用性 | 正向 |
| setup can be complicated | 初始配置复杂 | 上手难度高 | 易用性 | 负向 |
| pricing isn't publicly available | 未公开价格 | 价格透明度低 | 价格 | 负向 |

三种不同说法归一到同一 Attribute 是必要的:「未公开价格」「需要联系销售报价」「没有自助定价页」业务上是同一类问题,不归一就会把同类信号打散成零碎结论。

**Theme 必须中性**:「价格透明度低」与「价格有竞争力」方向相反,但都归入 Theme「价格」——只有这样才能在同一高层维度上比较本品与竞品各获得哪些正负认知。

## 四层与字段

| 字段 | 作用 | 示例 |
|---|---|---|
| `evidence_text` | 支撑该 Claim 的 AI 回答原文片段(来自 units 的 `unit`) | "Pricing isn't publicly available." |
| `claim` | 从单条回答拆出的最小、单一、可判断的观点 | 未公开价格 |
| `attribute` | 相似 Claim 归一后的稳定分析维度(带正/负) | 价格透明度低 |
| `theme` | 高层中性主题,用于跨品牌横向比较 | 价格 |
| `sentiment` | 正向 / 负向(不设中性层,不单独存储) | 负向 |

最小结构化单位:**Prompt × 平台 × 回答 × Brand × Claim**。

## 处理链路

```
AI 回答 → evidence_text → Claim → Attribute → Theme → 聚合统计
```

- `extract`(确定性):按品牌切出单元 → 即 evidence_text 候选。
- **语义环节**:逐单元读,拆出 Claim 并给 Attribute / Theme / 方向;同回答内语义相同的观点归一(跨回答保留)。不判事实真假;品牌未提及或无明确倾向的不生成 Claim,不记中性、不补值。
- `claims-assemble`(确定性):校验并回装上下文——`unit_index` 必须指向真实单元、品牌必须与单元一致、方向只允许正/负。产出 `claims.json`。
- `claims-metrics`(确定性):按下方口径出指标。

## 统计口径(不得自行变通)

- **回答内去重**:同一回答内,同一品牌 × 同一 Attribute × 同一方向**只计 1 次**;**跨回答分别计数**。
- **正向占比** = 正向 Attribute 信号数 ÷ 正负向 Attribute 信号数合计。
- **跨平台**:先算各平台正向占比,再对**有有效信号的平台等权平均**;**无有效信号的平台不补 0**。
- Theme 汇总:同一 Theme 下各 Attribute 汇总,用于本品与竞品的横向对比。

## 状态语义

| 状态 | 处理 |
|---|---|
| 回答未提及品牌 | 标「未提及品牌」，不进入情感分母 |
| 提及品牌但无明确情感 | 标「未识别到明确情感」，不记中性、不进入分母 |
| 同一 Attribute 有多个近义 Claim | 明细全部保留，统计计数按「回答内去重」算，并标注「统计计数：1 次」 |
| 回答命中多个品牌 | 本品与竞品各自保留自己的 Claim / Attribute / Theme / 方向 |

## 边界

- **不判断客观事实真假**。FactCheck 结构预留在 Claim 层(可独立验证的事实判断落在 Claim,不以 Attribute/Theme 作真假对象),售前诊断本期不启用。
- 只有回答明确涉及品牌、包含具体评价、且带明确正负倾向时才生成 Claim;品牌事实、功能描述、简单列举、无好坏倾向的描述都不是情感信息。
- 开放竞品只在提问明细层做同样识别,用于回查与补充展示,**不进入统一基线矩阵**。

## 与旧句级形态的关系

旧的 `<品牌>-labels.json`(整句正/负)与 `compute` 子命令仍然可用,是**降级形态**:它答不了「AI 在评价哪个方面」。新报告应走 Claim 层;已交付报告不必回改,重跑时再升级。两者不要混用——同一份报告里,汇总口径必须来自同一层。
