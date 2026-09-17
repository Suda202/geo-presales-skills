"""把 build_report_data.py 产出的 report-data.json 渲染成单文件 HTML 报告。

用法：
    python3 render_report.py --data report-data.json --out report.html

样式与交互分别来自 assets/report.css、assets/report-extra.css、assets/report.js，
全部内联进最终 HTML，产出与原型一致的单文件、无外部依赖（favicon 除外）报告。
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from urllib.parse import urlsplit

ASSETS = Path(__file__).resolve().parent.parent / "assets"

NAV_ITEMS = [
    ("overview", "核心洞察"),
    ("competition", "可见度"),
    ("sources", "引用"),
    ("distribution", "情感"),
    ("opportunities", "内容规划"),
    ("records", "明细"),
]

SECTIONS = [
    ("01", "overview", "核心洞察"),
    ("02", "competition", "可见度"),
    ("03", "sources", "引用"),
    ("04", "distribution", "情感"),
    ("05", "opportunities", "内容规划"),
    ("附录", "records", "问题明细"),
]

KPI_TIPS = [
    ("提及率", "发现类问题中，监测对象被 AI 提及的比例。越高说明监测对象越容易进入相关回答。"),
    ("提及率排名", "按提及率由高到低在当前品牌集合中的位置。"),
    ("声量份额", "监测对象提及量 ÷ 全部纳入品牌的提及量之和。"),
    ("平均提及位置", "监测对象被提及时的平均位置。数值越小，表示位置越靠前。"),
    ("引用份额", "指向监测对象官网的引用记录数 ÷ 全部引用记录数。"),
]


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def favicon(domain: str) -> str:
    host = urlsplit(domain if "//" in domain else f"//{domain}").netloc or domain
    host = host.split("/")[0]
    return f"https://favicone.com/{host}?s=64"


def kpi_row() -> str:
    cells = []
    for label, tip in KPI_TIPS:
        cells.append(
            '<div class="kpi"><span class="label">'
            f'{esc(label)}<button type="button" class="info" aria-label="查看{esc(label)}含义" '
            f'data-tip="{esc(tip)}">i</button></span>'
            '<strong class="value">—</strong></div>'
        )
    return '<div class="kpis" id="overviewKpis">' + "".join(cells) + "</div>"


def section_head(number: str, title: str) -> str:
    return (
        '<div class="section-head"><div class="section-title">'
        f'<span class="section-no">{esc(number)}</span><h2>{esc(title)}</h2>'
        "</div></div>"
    )


def panel(title: str, body_id: str, extra_class: str = "", head_extra: str = "") -> str:
    return (
        f'<article class="panel {extra_class}">'
        f'<div class="panel-head"><h3>{esc(title)}</h3>{head_extra}</div>'
        f'<div class="panel-body" id="{body_id}"></div></article>'
    )


def insight_note(label: str, body_id: str, accent: str = "") -> str:
    style = f' style="border-left-color:var(--{accent})"' if accent else ""
    return (
        f'<div class="insight-note"{style}>'
        f'<span class="insight-label">{esc(label)}</span>'
        f'<div class="insight-copy" id="{body_id}"></div></div>'
    )


def build_body(meta: dict) -> str:
    brand = esc(meta.get("brand", ""))

    masthead = (
        '<div class="masthead"><div class="shell masthead-inner">'
        f'<p class="eyebrow" id="reportEyebrow">GEO Presales Diagnosis · {esc(meta.get("generated_at", ""))}</p>'
        f'<div class="title-row"><div><h1 id="reportTitle">{brand}<span>海外 AI 搜索可见度售前诊断</span></h1></div></div>'
        "</div></div>"
    )

    shared_filter = (
        '<div class="shared-filter" aria-label="数据筛选">'
        '<div class="shared-filter-head"><strong>数据筛选</strong>'
        "<span>地区、平台和主题同时作用于 02 / 03 / 04 / 05 模块</span></div>"
        '<div style="display:grid;gap:12px">'
        '<div class="filter-tabs" id="regionTabs" aria-label="地区筛选"></div>'
        '<div class="filter-tabs" id="platformTabs" aria-label="平台筛选"></div>'
        '<div class="filter-tabs" id="topicTabs" aria-label="主题筛选"></div>'
        "</div></div>"
    )

    matrix_switch = (
        '<span class="matrix-switch">'
        '<button type="button" class="active" data-matrix-metric="mention">提及率</button>'
        '<button type="button" data-matrix-metric="share">声量份额</button>'
        '<button type="button" data-matrix-metric="rank">平均提及位置</button>'
        "</span>"
    )

    share_badge = (
        '<span style="display:inline-flex;align-items:center;gap:5px;padding:4px 10px;border-radius:999px;'
        'background:rgba(192,90,54,.1);border:1px solid rgba(192,90,54,.22);font-size:11px;line-height:1;color:var(--muted)" '
        'id="sourceShareBadge">引用份额 <b style="color:var(--gold-deep);font:700 18px/1 var(--serif);margin-left:1px">—</b></span>'
    )

    parts = []
    for number, section_id, title in SECTIONS:
        body = [section_head(number, title)]
        if section_id == "overview":
            body.append('<div class="section-body">')
            body.append(kpi_row())
            body.append(
                insight_note("结论", "overviewInsight")
            )
            body.append("</div>")
        elif section_id == "competition":
            body.append('<div class="section-body">')
            body.append(
                '<article class="panel"><div class="panel-head"><h3>提及率</h3></div>'
                '<div class="panel-body"><div class="bar-list compare-bars" id="competitionMentions"></div></div></article>'
            )
            body.append(
                '<div class="grid-2" style="gap:20px;margin-top:20px">'
                + panel("声量份额", "competitionShare", "donut-panel")
                + '<article class="panel average-rank-panel"><div class="panel-head"><h3>平均提及位置</h3></div>'
                '<div class="panel-body"><div class="rankdots" id="competitionRank"></div></div></article>'
                + "</div>"
            )
            body.append(
                '<article class="panel matrix-panel" id="platform-matrix" style="margin-top:20px">'
                '<div class="panel-head"><h3>平台 × 品牌矩阵</h3>' + matrix_switch + "</div>"
                '<div class="panel-body"><div class="matrix-wrap">'
                '<table class="matrix" id="platformMatrix" aria-label="各平台下品牌与竞品的指标矩阵"></table>'
                "</div></div></article>"
            )
            body.append(insight_note("结论", "competitionInsight"))
            body.append("</div>")
        elif section_id == "sources":
            body.append('<div class="section-body">')
            body.append(
                '<div class="grid-2" style="gap:20px">'
                + '<article class="panel"><div class="panel-head"><h3>官网引用页面</h3>' + share_badge + '</div>'
                + '<div class="panel-body">'
                + '<div class="page-list" id="officialPages">'
                + '<div class="page-head"><span>页面</span><span>引用份额</span></div>'
                + "</div></div></article>"
                + '<article class="panel"><div class="panel-head"><h3>引用来源类别</h3></div>'
                + '<div class="panel-body"><div class="bar-list source-type-list" id="sourceTypes"></div></div></article>'
                + "</div>"
            )
            body.append(
                '<div class="grid-2" style="gap:20px;margin-top:20px">'
                + '<article class="panel"><div class="panel-head"><h3>热门引用域名</h3></div>'
                + '<div class="panel-body">'
                + '<div class="source-head with-cat"><span>域名</span><span>类别</span><span>引用份额</span></div>'
                + '<div class="domain-list" id="sourceDomains"></div>'
                + "</div></article>"
                + '<article class="panel"><div class="panel-head"><h3>热门引用页面</h3></div>'
                + '<div class="panel-body">'
                + '<div class="page-list has-mention cat" id="sourcePages">'
                + '<div class="page-head"><span>页面</span><span>类别</span><span>页面中提及</span><span>引用份额</span></div>'
                + "</div></div></article>"
                + "</div>"
            )
            body.append(insight_note("结论", "sourcesInsight"))
            body.append("</div>")
        elif section_id == "distribution":
            body.append('<div class="section-body">')
            body.append(
                '<div class="sentiment-board">'
                '<div class="sentiment-overview" id="sentimentRates"></div>'
                '<div class="sentiment-evidence-card" id="sentimentEvidence"></div>'
                "</div>"
            )
            body.append(
                '<article class="panel" style="margin-top:20px">'
                '<div class="panel-head"><h3>竞品情感占比</h3>'
                '<span class="tag">正向情感占比</span></div>'
                '<div class="panel-body"><div id="sentimentOverviewBars"></div></div></article>'
            )
            body.append(
                '<article class="panel" style="margin-top:20px">'
                '<div class="panel-head"><h3>竞品情感矩阵</h3></div>'
                '<div class="panel-body"><div class="table-wrap" style="padding:0;border:0;box-shadow:none">'
                '<table class="attribute-matrix theme-matrix" id="sentimentMatrix"></table>'
                "</div></div></article>"
            )
            body.append("</div>")
        elif section_id == "opportunities":
            body.append('<div class="section-body">')
            body.append(
                '<div class="grid-2" style="gap:24px">'
                '<article class="panel" style="border-top:3px solid var(--gold)">'
                '<div class="panel-head" style="justify-content:space-between"><h3>官网阵地</h3>'
                '<span class="tag gold">事实定义权</span></div>'
                '<div class="panel-body"><div id="officialPlan"></div></div></article>'
                '<article class="panel" style="border-top:3px solid var(--blue)">'
                '<div class="panel-head" style="justify-content:space-between"><h3>第三方阵地</h3>'
                '<span class="tag blue">推荐与信任背书</span></div>'
                '<div class="panel-body"><div id="thirdPartyPlan"></div></div></article>'
                "</div>"
            )
            body.append(insight_note("落地服务闭环", "opportunitiesInsight"))
            body.append("</div>")
            body.append("</div>")
        elif section_id == "records":
            body.append('<div class="section-body">')
            body.append(
                '<div class="records-toolbar">'
                '<input class="records-search" id="recordSearch" type="search" placeholder="搜索编号或问题（中英文）" aria-label="搜索问题">'
                '<select class="records-intent-select" id="recordIntentFilter" aria-label="按诊断意图筛选">'
                '<option value="">全部意图</option>'
                '</select>'
                '</div>'
                '<div class="table-wrap records">'
                '<table class="records-table" id="recordTable" style="min-width:1080px"></table>'
                "</div>"
                '<div class="pagination" id="recordPagination" aria-label="问题明细分页" hidden></div>'
            )
            body.append("</div>")
        parts.append(f'<section class="section" id="{section_id}">' + "".join(body) + "</section>")
        if section_id == "overview":
            parts.append(shared_filter)

    nav = "".join(f'<a href="#{sid}">{esc(label)}</a>' for sid, label in NAV_ITEMS)

    shell = (
        '<body class="formal-report">'
        '<a class="skip" href="#main">跳到主要内容</a>'
        '<header class="topbar"><div class="shell topbar-inner">'
        '<div class="logo"><span class="logo-cn">海外 GEO</span>'
        '<span class="logo-tag">售前诊断</span></div>'
        f'<nav class="nav" aria-label="报告目录">{nav}</nav>'
        "</div></header>"
        + masthead
        + '<main id="main" class="shell">'
        + "".join(parts)
        + "</main>"
        + '<div class="drawer-mask" id="drawerMask" role="dialog" aria-modal="true" aria-label="问题详情">'
        '<aside class="drawer"><div class="drawer-head"><strong>问题详情</strong>'
        '<button class="drawer-close" id="drawerClose" type="button" aria-label="关闭">×</button>'
        '</div><div class="drawer-body" id="drawerBody"></div></aside></div>'
        '<footer><div class="shell"><span id="footerBrand"></span></div></footer>'
    )
    return shell


def check_javascript(js: str, source: Path) -> None:
    """渲染前校验交互脚本语法。

    语法错误会让整页空白，且浏览器只报一句 SyntaxError，排查成本远高于在这里拦住。
    node 不可用时跳过，不阻塞渲染。
    """
    import shutil
    import subprocess
    import tempfile

    node = shutil.which("node")
    if not node:
        return
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
        handle.write(js)
        temp_path = handle.name
    try:
        result = subprocess.run([node, "--check", temp_path], capture_output=True, text=True)
    finally:
        Path(temp_path).unlink(missing_ok=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise SystemExit(f"{source.name} 存在 JavaScript 语法错误：\n" + "\n".join(detail[:6]))


def slim_for_html(data: dict) -> dict:
    """剥掉渲染层用不到的大字段，再嵌进 HTML。

    记录级的 `brands` 是每题 × 全部纳入对象的统计（Bewinch 有 96 个对象），
    45 个切片合计约 20MB，而渲染层一个字段都没用到——页面只用切片级的
    `competition`/`matrix`。它保留在 report-data.json 里供归档与下游读取，
    但不进 HTML，否则单文件会从 3.6MB 涨到 22MB。
    """
    import copy
    slim = copy.deepcopy(data)
    for slice_value in slim.get("slices", {}).values():
        for record in slice_value.get("records", []):
            record.pop("brands", None)
    return slim


def build_html(data: dict) -> str:
    data = slim_for_html(data)
    meta = data.get("meta", {})
    title = f'{meta.get("brand", "")} · 海外 GEO 售前诊断报告'
    css = (ASSETS / "report.css").read_text(encoding="utf-8")
    css_extra = (ASSETS / "report-extra.css").read_text(encoding="utf-8")
    js = (ASSETS / "report.js").read_text(encoding="utf-8")
    check_javascript(js, ASSETS / "report.js")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    return (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f"<title>{esc(title)}</title>\n"
        "<style>\n" + css + "\n</style>\n"
        "<style>\n" + css_extra + "\n</style>\n"
        "</head>\n"
        + build_body(meta)
        + "\n<script>window.REPORT_DATA=" + payload + ";</script>\n"
        + "<script>\n" + js + "\n</script>\n</body>\n</html>\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="渲染海外 GEO 售前诊断报告 HTML")
    parser.add_argument("--data", required=True, help="report-data.json 路径")
    parser.add_argument("--out", required=True, help="输出的 HTML 路径")
    args = parser.parse_args()

    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    if data.get("schema") != "geo-presales-report-data/v1":
        raise SystemExit(f"数据 schema 不匹配：{data.get('schema')!r}")
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_html(data), encoding="utf-8")
    slices = data.get("slices", {})
    print(f"wrote {output}  slices={len(slices)}  bytes={output.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
