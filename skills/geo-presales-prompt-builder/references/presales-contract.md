# 海外 GEO 售前问题库契约（v8）

## 输入字段合同

v8 直接接受系统接口提交的评测 Case 中文业务字段，不要求 `target_attributes`，也不把输入改造成另一套 Builder 字段：

| 基础字段 | 可编号字段 | 主题与竞品字段 | 补充字段 |
|---|---|---|---|
| `公司名`、`业务 / 产品名称`、`品牌名称`、`业务模式`、`品类`、`垂直行业` | `目标客户 1…n`、`痛点 1…n`、`使用场景 1…n`、`产品特性 1…n` | `主题 1…n（宽泛/细分）`（1–3 个）、`官方域名`、三组 `竞品 n` 与 `竞品 n 官网域名` | `差异化优势`、`适用边界`、`补充内容` |

**格式兼容说明**：Prompt Builder 同时接受以下两种接口输入格式：
- **单字段合并格式**：`痛点`、`使用场景`、`产品特性`、`目标客户` 各为一个字段，多个值用 `，` 分隔；`主题` 为一个字段，1–3 个主题用 `，` 分隔，不带类型标注。
- **编号字段格式**（历史兼容）：`痛点 1…n`、`使用场景 1…n` 等分字段；`主题 1…n（宽泛/细分）`，括号标注仅作理解提示，不输出到 v8 字段。
若两种格式混合出现，以实际内容语义为准，不因字段名格式报错。

括号中的”宽泛/细分”只帮助理解 Topic，不输出 `topic_type`。品牌、品类、至少一个 Topic、官方域名以及三组竞品名称和官网域名为硬必填；纯 `B2C` 的垂直行业允许留空。`补充内容`字段必须保留但允许为空；为空时三组正式竞品默认适用于全部 Topic。其余业务字段必须足以为每 Topic 派生 3–5 个 P1 属性；P2 少于建议的 5 个时可保留现有数量并报告信息缺口，不得虚构补齐。

Accuracy 默认配额为 0，不需要上游事实包，也不产生 `fact_value / official_source_url / fact_checked_at`。如用户明确要求 Accuracy，先单独确认事实核验输入和产物合同，不把 Case 声明直接当成已核验真值。

## Topic、Attribute 与 Tags

- Topic 是 Prompt 集合的主组织单元，代表可长期独立监测的市场、场景或战略机会。每题只回指一个 `topic_id`。
- Attribute 是希望 AI 形成的战略认知、能力、特征或评价标准。Builder 在 `attribute_plan` 中按 Topic 规划优先级，逐题使用 `Attribute: …` Tag 建立关联；同名 Attribute 可以跨 Topic 聚合。
- Tags 是统一的自由字符串数组，承接诊断意图、品牌范围、Attribute 和其他横向分类。默认使用命名空间以避免同名冲突，不另建逐题 `attributes` 字段。

## 固定结构

- `schema_version=overseas-geo-question-bank/v8`
- 1–3 个 Topic；每 Topic 固定 25 题，整批总量为 25/50/75。
- 当前 Topic 适用竞品数为 `n`（1–3）时，六类 Intent 固定为 Discovery `23 - 2n`、Competitor `n`、Verification `0`、Accuracy `0`、Evaluation `1 + n`、Category Awareness `1`。
- Competitor 覆盖每个适用竞品各一条；Evaluation 覆盖目标品牌一条与每个适用竞品各一条；Discovery 在覆盖 P1 的前提下用独立购买问题补足固定配额。
- `quotas.per_topic` 保存未单列 Topic 共用的配额，`quotas.topic_overrides` 只在 Topic 的适用竞品数不同时使用。`quotas.intent_tags` 必须等于所有 Topic 配额之和。
- 每 Topic 的正式可见度题按实际 Discovery 与一条 Category Awareness 统计，不预设固定数量。
- v8 不包含 `diagnosis_intent`、逐题 `attributes`、`topic_type`、`question_type`、`funnel_intent`、`decision_stage`、`metric_scopes`、`attribute_pool`、`attribute_id`、`attribute_ids` 或 `priority_attribute_ids`。
- v8 必须包含 Builder 派生的 `attribute_plan`；每 Topic 恰好一项，同一 Attribute 和源字段允许被多个 Topic 使用，不做唯一归属。

v8 的 `config` 是闭合合同，只允许 `case_fields / brand_name / brand_object_type / category_label / official_domain / derived_field_sources / topics / attribute_plan / expected_total / quotas / competitor_selection`。拒绝 `target_audiences / pain_points / use_cases` 等平行输入字段及其他未声明配置，避免绕过评测集 Case 字段。

