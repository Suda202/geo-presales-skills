# 飞书 Case 评测集目标与写入合同

本公开 Skill 不包含具体飞书 Base URL、Base token 或 Table ID。执行前从已获授权的项目私有配置取得当前目标，并确认：

- 目标表是用于 GEO 售前诊断的 `Case评测集`；
- 使用经授权的用户身份（通常为 `--as user`）；
- 已验证 Base、Table 和当前 profile 均可读写。

不得把这些标识符写入公开仓库、评测产物或对外文档；配置缺失、身份不匹配或权限不足时停止写入并请求项目负责人提供授权目标。

每个 Case 对应一条 Record。写入前先用 `field-list` 获取真实 schema，再读取 Records，以 `品牌名称 + 业务 / 产品名称 + 主题` 识别已有 Case。维护同一 Case 时更新原 Record；新品牌或新的明确业务颗粒度创建 Record。

写入所有合同字段，但不写 `Case序号`。现有历史序号字段和历史值不参与识别、排序或维护。创建使用 `record-batch-create`，新增 Record 按飞书默认位置自然追加，不置顶、不倒序，也不移动已有记录；更新使用 `record-batch-update`。同一 Table 的批量写入串行执行。

写后读回目标 Record，至少核对：

- 品牌名称
- 主题
- 官方域名
- 竞品 1–3 及各自官网域名
- 补充内容

认证或权限失败时读取 `lark-shared`，以原用户身份修复；不静默改用 Bot 身份，也不退回本地 Markdown。
