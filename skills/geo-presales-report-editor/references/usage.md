# 使用说明

## 用户怎么调用

用户入口固定使用自然语言：

```text
生产售前报告
```

如果需要指定任务，可以说“生产 TASK-001 的售前报告”或“生产 Target 品牌最新一批售前报告”。下面的文件路径和命令只由 Skill 内部处理，不要求用户输入。

用户提供现成报告 CSV 时，直接说“根据最新统计修改这份报告 CSV”即可。此时直接编辑 CSV 内容，不要求用户重新导出 JSON，也不进入销售后台修改或上传。

## 现成 CSV 模式（首选）

1. 确认文件为 UTF-8 BOM、CRLF、`module,path,index,field,value` 五列。
2. 从附件、已确认统计文件或只读页面数据中提取证据。正式可见度和主要引用只读取 Discovery 筛选后的 `public_scope.visibility` 与 `public_scope.citation`，不继续引用未筛选的 `presentation_metrics`；情绪直接使用完整 `analysis_type=sentiment` 聚合，不再按诊断意图二次筛选。再综合整体、主题、平台、引用与跨维度关系。
3. 只修改后台允许回填的内容字段，保留原文件并输出新的 CSV。
4. 校验结构、编码、数字来源和客户文案门禁后，把 CSV 交给用户确认。不要打开页面回填、提交或上传。

现成 CSV 已有完整行结构时不运行 `prepare/finalize`。只有尚无 CSV、输入是 v2 后端统计包时，才进入下述生成模式。

## 后端统计包生成模式

公司后端把一次诊断的公共信息和正式统计写入一个 JSON 文件，再交给 `backend_report.py`。文件适配器已经实现；真实 HTTP 地址、鉴权和密钥由公司运行环境注入，本项目不会猜测或写死。

```bash
python3 scripts/backend_report.py prepare \
  --input /绝对路径/backend-payload.json \
  --run-dir /绝对路径/runs/TASK-001
```

`prepare` 会完成：

- 兼容解析 Dify JSON string 或直接 JSON 对象；
- 校验必填字段、字段类型、`task_id` 和 `batch_id` 一致性；
- 冻结原始输入、规范化输入和哈希；
- 生成 M02、M03、M04、M05、M07 和 M08 六个互不混合的事实任务；M03 在后端提供时同时读取主题/Tag 官网页面机会，未提供时只分析 Citation，不补推未引用页面。

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
- 模块 Schema、允许条数、空组和长度；
- 每条结论是否有真实证据引用；
- 引用的 JSON 指针、表达证据和行动方向是否存在；
- 输出数字是否出现在后端事实资源中；
- M05 是否越权重新分档或写行动；
- M06 是否与后端行动方向一一对应。
- M06 是否只使用后端正式问题路由，并写清目标载体、我方交付、客户动作/材料和同口径复测信号；非 Blog 官网不得写成我方直接修改或上线。
- M07 是否只解释后端匹配 Discovery Prompt 的正式一致性结果，没有本地拼样本、手算阈值或推断平台机制；客户文案统一用“主题”和“平均提及位置”。
- M02 是否只把决胜回答胜率称为竞品胜率，并逐一覆盖正式竞品及有证据的正面对比优劣势；总体胜率字段和文案会被拒绝。
- M07 是否只输出整体与主题的正式一致性判断；Attribute 是否仅作其他模块或跨模块解释证据，没有单独的跨平台状态。
- M08 是否只解释后端 `included/missing/conflicting/insufficient` 购买框架状态，没有重读原始回答或写成 Visibility、输赢因果和归因；品类认知类问题只写选择标准与问题关键属性、品牌预设差异点的契合关系。
- M03 是否把页面相关性与 Citation 状态分开，并且候选范围来自主题/Tag 相关官网页面扫描；Attribute/Prompt Gap 是否只作内部修改证据，没有变成独立客户字段。

## 依赖与并行

```text
M02 竞品表现 ─┐
M03 引用来源 ─┼─→ M01 数据总览 ───┐
M04 品牌表达 ─┤                    ├─→ M10 最终摘要
M05 品牌进入 ─┤                    │
M07 平台一致 ─┤                    │
M08 购买框架 ─┘                    │
  └──────────────→ M06 下一步行动 ─┘
```

M02–M05 与 M07–M08 可以分别执行。六个事实模块全部通过证据和数字校验或明确降级后，M01 才能综合主诊断、竞品决胜结果、购买框架、跨平台稳定性、证据关系与优先级。`platform_consistency` 缺失时，M07 自动记录降级，不会由报告脚本拼接平台数据；`market_perception_diagnostics` 缺失时，M08 自动记录降级，不会由报告脚本重新分析原始品类回答；`action_context` 缺失时，M06 自动记录降级并输出空行动，不会由报告脚本根据指标重算状态。

## 正式产物

```text
artifacts/report-upload.csv             # 正式后台回传文件；UTF-8 BOM、CRLF、固定五列
artifacts/report.json                   # 内部规范化对象输出
artifacts/dify-compatible-output.json   # 兼容旧 Dify 的七个 summary_* JSON string
artifacts/audit.json                    # 输入哈希、模块状态、证据引用和降级记录
```

把 `report-upload.csv` 交给用户确认后由用户上传，不要把内部 JSON 当作人工回传文件，也不要替用户操作报告页面。CSV 字段与行展开规则见 [上传 CSV 契约](report-upload-csv-contract.md)。当前版本不生成 HTML 或 PDF。

旧 Dify 与上传 CSV 尚无独立跨平台和购买框架字段，因此 M07、M08 保存在内部 `report.json` 和 `audit.json`；当对应判断会改变客户判断时，由 M01 将其写入数据总览并进入上传 CSV。不得擅自增加后台未知字段。

## 异常恢复

- 输入 JSON 错误：修正后使用新的空运行目录重新 `prepare`。
- 某模块 Schema 或证据校验失败：只修该模块结果并重新提交，不重跑其他模块。
- 后端缺少 `action_context`：可以接受降级报告，也可以由后端补齐后创建新批次；不要在已有冻结批次原地修改输入。旧 v2 方向没有 `route_type` 时继续按已有状态表达，但不得自行补判；新方向应提供路由、目标载体、责任字段和复测信号。
- 后端缺少 `platform_consistency`：允许兼容已有批次并降级 M07；新任务应由后端按同市场、同语言、同采集窗口和匹配 Discovery Prompt 补齐，报告侧不得自行重算。
- 后端缺少 `competitor_comparison_summary`：M02 仍可编辑 Discovery 竞争位置，但不生成正式竞品胜率和正面对比优劣势；等待后端按每个正式竞品补齐汇总，不从 `comparison_outcomes` 本地聚合。
- 后端缺少 `market_perception_diagnostics`：允许降级 M08；等待后端补齐与主题/Attribute 对齐的正式状态，不从 `market_perception` 或回答全文本地重判。
- 后端缺少 `page_opportunities`：M03 继续分析引用来源和已引用官网页面，但不得声称完成全站页面机会扫描；等待后端按主题/Tag 扫描相关官网页面并提供四象限、AI Gap、页面价值和 priority，不从 Citation 列表补推。
- 批次 ID 混用：阻断，不能拼接不同批次的模块。
