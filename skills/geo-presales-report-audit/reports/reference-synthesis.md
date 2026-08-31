# 参考扫描与取舍

更新时间：2026-08-19

## 当前 Skill 锚点

这个 Skill 的职责是审计已经生成的 GEO 售前报告及其 JSON 结构化结果，并维护能被研发直接修复和回归的 Bad Case。结构化分支覆盖可见度与情绪的独立或重叠样本、诊断意图标签、品牌提及、正文首次出现顺序排名、目标品牌情绪和引用清洗；它不生成报告，也不替代竞品研究、意图生成或普通网页审计。

## 扫描对象

- Agent Skills 官方规范：确认 `name`、`description`、渐进加载、相对路径和脚本自包含要求。
- Anthropic 官方 Skills 仓库：确认 Skill 应是可重复执行的自包含能力包，并需要在真实环境充分测试。
- OpenAI 官方 Skills 仓库及文档入口：确认使用可发现的 Skill 目录、清晰触发描述和跨客户端兼容思路。
- `yao-meta-skill`：采用 Production 模式、资源边界、触发评测和输出风险门禁。
- [OpenAI Evals README](https://github.com/openai/evals)：采用私有或业务真实样本作为金标回归集的模式。
- [Pydantic README](https://github.com/pydantic/pydantic)：采用先定义数据契约、再执行确定性校验的模式。
- [pytest 参数化文档](https://docs.pytest.org/en/stable/how-to/parametrize.html)：采用同一执行逻辑运行多组 `input/expected` fixture 的模式。

## 借用的通用模式

- 把“做什么、何时使用、何时不用”放进 frontmatter description，优先解决路由歧义。
- 保持 `SKILL.md` 为执行骨架，把领域判定细节放进 `references/`，把确定性操作放进 `scripts/`。
- 为团队复用补 `agents/interface.yaml`、维护元数据、正反触发样本和近邻路由样本。
- 对截图、报告和命令类输出预先列出可见风险，并用真实样本验证脚本。
- 将引用清洗、排名顺序和题型情绪映射做成 13 个可执行金标样本；任何差异以非零退出码阻断交付。
- 对 JSON 写回先定义允许字段和结构不变量，再应用人工审核补丁并输出真实 diff。

## 明确不借用

- 不复制外部示例的品牌语言、目录规模或治理重量。
- 不升级成 Library 或 Governed 模式；当前没有跨项目基础设施级需求。
- 不增加关键词自动判错、自动写飞书或固定问题清单。
- 不把报告生产、竞品研究、意图生成并入一个大 Skill。
- 不引入 OpenAI Evals、Pydantic 或 pytest 运行时依赖；只借用金标样本、规范校验和参数化回归的设计模式，使用标准库与现有依赖执行。

## 本地适配

- 保持项目级唯一源码路径 `.agents/skills/geo-presales-report-audit`；去掉名称中的 `overseas`，但保留完整报告审计边界。
- 飞书必须优先使用 `lark-cli`，网页必须通过 `web-access`。
- Task、记录号、错误类型、具体例子和标注截图继续作为 Bad Case 硬门槛。
- 状态更新必须基于当前报告样本，并在飞书写入后逐条读回。
- 数量对账必须先确认产品设计；固定 Top N 展示不等于总数，且不得混用原始引用数、唯一 URL 数、回答覆盖数和列表长度。
