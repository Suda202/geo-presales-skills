# Output Risk Profile

| 风险 | 典型表现 | 首版控制 |
|-|-|-|
| 标题/关键词进入监测 | `Best AI...`, `pricing comparison` | 五字段隔离、自然度门、程序高风险模式检查 |
| 品类不可见或漂移 | 使用 `specialized product suppliers`，或回答转向排除品类 | `category_expression_set`、占位词黑名单、排除品类与逐题 `category_visible` |
| 题量或样本结构静默缺失 | 目标 50，实际 49；Generic/Branded 不是 40/10 | 生成前冻结总量与问题类型，整批精确校验；三类意图只查都有，不设精确数 |
| 问题没有商业价值 | 只问概念、标准清单或购买流程 | 只生成 Recommendation/Comparison/Decision；Generic 题面必须要求具体候选、候选比较或最终选择 |
| 依赖回答偶然举品牌 | 问材料、安全或标准，AI 有时会顺带举例品牌 | Generic 题面必须主动索取候选品牌、候选比较或最终品牌选择；答案候选不限于已配置名单 |
| 三类商业意图只有措辞差异 | 条件取值相同，只换英文表达 | 用稳定 `intent_key` 拦截同条件伪意图，二遍 review 检查答案终点 |
| 品牌比较漏竞品或五题同构 | 三个竞品只覆盖两个，或五条均为近义一对一 | Branded Comparison 确定性 3+2：三竞品逐一覆盖，加两条关键因素/多品牌题 |
| 受众分布失衡 | 整批只服务少量受众 | 汇总 `target_audiences` 分布供 review，不为平均分配牺牲商业意图 |
| 固定价格题导致编造 | 无公开价格也硬凑两道预算题或具体金额 | 取消价格角度配额；按公开套餐、定制报价或总成本动态生成 |
| 伪多样性 | 条件不变却换句式，或每题自造唯一 cluster/scenario/constraint | `intent_key` 硬门；榜单词、元数据单例率与句首集中只作软警告；最终语义去重 |
| 交易问题变动作命令 | `Buy/Order/Gift/Give/Sign up/Request demo` | 区分决策咨询与现实执行，裸命令硬失败 |
| 品牌题诱导结论 | `Why is brand better?` | neutral_premise 硬门与竞品中性规则 |
| 品牌总体评价基准题缺失或模板漂移 | 某 Topic 没有基准题，或 company/product、品类、品牌、Topic 拼错 | 每 Topic 恰好 1 条固定 Evaluate 模板，硬归 Branded + Decision，不新增意图字段 |
| 购买对象偷换 | 本应推荐 OEM/ODM 电池厂，却改问热管理厂商、储能系统商或大型项目合作伙伴 | 二遍 review 比较“问题要求选择的对象”与 Topic 的购买集合；不是同一类候选即失败 |
| Generic 泄漏客户实体 | 不含主品牌名，但出现产品名、别名或空格/驼峰变体 | 全部品牌、产品、aliases 与冻结竞品进入 Generic 硬门；自动兼容机械写法变体 |
| 低可比竞品被当作全面替代品 | 对 adjacent/fallback 问“谁更好”或综合排名 | 冻结 3 竞品及 `comparison_policy`；低可比只用 `allowed_dimensions`，空维度只澄清品类/场景 |
| 中译缺失 | 销售无法快速确认英文题意 | `zh_translation` 存在、非空且含汉字为硬门；语义准确性由 review 确认 |
| 过长复杂题 | 多任务拼接、回答漂移 | 不设词数硬门；用自然度、必要条件与单一主要意图复核 |
| 短问题被无意义扩写 | `Is X worth it?` 被灌水 | 不设下限，完整自然短问原样保留 |
| 专业术语被同义改写掉 | 输入含 GEO/AEO，整批只剩 AI search visibility | 输入驱动 `required_term_coverage`、Generic/Branded 最低覆盖与缩写消歧 |
| 省略术语配置绕过检查 | 输入明写 GEO/AEO，但题库不输出 `required_term_coverage` | v3 必填 `professional_term_assessment`；required 决策与配额 key 一致；旧库显式 legacy warning |
| 为术语配额堆关键词 | 每题追加 `(GEO/AEO)` 或只换术语造重复题 | `term_slot` 预分配、自然度门与语义去重 |
| 程序通过但语义仍差 | 布尔字段被错误自评 | 脚本不替代第二遍语义 review，失败样本进入 eval |

当前版本不声称能用规则脚本判断完整回答是否一定包含品牌候选、跨 Topic 语义对齐或真实用户频次；这些仍需要独立 LLM/人工 review 与真实数据校准。
