# 去引用清洗层内联锚点删除门禁

日期：2026-09-16
触发变更：修改 `scripts/structured_result_audit.py` 的 `remove_citations`，新增内联内容锚点判定；新增 4 个回归测试。

## 为什么加

`remove_citations` 原先对去引用后的**所有剩余 `<a>`** 一律「连锚文本一起删除」（商品卡容器内的除外）。这条规则本意是清掉引用来源名、favicon 文本和 `+1`，但把**句子里作为内容出现的链接**也一并删了，于是正文丢句子成分、甚至丢真实品牌提及。

Task 246（KeepBalance）实证两条：

1. **丢品牌提及**：`chatgpt #10119` 的正文原文是
   `<li><p><strong><a class="decorated-link" href="https://www.personanutrition.com/">Persona Nutrition</a></strong> — certified nutritionists provide ongoing 1:1 consultations…</p></li>`。
   删除锚文本后正文成了 `The clearest matches are: — certified nutritionists provide…`，句子没有主语，`Persona Nutrition` 从品牌序列里消失，只剩 `Rootine`。
2. **丢句子主语**：Gemini 购物卡的商品名在描述句里以 `<product-link>` 内联出现，例如 `The <product-link><a>Garden of Life Vitamin Code Family</a></product-link> offers raw whole food nutrition…`。删除后成了 `The offers raw whole food nutrition…`。同样的句子在 gemini #10113、#10120、#10144、#10147、#10153 共 5 条记录中出现。

缺陷类型：**清洗层（去引用）过度删除**。

## 修复内容

`remove_citations` 的锚点处理改为三分支，判定顺序固定：

| 顺序 | 条件 | 处理 |
|---|---|---|
| 1 | 在 `PRODUCT_CARD_SELECTORS` 命中的商品卡容器内（原逻辑） | 解包，保留可见标题 |
| 2 | 锚文本含 `Opens in a new window`，或 class 含 `product-wrapper` | 整体删除（屏幕阅读器重复元数据，含渠道名与评分） |
| 3 | 位于 `<strong>`/`<b>` 内，或同一文本块内锚点之後仍有可见文字 | 解包，保留文字（句子内容） |
| 4 | 其余 | 连锚文本删除（引用来源名、收尾链接标签） |

判定 3 中的「之後仍有文字」用临时标记串在同一块级祖先（`p/li/td/th/h1-h6`）内取锚点之后的可见文本，避免把大 div 里后续兄弟节点的文字误当成句子延续。

分支 4 保留原行为，实测确实只落在收尾标签上：`chatgpt #10134` 的 `BYHEALTH investor relations` 与 `chatgpt #10142` 的 `Ritual's ingredient sourcing disclosures`，两者都独占段落或位于句末，删除正确。

## 验证

| 验证项 | 结果 |
|---|---|
| Task 246 全部 96 条清洗结果前后对比 | 6 条变化（chatgpt #10119；gemini #10113、#10120、#10144、#10147、#10153），全部为恢复句子成分 |
| 同批 96 条 `brand_rankings` 影响 | **0 条变化**，已交付的修正结果不需重跑 |
| 货架噪声（`Opens in a new window` 块、渠道名） | 未回灌正文 |
| `tests/test_scripts.py` | Ran 35 tests OK (skipped=1) |
| `scripts/run_structured_result_evals.py` | structured_result_cases=14 passed=14 failed=0 |

## 固化的缺陷与回归测试

| 缺陷 | 回归测试 |
|---|---|
| 加粗内联实体链接被整体删除，丢品牌提及 | `test_bolded_inline_entity_link_keeps_its_text` |
| 商品卡商品名以 `<product-link>` 内联出现在句中，丢句子主语 | `test_gemini_product_link_mid_sentence_keeps_product_title` |
| 收尾来源标签链接仍应删除（防止过度纠偏） | `test_trailing_source_label_link_is_deleted` |
| 屏幕阅读器重复元数据块仍应删除 | `test_product_wrapper_screen_reader_block_is_deleted` |

## 未覆盖范围

- 本修复只作用于本 skill 的去引用包（`prepare` 产出的 `cleaned_text`），不回写 `answer_text`，也不改后端 JSON 的任何字段。
- `scripts/de_cite_crawl.py`（原始采集层）不受影响：它用 `MD_LINK.sub(r"\1", …)` 保留锚文本，本就没有该缺陷。
- 后端生产管线是否使用同类「删锚文本」清理，需要另行核实；若一致，应把同一判定移植过去。
