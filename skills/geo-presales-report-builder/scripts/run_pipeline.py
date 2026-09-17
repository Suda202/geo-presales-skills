"""售前报告流水线驾驶脚本:一条命令跑到下一个暂停点。

把「采集目录 → HTML」的确定性步骤按序串起来;遇到需要语义工作或人工
决定的环节(词表冻结、情感判读、观点归纳、翻译)时停下,打印该暂停点
缺什么文件、按什么格式补,补齐后重跑本命令自动续跑。

本脚本只调度、不实现:每一步都 subprocess 调用各 skill 既有脚本,口径
和校验完全以被调脚本为准。步骤定义的权威说明仍是 SKILL.md 执行流程。

用法(最少参数):
    python3 scripts/run_pipeline.py --collect <采集目录> --questions <题库.csv> \
        --case <Case.json> --lexicon <词表.json> --out-dir <输出目录> \
        [--brands "目标,配置1,配置2,配置3,开放1" --target <目标品牌>] \
        [--regions MY,SG] [--dry-run]

不带 --brands/--target 时跳过情感环节(报告情感板块为 pending)。
翻译环节按 translation-batches 目录是否就绪自动接入,缺席不阻塞主链。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent.parent
CRAWL_INTEGRITY = SKILLS / "geo-presales-crawl-integrity" / "scripts" / "audit_crawl_integrity.py"
JUDGE = SKILLS / "geo-presales-sentiment-judge" / "scripts" / "sentiment_sentences.py"


class Pause(Exception):
    """流水线在暂停点停下:message 告诉使用者补什么。"""


def run(cmd: list, dry: bool, label: str) -> None:
    printable = " ".join(str(c) for c in cmd)
    print(f"→ [{label}] {printable}")
    if dry:
        return
    result = subprocess.run([str(c) for c in cmd])
    if result.returncode != 0:
        raise SystemExit(f"[{label}] 失败(退出码 {result.returncode}),流水线停止:{printable}")


def stage_crawl_integrity(args, out: Path) -> None:
    audit = out / "crawl-integrity.json"
    if audit.exists():
        print(f"✓ [0 采集校验] 已存在 {audit}(重跑请先删除)")
        return
    cmd = [sys.executable, CRAWL_INTEGRITY, "--collect-dir", args.collect,
           "--target", args.target or "-", "--out", audit]
    printable = " ".join(str(c) for c in cmd)
    print(f"→ [0 采集校验] {printable}")
    if args.dry_run:
        return
    result = subprocess.run([str(c) for c in cmd])
    if result.returncode == 2:
        raise SystemExit(
            f"[0 采集校验] 有阻断缺陷(退出码 2),按 geo-presales-crawl-integrity 的缺陷分派"
            f"修采集或显式降级口径后再继续。报告:{audit}")
    if result.returncode == 1:
        print(f"⚠ [0 采集校验] 有警告(退出码 1),按缺陷目录补齐口径后再采信指标。报告:{audit}")


def stage_lexicon(args) -> None:
    if args.lexicon.exists():
        print(f"✓ [1 品牌词表] {args.lexicon}")
        return
    candidates = args.out_dir / "brand-candidates.csv"
    run([sys.executable, HERE / "mine_brand_lexicon.py",
         "--collect-dir", args.collect, "--out", candidates], args.dry_run, "1 词表挖掘")
    raise Pause(
        f"词表 {args.lexicon} 不存在。已挖掘候选到 {candidates},"
        f"请人工过一遍冻结成 brands[].name/aliases/type 结构后重跑。"
        f"机器无法可靠区分品牌名与品类词,这一步不能自动化。")


def stage_build(args, out: Path) -> None:
    report = out / "report-data.json"
    cmd = [sys.executable, HERE / "build_report_data.py",
           "--collect", args.collect, "--questions", args.questions,
           "--case", args.case, "--lexicon", args.lexicon,
           "--domain-cache", HERE.parent / "assets" / "domain-categories.json",
           "--out", report]
    if args.regions:
        cmd += ["--regions", args.regions]
    run(cmd, args.dry_run, "2 数据生成")


def stage_sentiment(args, out: Path) -> None:
    if not (args.brands and args.target):
        print("○ [3 情感] 未提供 --brands/--target,跳过(报告情感板块为 pending)")
        return
    units = out / "sentiment-units.json"
    batches = out / "sentiment-batches"
    claims_dir = out / "sentiment-claims"
    judged = claims_dir / "judged-sentences.json"
    brand_list = [b.strip() for b in args.brands.split(",") if b.strip()]

    if not units.exists():
        run([sys.executable, JUDGE, "extract", "--bank", args.questions,
             "--crawl-dir", args.collect, "--lexicon", args.lexicon,
             "--output", units], args.dry_run, "3a 情感抽取")
    else:
        print(f"✓ [3a 情感抽取] {units}")

    missing_labels = [b for b in brand_list if not (batches / f"{b}-labels.json").exists()]
    if missing_labels:
        run([sys.executable, HERE / "prep_sentiment_handoff.py", "split",
             "--units", units, "--brands", args.brands, "--out-dir", batches],
            args.dry_run, "3b 判读拆批")
        raise Pause(
            f"缺判读标签:{', '.join(missing_labels)}。批次视图已在 {batches}/<品牌>.json,"
            f"请按 geo-presales-sentiment-judge 的判读规则逐句语义判读,"
            f"写 {batches}/<品牌>-labels.json(全局 idx,格式 {{\"positive\":[...],\"negative\":[...]}}),"
            f"拿不准的记入 {batches}/review-queue.md 交 Suda 裁决。禁止关键词自动打标。")

    run([sys.executable, HERE / "prep_sentiment_handoff.py", "assemble",
         "--units", units, "--labels-dir", batches, "--brands", args.brands,
         "--out", judged], args.dry_run, "3c 判读回装")

    missing_claims = [b for b in brand_list if not (claims_dir / f"{b}-claims.json").exists()]
    if missing_claims:
        raise Pause(
            f"缺观点归纳:{', '.join(missing_claims)}。请读 {judged} 按品牌把判读句子"
            f"归纳成 4–8 组,写 {claims_dir}/<品牌>-claims.json"
            f"(格式见 references/sentiment-handoff-contract.md,indices 指向同方向数组下标,须互斥且穷尽)。")

    run([sys.executable, HERE / "prep_sentiment_handoff.py", "check-claims",
         "--judged", judged, "--claims-dir", claims_dir], args.dry_run, "3d 归纳校验")

    run([sys.executable, HERE / "attach_sentiment.py",
         "--report", out / "report-data.json", "--units", units,
         "--labels-dir", batches, "--brands", args.brands, "--target", args.target,
         "--out", out / "report-data.json"], args.dry_run, "3e 情感接入")


def stage_translations(args, out: Path) -> None:
    batches = out / "translation-batches"
    if not batches.exists():
        print(f"○ [4 译文] {batches} 不存在,跳过(抽屉只显示原文)。需要译文时先跑"
              f" export_translations.py 再分批翻译,详见 SKILL.md 第 6 步")
        return
    pending = [p.name for p in sorted(batches.glob("*.json"))
               if not p.name.endswith("-zh.json") and not (batches / f"{p.stem}-zh.json").exists()]
    if pending:
        raise Pause(
            f"译文批次未齐:{len(pending)} 个批次缺 <批次>-zh.json(如 {pending[:3]})。"
            f"翻译完补齐后重跑;确需部分交付时手动跑 attach_translations.py --allow-partial。")
    run([sys.executable, HERE / "attach_translations.py",
         "--report", out / "report-data.json", "--batches", batches,
         "--out", out / "report-data.json"], args.dry_run, "4 译文回填")


def stage_verify_render(args, out: Path) -> None:
    run([sys.executable, HERE / "verify_report_data.py",
         "--report", out / "report-data.json", "--collect", args.collect],
        args.dry_run, "5 独立校验")
    html = out / f"{args.brand_name or 'report'}-售前诊断报告.html"
    run([sys.executable, HERE / "render_report.py",
         "--data", out / "report-data.json", "--out", html], args.dry_run, "6 渲染")
    print(f"完成:{html}\n最后一步是人工/代理浏览器验证:逐个切国家/平台/主题,确认各模块有数、无空白、无变形。")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--collect", type=Path, required=True)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--lexicon", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--brands", help="展示品牌(含目标),与词表标准名一致;缺省跳过情感环节")
    parser.add_argument("--target", help="目标品牌标准名")
    parser.add_argument("--regions", help="逗号分隔区域,透传给 build_report_data")
    parser.add_argument("--brand-name", help="输出 HTML 文件名用的品牌名,缺省 report")
    parser.add_argument("--dry-run", action="store_true", help="只打印步骤计划,不执行")
    args = parser.parse_args()

    for path, label in ((args.collect, "采集目录"), (args.questions, "题库"), (args.case, "Case")):
        if not path.exists():
            raise SystemExit(f"{label}不存在:{path}")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    try:
        stage_crawl_integrity(args, args.out_dir)
        stage_lexicon(args)
        stage_build(args, args.out_dir)
        stage_sentiment(args, args.out_dir)
        stage_translations(args, args.out_dir)
        stage_verify_render(args, args.out_dir)
    except Pause as pause:
        print(f"\n⏸ 暂停点:{pause}\n补齐后重跑同一命令即可续跑。")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
