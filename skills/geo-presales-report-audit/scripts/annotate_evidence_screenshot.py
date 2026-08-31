#!/usr/bin/env python3
"""Add deterministic evidence annotations to a report screenshot."""

from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any, Iterable


RED = (225, 32, 38, 255)
WHITE = (255, 255, 255, 255)
DARK = (25, 28, 36, 255)
MUTED = (210, 214, 225, 255)


def parse_points(raw: str, label: str) -> tuple[int, int, int, int]:
    try:
        values = tuple(int(part.strip()) for part in raw.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{label} 坐标必须是整数：{raw}") from exc
    if len(values) != 4:
        raise argparse.ArgumentTypeError(f"{label} 必须包含四个坐标：{raw}")
    return values


def load_pillow() -> tuple[Any, Any, Any]:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:  # pragma: no cover - depends on local environment
        raise SystemExit("缺少 Pillow。请先安装 Pillow，再运行截图标注脚本。") from exc
    return Image, ImageDraw, ImageFont


def find_font(image_font: Any, size: int, explicit: str | None = None) -> Any:
    candidates = [
        explicit,
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return image_font.truetype(candidate, size=size)
    return image_font.load_default()


def wrapped_lines(
    draw: Any,
    text: str,
    font: Any,
    max_width: int,
) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        current = ""
        for char in paragraph:
            candidate = current + char
            width = draw.textbbox((0, 0), candidate, font=font)[2]
            if current and width > max_width:
                lines.append(current)
                current = char
            else:
                current = candidate
        lines.append(current)
    return lines


def draw_arrow(
    draw: Any,
    points: tuple[int, int, int, int],
    offset_y: int,
    width: int,
) -> None:
    x1, y1, x2, y2 = points
    y1 += offset_y
    y2 += offset_y
    draw.line((x1, y1, x2, y2), fill=RED, width=width)
    angle = math.atan2(y2 - y1, x2 - x1)
    head = max(14, width * 4)
    spread = math.pi / 7
    left = (x2 - head * math.cos(angle - spread), y2 - head * math.sin(angle - spread))
    right = (x2 - head * math.cos(angle + spread), y2 - head * math.sin(angle + spread))
    draw.polygon([(x2, y2), left, right], fill=RED)


def check_bounds(
    entries: Iterable[tuple[int, int, int, int]],
    width: int,
    height: int,
    label: str,
) -> None:
    for entry in entries:
        x1, y1, x2, y2 = entry
        if not (0 <= x1 <= width and 0 <= x2 <= width and 0 <= y1 <= height and 0 <= y2 <= height):
            raise SystemExit(f"{label} 坐标超出原图范围 {width}x{height}：{entry}")


def main() -> None:
    parser = argparse.ArgumentParser(description="给售前报告截图叠加问题说明、红框、箭头和编号。")
    parser.add_argument("--input", required=True, help="原始截图路径")
    parser.add_argument("--output", required=True, help="标注后 PNG/JPEG 路径")
    parser.add_argument("--title", required=True, help="以‘问题：’开头的人话说明")
    parser.add_argument("--subtitle", default="", help="Task 与记录号，例如 Task 123 · #4567")
    parser.add_argument("--note", action="append", default=[], help="补充证据说明，可重复")
    parser.add_argument("--box", action="append", default=[], help="红框 x1,y1,x2,y2，可重复")
    parser.add_argument("--arrow", action="append", default=[], help="箭头起点和终点 x1,y1,x2,y2，可重复")
    parser.add_argument("--font", help="可选字体文件路径")
    parser.add_argument("--line-width", type=int, default=5, help="红框和箭头线宽")
    args = parser.parse_args()

    Image, ImageDraw, ImageFont = load_pillow()

    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    if not input_path.is_file():
        raise SystemExit(f"找不到原始截图：{input_path}")
    if input_path == output_path:
        raise SystemExit("输出路径不能覆盖原始截图，请保留未标注原图。")
    if not args.title.strip().startswith("问题："):
        raise SystemExit("--title 必须以‘问题：’开头，并直接写明问题。")

    boxes = [parse_points(raw, "红框") for raw in args.box]
    arrows = [parse_points(raw, "箭头") for raw in args.arrow]
    if not boxes and not arrows:
        raise SystemExit("至少提供一个 --box 或 --arrow，指出原始证据。")

    source = Image.open(input_path).convert("RGBA")
    check_bounds(boxes, source.width, source.height, "红框")
    check_bounds(arrows, source.width, source.height, "箭头")

    margin = max(28, source.width // 40)
    title_font = find_font(ImageFont, max(24, min(42, source.width // 28)), args.font)
    body_font = find_font(ImageFont, max(18, min(30, source.width // 38)), args.font)
    scratch = Image.new("RGBA", (source.width, 10), DARK)
    scratch_draw = ImageDraw.Draw(scratch)
    title_lines = wrapped_lines(scratch_draw, args.title.strip(), title_font, source.width - 2 * margin)
    detail_parts = [part.strip() for part in [args.subtitle, *args.note] if part.strip()]
    detail_lines: list[str] = []
    for part in detail_parts:
        detail_lines.extend(wrapped_lines(scratch_draw, part, body_font, source.width - 2 * margin))

    title_height = max(34, title_font.getbbox("问题")[3] - title_font.getbbox("问题")[1] + 10)
    body_height = max(27, body_font.getbbox("证据")[3] - body_font.getbbox("证据")[1] + 8)
    banner_height = margin * 2 + title_height * len(title_lines) + body_height * len(detail_lines)

    canvas = Image.new("RGBA", (source.width, banner_height + source.height), WHITE)
    canvas.paste(Image.new("RGBA", (source.width, banner_height), DARK), (0, 0))
    canvas.paste(source, (0, banner_height))
    draw = ImageDraw.Draw(canvas)

    y = margin
    for line in title_lines:
        draw.text((margin, y), line, font=title_font, fill=WHITE)
        y += title_height
    for line in detail_lines:
        draw.text((margin, y), line, font=body_font, fill=MUTED)
        y += body_height

    for index, (x1, y1, x2, y2) in enumerate(boxes, start=1):
        top = min(y1, y2) + banner_height
        bottom = max(y1, y2) + banner_height
        left = min(x1, x2)
        right = max(x1, x2)
        draw.rounded_rectangle((left, top, right, bottom), radius=8, outline=RED, width=args.line_width)
        badge_radius = max(15, args.line_width * 3)
        badge_center = (left + badge_radius, top + badge_radius)
        draw.ellipse(
            (
                badge_center[0] - badge_radius,
                badge_center[1] - badge_radius,
                badge_center[0] + badge_radius,
                badge_center[1] + badge_radius,
            ),
            fill=RED,
        )
        label = str(index)
        label_box = draw.textbbox((0, 0), label, font=body_font)
        draw.text(
            (
                badge_center[0] - (label_box[2] - label_box[0]) / 2,
                badge_center[1] - (label_box[3] - label_box[1]) / 2 - 1,
            ),
            label,
            font=body_font,
            fill=WHITE,
        )

    for arrow in arrows:
        draw_arrow(draw, arrow, banner_height, args.line_width)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix.lower() in {".jpg", ".jpeg"}:
        canvas.convert("RGB").save(output_path, quality=95)
    else:
        canvas.save(output_path, format="PNG")
    print(f"已生成标注截图：{output_path}")


if __name__ == "__main__":
    main()