## `attribute_plan` 合同

- 每个 Topic 恰好一项，只包含 `topic_id / priorities / excluded`。
- `priorities` 恰好包含 `P1 / P2 / P3`：P1 必须 3–5 个，P2 建议 5–10 个且不得超过 10，P3 允许 0–10 个。
- P1 / P2 / P3 表示 Attribute 在当前 Topic 下的优先级，不是 Attribute 类型或 Prompt 优先级；这些分档属于本项目的生成合同，不是 Profound 原始分类。
- P1 每项恰好包含 `attribute / source_field / source_value / decision_reason / verification_statement`；P2/P3 不包含 `verification_statement`。
- `excluded` 可为空；每项包含 `candidate / source_field / source_value / reason / route`，`route` 只允许 `exclude` 或 `accuracy_only`。
- 当前 Topic 的 `validation_items` 和 Verification 的 Attribute Tags 与 P1 的强绑定已随 Verification 配额归 0 暂停使用；完整示例见 [属性规划](attribute-planning.md)。

## Case / Topic 示例骨架

下列片段专门展示 Case、Topic、配额和竞品字段，为缩短篇幅省略了 v8 必填的 `attribute_plan`；完整题库必须按上述合同补全。

```json
{
  "schema_version": "overseas-geo-question-bank/v8",
  "config": {
    "case_fields": {
      "公司名": "Shanghai Edgelight Industry Co., Ltd.",
      "业务 / 产品名称": "LED Display and Commercial Display Solutions",
      "品牌名称": "Edgelight",
      "业务模式": "B2B",
      "品类": "LED 显示屏制造商与商业显示解决方案提供商",
      "垂直行业": "商业 AV 零售与商业地产 企业设施 舞台与体育场馆",
      "目标客户 1": "商业 AV 集成商与 LED 显示屏分销商——关注参数 集成与服务",
      "目标客户 2": "零售 商业地产与品牌体验团队——关注视觉效果 可靠性与项目成本",
      "目标客户 3": "企业 政企园区与会议设施团队——关注清晰度 文件与维护",
      "目标客户 4": "舞台制作 体育场馆与活动技术团队——关注亮度 刷新率与结构灵活性",
      "痛点 1": "项目团队难以让像素间距 亮度 刷新率 观看距离与结构适配具体场馆",
      "痛点 2": "安装调试 文件 认证与售后缺口会延误交付并提高项目总成本",
      "使用场景 1": "在企业与商业空间安装固定式 LED 显示屏",
      "使用场景 2": "为裸眼 3D 舞台与场馆打造创意沉浸式 LED 体验",
      "产品特性 1": "室内外 固装 租赁与创意 LED 显示产品组合",
      "产品特性 2": "像素间距 亮度 刷新率 色彩与画质能力",
      "产品特性 3": "结构定制与内容控制集成",
      "产品特性 4": "项目设计 安装调试 文件 认证与售后服务",
      "差异化优势": "具备 20 多年 LED 领域经验 同时覆盖 LED 显示屏 电源 控制器 广告照明产品与项目解决方案 官网声明拥有五座全球生产基地 产品销往 50 多个国家并获得 100 多项国际认证",
      "适用边界": "只采购 LED 照明 驱动电源 控制器 广告照明配件或不需要 LED 显示屏的完整建筑 AV 与媒体制作服务的客户",
      "主题 1（宽泛）": "LED 显示屏制造商与商业显示解决方案提供商",
      "主题 2（细分）": "面向企业与商业空间的固定安装 LED 显示解决方案",
      "主题 3（细分）": "面向裸眼 3D 舞台与场馆体验的创意沉浸式 LED 显示屏",
      "官方域名": "https://edgelight.com",
      "竞品 1": "SANSI LED (Shanghai Sansi)",
      "竞品 1 官网域名": "https://www.sansi.com",
      "竞品 2": "Unilumin",
      "竞品 2 官网域名": "https://en.unilumin.com",
      "竞品 3": "LianTronics",
      "竞品 3 官网域名": "https://www.liantronics.com",
      "补充内容": "本次只在 LED 显示屏制造与商业显示解决方案范围内评测边光 不把 LED 电源 控制器 装饰照明 广告灯箱和物联网产品混入同一主题。官网列出室内外全彩屏 租赁屏 创意显示 玻璃相关显示与 LED 地砖屏等产品 并展示政企园区 商业环境和裸眼 3D 解决方案 项目案例覆盖商业项目 舞台剧场 会议显示 体育场馆和标识标牌。买家主要比较像素间距 亮度 刷新率 观看距离 色彩与画质 室内外耐候 结构定制 内容与控制集成 安装调试 服务 文件 认证 交期和项目总成本。SANSI LED Unilumin 与 LianTronics 作为可比的 LED 显示与解决方案提供商保留 仅照明或通用 AV 供应商不纳入本 Case。"
    },
    "brand_name": "Edgelight",
    "brand_object_type": "company",
    "category_label": "LED display manufacturer and commercial display solution provider",
    "official_domain": "https://edgelight.com",
    "derived_field_sources": {
      "brand_name": "品牌名称",
      "category_label": "品类",
      "official_domain": "官方域名"
    },
    "topics": [
      {
        "topic_id": "topic_1",
        "topic": "LED display manufacturers and commercial display solution providers",
        "source_field": "主题 1（宽泛）",
        "source_value": "LED 显示屏制造商与商业显示解决方案提供商"
      },
      {
        "topic_id": "topic_2",
        "topic": "fixed-installation LED display solutions for corporate and commercial spaces",
        "source_field": "主题 2（细分）",
        "source_value": "面向企业与商业空间的固定安装 LED 显示解决方案"
      },
      {
        "topic_id": "topic_3",
        "topic": "creative immersive LED displays for naked-eye 3D, stage and venue experiences",
        "source_field": "主题 3（细分）",
        "source_value": "面向裸眼 3D 舞台与场馆体验的创意沉浸式 LED 显示屏"
      }
    ],
    "expected_total": 75,
    "quotas": {
      "intent_tags": {"Intent: Discovery": 51, "Intent: Competitor": 9, "Intent: Verification": 0, "Intent: Accuracy": 0, "Intent: Evaluation": 12, "Intent: Category Awareness": 3},
      "per_topic": {"Intent: Discovery": 17, "Intent: Competitor": 3, "Intent: Verification": 0, "Intent: Accuracy": 0, "Intent: Evaluation": 4, "Intent: Category Awareness": 1}
    },
    "competitor_selection": {
      "status": "frozen",
      "selection_count": 3,
      "formal_competitors": [
        {"name": "SANSI LED (Shanghai Sansi)", "official_domain": "https://www.sansi.com", "source_fields": ["竞品 1", "竞品 1 官网域名"]},
        {"name": "Unilumin", "official_domain": "https://en.unilumin.com", "source_fields": ["竞品 2", "竞品 2 官网域名"]},
        {"name": "LianTronics", "official_domain": "https://www.liantronics.com", "source_fields": ["竞品 3", "竞品 3 官网域名"]}
      ]
    }
  },
  "questions": []
}
```

