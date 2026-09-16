# 已知缺陷目录

每条都有一手证据、检测方法和影响范围。新增缺陷必须附可复跑样本，不接受推测。

---

## D1 · 提及标记扫了整个响应体（阻断）

**现象**：采集器自带的 `mentioned_<brand>` 标记为 `True`，但模型回答正文里该品牌一次都没出现。

**根因**：标记逻辑把整个响应体当成回答文本，连带检索结果（`search_result`、`sse_data`）一起匹配。品牌官网出现在模型的检索结果里，就被计成了一次「提及」。

**实测证据**（Botslab，2026-09-16，`security-camera-results-20260916-145031`）：

`mention-summary.json` 记录 Botslab 提及 4 次、提及率 4.44%。逐字段核查：

| 文件 | 回答正文命中 | search_result 命中 | sse_data 命中 |
|---|---:|---:|---:|
| `scraper.chatgpt/US/0010.json` | 0 | 4 | 11 |
| `scraper.chatgpt/US/0019.json` | 0 | 4 | 11 |
| `scraper.chatgpt/US/0034.json` | 0 | 4 | 11 |
| `scraper.chatgpt/US/0036.json` | 0 | 4 | 11 |

命中的是 `www.botslab.com` 的博客《Best Home Security Camera Brands for Homeowners in 2026 – Botslab》，标题与题目高度对应。其余 86 个文件里的 `botslab` 命中是 JSON 键名 `mentioned_botslab` 本身。**按回答正文口径，真实提及率是 0/89，不是 4.44%。**

**检测**：`audit_crawl_integrity.py` 的 `MENTION_FLAG_LAYER_MIXING`。

**影响**：会直接抬高所有品牌（尤其目标品牌）的对外提及率。凡以该标记为分母依据的报告数字都不可信。

**附带结论（不是缺陷，是机会）**：品牌官网能被检索到却没进正文引用，说明「被检索」到「被提及/被引用」之间存在断层——用 `TARGET_IN_RETRIEVAL_ONLY` 单独统计，这是内容优化的直接抓手。

---

## D2 · 正文丢失引用定义行（警告）

**现象**：正文引用标记引用了某个编号，但正文尾部的 `[编号]: url "标题"` 定义行没有交付。

**实测证据**：

- Gemini：`security-camera-results-20260916-145031/scraper.gemini/US/0012.json`、`0017.json` 正文只有 `[2]:`、`[3]:` 等，缺 `[1]:`；`citations` 数组仍保留该条。
- AIMode：`botslab 爬虫数据/scraper.aimode/0001.json` 标记引用 1、4、5、6、7、10–24，定义行只有 10–24，**开头 9 条被截断**；`citations` 数组共 24 条完整。

**检测**：`MISSING_REFERENCE_DEFINITION`。

**修复规则（已验证）**：缺失编号 `N` 时，取引用字段数组的第 `N` 个元素（`citations[N-1]` / `content_references[N-1]`）。已验证 label 与来源名逐条吻合：

| 文件 | 正文 label | 数组第 N 条来源名 | 一致 |
|---|---|---|---|
| aimode/0001 `[1]` | Vortex Radar | Vortex Radar | ✅ |
| aimode/0001 `[4]` | PCMag | PCMag | ✅ |
| aimode/0001 `[5]` | YouTube | YouTube | ✅ |
| aimode/0001 `[6]` | Reddit | Reddit | ✅ |
| aimode/0001 `[7]` | REDTIGER Official | REDTIGER Official | ✅ |
| gemini/0012 `[1]` | Dash Cam Insight | Dash Cam Insight | ✅ |

回退必须在产出里标注来源，不能与前向匹配混为一谈。

---

## D3 · 引用字段为空但正文有引用（警告）

**现象**：供应商引用字段是空数组，而正文里引用标记和定义行都在。

**实测证据**：`security-camera-results-20260916-145031/scraper.chatgpt/US/0040.json`——正文 4 次标记（`([SecurityCam Lab][1])`、`([WIRED][2])`、`([Tom's Guide][3])`、`([SecurityCam Lab][1])`）、3 条定义行，但 `content_references` 是 `[]`。该条正文里 `[文字](url)` 超链接数为 **0**，即引用确实以标记形式呈现，不是超链接形式。

