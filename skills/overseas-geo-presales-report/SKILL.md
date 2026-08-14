---
name: overseas-geo-presales-report
description: 生产或生成海外 GEO 售前报告。用户说“生产售前报告”“生成售前报告”“出一份海外 GEO 售前报告”时使用；自动从当前任务、附件、已给出的任务 ID 或工作区中定位公司后端统计包，再生成可审计的中文报告和 Dify 兼容输出。不要要求用户编写命令或提供绝对路径。
---

# 海外 GEO 售前报告

## 用户入口

用户只需要说：

```text
生产售前报告
```

也可以补充自然语言限定，例如：

```text
生产 TASK-001 的售前报告
生产 Target 品牌最新一批售前报告
```

不要让用户输入 CLI、运行目录或绝对路径。路径解析、运行目录和脚本调用都是 Skill 的内部工作。

## 输入定位

按以下顺序自动定位后端统计包：

1. 当前对话附件或用户刚提到的文件。
2. 当前任务已经给出的 `task_id`、品牌名或后端返回结果。
3. 工作区中与任务 ID 或品牌匹配的后端统计包。
4. 已配置的公司后端适配器。

找到唯一匹配项后直接执行。存在多个候选时，只问用户要生成哪个任务或品牌；没有找到时，只问“请给我任务 ID，或把后端统计结果发过来”。不要要求用户拼写文件路径。

## 职责边界

本 Skill 是售前链路最后一环，只解释公司后端已经统计和分组的数据，不负责发现竞品、生成问题、采集回答、逐回答分析或重新计算正式指标。

完整调用链为：

```text
overseas-geo-competitor-research
→ yao-overseas-geo-intent-miner
→ 搜索团队采集服务（外部上游）
→ 逐回答分析服务与公司后端聚合
→ overseas-geo-presales-report
```

本次新增的两个项目自有 Skill 不带 `yao`。生产采集由搜索团队负责，本 Skill 不调用项目内 crawler。项目内 crawler 只可用于本地测试和 shadow audit。

## 内部执行

开始前读取 [后端输入契约](references/backend-input-contract.md) 和 [报告任务契约](references/backend-report-task-contract.md)。命令和异常恢复见 [使用说明](references/usage.md)。

以下命令仅供 Skill 内部执行，不作为用户调用方式。

1. 校验并冻结后端统计包。

   ```bash
   python3 scripts/backend_report.py prepare \
     --input /绝对路径/backend-payload.json \
     --run-dir /绝对路径/runs/<run-id>
   ```

2. 获取当前可执行任务。

   ```bash
   python3 scripts/backend_report.py next-task \
     --run-dir /绝对路径/runs/<run-id> \
     --all-ready \
     --inline
   ```

   初始同时开放 M02 竞品表现、M03 引用来源、M04 品牌表达和 M05 品牌进入机会。可以分别处理，禁止合并成一个大而全的输出。

3. 对每个任务读取其资源文件，只生成任务要求的一个模块结果 JSON，再提交校验。

   ```bash
   python3 scripts/backend_report.py submit-task \
     --run-dir /绝对路径/runs/<run-id> \
     --task-id <task-id> \
     --result /绝对路径/result.json
   ```

4. 重复获取与提交。依赖顺序由脚本控制：

   - M02、M03、M04、M05 可并行。
   - M01 数据总览在 M05 完成后开放。
   - M06 行动在 M02–M05 完成且后端提供 `action_context` 后开放。
   - M10 最终摘要在前述模块全部完成后开放。

5. 查看状态并生成正式产物。

   ```bash
   python3 scripts/backend_report.py status --run-dir /绝对路径/runs/<run-id>
   python3 scripts/backend_report.py finalize --run-dir /绝对路径/runs/<run-id>
   ```

## 硬边界

- 禁止重新计算提及率、声量占比、平均排名、官网引用率、问题机会分档或情绪比例。
- 禁止把 `question_details` 或表达证据重新聚合成一套与后端不同的正式指标。
- 所有非空结论必须返回证据引用；脚本会检查 JSON 指针、表达证据 ID、行动方向 ID 和依赖模块是否真实存在。
- 输出数字必须能在任务事实资源中找到；不得手算、换口径或补写输入中没有的数字。
- M05 只能解释后端已经分好的 `p0/p1/p2`，客户文案不得出现内部编码，也不能写行动建议。
- M06 只能服从后端 `action_context`。未提供时明确降级为空行动，并记录警告，不在本地重建行动状态。
- M10 只能综合已定稿模块，禁止引入新事实。

## 兼容与影子审计

生产入口是 `scripts/backend_report.py`。它同时接受当前 Dify 的六个 JSON string 字段和直接 JSON 对象，并输出 `artifacts/dify-compatible-output.json`。

原 `scripts/geo_presales.py` 保留用于本地 crawler、公式回归和后端对账，只是 shadow audit，不得把它生成的本地指标覆盖公司后端正式统计。详细边界见 [影子审计说明](references/shadow-audit.md)。