`formal_competitors[].topic_ids` 为可选字段。省略时表示该竞品适用于全部 Topic；Case 的补充内容声明局部边界时必须填写非空 Topic ID 数组。例如 Botslab 使用 `70mai → [topic_1]`、`Reolink → [topic_2]`、`aosu → [topic_2]`。三组竞品仍是 Case 级正式集合，但 Competitor 题按 Topic 子集生成。

生成 Builder 派生的 `attribute_plan`，但不生成 Attribute ID 或单独的逐题属性字段。同一 Attribute 与 `source_field / source_value` 可以出现在多个 Topic 中；逐题通过 Attribute Tag 关联，默认不读取 Accuracy 事实包。

## 每题字段

所有问题必填：

- `question_id`：全批唯一。
- `topic_id`：回指 1–3 个正式 Topic；不附带 `topic_type`。
- `tags`：非空字符串数组；默认至少包含一个 `Intent: …` 和一个 `Brand Scope: …`，按题面需要包含零个或多个 `Attribute: …`，也允许增加其他自由 Tag。
- `analysis_type`：按 v8 的 Prompt 生成角色填写。
- `formal_visibility_eligible`：按 v8 的 Prompt 生成角色填写，决定是否进入正式可见度题集。
- `intent_key`：全批唯一，不能只换措辞伪造新意图。
- `user_question / zh_translation / monitoring_prompt`：英文根问题、等义中文和采集字段；`monitoring_prompt` 必须等于 `user_question`。
- `quality_checks`：已执行的检查全部为 `true`。

默认题库不包含 Verification 题与 `validation_items`、Accuracy 题或事实包字段。如用户明确要求 Verification 或 Accuracy，先单独确认产物合同，不临时复用默认 Builder 合同。

## Tags 合同

