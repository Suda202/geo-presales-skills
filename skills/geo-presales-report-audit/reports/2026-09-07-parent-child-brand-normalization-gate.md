# 父品牌—子品牌—产品线动态归一门禁

日期：2026-09-07

## 本轮变更

- 将父品牌、子品牌和产品线从“默认保留层级”细化为“以输入正式竞品为锚点、结合回答实体关系判定”。
- 正式竞品完整名称优先作为规范名；只有回答明确等同、同一候选、可靠一手来源或确定误拼时才归一。
- 回答明确区分不同公司、项目、采购对象或层级时保持独立；不能仅凭集团隶属、相似名称或引用来源合并。
- 增加 `NVIDIA Cosmos` 归一及 `Aether AI` / `AETHER Robotics` 分离的回归样本。

## 门禁结果

- `python3 scripts/run_structured_result_evals.py`：14/14 通过。
- `python3 -m unittest discover -s tests -v`：21/21 通过。
- `python3 ~/.agents/skills/skill-creator/scripts/quick_validate.py .`：Skill is valid。

## 证据来源

Task 211 的回答明确把 `Aether AI / Aether Labs` 与 `AETHER Robotics` 描述为不同项目；该样本用于验证“相似名称不自动合并”。正式竞品为 `NVIDIA Cosmos` 的样本用于验证父品牌和产品线归一到配置中的完整竞品名，而不是反向改成父品牌简称。
