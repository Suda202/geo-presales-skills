# 渲染规范(数据层产出 → 客户 HTML)

数据层把回答正文转成成品 HTML(`answer_html` / `answer_zh_html`),渲染层直接注入。以下规则来自 Bewinch 报告的实战缺陷,改 `assets/report.js`、`assets/report-extra.css` 或 `scripts/build_report_data.py` 的 markdown 转换前必读。

**源码真相在本 skill**:任何视觉修订都改 `scripts/` 与 `assets/`,然后完整重跑数据链(build → attach_sentiment → attach_translations → verify → render)。手改已渲染的 HTML 会在下次重渲染时被静默覆盖,且让产物与 `report-data.json` 脱钩。

## 正文渲染(顺序敏感)

Markdown 转换的处理顺序不能随意调换,引用 pill 必须在普通链接之前:

1. 先收集脚注定义行 `[N]: url "标题"`,定义行本身从正文移除,但 URL 要留住供 pill 链接。
2. **引用 pill**:`([来源名][N])` 与 `[来源名][N]` 渲染成句尾可点击的 pill,`href` 取脚注 URL,`title` 取来源名;取不到 URL 时降级为不可点击的 `<span>` 而不是丢弃。
3. **Markdown 链接**:URL 里允许一层括号(如 `.../product(tk-cs200-hma)?utm=...`),正则必须容忍,否则链接在首个 `)` 提前闭合、`?utm_source=...)` 漏成可见文本。
4. **表格**:行内 `<br>` 不能换成换行(会把单行表格拆碎、整表退化成裸管道文本),应转成 ` / `;行单元格数**多于**表头时,把溢出格合并进最后一列(前 N-1 列仍对齐),**不要整行丢弃**——实测一条 AIO 回答 80% 正文都在一个超宽行里,丢弃即静默吞内容;少列的行补空。
5. 跨单元格断裂的连续星号(`**LG…/…Wa**`)是碎片,直接删,不要渲染成粗体。

硬约束:

- 品牌高亮**不得覆盖 pill 自身的颜色**;高亮规则要在 pill 生成之后排除 pill 内部文本。
- `answer_html` / `answer_zh_html` 已是转义好的成品,渲染层不要再二次转义。

## 商品卡(ChatGPT 商品表)

- **不要**把 `id / goods / price / rating / merchants / picture` 原始表格直接渲染给客户;19 位商品 ID 无意义。
- 用采集的结构化字段 `task_result.products` 渲染成平台风格商品卡:标题、价格、评分、商家。
- 有 `logo` / `image` 就显示,没有就隐藏占位,**不留空白框**。
- 处理 `product[...]` / `entity[...]` 占位 token;`<img src="data:image/jpeg;base64,...">` 这类内联图会撑爆单元格,需保护后再渲染。

## 交互与文案

- 筛选项:诊断意图用下拉框;「国家」统一叫**「地区」**;搜索框加宽。
- 同一个问题的不同平台 / 地区 variant tab 放**抽屉顶部**;主题汇总行默认展开。
- 排名均值只统计实际提及的问题,未提及的记录不得拉低口径。
- 指标名对外统一用**「发现类问题」**,不写「可见度问题」,也不写「通用回答」等虚构口径。
- 内容规划文案**固定口径,不随品牌数据变化**;第三方阵地先社区(Reddit / LinkedIn),不承诺具体见效时间,只写执行事项与持续监测。

## 验证

- 脚本化遍历 tab 时,**每次点击前重新 querySelector**:tab 按钮每次切换都被 `buildTabs()` 用 innerHTML 重建,开头缓存的引用第一次点击后即失效、后续点击静默无效(Bewinch 案例两轮「45 切片全通过」实际只测了一个切片)。
- 改了 JS / CSS 后必须重做浏览器验证:逐层切国家 / 平台 / 主题,确认各模块有数、无空白、无变形。