`tags` 字段接受任意非空字符串，不设全局封闭枚举。单个 Tag 不得包含分号 `;`，以便 JSON 被其他兼容适配器安全序列化；当前上传 CSV 本身不输出 Tags。Builder 默认使用以下常用命名：

| 命名空间 | 默认值与规则 |
|---|---|
| `Intent: …` | 每题恰好一个常用生成角色：`Discovery / Competitor / Verification / Accuracy / Evaluation / Category Awareness`。六类数量必须符合固定 Topic 配额；仍可添加其他非默认自定义 Intent Tag。 |
| `Brand Scope: …` | 每题恰好一个。题面出现目标品牌或正式竞品时为 `Branded`，否则为 `Non-Branded`；以实际题面为准。 |
| `Attribute: …` | 零个或多个；名称必须来自当前 Topic 的 `attribute_plan`。Discovery 的 Attribute Tags 整批覆盖全部 P1；同名 Attribute 可跨 Topic。 |

其他自由 Tags 建议继续使用 `Namespace: Value`，例如 `Lifecycle: Consideration`、`Region: North America`。增删这些 Tags 不得改变分析路由。

## 分流合同

| 默认诊断 Tag | analysis_type | formal_visibility_eligible |
|---|---|---|
| `Intent: Discovery` | `visibility,sentiment` | `true` |
| `Intent: Competitor` | `sentiment` | `false` |
| `Intent: Verification` | 空 | `false` |
| `Intent: Accuracy` | `accuracy` | `false` |
| `Intent: Evaluation` | `sentiment` | `false` |
| `Intent: Category Awareness` | 空 | `true` |

每 Topic 的正式可见度题为实际 Discovery，再加一条 Category Awareness。Competitor 只统计情感，不进入正式 Visibility、声量、排名、Share of Voice 或聚合引用指标。v8 不要求 `metric_scopes`；Tags 只是聚合维度，兼容适配器即使产生旧字段，也不得改变核心路由。

品牌边界：Discovery 与 Category Awareness 不出现目标品牌或任何正式竞品；Competitor 出现目标品牌和恰好一个正式竞品；Evaluation 每题只出现一个品牌，并在每 Topic 内分别覆盖目标品牌和每个适用竞品恰好一次；不得使用不适用于当前 Topic 的竞品。Evaluation 须把 Topic 转写为具体业务范围或场景；只限制英文 Prompt 正文：`user_question / monitoring_prompt` 及 CSV `query` 不得出现独立单词 `topic`。中文翻译、CSV `topic` 列及其他元数据不受此限制。

## CSV 固定字段导出

字段顺序固定为：

| CSV 列 | 来源 |
|-|-|
| `query` | `user_question` |
| `question_zh` | `zh_translation` |
| `topic` | 对应评测集 `主题 n（宽泛/细分）` 的原始中文值 |
| `diagnosis_intent` | 从 JSON 唯一默认 Intent Tag 转写：`discovery / competitor / verification / accuracy / evaluation / category_awareness` |
| `tags` | 上传适配列：允许留空；若填写必须短于 200 字符，并使用英文逗号、中文逗号或换行分隔，且优先保留可上传的最小化摘要，不把 JSON 里的完整 Attribute 列表直接搬进来 |
| `question_types` | `visibility,sentiment / sentiment`；Discovery、Verification、Accuracy 与 Category Awareness 填 `visibility,sentiment`，Competitor 与 Evaluation 填 `sentiment` |
| `purchase_intent` | 可空或 `0 / 1 / 2 / 3`，分别表示无、推荐、比较、决策 |
| `persona_name` | 可空，最多 200 字符 |
| `scene_name` | 可空，最多 200 字符 |

CSV 上传模板现在包含 `tags` 列，但它只用于补充上传侧的自由标签；JSON 仍保留完整 `tags` 数组作为唯一权威来源。上传 CSV 不应承载 JSON 里完整的 Attribute 列表或过长的标签串。JSON 仍不生成独立 `diagnosis_intent` 或 `question_type` 字段；这两个 CSV 字段只由上传适配器导出。

## 旧版兼容

validator 允许只读旧 v7/v6/v5 题库，但新生成默认为 v8。旧 `diagnosis_intent` 只能作为 v7/v6 的兼容字段，不得出现在 v8。不得用 v5 的三个固定 Topic、`target_attributes`、`topic_type`、`metric_scopes`、单属性 Verification 或 `paired_discovery_ids` 作为新题库生成规则；不得只改 `schema_version` 伪造迁移。
