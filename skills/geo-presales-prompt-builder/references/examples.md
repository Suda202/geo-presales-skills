# 海外 GEO 生问正反例

## BPI-81 暴露的两个核心问题

| 实际问题（英文 / 中文） | 问题在哪里 |
|-|-|
| `What certification coverage criteria should buyers evaluate when choosing specialized product suppliers?`<br>买方在选择专业产品供应商时，应评估哪些认证覆盖标准？ | 看不出在问充电电池；`specialized product suppliers` 是跨品类占位词。答案也只会给认证清单，不会稳定给出电池供应商候选。 |
| `What certifications should OEM procurement managers evaluate when choosing a rechargeable battery manufacturer?`<br>OEM 采购经理在选择充电电池制造商时，应评估哪些认证？ | 品类已经可见，但仍是教育型评估框架；答案大概率只讲认证，不会命名具体供应商候选。 |

品类落地合格不代表商业意图合格，两道门要分别检查。更合格的商业题例如：

- `Which rechargeable battery manufacturers can support the certifications required for consumer electronics packs?`
  哪些充电电池制造商能够支持消费电子电池包所需的认证？
- `Which battery suppliers offer low-MOQ custom LiPo cells for wearable startups?`
  哪些电池供应商能为可穿戴设备初创公司提供低起订量的定制聚合物锂电芯？

第二条即使不出现 `rechargeable battery` 原词，`battery suppliers` 与 `LiPo cells` 已能明确品类。

## 不生成的非商业问法

| 类型 | 反例（英文 / 中文） | 为什么不合格 |
|-|-|-|
| 概念科普 | `What is CRM software?`<br>什么是 CRM 软件？ | 答案是解释，不会产生品牌候选。 |
| 解释型比较 | `What is the difference between CRM and ERP?`<br>CRM 和 ERP 有什么区别？ | 只解释区别，没有要求取舍。 |
| 教育型框架 | `What should I look for in a CRM?`<br>选择 CRM 时应该看哪些方面？ | 答案是标准清单，不是品牌推荐。 |
| 购买流程 | `Where can I buy CRM software?`<br>在哪里购买 CRM 软件？ | 容易退化成购买渠道或流程说明。 |

| 失败输入 | 失败原因 | 合格 `user_question` | 应保留到其他字段的内容 |
|-|-|-|-|
| `Buy AI brand tracking tool subscription` | 裸购买命令、品类歧义 | `Which AI search visibility tool should I choose for a small marketing team?` | retrieval: `AI search visibility tool subscription` |
| `AI search tracking tool demo request` | 表单/标题式短语 | `Which AI search visibility platforms offer a free demo?` | evidence: `AI visibility platform free demo` |
| `Top-rated AI search tracking tools based on user reviews` | 榜单标题 | `Which AI search visibility tools receive the strongest user reviews?` | title: `Top-Rated AI Search Visibility Tools by User Reviews` |
| `Best AI brand tracking tools pricing comparison` | SEO 标题、品类歧义 | `How do leading AI search visibility tools compare on pricing?` | retrieval: `AI search visibility tool pricing comparison` |
| `Sign up for Peec AI` | 要求执行现实动作 | `How can I start a Peec AI trial?` | evidence: `Peec AI trial sign-up requirements` |
| `Which one is cheaper?` | 依赖上下文 | `Which is more affordable for a small SEO agency, Peec AI or Otterly AI?` | standalone 字段使用右侧完整问题 |
| `Why is Peec AI better than Profound?` | 预设优劣 | `How do Peec AI and Profound compare for enterprise marketing teams?` | — |
| `Which CRM is best?` | 无问题；短但品类清楚且要求推荐 | 原样保留 | 不因短于 6 词扩写 |
| `Which GEO tools are best?` | GEO 可能被理解为 geography，缺少独立语境 | `Which generative engine optimization (GEO) tools work well for SEO agencies?` | retrieval: `best GEO tools for SEO agencies` |
| `AEO platform pricing` | 缩写歧义、关键词短语 | `Which answer engine optimization (AEO) platforms should buyers compare on pricing?` | retrieval: `AEO platform pricing` |
| `How does Peec AI track AI visibility?`（整批唯一专业词面） | 语义相关，但不能覆盖输入中的 GEO 专业受众 | `How should agencies evaluate Peec AI for generative engine optimization (GEO) reporting?` | — |

## 冻结竞品的出题边界

| 竞品等级 | `allowed_dimensions` | 合格问法 | 禁止问法 |
|-|-|-|-|
| `direct` | reporting, AI answer monitoring | `How do Peec AI and Profound compare on AI answer monitoring workflows?` | 无证据预设一方领先 |
| `adjacent` | AI answer monitoring | `How do Peec AI and Adjacent Example differ in AI answer monitoring scope?` | `Which is better overall, Peec AI or Adjacent Example?` |
| `fallback` | 空 | `How do Peec AI and Fallback Example fit into different stages of a marketing workflow?` | 功能、效果、价格或综合强弱比较 |

