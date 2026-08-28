# Quality Rubric

- **5**：默认输出 `overseas-geo-question-bank/v8`，直接消费 Edgelight 型评测集 Case 原始中文字段，不要求 `target_attributes`。Topic 是 Prompt 主组织；生题前生成可溯源的 `Attribute × Topic` 规划，每 Topic 有 3–5 个 P1、建议 5–10 个 P2、0–10 个 P3 及可为空的 `excluded`。每题使用自由 `tags`：一个默认 Intent Tag、一个由题面反推的 Branded / Non-Branded Tag、零个或多个来自当前 Topic 规划的 Attribute Tag，并允许其他自由 Tag。P1 与 Verification 的 `validation_items` 及 Attribute Tags 按顺序强绑定，Discovery Attribute Tags 覆盖全部 P1并优先覆盖有独立诊断价值的 P2，Competitor 使用双方可比的 P1 和高优先 P2。Discovery 在每个 Topic 内严格超过 50%；每 Topic 只为目标品牌生成一条 Evaluation，竞品情绪矩阵留给售后。支持 1–3 Topic，按 Attribute 信息量弹性分配且允许 Topic 不等量，实际配额与产物一致，整批不超过 60；10–25/Topic 仅作软参考。`analysis_type` 与 `formal_visibility_eligible` 独立于自由 Tags。默认 Accuracy 为 0；Evaluation 与 Category Awareness 使用固定模板。v8 不含 `diagnosis_intent`、逐题 `attributes`、Attribute ID、`topic_type` 或 `metric_scopes`；JSON、CSV、英文问题、中文译文和确定性校验均通过。
- **4**：全部硬门通过，但目标客户、场景或评价标准的覆盖分布略弱，或英文表达略显模板化。
- **3**：实际题量记录与六个常用 Intent Tags 基本正确，但 Topic / Attribute 路由、Attribute Tags、品牌范围 Tag、P1 与 Verification 对齐、竞品同构或固定模板有一项需要人工修订。
- **2**：仍依赖旧 `target_attributes`、固定三个 Topic、`diagnosis_intent` 固定字段、单属性 Verification 或 v5 双重指标路由，虽能生成问题但不符合新流程。
- **1**：实际题数与已记录配额不一致、整批超过 60、品牌边界破坏、品类明显漂移、事实被编造，或把检索词直接作为监测 Prompt。
