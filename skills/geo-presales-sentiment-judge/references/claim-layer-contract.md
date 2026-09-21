# Claim 层契约(evidence_text → Claim → Attribute → Theme)

情感分析的正式结构。2026-09-20 由 Suda 定稿;**2026-09-21 明确为三层各由一趟独立工序产出——抽取只出 Claim,Attribute 与 Theme 各做一趟聚类**。此前只有「整句判方向 + 标签归纳」两档降级形态,没有 Claim/Attribute 层。本文件是四层结构的唯一定义点。

## 为什么要拆层

一段回答常同时包含多个意思,不拆就无法判断 AI 到底在评价哪一面,同类信号也无法稳定汇总。示例:

> "Profound is powerful and easy to use once configured, but setup can be complicated and pricing isn't publicly available."

拆解后:

| AI 原文片段(evidence_text) | Claim(标准化语义判断) | Attribute(相近 Claim 的聚类) | Theme(Attribute 的聚类) | 情感 |
|---|---|---|---|---|
| "Profound is powerful" | 产品能力强 | Product Capability > Strong | Product Capability | 正向 |
| "easy to use once configured" | 易用性好 | Ease of Use > Easy | Ease of Use | 正向 |
| "setup can be complicated" | 上手难度高 | Ease of Use > Complex | Ease of Use | 负向 |
| "pricing isn't publicly available" | 未公开定价页 | Pricing > Opaque | Pricing | 负向 |

三种不同说法归一到同一 Attribute 是必要的:「未公开定价页」「要联系销售报价」「没有自助定价页」业务上是同一类问题,不归一就会把同类信号打散成零碎结论。

**Theme 必须中性**:`Pricing > Opaque` 与 `Pricing > Competitive` 方向相反,但都归入 Theme `Pricing`——只有这样才能在同一高层维度上比较本品与竞品各获得哪些正负认知。

## 四层与字段

| 字段 | 作用 | 示例 |
|---|---|---|
| `evidence_text` | 支撑该 Claim 的 AI 回答原文片段(来自 units 的 `unit`),用于溯源 | "Pricing isn't publicly available." |
| `claim` | **标准化后的语义判断**,同义说法应写成同一短语;不是原文摘抄 | 未公开定价页 |
| `attribute` | **多个相近 Claim 的聚类**,「维度 > 极性」形式,跨品牌通用 | Pricing > Opaque |
| `theme` | **Attribute 的再聚类**,高层中性主题 | Pricing |
| `sentiment` | 正向 / 负向(不设中性层,不单独存储) | 负向 |

命名语言随报告语言(中文报告写「价格 > 不透明」)。**Attribute 带极性、Theme 中性**,这是两者的分工。

最小结构化单位:**Prompt × 平台 × 回答 × Brand × Claim**。

## 处理链路

```
AI 回答 → evidence_text →[抽取]→ Claim →[聚类 1]→ Attribute →[聚类 2]→ Theme → 聚合统计
```

三层各由一趟独立工序产出,**抽取不产 Attribute / Theme**:

- `extract`(确定性):按品牌切出单元 → 即 evidence_text 候选。
- **抽取环节**(语义,可并行分片):逐单元读,只产出 `claim` + `sentiment` + 指回单元的 `unit_index`。不判事实真假;品牌未提及或无明确倾向的不生成 Claim,不记中性、不补值。
- `claims-cluster-list`(确定性):把 claim 收敛成**去重清单**(distinct 值 + 计数),作为聚类的输入。
- **聚类 1 · claim → attribute**(语义,全局一次):在去重后的 claim 清单上做,把相近 claim 归到同一 attribute。
- **聚类 2 · attribute → theme**(语义,全局一次):在去重后的 attribute 清单上做,把 attribute 归到高层中性主题。
- `claims-assemble`(确定性):用两张映射表回装——`unit_index` 必须指向真实单元、品牌必须与单元一致、方向只允许正/负、**每个 claim 必须有 attribute、每个 attribute 必须有 theme**。产出 `claims.json`。
- `claims-metrics`(确定性):按下方口径出指标。

**为什么聚类要在去重清单上做、且与抽取分开**:聚类的判断对象是「这个说法属于哪一类」,与它出现在哪条回答、哪个品牌无关。若在抽取时逐条顺带赋值,同一条 claim 会被重复判几十次、同一个 attribute 会被各回答各起一个名字——实测同一份报告里「服务与售后」与「服务与覆盖」并存、同一 attribute 挂到两个 theme。分开做还有两个好处:聚类结果是一张**可逐行人复核的映射表**(claim→attribute、attribute→theme),且同一 attribute 结构上只可能有一个 theme,漂移无从发生。

## 统计口径(不得自行变通)

**统计基础是 Claim occurrence(claim 的出现次数)**——不是 attribute、也不是句子。

- **回答内去重**:同一回答内,同一品牌 × 同一 **semantic claim 只计 1 次**;同一 Attribute 下的**不同 Claim 各计一次**;**跨回答分别计数**。`claims-metrics` 按 claim 文本(压空白 + 忽略大小写)做确定性兜底去重。
- **正向占比** = 正向 Claim 信号数 ÷ 正负向 Claim 信号数合计。
- **跨平台**:先算各平台正向占比,再对**有有效信号的平台等权平均**;**无有效信号的平台不补 0**。
- **Attribute / Theme 是分组维度,不进分子分母**:矩阵按 Theme × 品牌展示、单元格取该主题下计数最高的 attribute 作代表描述,但分组求和恒等于 claim 信号总数。

## 状态语义

| 状态 | 处理 |
|---|---|
| 回答未提及品牌 | 标「未提及品牌」，不进入情感分母 |
| 提及品牌但无明确情感 | 标「未识别到明确情感」，不记中性、不进入分母 |
| 同一 Attribute 下有多个 Claim | 属正常：Attribute 是聚类层，本来就会收多个 claim；统计上**各计一次**，明细全部保留 |
| 回答命中多个品牌 | 本品与竞品各自保留自己的 Claim / Attribute / Theme / 方向 |

## 边界

- **不判断客观事实真假**。FactCheck 结构预留在 Claim 层(可独立验证的事实判断落在 Claim,不以 Attribute/Theme 作真假对象),售前诊断本期不启用。
- 只有回答明确涉及品牌、包含具体评价、且带明确正负倾向时才生成 Claim;品牌事实、功能描述、简单列举、无好坏倾向的描述都不是情感信息。
- 开放竞品只在提问明细层做同样识别,用于回查与补充展示,**不进入统一基线矩阵**。

## 与旧句级形态的关系

旧的 `<品牌>-labels.json`(整句正/负)与 `compute` 子命令仍然可用,是**降级形态**:它答不了「AI 在评价哪个方面」。新报告应走 Claim 层;已交付报告不必回改,重跑时再升级。两者不要混用——同一份报告里,汇总口径必须来自同一层。

**重跑与迁移**:跑过之后需要修复抽取器或替换已交付报告时,按 `geo-presales-report-builder/references/rerun-and-artifact-hygiene.md` 执行——Claim 路径的索引基座是 `claims.json` 的 `unit_index`,重抽 units 后旧 claims 整体失效,**不能改索引硬套**;句级路径按该文档的内容键规则迁移 labels。共同底线是确定性清洗不得改变任何人的语义判断。

**Claim 路径的产物清单**(缺一不可,重跑时按内容键迁移而非按数组位置):
`claims-raw.json`(抽取,claim 级)、`claim-attributes.json`(聚类 1)、`attribute-themes.json`(聚类 2)、`claims.json`(回装)。改聚类只需重跑 `claims-assemble` 之后的步骤,不必重抽 claim。
