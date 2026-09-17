# 已验证案例备注(数据快照,随任务时间点固定)

本文件收录 SKILL.md 中引用的历史案例细节。这些是特定任务时点的数据快照,用于理解规则的来历;数字不随采集更新,不要当作当前口径或预期值。

## Bewinch(2026-09,东南亚净水器)

- **双 Case 版本教训**:磁盘上同时存在两份 Case——`2026-09-14-case/case-fields.json`(初版)与 `2026-09-14-client-crosscheck/case-fields-updated.json`(客户核对版),竞品集不同。取错会让整份报告的竞品对比失去意义。这是 SKILL「Case 记录必须以客户确认后的最新版本为准」规则的出处。
- **采集缺陷规模**(跳过 crawl-integrity 前置校验就会把这些当成品牌表现):AIO 21 条空答案、Perplexity 103 条空 URL 占位、ChatGPT 73 条题面缺失。
- **开放品牌词表规模**:词表命中 96 个品牌;前端榜单只展示 5 行,其余 91 个在环形图合并为「其他品牌」。
- **空答案导致分母不等**:AIO 因 8 条空答案,Discovery 分母为 60,其余平台为 68。

## Botslab(2026-09,行车记录仪)

- `mentioned_<brand>` 字段层混用的实测后果:报告口径写 4.44% 提及率,按正文口径实际是 0/89(细节见 `../../geo-presales-crawl-integrity/SKILL.md` 与其缺陷目录 D1)。

## 2026-09-16 口径静默漂移事故(变更纪律出处)

见 `../../geo-presales-report-editor/SKILL.md`「底层的归属与变更纪律」一节;该事故同时推动了 prompt-builder v4.8.0 对 CSV `question_types` 契约的修正(Verification / Accuracy / Category Awareness 不再带 `sentiment`)。
