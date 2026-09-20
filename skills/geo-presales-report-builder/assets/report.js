/* 海外 GEO 售前诊断报告 · 交互层
 * 数据来源：页面内嵌的 window.REPORT_DATA（geo-presales-report-data/v1）。
 * 静态外壳由 scripts/render_report.py 产出，本文件负责按 国家 / 平台 / 主题 三层 tab 重渲染各模块。
 */
(function () {
  "use strict";

  var DATA = window.REPORT_DATA || {};
  var META = DATA.meta || {};
  var SLICES = DATA.slices || {};
  var FILLS = ["gold", "blue", "cyan", "green", "amber", "red", ""];
  var MAX_COMPETITION_ROWS = 5;

  var state = { region: "", platform: "", topic: "", matrixMetric: "mention", expanded: {}, page: 1 };
  var PAGE_SIZE = 20;

  function esc(value) {
    return String(value === null || value === undefined ? "" : value).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function favicon(domainOrUrl) {
    var d = String(domainOrUrl || "").replace(/^https?:\/\//, "").split("/")[0];
    return "https://favicone.com/" + encodeURIComponent(d) + "?s=64";
  }
  // 品牌显示名：剥掉数据层 key 里的品类/产品线后缀，让榜单读品牌本身。
  // 识别别名仍用全称匹配（数据层 key 不变），仅展示层精简。
  // 后缀词表由数据层按品类注入（meta.brand_suffixes）；缺省用净水器词表兜底，
  // 换品类时应提供该品类的后缀（如显示屏品类要剥 "Display"/"LED"）。
  var BRAND_SUFFIX = (function () {
    var custom = (DATA.meta || {}).brand_suffixes;
    if (custom && custom.length) {
      return new RegExp("\\s+(" + custom.map(function (w) {
        return String(w).replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/\s+/g, "\\s*");
      }).join("|") + ")$", "i");
    }
    return /\s+(Water|Water\s*Purifier|Purification|Aqua|Filters?)$/i;
  })();
  function displayBrand(name) {
    var n = String(name || "").replace(/\s*★\s*$/, "");
    return n.replace(BRAND_SUFFIX, "").trim() || n;
  }
  function logo(domain, size, brandName) {
    var s = size || 16;
    var initial = displayBrand(brandName || domain || "?").trim().charAt(0).toUpperCase();
    // icon 加载失败时回退为首字母占位块，保持行对齐（原来 this.remove() 会留空白）
    // 注意：onerror 属性值用双引号包裹，内部所有双引号必须用 &quot; 转义
    var fallbackSpan = '<span class="entity-logo entity-logo-fallback" style="width:' + s + 'px;height:' + s + 'px;font-size:' + Math.round(s * 0.62) + 'px">' + initial + '</span>';
    if (!domain) {
      return fallbackSpan;
    }
    var escapedFallback = fallbackSpan.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '&quot;');
    return '<img class="entity-logo" src="' + favicon(domain) + '" width="' + s + '" height="' + s + '" alt="" loading="lazy" onerror="this.outerHTML=\'' + escapedFallback + '\'">';
  }
  function sliceKey(region, platform, topic) {
    return [region, platform, topic].join("|");
  }
  function currentSlice() {
    // 逐级降级：精确切片 → 同国家全平台全主题 → 首个国家的精确切片 → 首个国家的全量切片。
    // 「全部地区」等合并切片由数据层产出；缺失时不能让整页空白。
    var firstRegion = (META.regions || [])[0] || "";
    var candidates = [
      sliceKey(state.region, state.platform, state.topic),
      sliceKey(state.region, "", ""),
      sliceKey(firstRegion, state.platform, state.topic),
      sliceKey(firstRegion, "", "")
    ];
    for (var i = 0; i < candidates.length; i += 1) {
      if (SLICES[candidates[i]]) return SLICES[candidates[i]];
    }
    return { kpis: {}, competition: {}, matrix: {}, sources: {}, sentiment: {}, records: [] };
  }
  function catTag(name) {
    if (!name) return "";
    return '<span class="cat-tag cat-' + esc(name) + '">' + esc(name) + "</span>";
  }
  function pctWidth(value) {
    var n = parseFloat(String(value).replace("%", ""));
    return Number.isFinite(n) ? Math.max(2, Math.min(100, n)) + "%" : "0%";
  }
  function rankDotLeft(value) {
    var n = parseFloat(value);
    if (!Number.isFinite(n)) return "50%";
    return Math.max(2, Math.min(98, 2 + ((n - 1) / 5) * 96)) + "%";
  }

  /* ---------- 基础信息 ---------- */

  function renderMasthead() {
    var el = document.getElementById("reportTitle");
    if (el) el.innerHTML = esc(META.brand || "") + "<span>海外 AI 搜索可见度售前诊断</span>";
    var eyebrow = document.getElementById("reportEyebrow");
    if (eyebrow) eyebrow.textContent = "GEO Presales Diagnosis · " + esc(META.generated_at || "");
    var foot = document.getElementById("footerBrand");
    if (foot) foot.textContent = "海外 GEO 售前诊断报告 · " + esc(META.brand || "");
  }

  /* ---------- tab ---------- */

  function buildTabs(containerId, values, activeValue, dataAttr, allLabel, toggleable) {
    var el = document.getElementById(containerId);
    if (!el) return;
    var html = "";
    if (allLabel) {
      html += '<button class="tab-btn' + (activeValue === "" ? " active" : "") +
        '" type="button" data-' + dataAttr + '="" data-toggle="' + (toggleable ? "1" : "0") + '">' + esc(allLabel) + "</button>";
    }
    values.forEach(function (value) {
      html += '<button class="tab-btn' + (activeValue === value ? " active" : "") +
        '" type="button" data-' + dataAttr + '="' + esc(value) + '" data-toggle="' + (toggleable ? "1" : "0") + '">' + esc(value) + "</button>";
    });
    el.innerHTML = html;
  }

  function renderTabs() {
    buildTabs("regionTabs", META.regions || [], state.region, "region", "全部地区", false);
    buildTabs("platformTabs", META.platforms || [], state.platform, "platform", "全部平台", false);
    buildTabs("topicTabs", META.topics || [], state.topic, "topic", "全部主题", true);
  }

  /* ---------- 核心洞察 KPI ---------- */

  function renderKpis() {
    var slice = currentSlice();
    var k = slice.kpis || {};
    var el = document.getElementById("overviewKpis");
    if (!el) return;
    var items = [
      ["提及率", k.mention_rate, "可见度问题中，监测对象被 AI 提及的比例。越高说明监测对象越容易进入相关回答。"],
      ["提及率排名", k.mention_rank, "按提及率由高到低在当前品牌集合中的位置。"],
      ["声量份额", k.share_of_voice, "监测对象提及量 ÷ 全部纳入品牌的提及量之和。"],
      ["平均提及位置", k.average_rank, "监测对象被提及时的平均位置。数值越小，表示位置越靠前。"],
      ["引用份额", k.official_share, "指向监测对象官网的引用记录数 ÷ 全部引用记录数。"]
    ];
    el.innerHTML = items.map(function (row) {
      return '<div class="kpi"><span class="label">' + esc(row[0]) +
        '<button type="button" class="info" aria-label="查看' + esc(row[0]) + '含义" data-tip="' + esc(row[2]) + '">i</button>' +
        '</span><strong class="value">' + esc(row[1] || "—") + "</strong></div>";
    }).join("");
  }

  /* ---------- 02 可见度 ---------- */

  function renderCompetition() {
    var slice = currentSlice();
    var comp = slice.competition || {};
    var mention = (comp.mention || []).slice(0, MAX_COMPETITION_ROWS);
    var rank = (comp.rank || []).slice(0, MAX_COMPETITION_ROWS);

    var mentionEl = document.getElementById("competitionMentions");
    if (mentionEl) {
      mentionEl.innerHTML = mention.map(function (row) {
        var color = row[4] || "";
        var isTarget = color === "gold";
        return '<div class="bar-row' + (isTarget ? " is-target" : "") + '">' +
          '<span class="bar-rank">' + esc(row[5]) + "</span>" +
          '<span class="bar-label">' + logo(row[1], 16, row[0]) + esc(displayBrand(row[0])) + "</span>" +
          '<div class="track"><div class="fill ' + esc(color) + '" style="width:' + pctWidth(row[3]) + '"></div></div>' +
          '<b class="bar-val">' + esc(row[2]) + "</b></div>";
      }).join("") || emptyRow("暂无数据");
    }

    var rankEl = document.getElementById("competitionRank");
    if (rankEl) {
      rankEl.innerHTML = rank.map(function (row) {
        var isTarget = row[3] === "target";
        return '<div class="rankdot-row' + (isTarget ? " is-target" : "") + '">' +
          '<span class="rankdot-name">' + logo(row[1], 18, row[0]) + esc(displayBrand(row[0])) + "</span>" +
          '<span class="rankdot-track"><i class="' + (isTarget ? "gold" : "") + '" style="left:' + rankDotLeft(row[2]) + '"></i></span>' +
          '<span class="rankdot-val">' + esc(row[2]) + "</span></div>";
      }).join("") || emptyRow("暂无数据");
    }

    var share = comp.share || [];
    var donutEl = document.getElementById("competitionShare");
    if (donutEl) {
      var segments = [];
      var total = 0;
      mention.forEach(function (row, index) {
        var value = Number(share[index] || 0);
        var color = row[4] || "";
        segments.push({
          name: row[0],
          value: value,
          color: "var(--" + (color === "gold" ? "gold" : color === "" ? "navy" : color) + ")",
          target: color === "gold"
        });
        total += value;
      });
      // 声量份额分母是全部纳入品牌（含未展示的开放品牌），展示几行相加不足 100%，
      // 余量单列为「其他品牌」，否则环形图只会画出一小块。
      var residual = Math.round((100 - total) * 10) / 10;
      if (residual > 0.5) {
        segments.push({ name: "其他品牌", value: residual, color: "var(--quiet)", target: false });
      }
      // 环形图与图例使用同一份排序结果，保证颜色与品牌一一对应。
      segments.sort(function (a, b) { return b.value - a.value; });
      var stops = [];
      var cursor = 0;
      segments.forEach(function (seg) {
        stops.push(seg.color + " " + cursor + "% " + (cursor + seg.value) + "%");
        cursor += seg.value;
      });
      if (!stops.length) stops.push("var(--line) 0% 100%");
      var targetRow = segments.filter(function (r) { return r.target; })[0] || segments[0];
      donutEl.innerHTML =
        '<div class="donut-wrap"><div class="donut" style="background:conic-gradient(' + stops.join(",") + ')"></div>' +
        '<div class="donut-center"><b>' + esc(targetRow ? targetRow.value.toFixed(1) + "%" : "—") + "</b><small>" +
        esc((targetRow ? displayBrand(targetRow.name) : "")) + "</small></div></div>" +
        '<div class="donut-legend">' + segments.map(function (row) {
          return "<div" + (row.target ? ' class="is-target"' : "") + '><i style="background:' + row.color + '"></i><span>' +
            esc(displayBrand(row.name)) + "</span><b>" + row.value.toFixed(1) + "%</b></div>";
        }).join("") + "</div>";
    }

    renderMatrix();
  }

  function renderMatrix() {
    var slice = currentSlice();
    var matrix = slice.matrix || {};
    var metric = state.matrixMetric;
    var platforms = (matrix.platforms || []).length ? matrix.platforms : (META.platforms || []);
    var rows = matrix[metric] || [];
    var el = document.getElementById("platformMatrix");
    if (!el) return;
    if (!rows.length) { el.innerHTML = ""; return; }
    var head = "<thead><tr><th>品牌</th>" + platforms.map(function (p) { return "<th>" + esc(p) + "</th>"; }).join("") + "</tr></thead>";
    var body = "<tbody>" + rows.map(function (row) {
      var cells = platforms.map(function (_, index) {
        var value = (row.vals || [])[index];
        if (value === null || value === undefined) return "<td>—</td>";
        if (metric === "rank") return "<td>" + Number(value).toFixed(1) + "</td>";
        return "<td>" + Number(value).toFixed(1) + "%</td>";
      }).join("");
      return "<tr" + (row.target ? ' class="is-target"' : "") + '><td class="brand-cell">' + esc(displayBrand(row.name)) + "</td>" + cells + "</tr>";
    }).join("") + "</tbody>";
    el.innerHTML = head + body;
  }

  /* ---------- 03 引用 ---------- */

  function renderSources() {
    var slice = currentSlice();
    var sources = slice.sources || {};
    var badge = document.getElementById("sourceShareBadge");
    if (badge) {
      badge.innerHTML = "引用份额 <b>" + esc(sources.official_share || "—") + "</b>";
    }

    var typesEl = document.getElementById("sourceTypes");
    if (typesEl) {
      var types = sources.types || [];
      var max = types.reduce(function (acc, row) {
        return Math.max(acc, parseFloat(String(row[1]).replace("%", "")) || 0);
      }, 0) || 1;
      typesEl.innerHTML = '<div class="bar-head"><span>类别</span><span>引用份额</span></div>' +
        (types.map(function (row) {
        var value = parseFloat(String(row[1]).replace("%", "")) || 0;
        return '<div class="bar-row"><span class="bar-label">' + esc(row[0]) + "</span>" +
          '<div class="track"><div class="fill ' + esc(row[3] || "") + '" style="width:' + Math.max(2, (value / max) * 100) + '%"></div></div>' +
          '<b class="bar-val">' + esc(row[1]) + "</b></div>";
      }).join("") || emptyRow("暂无数据"));
    }

    var domainsEl = document.getElementById("sourceDomains");
    if (domainsEl) {
      var domains = sources.domains || [];
      domainsEl.innerHTML = domains.map(function (row) {
        return '<div class="domain-row"><span class="domain-name">' + logo(row[0]) + esc(row[0]) + "</span>" +
          catTag(row[2]) + '<span class="share">' + esc(row[1]) + "</span></div>";
      }).join("") || emptyRow("暂无数据");
    }

    var pagesEl = document.getElementById("sourcePages");
    if (pagesEl) {
      var pages = sources.pages || [];
      var pageHead = '<div class="page-head"><span>页面</span><span>类别</span><span>页面中提及</span><span>引用份额</span></div>';
      pagesEl.innerHTML = pageHead + (pages.map(function (row) {
        var miss = row[2] === "未提及";
        return '<div class="page-item" data-tip="' + esc(row[0]) + '">' +
          '<div class="page-title-with-logo">' + logo(row[0], 18) +
            '<small class="page-url">' + esc(row[0]) + "</small></div>" +
          catTag(row[1]) +
          '<span class="page-mention' + (miss ? " miss" : "") + '">' + esc(row[2]) + "</span>" +
          '<span class="count">' + esc(row[3]) + "</span></div>";
      }).join("") || emptyRow("暂无数据"));
    }

    var officialEl = document.getElementById("officialPages");
    if (officialEl) {
      var official = sources.official_pages || [];
      var officialHead = '<div class="page-head"><span>页面</span><span>引用份额</span></div>';
      officialEl.innerHTML = officialHead + (official.map(function (row) {
        return '<div class="page-item" data-tip="' + esc(row[0]) + '"><div class="page-title-with-logo">' +
          logo(META.official_domain, 18) +
          '<small class="page-url">' + esc(row[0]) + "</small></div>" +
          '<span class="count">' + esc(row[1]) + "</span></div>";
      }).join("") || emptyRow("官网尚未被引用"));
    }
  }

  /* ---------- 04 情感 ---------- */

  function renderSentiment() {
    var slice = currentSlice();
    var sentiment = slice.sentiment || {};
    var summary = sentiment.summary || {};
    var claims = sentiment.claims || { pos: [], neg: [] };

    var el = document.getElementById("sentimentRates");
    if (el) {
      var intro = "<h3>" + esc((META.brand || "") + " 的正负向表达") + "</h3>";
      el.innerHTML = intro +
        bucket("正向", summary.pos_rate, "pos", claims.pos || []) +
        bucket("负向", summary.neg_rate, "neg", claims.neg || []);
      var first = (claims.pos || [])[0] || (claims.neg || [])[0] || null;
      showEvidence(first, first && (claims.pos || []).indexOf(first) >= 0 ? "pos" : "neg");
    }
    renderSentimentOverview();
    renderSentimentMatrix();
  }

  function sentimentRateValue(text) {
    var n = parseFloat(String(text || "").replace("%", ""));
    return isFinite(n) ? n : null;
  }

  function sentimentRateClass(value) {
    if (value == null) return "rate-none";
    if (value >= 80) return "rate-good";
    if (value >= 60) return "rate-mid";
    return "rate-bad";
  }

  function renderSentimentOverview() {
    var slice = currentSlice();
    var byBrand = ((slice.sentiment || {}).by_brand) || {};
    var el = document.getElementById("sentimentOverviewBars");
    if (!el) return;
    var brands = (META.sentiment_brands && META.sentiment_brands.length
      ? META.sentiment_brands : Object.keys(byBrand));
    if (!brands.length) {
      el.innerHTML = '<p class="support-line">情感判读尚未接入</p>';
      return;
    }
    var target = META.brand || "";
    var items = brands.map(function (brand) {
      var cell = byBrand[brand] || {};
      var rateText = cell.pos_rate || "—";
      var value = sentimentRateValue(rateText);
      var width = value == null ? 0 : Math.max(2, Math.min(100, value));
      return '<div class="sentiment-overview-bar' + (brand === target ? " is-target" : "") + '">' +
        '<div class="bar-head"><span class="bar-brand">' + esc(displayBrand(brand)) +
        (brand === target ? " ★" : "") + "</span>" +
        '<span class="bar-value">' + esc(rateText) + "</span></div>" +
        '<div class="bar-track"><span class="bar-fill ' + sentimentRateClass(value) +
        '" style="width:' + width + '%"></span></div>' +
        "</div>";
    }).join("");
    el.innerHTML = '<div class="sentiment-overview-bars">' + items + "</div>";
  }

  function bucket(title, rateText, dir, items) {
    var chips = items.map(function (item, index) {
      return '<button type="button" class="sentiment-chip ' + dir + (index === 0 ? " active" : "") +
        '" data-claim="' + esc(dir + ":" + index) + '">' + esc(item.label || item.text) + "</button>";
    }).join("") || '<span class="support-line">暂无判读结果</span>';
    return '<div class="sentiment-bucket">' +
      '<div class="sentiment-rate ' + dir + '">' + esc(rateText || "—") + " " + esc(title) + "</div>" +
      '<div class="sentiment-chip-list">' + chips + "</div></div>";
  }

  function showEvidence(item, dir) {
    var el = document.getElementById("sentimentEvidence");
    if (!el) return;
    if (!item || !item.evidence) {
      el.innerHTML = '<p class="support-line">暂无判读结果</p>';
      return;
    }
    var ev = item.evidence;
    var platform = PLATFORM_LABEL_WITH_DIR[ev.platform] || ev.platform || "";
    var where = [ev.region, platform, ev.question_id].filter(Boolean).join(" · ");
    // 句子里残留的 markdown 加粗先转义再转 <strong>，避免裸 ** 显示
    var sentenceHtml = esc(ev.sentence || "")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    el.innerHTML =
      '<span class="sentiment-evidence-dir ' + esc(dir) + '">' + (dir === "pos" ? "正向" : "负向") + "</span>" +
      '<h4 class="sentiment-evidence-claim">' + esc(item.label || "") + "</h4>" +
      '<p class="sentiment-evidence-where">' + esc(where) + "</p>" +
      '<blockquote class="sentiment-evidence-text">' + sentenceHtml + "</blockquote>" +
      '<button type="button" class="sentiment-evidence-toggle" data-open-answer="' +
      esc(ev.question_id || "") + '" data-open-region="' + esc(ev.region || "") +
      '" data-open-platform="' + esc(platform) + '">查看对应回答</button>';
  }

  var PLATFORM_LABEL_WITH_DIR = { overview: "AIO", gemini: "Gemini", chatgpt: "ChatGPT", perplexity: "Perplexity" };

  function renderSentimentMatrix() {
    var slice = currentSlice();
    var themeMatrix = (slice.sentiment || {}).theme_matrix || null;
    var el = document.getElementById("sentimentMatrix");
    if (!el) return;
    if (!themeMatrix || !themeMatrix.themes || !themeMatrix.brands) {
      el.innerHTML = '<tbody><tr><td class="support-line">情感判读尚未接入</td></tr></tbody>';
      return;
    }
    var themes = themeMatrix.themes;
    var brands = themeMatrix.brands;
    var matrix = themeMatrix.matrix || {};
    var target = META.brand || "";
    var head = "<thead><tr><th>Theme</th>" +
      brands.map(function (b) {
        return '<th class="' + (b === target ? "is-target" : "") + '">' + esc(displayBrand(b)) +
          (b === target ? " ★" : "") + "</th>";
      }).join("") + "</tr></thead>";
    var body = "<tbody>" + themes.map(function (theme) {
      var row = matrix[theme] || {};
      var cells = brands.map(function (brand) {
        var cell = row[brand] || { pos: 0, neg: 0, rate: "—", top_claim: "", top_dir: "" };
        var display = cell.top_claim || "—";
        var dirClass = cell.top_dir === "pos" ? "dir-pos" : cell.top_dir === "neg" ? "dir-neg" : "dir-none";
        var title = esc(brand + " · " + theme + " · 正 " + cell.pos + " / 负 " + cell.neg);
        return '<td class="theme-cell ' + dirClass + '" title="' + title + '">' + esc(display) + "</td>";
      }).join("");
      return "<tr><th>" + esc(theme) + "</th>" + cells + "</tr>";
    }).join("") + "</tbody>";
    el.innerHTML = head + body;
  }

  /* ---------- 附录 问题明细 ---------- */

  function recordsForSlice() {
    var slice = currentSlice();
    var all = slice.records || [];
    var query = (state.recordQuery || "").toLowerCase().trim();
    var intent = state.recordIntent || "";
    if (!query && !intent) return all;
    return all.filter(function (r) {
      if (intent && r.intent !== intent) return false;
      if (query) {
        var hay = [String(r.qid), r.en, r.zh].join(" ").toLowerCase();
        if (!hay.includes(query)) return false;
      }
      return true;
    });
  }

  var RECORD_HEAD = "<thead><tr>" +
    '<th class="num">编号</th><th>问题</th><th class="num">提及率</th>' +
    '<th class="num">提及率排名</th><th class="num">声量份额</th>' +
    '<th class="num">引用份额</th><th class="center">正向情感占比</th>' +
    '<th class="center">详情</th></tr></thead>';

  function renderRecords() {
    var records = recordsForSlice();
    var groups = {};
    var order = [];
    records.forEach(function (record) {
      var topic = record.topic || "未分组";
      if (!groups[topic]) { groups[topic] = []; order.push(topic); }
      groups[topic].push(record);
    });

    var table = document.getElementById("recordTable");
    if (!table) return;
    if (!order.length) {
      table.innerHTML = RECORD_HEAD +
        '<tbody><tr><td class="empty" colspan="8">没有符合当前条件的记录</td></tr></tbody>';
      renderPagination(0, 1);
      return;
    }

    var pages = Math.max(1, Math.ceil(order.length / PAGE_SIZE));
    if (state.page > pages) state.page = pages;
    var visible = order.slice((state.page - 1) * PAGE_SIZE, state.page * PAGE_SIZE);

    table.innerHTML = RECORD_HEAD + visible.map(function (topic) {
      var rows = groups[topic];
      var isOpen = state.expanded[topic] !== false;
      // 按主题聚合：提及率/声量/引用份额取均值，排名只统计有提及的题（没提及的题 rank=末位，会拉高均值）
      var withMention = rows.filter(function (r) { return r.mention_rate && r.mention_rate !== "—"; });
      var avgMention = withMention.length ?
        (withMention.reduce(function (a, r) { return a + parseFloat(r.mention_rate); }, 0) / withMention.length).toFixed(1) + "%" : "—";
      var mentioned = rows.filter(function (r) { return r.mentioned; });
      var avgRank = mentioned.length ?
        (mentioned.reduce(function (a, r) { return a + parseFloat(r.rank); }, 0) / mentioned.length).toFixed(1) : "—";
      var withShare = rows.filter(function (r) { return r.share && r.share !== "—"; });
      var avgShare = withShare.length ?
        (withShare.reduce(function (a, r) { return a + parseFloat(r.share); }, 0) / withShare.length).toFixed(1) + "%" : "—";
      var withCite = rows.filter(function (r) { return r.citation_share && r.citation_share !== "—"; });
      var avgCite = withCite.length ?
        (withCite.reduce(function (a, r) { return a + parseFloat(r.citation_share); }, 0) / withCite.length).toFixed(1) + "%" : "—";
      var withSent = rows.filter(function (r) { return r.sentiment && r.sentiment !== "—"; });
      var avgSent = withSent.length ?
        (withSent.reduce(function (a, r) { return a + parseFloat(r.sentiment); }, 0) / withSent.length).toFixed(1) + "%" : "—";

      var head = '<tr class="group-head" role="button" tabindex="0" aria-expanded="' + isOpen + '">' +
        '<td class="num group-toggle-cell"><span class="group-chevron">▸</span></td>' +
        "<td><strong>" + esc(topic) + '</strong><span class="group-count">' + rows.length + "</span></td>" +
        '<td class="rank-num num"><strong>' + esc(avgMention) + '</strong></td>' +
        '<td class="rank-num num"><strong>' + esc(avgRank) + '</strong></td>' +
        '<td class="rank-num num"><strong>' + esc(avgShare) + '</strong></td>' +
        '<td class="rank-num num"><strong>' + esc(avgCite) + '</strong></td>' +
        '<td class="center"><strong>' + esc(avgSent) + '</strong></td>' +
        '<td class="center"></td></tr>';
      var items = rows.map(function (record) {
        return '<tr class="q-row">' +
          '<td class="num">' + esc(record.qid) + "</td>" +
          '<td class="q"><b>' + esc(record.en) + "</b><small>" + esc(record.zh) + "</small></td>" +
          '<td class="rank-num num">' + esc(record.mention_rate || "—") + "</td>" +
          '<td class="rank-num num">' + esc(record.rank || "—") + "</td>" +
          '<td class="rank-num num">' + esc(record.share || "—") + "</td>" +
          '<td class="rank-num num">' + esc(record.citation_share || "—") + "</td>" +
          '<td class="center">' + (record.sentiment ? esc(record.sentiment) : '<span aria-label="不适用">—</span>') + "</td>" +
          '<td class="center"><button class="detail-btn" type="button" data-detail="' + esc(record.qid) + '">查看</button></td></tr>';
      }).join("");
      return '<tbody class="topic-group open" data-group-topic="' + esc(topic) + '">' + head + items + "</tbody>";
    }).join("");
    renderPagination(order.length, pages);
  }

  function renderPagination(total, pages) {
    var el = document.getElementById("recordPagination");
    if (!el) return;
    if (pages <= 1) { el.hidden = true; el.innerHTML = ""; return; }
    el.hidden = false;
    el.innerHTML = '<span class="page-status">' + total + " 组 · 第 " + state.page + " / " + pages + " 页</span>" +
      '<button class="page-btn" type="button" data-page="' + (state.page - 1) + '"' + (state.page <= 1 ? " disabled" : "") + ' aria-label="上一页">‹</button>' +
      '<button class="page-btn" type="button" data-page="' + (state.page + 1) + '"' + (state.page >= pages ? " disabled" : "") + ' aria-label="下一页">›</button>';
  }

  function detailFor(qid) {
    var details = DATA.details || {};
    var regions = state.region ? [state.region] : (META.regions || []);
    var platforms = state.platform ? [state.platform] : (META.platforms || []);
    var padded = String(qid).padStart(4, "0");
    for (var r = 0; r < regions.length; r += 1) {
      for (var p = 0; p < platforms.length; p += 1) {
        var entry = details[regions[r] + "|" + platforms[p] + "|" + padded];
        if (entry) return { entry: entry, region: regions[r], platform: platforms[p] };
      }
    }
    return null;
  }

  function allDetailsFor(qid) {
    var details = DATA.details || {};
    var padded = String(qid).padStart(4, "0");
    var results = [];
    (META.regions || []).forEach(function (r) {
      (META.platforms || []).forEach(function (p) {
        var entry = details[r + "|" + p + "|" + padded];
        if (entry) results.push({ entry: entry, region: r, platform: p });
      });
    });
    return results;
  }


  function answerSwitch(entry) {
    var hasZh = !!entry.answer_zh_html;
    var tabs = '<div class="answer-tabs" role="tablist" aria-label="切换回答语言">' +
      '<button class="answer-tab active" type="button" role="tab" aria-selected="true" data-answer-tab="en">回答原文</button>' +
      (hasZh
        ? '<button class="answer-tab" type="button" role="tab" aria-selected="false" data-answer-tab="zh">中文译文</button>'
        : "") +
      "</div>";
    var panels =
      '<div class="answer-panel active answer-md" data-answer-panel="en">' +
      (entry.answer_html || '<p class="support-line">该回答无可解析内容</p>') + "</div>" +
      (hasZh
        ? '<div class="answer-panel answer-md" data-answer-panel="zh">' + entry.answer_zh_html + "</div>"
        : "");
    return '<div class="answer-switch">' + tabs + panels + "</div>";
  }

  function openDrawer(qid) {
    var key = String(qid).padStart(4, "0");
    var record = recordsForSlice().filter(function (r) {
      return String(r.qid).padStart(4, "0") === key;
    })[0];
    var variants = allDetailsFor(qid);
    var found = detailFor(qid);
    var body = document.getElementById("drawerBody");
    if (!body) return;
    if (!found) {
      body.innerHTML = '<div class="detail-layout"><div class="detail-main">' +
        '<p class="drawer-q">' + esc(record ? record.en : "") + "</p>" +
        '<p class="drawer-zh">' + esc(record ? record.zh : "") + "</p>" +
        '<p class="support-line">当前采集目录里没有这道题的原始回答。</p></div></div>';
      document.getElementById("drawerMask").classList.add("open");
      document.body.style.overflow = "hidden";
      return;
    }
    // 当前选中的变体（默认当前切片的）
    state.drawerVariant = state.drawerVariant || {};
    var selectedKey = found.region + "|" + found.platform;
    if (state.drawerVariant[key] && variants.some(function (v) { return (v.region + "|" + v.platform) === state.drawerVariant[key]; })) {
      selectedKey = state.drawerVariant[key];
      found = variants.filter(function (v) { return (v.region + "|" + v.platform) === selectedKey; })[0];
    }
    var entry = found.entry;

    // 平台/国家切换 tab：只在有多个变体时显示
    var variantTabs = "";
    if (variants.length > 1) {
      variantTabs = '<div class="variant-tabs" role="tablist" aria-label="切换平台与地区">' +
        variants.map(function (v) {
          var vKey = v.region + "|" + v.platform;
          var active = vKey === selectedKey;
          return '<button class="variant-tab' + (active ? " active" : "") + '" type="button" role="tab" aria-selected="' + active +
            '" data-variant="' + esc(vKey) + '" data-variant-qid="' + esc(qid) + '">' +
            esc(v.region) + " · " + esc(v.platform) + "</button>";
        }).join("") + "</div>";
    }
    var ranking = (entry.brands || []).map(function (row) {
      return '<div class="brand-rank-row' + (row.target ? " self-brand" : "") + '">' +
        '<span class="brand-name">' + logo(row.domain, 18, row.name) + esc(displayBrand(row.name)) + (row.target ? ' <span class="drawer-sentiment-star">★</span>' : '') + "</span><strong>" +
        esc(row.rank) + "</strong></div>";
    }).join("") || '<p class="support-line">该回答未提及已配置品牌</p>';

    // 引用列表：icon + URL 同一行，URL 单行截断，hover 显示完整
    function citationRow(row, hidden) {
      return '<article class="citation-item"' + (hidden ? " hidden" : "") + ">" +
        logo(row.host, 18) +
        '<a class="citation-url" href="' + esc(row.url) + '" target="_blank" rel="noopener noreferrer" title="' + esc(row.url) + '">' + esc(row.url) + "</a></article>";
    }
    // 引用：平台原始字段（去重后的 URL）
    var platformCitations = (entry.platform_citations || []).map(function (row, index) {
      return citationRow(row, index >= 5);
    }).join("");
    if (!platformCitations) platformCitations = '<p class="support-line">该回答没有可解析的引用记录</p>';
    var citationToggle = (entry.platform_citations || []).length > 5
      ? '<button class="source-toggle" type="button" data-source-toggle aria-expanded="false">查看全部来源</button>'
      : "";

    // 搜索来源：仅 ChatGPT 的 search_result
    var searchResults = (entry.search_results || []).map(function (row, index) {
      var host = row.url.replace(/^https?:\/\//, "").replace(/\/.*$/, "");
      return citationRow({ host: host, url: row.url }, index >= 5);
    }).join("");
    var searchSection = "";
    if (searchResults) {
      searchSection = '<section class="detail-section"><div class="detail-section-head"><h4>搜索来源</h4><span>' +
        (entry.search_results || []).length + ' 个结果</span></div>' +
        '<div class="citation-list">' + searchResults + "</div>" +
        ((entry.search_results || []).length > 5
          ? '<button class="source-toggle" type="button" data-source-toggle aria-expanded="false">查看全部来源</button>'
          : "") + "</section>";
    }

    // 品牌情感：展示该回答中识别到品牌的正/负向 claim 标签
    var sentimentBrands = ((entry.sentiment || {}).brands) || [];
    var sentimentSection = "";
    if (sentimentBrands.length) {
      var targetName = META.brand || "";
      var sorted = sentimentBrands.slice().sort(function (a, b) {
        if (a.brand === targetName) return -1;
        if (b.brand === targetName) return 1;
        return 0;
      });
      var blocks = sorted.map(function (sb) {
        var isTarget = sb.brand === targetName;
        // 按 label 去重，同一 label 只显示一次
        var seen = {};
        var claims = [];
        (sb.pos_claims || []).forEach(function (c) {
          var label = c.label || "";
          if (seen["pos|" + label]) return;
          seen["pos|" + label] = true;
          claims.push('<div class="drawer-claim"><span class="drawer-claim-dir pos">正向</span>' +
            '<span class="drawer-claim-label">' + esc(label) + '</span></div>');
        });
        (sb.neg_claims || []).forEach(function (c) {
          var label = c.label || "";
          if (seen["neg|" + label]) return;
          seen["neg|" + label] = true;
          claims.push('<div class="drawer-claim"><span class="drawer-claim-dir neg">负向</span>' +
            '<span class="drawer-claim-label">' + esc(label) + '</span></div>');
        });
        if (!claims.length) return "";
        return '<div class="drawer-sentiment-brand' + (isTarget ? " is-target" : "") + '">' +
          '<div class="drawer-sentiment-name">' + esc(displayBrand(sb.brand)) + (isTarget ? ' <span class="drawer-sentiment-star">★</span>' : '') + '</div>' +
          claims.join("") + '</div>';
      }).filter(Boolean).join("");
      if (blocks) {
        sentimentSection = '<section class="detail-section"><div class="detail-section-head"><h4>品牌情感</h4></div>' +
          '<div class="drawer-sentiment">' + blocks + '</div></section>';
      }
    }

    body.innerHTML =
      '<div class="detail-layout"><div class="detail-main">' +
      variantTabs +
      '<p class="drawer-q">' + esc(record ? record.en : "") + "</p>" +
      '<p class="drawer-zh">' + esc(record ? record.zh : entry.question_zh) + "</p>" +
      '<div class="detail-meta-grid">' +
      '<div class="detail-meta-cell"><span>主题</span><strong>' + esc(record ? record.topic : "—") + "</strong></div>" +
      '<div class="detail-meta-cell"><span>诊断意图</span><strong>' + esc(record ? record.intent : "—") + "</strong></div>" +
      '<div class="detail-meta-cell"><span>标签</span><strong>' + esc(record ? record.tag : "—") + "</strong></div>" +
      '<div class="detail-meta-cell"><span>引用份额</span><strong>' +
      esc(entry.citation_share || "—") + "</strong></div>" +
      "</div>" +
      // answer_html / answer_zh_html 在数据层由 markdown 转换并转义过，这里直接注入，不再二次 esc。
      answerSwitch(entry) +
      "</div>" +
      '<aside class="detail-side">' +
      '<section class="detail-section"><div class="detail-section-head"><h4>品牌提及</h4><span>' +
      (entry.brands || []).length + " 个结果</span></div>" +
      '<div class="brand-ranking">' + ranking + "</div></section>" +
      sentimentSection +
      '<section class="detail-section"><div class="detail-section-head"><h4>引用</h4><span>' +
      (entry.platform_citations || []).length + " 个来源</span></div>" +
      '<div class="citation-list">' + platformCitations + "</div>" + citationToggle + "</section>" +
      searchSection +
      "</aside></div>";

    document.getElementById("drawerMask").classList.add("open");
    document.body.style.overflow = "hidden";
  }

  function closeDrawer() {
    var mask = document.getElementById("drawerMask");
    if (mask) mask.classList.remove("open");
    document.body.style.overflow = "";
  }

  /* ---------- 内容规划 ---------- */

  function renderOpportunities() {
    var records = recordsForSlice();
    var slice = currentSlice();
    var pages = ((slice.sources || {}).pages) || [];
    var official = ((slice.sources || {}).official_pages) || [];
    // 官网清单取「目标品牌本该出现却没进回答」的题：发现类问题（用户没点名品牌，
    // 品牌本该争夺一席），或题面点名目标品牌的问题（明确在问它，AI 说不出话就是缺口）。
    // 题面只点名竞品的评价题不算——品牌本来就不该在那道题里出现。
    var absent = records.filter(function (r) {
      return (r.discovery || r.target_in_question) && !r.mentioned;
    });

    var officialEl = document.getElementById("officialPlan");
    if (officialEl) {
      var cards = absent.slice(0, 3).map(function (record, index) {
        return '<div class="plan-card"><div class="plan-card-head"><strong>' + (index + 1) + ". " +
          esc(record.zh || record.en) + '</strong><span class="plan-tag gold">补内容</span></div>' +
          '<p class="plan-card-body"><strong>解决问题：</strong>该问题下监测对象尚未进入回答，需建立可被引用的官方事实页。</p></div>';
      }).join("");
      officialEl.innerHTML = cards || '<p class="support-line">当前切片下没有缺失问题</p>';
    }

    var thirdEl = document.getElementById("thirdPartyPlan");
    if (thirdEl) {
      // 只挑「页面存在但 AI 没在里面提到我们」的——已提及的页面不需要再介入。
      var targets = pages.filter(function (row) { return row[2] === "未提及"; })
        .slice(0, 3).map(function (row, index) {
          return '<div class="plan-card"><div class="plan-card-head"><strong>' + (index + 1) + ". " +
            esc(row[0]) + '</strong><span class="plan-tag blue">' + esc(row[1] || "第三方") + "</span></div>" +
            '<p class="plan-card-body"><strong>介入方式：</strong>该页面在 ' + esc(row[3]) +
            " 的引用中承担主要来源，页面中" + esc(row[2]) + "监测对象。</p></div>";
        }).join("");
      thirdEl.innerHTML = targets || '<p class="support-line">当前切片下没有未提及的第三方页面</p>';
    }

  }

  /* ---------- 结论卡 ---------- */

  function setInsight(id, headline, points) {
    var el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = "<h4>" + esc(headline) + "</h4>" + (points.length
      ? "<ul>" + points.map(function (p) {
          return '<li><span class="point-copy">' + p + "</span></li>";
        }).join("") + "</ul>"
      : "");
  }

  function targetRow(rows) {
    return (rows || []).filter(function (r) { return r.target; })[0] || null;
  }

  function renderInsights() {
    var slice = currentSlice();
    var k = slice.kpis || {};
    var mention = (slice.competition || {}).mention || [];
    var target = mention.filter(function (r) { return (r[4] || "") === "gold"; })[0];
    var leader = mention[0];
    var scope = (state.region || "全部地区") + (state.platform ? " · " + state.platform : "") +
      (state.topic ? " · " + state.topic : "");

    if (leader && target) {
      var gap = (parseFloat(leader[2]) - parseFloat(target[2])).toFixed(1);
      var mentionRate = parseFloat(k.mention_rate) || 0;
      var mentionRank = parseInt(k.mention_rank) || 0;
      var shareRate = parseFloat(k.share_of_voice) || 0;
      var avgRank = parseFloat(k.average_rank) || 0;
      var citeShare = parseFloat(k.official_share) || 0;

      // 三层叙事：心智基本盘 → 断层 → 根因
      var narrative = "";
      if (mentionRate >= 60) {
        narrative = "AI 对本品牌「知道且主动推荐」——心智基本盘稳固，";
        if (mentionRank > 3) narrative += "但排名仍有提升空间，";
        narrative += "需守住现有优势并向薄弱环节渗透。";
      } else if (mentionRate >= 30) {
        narrative = "AI 对本品牌「知道但不主动推荐」——心智基本盘存在，";
        narrative += "但在发现型问题中大量未进入首选名单，存在明显的推荐断层。";
      } else {
        narrative = "AI 对本品牌「认知薄弱」——在发现型问题中极少被主动提及，";
        narrative += "心智基本盘尚未建立，需要先解决「被知道」的问题。";
      }

      setInsight("overviewInsight", narrative,
        [
          "<strong>心智现状：</strong>提及率 " + esc(k.mention_rate || "—") +
            "（第 " + esc(k.mention_rank || "—") + " 位），声量份额 " + esc(k.share_of_voice || "—") +
            "，平均提及位置 " + esc(k.average_rank || "—") + "。",
          "<strong>与头部差距：</strong>当前领先品牌为 " + esc(leader[0]) + "（" + esc(leader[2]) +
            "），监测对象与其相差 " + gap + " 个百分点。",
          citeShare < 5
            ? "<strong>根因判断：</strong>官网引用份额仅 " + esc(k.official_share || "—") +
              "，AI 可引用的官方事实源不足，第三方信源主导了叙事权。"
            : "<strong>信源优势：</strong>官网引用份额 " + esc(k.official_share || "—") +
              "，官方事实源已有基础，可继续扩大覆盖。"
        ]);
    } else {
      setInsight("overviewInsight", "当前切片下监测对象未出现在任何回答中。", []);
    }

    var matrix = slice.matrix || {};
    var sentTarget = targetRow(matrix.mention || []);
    var platforms = matrix.platforms || [];
    if (sentTarget && platforms.length) {
      // 跨平台横切看共识：所有平台两两差距都 ≤10pt 才叫有共识；否则就是无共识，
      // 直接点名提及率最高的平台，并把单一平台高低和"优化目标"解耦。
      var vals = (sentTarget.vals || []).map(function (v, i) {
        return v === null || v === undefined ? null : { name: platforms[i], value: v };
      }).filter(Boolean);
      var headline = "";
      var points = [];
      if (!vals.length) {
        headline = "当前切片下监测对象未进入任何平台回答。";
      } else {
        var sorted = vals.slice().sort(function (a, b) { return b.value - a.value; });
        var top = sorted[0];
        var bottom = sorted[sorted.length - 1];
        var spread = top.value - bottom.value;
        if (spread <= 10 && sorted.length >= 2) {
          var avg = sorted.reduce(function (a, c) { return a + c.value; }, 0) / sorted.length;
          headline = "跨平台存在共识：各平台提及率接近（均值约 " + avg.toFixed(1) + "%）。";
          points.push("<strong>各平台：</strong>" + sorted.map(function (c) {
            return c.name + " " + c.value.toFixed(1) + "%";
          }).join("、") + "。");
        } else {
          headline = "跨平台差距较大（最高与最低相差 " + spread.toFixed(1) + " 个百分点），未形成共识。";
          points.push("<strong>提及率最高：</strong>" + top.name + " " + top.value.toFixed(1) + "%。");
          if (sorted.length > 1) {
            points.push("<strong>其他平台：</strong>" + sorted.slice(1).map(function (c) {
              return c.name + " " + c.value.toFixed(1) + "%";
            }).join("、") + "。");
          }
        }
        points.push("<strong>怎么看：</strong>不同平台的信源偏好不同（如 Google 系更常引用 YouTube），同一品牌在各平台表现有差异是普遍现象。多平台一致偏低才代表真实的认知缺口；单一平台的高低波动，会随后续内容分发自然收敛。");
      }
      setInsight("competitionInsight", headline, points);
    }

    var sources = slice.sources || {};
    var topDomain = (sources.domains || [])[0];
    var officialPages = (sources.official_pages || []).length;
    setInsight("sourcesInsight",
      "官网引用份额 " + esc(sources.official_share || "—") + "。",
      [
        topDomain ? "<strong>最大来源：</strong>" + esc(topDomain[0]) + "（" + esc(topDomain[2]) +
          "，计入 " + esc(topDomain[1]) + " 条）。" : "",
        officialPages <= 2
          ? "<strong>风险：</strong>官网可被引用的页面过少，事实定义权主要落在第三方。"
          : "<strong>现状：</strong>官网已有多个页面被引用，可继续按主题扩展。"
      ].filter(Boolean));

    // 落地服务闭环：固定话术，不承诺时间
    var oppEl = document.getElementById("opportunitiesInsight");
    if (oppEl) {
      oppEl.innerHTML = "<h4>以上内容资产按「诊断 → 生产 → 信源分发 → 周期复测」四步推进</h4>" +
        "<ul>" +
        "<li><span class=\"point-copy\"><strong>官网事实底座：</strong>上线结构化事实指南，确保 AI 可引用到权威定义。</span></li>" +
        "<li><span class=\"point-copy\"><strong>第三方信源：</strong>推进 Reddit、LinkedIn 等社区讨论沉淀，辅以媒体评测植入。</span></li>" +
        "<li><span class=\"point-copy\"><strong>周期复测回流：</strong>持续监测并定期重跑全量评估，对比各项指标变化。</span></li>" +
        "</ul>";
    }
  }

  function emptyRow(text) {
    return '<p class="support-line">' + esc(text) + "</p>";
  }

  /* ---------- 渲染总入口 ---------- */

  function renderAll() {
    renderKpis();
    renderCompetition();
    renderSources();
    renderSentiment();
    renderRecords();
    renderOpportunities();
    renderInsights();
    renderTabs();
    renderIntentFilter();
  }

  /* ---------- 明细表意图筛选 ---------- */

  function renderIntentFilter() {
    var el = document.getElementById("recordIntentFilter");
    if (!el) return;
    var slice = currentSlice();
    var intents = [];
    (slice.records || []).forEach(function (r) {
      var label = r.intent || "";
      if (label && intents.indexOf(label) < 0) intents.push(label);
    });
    var html = '<option value="">全部意图</option>';
    intents.forEach(function (label) {
      html += '<option value="' + esc(label) + '"' + (state.recordIntent === label ? " selected" : "") + '>' + esc(label) + "</option>";
    });
    el.innerHTML = html;
  }

  /* ---------- 事件 ---------- */

  function bindEvents() {
    document.addEventListener("click", function (event) {
      var tab = event.target.closest(".filter-tabs [data-region],.filter-tabs [data-platform],.filter-tabs [data-topic]");
      if (tab) {
        if (tab.hasAttribute("data-region")) state.region = tab.getAttribute("data-region");
        if (tab.hasAttribute("data-platform")) state.platform = tab.getAttribute("data-platform");
        if (tab.hasAttribute("data-topic")) {
          var next = tab.getAttribute("data-topic");
          state.topic = (tab.getAttribute("data-toggle") === "1" && state.topic === next) ? "" : next;
        }
        state.page = 1;
        renderAll();
        return;
      }
      var switchBtn = event.target.closest("[data-matrix-metric]");
      if (switchBtn) {
        state.matrixMetric = switchBtn.getAttribute("data-matrix-metric");
        Array.prototype.forEach.call(document.querySelectorAll("[data-matrix-metric]"), function (btn) {
          btn.classList.toggle("active", btn === switchBtn);
        });
        renderMatrix();
        return;
      }
      var chip = event.target.closest("[data-claim]");
      if (chip) {
        var sliceNow = currentSlice();
        var parts = chip.getAttribute("data-claim").split(":");
        var group = ((sliceNow.sentiment || {}).claims || {})[parts[0]] || [];
        Array.prototype.forEach.call(document.querySelectorAll(".sentiment-chip"), function (btn) {
          btn.classList.remove("active");
        });
        chip.classList.add("active");
        showEvidence(group[Number(parts[1])], parts[0]);
        return;
      }
      var openAnswer = event.target.closest("[data-open-answer]");
      if (openAnswer) {
        var wantRegion = openAnswer.getAttribute("data-open-region");
        var wantPlatform = openAnswer.getAttribute("data-open-platform");
        if (wantRegion && META.regions.indexOf(wantRegion) >= 0) state.region = wantRegion;
        if (wantPlatform && META.platforms.indexOf(wantPlatform) >= 0) state.platform = wantPlatform;
        state.topic = "";
        renderAll();
        openDrawer(openAnswer.getAttribute("data-open-answer"));
        return;
      }
      var groupHead = event.target.closest(".group-head");
      if (groupHead) {
        var group = groupHead.closest(".topic-group");
        var name = group.getAttribute("data-group-topic");
        var willOpen = !group.classList.contains("open");
        group.classList.toggle("open", willOpen);
        state.expanded[name] = willOpen;
        return;
      }
      var pageBtn = event.target.closest(".page-btn");
      if (pageBtn && !pageBtn.disabled) {
        state.page = Number(pageBtn.getAttribute("data-page"));
        renderRecords();
        return;
      }
      var answerTab = event.target.closest("[data-answer-tab]");
      if (answerTab) {
        var wanted = answerTab.getAttribute("data-answer-tab");
        Array.prototype.forEach.call(document.querySelectorAll("#drawerBody .answer-tab"), function (btn) {
          var on = btn === answerTab;
          btn.classList.toggle("active", on);
          btn.setAttribute("aria-selected", String(on));
        });
        Array.prototype.forEach.call(document.querySelectorAll("#drawerBody .answer-panel"), function (panel) {
          panel.classList.toggle("active", panel.getAttribute("data-answer-panel") === wanted);
        });
        return;
      }
      var sourceToggle = event.target.closest("[data-source-toggle]");
      if (sourceToggle) {
        var expanded = sourceToggle.getAttribute("aria-expanded") === "true";
        sourceToggle.setAttribute("aria-expanded", String(!expanded));
        sourceToggle.textContent = expanded ? "查看全部来源" : "收起来源";
        Array.prototype.forEach.call(document.querySelectorAll("#drawerBody .citation-item"), function (item, index) {
          if (index >= 5) item.hidden = expanded;
        });
        return;
      }
      var detailBtn = event.target.closest("[data-detail]");
      if (detailBtn) { openDrawer(detailBtn.getAttribute("data-detail")); return; }
      if (event.target.closest("#drawerClose") || event.target.id === "drawerMask") { closeDrawer(); return; }
      var variantTab = event.target.closest("[data-variant]");
      if (variantTab) {
        var vKey = variantTab.getAttribute("data-variant");
        var vQid = variantTab.getAttribute("data-variant-qid");
        state.drawerVariant = state.drawerVariant || {};
        state.drawerVariant[String(vQid).padStart(4, "0")] = vKey;
        openDrawer(vQid);
        return;
      }
      var intentSelect = event.target.closest("#recordIntentFilter");
      if (intentSelect) return; // select handled by change event below
    });

    var searchEl = document.getElementById("recordSearch");
    if (searchEl) {
      searchEl.addEventListener("input", function () {
        state.recordQuery = searchEl.value;
        state.page = 1;
        renderRecords();
      });
    }
    var intentSelect = document.getElementById("recordIntentFilter");
    if (intentSelect) {
      intentSelect.addEventListener("change", function () {
        state.recordIntent = intentSelect.value;
        state.page = 1;
        renderRecords();
      });
    }

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeDrawer();
    });

    var navLinks = Array.prototype.slice.call(document.querySelectorAll(".nav a"));
    var sections = navLinks.map(function (link) { return document.querySelector(link.getAttribute("href")); });
    window.addEventListener("scroll", function () {
      var activeIndex = 0;
      sections.forEach(function (section, index) {
        if (section && section.getBoundingClientRect().top <= 120) activeIndex = index;
      });
      navLinks.forEach(function (link, index) { link.classList.toggle("active", index === activeIndex); });
    }, { passive: true });
  }

  function boot() {
    if (!META.regions || !META.regions.length) {
      var main = document.getElementById("main");
      if (main) main.insertAdjacentHTML("afterbegin", '<p class="support-line">报告数据缺失：meta.regions 为空。</p>');
      return;
    }
    state.region = "";
    try {
      renderMasthead();
      renderAll();
      bindEvents();
    } catch (error) {
      // 渲染期异常会让页面半渲染且没有明显症状，这里显式报出来，避免把残页当成品交付。
      var main = document.getElementById("main");
      if (main) {
        main.insertAdjacentHTML("afterbegin",
          '<p class="support-line" style="color:var(--red)">报告渲染中断：' +
          esc(error && error.message) + "。请检查 report.js 与 report-data.json。</p>");
      }
      if (window.console && console.error) console.error(error);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
