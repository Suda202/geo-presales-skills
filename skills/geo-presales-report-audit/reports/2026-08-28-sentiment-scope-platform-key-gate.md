# 情绪职责、复合记录键与 Gemini 来源清洗门禁

日期：2026-08-28

## 本轮修正

- 用 Prompt 的机器可读职责判断情绪：`question_types` 可同时包含 `visibility` 与 `sentiment`；题型展示标签不再覆盖明确 scope。
- 将 JSON 记录身份从单一 `wordid` 改为 `platform + wordid`，同一问题的多平台回答可精确补丁。
- 允许采集失败记录缺少或使用 `answer_text=null`，审核包将其标记为不可语义审核，不猜测修改。
- 删除 Gemini `.source-inline-chip-container` 等来源 UI 后再计算品牌首次出现位置。
- 补丁仍只允许修改 `brand_rankings` 与 `sentiment`，其他字段逐值不变。

## 真实样本回归

Task 175 共 120 条平台记录，脚本成功生成完整审核包；其中 12 条无回答被保留并标记不可语义审核。补丁按复合键精确应用，输入输出记录数均为 120。

Task 175 的 Prompt 配置明确只有 8151、8171、8191 承担 sentiment。其余 Visibility 记录不因回答出现正面措辞进入情绪；这与“同时承担 sentiment 的通用题应按总体评价判断”共同成立，依据始终是 Prompt 的真实职责而非题型名称。

## 门禁结果

- `python3 -m unittest discover -s tests -v`：20/20 通过。
- `python3 scripts/run_structured_result_evals.py`：15/15 通过。
- Task 175 `prepare`：120/120 成功，12 条不可语义审核记录正确标记。
- Task 175 `apply + validate --before`：87 条记录发生 102 个目标字段变化；非目标字段、顶层字段与记录集合保持不变。
