# v8 Edgelight 生问正反例

以下例子只使用 Edgelight Case 的现有字段；`attribute_plan` 由这些字段派生，不要求 Case 填写 `target_attributes`。LED 显示屏 Topic 的 P1 可包括产品与场景覆盖、视觉规格选型、结构与内容控制集成、项目交付支持；“官网将 LED 显示屏列为独立类别”应进入 `excluded`。

| 默认 Intent Tag | 合格英文示例 | 其他 Tags 与关键要求 |
|---|---|---|
| `Intent: Discovery` | `Which LED display manufacturers are strong options for commercial AV integrators that need both display products and project support?` | `Brand Scope: Non-Branded`；按实际条件挂 `Attribute: Project Support` 等 Tag；不出现 Edgelight 或竞品。 |
| `Intent: Competitor` | `How do Edgelight and SANSI LED compare as providers of LED display and commercial display solutions in terms of product range, display performance, structural customization, and project support?` | `Brand Scope: Branded`；只出现目标品牌与竞品 1；Attribute Tags 对应比较维度。 |
| `Intent: Competitor` | `How do Edgelight and Unilumin compare as providers of LED display and commercial display solutions in terms of product range, display performance, structural customization, and project support?` | 除竞品名外与上一题的题面和 Attribute Tags 完全同构。 |
| `Intent: Evaluation` | `Evaluate the LED display manufacturer and commercial display solution provider company Edgelight on LED display manufacturers and commercial display solution providers` | `Brand Scope: Branded`；固定模板，不出现独立单词 `topic`。 |
| `Intent: Category Awareness` | `What is a LED display manufacturer and commercial display solution provider, and how should I evaluate one for LED display manufacturers and commercial display solution providers?` | `Brand Scope: Non-Branded`；固定品类优先模板，不出现任何品牌。 |

第三条 Competitor 只把上述模板中的 `SANSI LED` 替换为 `LianTronics`。不要为了“更贴合竞品”改变任务、条件、比较维度、词序或标点。

Topic 局部竞品例子：Botslab 的“智能行车记录仪”只与 70mai 比较；“家庭安防摄像头”只与 Reolink 和 aosu 比较。前者生成 1 条 Competitor，后者生成 2 条 Competitor；各自 Discovery 数量按当前 Topic 的适用竞品数 `n` 分别取 `23-2×1=21` 和 `23-2×2=19`，Verification 均为 0。不得让 70mai 出现在家庭安防比较题，也不得让 Reolink 或 aosu 出现在行车记录仪比较题。

反例：

- `What should buyers look for in an LED display?`：若标为 Discovery，只给标准清单，不要求具体候选；应使用品类优先 Category Awareness 模板，或改问制造商候选。
- `Its product portfolio includes LED displays as a separate product category.`：只验证官网目录分类，不改变采购入围或选型判断。
- `A listed product specifies 12 V, 8 A, and 96 W output.`：宽泛 LED 驱动电源 Topic 下不应以单款 SKU 的孤立精确参数代替品类级选型能力；精确值核对属于具体型号或 Accuracy 合同。
- 默认不生成 Verification 与 Accuracy 题，也不要求上游事实包；如用户明确要求，先单独确认合同。
- 售前不为 Unilumin 等竞品生成 Evaluation；竞品情绪矩阵留给售后生词，避免挤压 Discovery。
- `Why is Edgelight better than Unilumin?`：预设胜者。
- `How do Edgelight, Unilumin and LianTronics compare?`：破坏一对一控制变量。
- 为 SANSI LED 问产品范围、为 Unilumin 问刷新率：即使各题合理，也破坏同一 Topic 竞品题“仅竞品名不同”的合同。
- 在 Case 中新增“AI 已把 Edgelight 与项目支持强关联”：这是采集后的 `observed_associations`，不得作为 Builder 输入或预写结论。
- 给不出现任何品牌的 Discovery 写 `Brand Scope: Branded`：品牌范围必须由题面实际提及确定。
- 给“智能行车记录仪”Topic 的问题挂只存在于“家庭安防摄像头”规划中的 Attribute：Attribute Tag 必须回指当前 Topic；若 `Night Vision` 在两个 Topic 都有规划，可在两边使用同名 Tag 跨 Topic 聚合。