## 一条意图的五个字段

```json
{
  "user_question": "Which AI search visibility tool is best for a small SEO agency?",
  "zh_translation": "哪款 AI 搜索可见性工具最适合小型 SEO 代理商？",
  "standalone_rewrite": "Which AI search visibility platform is best for a small SEO agency monitoring brand mentions across generative search platforms?",
  "retrieval_rewrite": "AI search visibility tools for small SEO agencies",
  "evidence_query": "AI visibility platform pricing features agency reviews",
  "title_seed": "Best AI Search Visibility Tools for Small SEO Agencies",
  "monitoring_prompt": "Which AI search visibility tool is best for a small SEO agency?"
}
```

关键词和标题不是废料，但必须留在正确字段，不能进入监测。

## 专业术语不是关键词堆砌

合格的 50 题题库应同时保留：

- 普通用户表达：`Which AI search visibility tools work well for agencies?`
- 专业用户表达：`Which generative engine optimization (GEO) tools work well for agencies?`
- 品牌关联表达：`How should agencies evaluate Peec AI for GEO reporting across AI search platforms?`

三者回答边界必须不同，不能只替换术语后把同一道题重复计算。

## 六种组合与 Branded Comparison 3+2

| 格子 | 合格示例 | 答案终点 |
|-|-|-|
| Generic Recommendation | `Which AI visibility platforms are worth considering for a small agency?` | 品牌候选或推荐 |
| Generic Comparison | `Which AI visibility platforms should a small agency compare for weekly reporting, and what trade-offs separate them?` | 命名候选平台，再比较差异并取舍 |
| Generic Decision | `Which AI visibility platform is the best fit for a small agency?` | 明确推荐或适配判断 |
| Branded Recommendation | `Should a small agency shortlist Peec AI for weekly AI visibility reporting?` | 是否值得纳入候选及理由 |
| Branded Comparison | `How does Peec AI compare with Profound on AI answer monitoring?` | 与正式竞品中性比较 |
| Branded Decision | `Is Peec AI the right choice for a small SEO agency?` | 是否选择或采用品牌 |

表格表达六种答案目标，不代表六格配额。实际有 5 条 Branded Comparison 时，不应是五条换名字的近义题：前三条分别只命中一个正式竞品，后两条使用不点名竞品的关键因素问法，或同时命中两个以上正式竞品。`adjacent/fallback` 即使需要完成独立覆盖，也不能越过其 `allowed_dimensions`。

## Lit by Larry 回归：意图优先于模拟原话

| 反例 | 失败原因 | 修复方向 |
|-|-|-|
| `How do lab-grown diamonds compare with natural diamonds in price and quality?` | Generic 答案可以只讲材料差异，不出现珠宝品牌。 | 改问消费者应比较哪些珠宝品牌，以及候选品牌在相关维度上的取舍。 |
| `What lab-grown diamond jewelry brands should shoppers consider when diamond sparkle matters most?` | “闪耀最重要”是为了制造差异而编出的低频条件，不来自输入。 | 使用设计、工艺、价值、证书、礼赠或线上信任等有依据的购买条件。 |
| `Should buyers choose one brand offering both lab-grown diamonds and colored gemstones instead of separate specialist brands?` | 把整批品类广度错误变成单题的罕见组合策略。 | 单题可只问钻石、祖母绿、蓝宝石、红宝石或混合设计；整批检查覆盖。 |

Generic 可以写 `Which jewelry brands...`，但不能写 Lit by Larry、Chatham 等具体品牌实体。问题不需要复刻用户逐字说法，也不设词数硬门；它必须清楚表达真实购买意图，并让合理答案自然命名具体候选品牌。

## 固定品牌总体评价基准题

| 对象 | 合格模板 | 中文理解 |
|-|-|-|
| 公司 | `Evaluate the CRM software company HubSpot on small business sales management` | 评价 CRM 软件公司 HubSpot 在小企业销售管理上的表现 |
| 产品 | `Evaluate the men's fragrance product Bleu de Chanel on fragrance gift shopping` | 评价男士香水产品 Bleu de Chanel 在香水礼品选购上的表现 |
| 公司 | `Evaluate the rechargeable battery company BPI on Rechargeable battery manufacturers for OEM/ODM procurement` | 评价充电电池公司 BPI 在面向 OEM/ODM 采购的充电电池制造商主题上的表现 |

每 Topic 只生成 1 条，放在 Branded，硬归 `decision`，不新增情绪意图字段。不能写成 `Evaluate the rechargeable battery manufacturer company...`，也不能把 company/product 与监测对象类型弄反。
