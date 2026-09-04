# Case 主题拆分示例

示例只展示判断方式，不复制固定词面。

## 命名颗粒度

| 候选 | 判断 | 原因 |
|---|---|---|
| `Colored Gemstone Jewelry` | 保留 | 简短且只表达核心品类，适合作为 Coverage Topic。 |
| `Everyday Gemstone Jewelry` | 保留 | 只增加一个真实场景限定，可作为 Depth Topic。 |
| `Jewelry for Daily Wear` | 保留 | 是简洁的主题名，不是完整问题。 |
| `Affordable Lab-Grown Colored Gemstone Jewelry for Everyday Wear` | 淘汰并放宽 | 同时塞入价格，材料，品类和场景；保留核心品类或一个场景限定，其余下沉 Prompt。 |
| `What are the best lab-grown gemstone jewelry brands for everyday wear?` | 淘汰 | 这是带评价和场景条件的 Prompt，不是 Topic。 |

`Historical Data` 作为 Coverage Topic 时，应短于 `Historical Data for Marketers` 这类 Depth Topic。Depth 可以稍长，但只保留一个会改变购买判断的限定。正式 Case 仍按字段合同输出中文 Topic；以上英文例子只用于展示命名长度和信息密度。

## Topic 与 Attribute 路由

| 候选 | 路由 | 原因 |
|---|---|---|
| `CRM for Agencies` | Topic | 本身是完整 Use Case 和市场，可独立承载 Agency CRM 的发现、比较和验证 Prompts。 |
| `AI Marketing Automation` | 视 Case 判断 | 若是公司长期独立投入且候选集合、任务和优化动作明显变化，作为 Topic；若只是多个 CRM 场景共有能力，路由为 Attribute。 |
| `Easy to Use`、`No Subscription`、`Local Storage` | Attribute | 是横跨多个市场或场景的能力与评价标准，不是 Prompt 集合的主组织单元。 |
| `Night Vision` | Attribute | 在“智能行车记录仪”和“家庭安防摄像头”中都可被分析；保持两个 Topic，通过同名 Attribute 跨 Topic 聚合。 |
| `Customizable`、`Daily Wear` | Attribute | 可横跨培育宝石、日常珠宝和定制珠宝等 Topic，不应为每个能力重复创建 Topic。 |
| `Enterprise Security` | 视 Case 判断 | 若代表独立 Enterprise 市场 / ICP 且购买集合改变，可作为 Topic；否则作为横跨现有 Topic 的 Attribute。 |

诊断意图、Branded / Non-Branded 和购买阶段均不是 Topic 或 Attribute 候选；它们由下游 Prompt Tags 承载。

## TapNow

- 宽泛候选：AI 视频创作平台
- 细分候选：品牌活动 AI 视频，电商广告 AI 视频

品牌活动与电商广告的任务、评价标准和内容行动不同，可以拆分；“可控多镜头”等具体评价标准下沉到 Prompt。电影长片不属于该 Case 的适用边界。

## BPI

- 宽泛候选：充电电池制造商
- 细分候选：医疗设备定制电池，工业设备定制电池

医疗设备与工业设备的认证、安全、耐用性、温度和连续供货标准明显不同；这些标准分别下沉到 Prompt。OEM 与 ODM 只是采购模式用词变化，不单独拆分。

## 产品线与双 Topic

- TachinGlove Case：`touch data acquisition gloves` 为 Coverage Topic，`robot teleoperation and imitation learning` 为同一手套产品线内的 Depth Topic。
- 机器人全身触觉系统、智能座舱触感和陪伴触感是不同产品线；即使来自同一公司，也应各自建 Case，不能作为 TachinGlove Case 的第二 Topic。
- 若输入只支持“工业金属带锯床制造商”一个核心品类，继续从同产品线的核心客户或使用任务中选择一个会改变购买判断的 Depth Topic；不得用型号、参数或另一产品线补位。
