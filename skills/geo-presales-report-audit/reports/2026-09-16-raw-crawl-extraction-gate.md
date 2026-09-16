# 原始爬虫层品牌抽取接入门禁

日期：2026-09-16
触发变更：新增原始采集层处理能力（两个脚本 + 一个参考文档 + 一个词典资产），并修改 SKILL.md 触发描述。

## 为什么加

本 skill 原本只覆盖报告 JSON 层（有 `wordid` / `brand_rankings`）。Botslab 两个数据集的处理暴露了上游缺口：指标计算前没有「把原始回答变成可靠品牌序列」的确定性流程，靠每个数据集手工复制脚本，两份副本已经分叉。

同时 `geo-presales-report-builder` 的品牌识别唯一入口是 `find_alias_spans`（纯别名匹配），无法做实体角色判断，其文档也承认「机器无法可靠区分品牌名与品类词/技术缩写」——品牌抽取归本 skill。

## 新增内容

| 文件 | 作用 |
|---|---|
| `scripts/de_cite_crawl.py` | 采集目录 → 去引用正文（`normalized-answers.jsonl`），含清空商品卡 `merchants` 列的 `body_ranking` |
| `scripts/verify_brand_extraction.py` | 品牌抽取独立复核：名称在正文、首现顺序、标准名一致性、词典召回 |
| `references/raw-crawl-extraction.md` | 去引用规则、分片契约、校验项、已知陷阱 |
| `assets/brand_lexicon.botslab-2topics.json` | Botslab 两 Topic 标准品牌别名表 |

## 验证

在 Botslab 两个真实数据集上跑通：

| 数据集 | 回答数 | `de_cite_crawl.py` | `verify_brand_extraction.py` |
|---|---:|---|---|
| `botslab-results-20260915-162219`（topic_1） | 150 | 产出与既有结果逐字段一致（0 处差异） | 退出码 2，正确报出 `Lamtto`/`LAMTTO`、`Wolfbox`/`WOLFBOX` 未归一 |
| `security-camera-results-20260916-145031`（topic_2） | 89 | 同上 | 退出码 0，四项检查全通过 |

`de_cite_crawl.py` 的产出与数据集内既有的 `normalize.py` 逐字节一致，可直接替换手工副本。

## 固化的缺陷

- **标准名未归一**（本次实证）：分片抽取时两个分片各写一种大小写，未归一直接排名会让 `Lamtto`/`LAMTTO` 与 `Wolfbox`/`WOLFBOX` 各占一个名次，品牌总数从 20 虚增到 22。已固化为 `verify_brand_extraction.py` 第 3 项检查，并加回归测试 `test_name_variant_collision_blocks`。
- **merchants 列误作首现**：品牌自营店属销售渠道，不计入首现位置。已由 `body_ranking` 的列清空保证，测试 `test_blanks_merchant_column_but_keeps_goods_title` 覆盖。

## 门禁结果

```
tests/test_scripts.py               Ran 31 tests  OK (skipped=1)
scripts/run_structured_result_evals.py   structured_result_cases=14 passed=14 failed=0
```

新增 10 个测试用例（去引用 4 个、品牌抽取复核 6 个），原有 21 个用例全部保持通过。
