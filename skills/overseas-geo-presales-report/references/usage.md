# 使用说明

## 用户怎么调用

用户入口固定使用自然语言：

```text
生产售前报告
```

如果需要指定任务，可以说“生产 TASK-001 的售前报告”或“生产 Target 品牌最新一批售前报告”。下面的文件路径和命令只由 Skill 内部处理，不要求用户输入。

## 推荐输入方式

公司后端把一次诊断的公共信息和六组正式数据写入一个 JSON 文件，再交给 `backend_report.py`。文件适配器已经实现；真实 HTTP 地址、鉴权和密钥由公司运行环境注入，本项目不会猜测或写死。

```bash
python3 scripts/backend_report.py prepare \
  --input /绝对路径/backend-payload.json \
  --run-dir /绝对路径/runs/TASK-001
```

`prepare` 会完成：

- 兼容解析 Dify JSON string 或直接 JSON 对象；
- 校验必填字段、字段类型、`task_id` 和 `batch_id` 一致性；
- 冻结原始输入、规范化输入和哈希；
- 生成 M02、M03、M04、M05 四个互不混合的初始任务。

## 处理任务

```bash
python3 scripts/backend_report.py next-task \
  --run-dir /绝对路径/runs/TASK-001 \
  --all-ready \
  --inline
```

结果必须使用任务信封中的 `protocol_version`、`run_id`、`task_id`、`kind`、`module_id` 和 `task_digest`。只填写 `output.content` 与 `output.evidence_refs`，不要输出 Markdown 或解释过程。

```bash
python3 scripts/backend_report.py submit-task \
  --run-dir /绝对路径/runs/TASK-001 \
  --task-id T-M02-xxxxxxxxxxxx \
  --result /绝对路径/M02-result.json
```

提交后脚本会检查：

- 结果信封是否对应原任务；
- 模块 Schema、固定条数、空组和长度；
- 每条结论是否有真实证据引用；
- 引用的 JSON 指针、表达证据和行动方向是否存在；
- 输出数字是否出现在后端事实资源中；
- M05 是否越权重新分档或写行动；
- M06 是否与后端行动方向一一对应。

## 依赖与并行

```text
M02 竞品表现 ─┐
M03 引用来源 ─┼─→ M06 下一步行动 ─┐
M04 品牌表达 ─┤                    │
M05 品牌进入 ─┴─→ M01 数据总览 ───┼─→ M10 最终摘要
```

M02–M05 可以分别执行。`action_context` 缺失时，M06 自动记录降级并输出空行动，不会由报告脚本根据指标重算状态。

## 正式产物

```text
artifacts/report.json                  # 规范化对象输出
artifacts/dify-compatible-output.json  # 当前七个 summary_* JSON string
artifacts/audit.json                   # 输入哈希、模块状态、证据引用和降级记录
```

## 异常恢复

- 输入 JSON 错误：修正后使用新的空运行目录重新 `prepare`。
- 某模块 Schema 或证据校验失败：只修该模块结果并重新提交，不重跑其他模块。
- 后端缺少 `action_context`：可以接受降级报告，也可以由后端补齐后创建新批次；不要在已有冻结批次原地修改输入。
- 批次 ID 混用：阻断，不能拼接不同批次的模块。
