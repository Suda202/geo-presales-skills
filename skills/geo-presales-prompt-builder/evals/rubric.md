# Quality Rubric

- **5**：默认输出 `overseas-geo-question-bank/v8`，直接消费系统接口提交的评测 Case 原始中文业务字段，不要求 `target_attributes`。Topic 是 Prompt 主组织；生题前生成可溯源的 `Attribute × Topic` 规划。每 Topic 按适用竞品数 `n` 固定生成 Discovery `22-2n`、Competitor `n`、Verification `1`、Accuracy `0`、Evaluation `1+n`、Category Awareness `1`，合计 25 题。Evaluation 覆盖目标品牌及每个适用竞品各一题。JSON 每题保留自由 `tags`、独立 `analysis_type` 与 `formal_visibility_eligible`，不含独立 `diagnosis_intent`；上传 CSV 使用 `diagnosis_intent` 列并新增 `tags` 列，其中 `tags` 允许留空但若填写必须短于 200 字符且只保留可上传的最小化摘要，不能把 JSON 的完整 Attribute 列表直接搬入。Competitor/Evaluation 的 `question_types` 为 `sentiment`。JSON、CSV、英文问题、中文译文和确定性校验均通过。
- **4**：全部硬门通过，但目标客户、场景或评价标准的覆盖分布略弱，或英文表达略显模板化。
- **3**：实际题量记录与六个常用 Intent Tags 基本正确，但 Topic / Attribute 路由、Attribute Tags、品牌范围 Tag、P1 与 Verification 对齐、竞品同构或固定模板有一项需要人工修订。
- **2**：仍依赖旧 `target_attributes`、固定三个 Topic、JSON 内保留 `diagnosis_intent` 固定字段、单属性 Verification 或 v5 双重指标路由，虽能生成问题但不符合新流程。
- **1**：实际题数与固定 25 题 Topic 配额不一致、品牌边界破坏、品类明显漂移、事实被编造，或把检索词直接作为监测 Prompt。