**检测**：`EMPTY_CITATION_FIELD`。

**影响**：直接用字段统计会把这条判成「无引用」，ChatGPT 引用次数少算 4 次。

---

## D4 · 引用次数与去重来源混用（口径提醒）

**现象**：产出里只给一个「引用数」，读者按来源页面数理解。

**依据**：见 [数据分层契约](layer-contract.md#两个计数单位必须同时给出)。实例：ChatGPT `US/0040.json` 是 **4 次引用 / 3 个来源页面**（SecurityCam Lab 被引两次）。

**检测**：脚本对每条样本恒定输出 `CITATION_UNITS`，要求下游两个数一起给。

---

## D5 · 空回答与失败页混入分母（阻断）

**现象**：模型返回错误提示页，被当成正常回答计入分母。

**实测证据**：

- `security-camera-results-20260916-145031/scraper.gemini/US/0018.json`：正文为 `I encountered an error doing what you asked. Could you try again?`（65 字符）。
- `botslab 爬虫数据/scraper.overview/0029.json`：正文为空。

**检测**：`EMPTY_ANSWER`、`FAILED_ANSWER`。

**处理**：不进任何分母，也不计为「未提及」。四个平台分母因此可以不等。

---

## D6 · 采集改写了字词与正文尾部（警告）

**现象**：响应体里出现不成词的片段、被替换的同音/形近词，或正文在句中戛然而止。字段层面全部正常，任何按字段取数的流程都不会报错，**只有逐字读正文才会发现**。

**实测证据**（Bewinch 2026-09-15，全部出现在 Perplexity）：

| 文件 | 正文原文 | 应为 |
|---|---|---|
| `scraper.perplexity/MY/0044.json` | `plug-and-dline` | plug-and-play |
| `scraper.perplexity/MY/0045.json` | `faucet-ted`、`greenhouse of model options` | faucet-connected、gamut/range of model options |
| `scraper.perplexity/MY/0048.json` | `faucet-mipe` | faucet-mounted |
| `scraper.perplexity/SG/0011.json` | `side-t mounted` | side-tank mounted |

另有多处正文在句中被截断（结尾孤立的 `#`、`…or yo`、未闭合的引用块）与渲染残留（`product["turn1product0",…]`）。发现路径：翻译阶段逐句读原文时暴露，常规字段核查与指标计算都不会报错。

**检测**：`TEXT_CORRUPTION`，含三部分——`corrupted_words`（命中 `KNOWN_TEXT_CORRUPTION` 词表）、`truncated_tail`（尾部截断）。

**词表维护**：`KNOWN_TEXT_CORRUPTION` 是**显式清单，不是启发式**。产品名与型号（`G3-Pro`、`Waterdrop-A1`）同真损坏在形状上无法区分，用正则猜会大量误报。发现新损坏时追加进清单。

**处理**：警告级，不阻断指标计算；但**受影响条目的原文与译文不得直接交付给客户**，须先人工校正，或在报告里标注该条为采集异常。若同一平台的损坏持续出现，反馈给采集供应商时附上文件与原文片段。

---

## D7 · 平台没有字段契约（阻断）

**现象**：采集目录里出现 `scraper.<name>` 目录，但 `references/platform-contract.json` 与脚本内置契约都没有这个平台。此时该平台的**全部样本不会被审计**，而脚本仍然会输出一份「看起来完整」的报告。

**为什么单列一条**：这是**静默漏检**，比报错更危险。实测发生过一次——Perplexity 不在契特里，400 条采样只审计了 300 条，D6 的词损坏一个都没扫到，而输出没有任何异常提示。

**检测**：`UNKNOWN_PLATFORM_CONTRACT`，报告里 `unknown_platforms` 列出全部未登记平台。

**处理**：**不得宣称采集可信**。在 `references/platform-contract.json` 补该平台的四层字段映射后重跑。平台会持续扩展，新增平台只需改这个 JSON，不必改脚本。

---

## 判读边界

- 检测只报事实与受影响记录，不修改采集文件。
- 不把第三方模型的正常输出差异当成采集缺陷。
- 不因为某条回答「看起来像 bug」就归因，必须能指到字段和记录。
