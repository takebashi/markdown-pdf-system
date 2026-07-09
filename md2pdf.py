#!/usr/bin/env python
from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    HRFlowable,
    Image,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)


FONT_BODY = "JPBody"
FONT_BODY_BOLD = "JPBody-Bold"
FONT_SERIF = "JPSerif"
FONT_CODE = "Courier"


@dataclass(frozen=True)
class Theme:
    name: str
    accent: colors.Color
    accent_dark: colors.Color
    text: colors.Color
    muted: colors.Color
    line: colors.Color
    soft_bg: colors.Color
    code_bg: colors.Color
    quote_bg: colors.Color
    table_header_bg: colors.Color
    table_stripe_bg: colors.Color


THEMES = {
    "business": Theme(
        name="business",
        accent=colors.HexColor("#2563eb"),
        accent_dark=colors.HexColor("#1e3a8a"),
        text=colors.HexColor("#111827"),
        muted=colors.HexColor("#6b7280"),
        line=colors.HexColor("#d1d5db"),
        soft_bg=colors.HexColor("#eff6ff"),
        code_bg=colors.HexColor("#f8fafc"),
        quote_bg=colors.HexColor("#f0f9ff"),
        table_header_bg=colors.HexColor("#1f2937"),
        table_stripe_bg=colors.HexColor("#f9fafb"),
    ),
    "editorial": Theme(
        name="editorial",
        accent=colors.HexColor("#0f766e"),
        accent_dark=colors.HexColor("#134e4a"),
        text=colors.HexColor("#18181b"),
        muted=colors.HexColor("#71717a"),
        line=colors.HexColor("#d4d4d8"),
        soft_bg=colors.HexColor("#ecfdf5"),
        code_bg=colors.HexColor("#fafafa"),
        quote_bg=colors.HexColor("#f0fdfa"),
        table_header_bg=colors.HexColor("#27272a"),
        table_stripe_bg=colors.HexColor("#fafafa"),
    ),
}


@dataclass
class Block:
    kind: str
    text: str = ""
    level: int = 0
    language: str = ""
    ordered: bool = False
    items: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    alt: str = ""
    target: str = ""


class AccentBlock(Flowable):
    def __init__(self, title: str, subtitle: str, meta_line: str, theme: Theme):
        super().__init__()
        self.title = title
        self.subtitle = subtitle
        self.meta_line = meta_line
        self.theme = theme
        self.width = 0
        self.height = 54 * mm

    def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
        self.width = avail_width
        return avail_width, self.height

    def draw(self) -> None:
        c = self.canv
        c.saveState()
        c.setFillColor(self.theme.soft_bg)
        c.roundRect(0, 0, self.width, self.height, 5 * mm, stroke=0, fill=1)
        c.setFillColor(self.theme.accent)
        c.rect(0, 0, 4.5 * mm, self.height, stroke=0, fill=1)

        c.setFillColor(self.theme.accent_dark)
        c.setFont(FONT_BODY, 19)
        title_lines = split_for_canvas(self.title, 34)
        y = self.height - 17 * mm
        for line in title_lines[:2]:
            c.drawString(10 * mm, y, line)
            y -= 8 * mm

        if self.subtitle:
            c.setFillColor(self.theme.text)
            c.setFont(FONT_BODY, 9.5)
            for line in split_for_canvas(self.subtitle, 58)[:2]:
                c.drawString(10 * mm, y - 2 * mm, line)
                y -= 5.5 * mm

        c.setFillColor(self.theme.muted)
        c.setFont(FONT_BODY, 8)
        c.drawString(10 * mm, 8 * mm, self.meta_line)
        c.restoreState()


class DesignedDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str, title: str, theme: Theme):
        self.report_title = title
        self.theme = theme
        super().__init__(
            filename,
            pagesize=A4,
            leftMargin=19 * mm,
            rightMargin=19 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
            title=title,
            author="Markdown to PDF",
        )
        frame = Frame(
            self.leftMargin,
            self.bottomMargin + 7 * mm,
            self.width,
            self.height - 9 * mm,
            id="normal",
            showBoundary=0,
        )
        self.addPageTemplates(
            [
                PageTemplate(
                    id="document",
                    frames=[frame],
                    onPage=self._draw_page_chrome,
                )
            ]
        )

    def _draw_page_chrome(self, canvas, doc) -> None:
        canvas.saveState()
        page_w, page_h = A4
        canvas.setStrokeColor(self.theme.line)
        canvas.setLineWidth(0.5)
        canvas.line(self.leftMargin, 13 * mm, page_w - self.rightMargin, 13 * mm)

        canvas.setStrokeColor(self.theme.accent)
        canvas.setLineWidth(1.4)
        canvas.line(self.leftMargin, page_h - 13 * mm, self.leftMargin + 32 * mm, page_h - 13 * mm)

        canvas.setFillColor(self.theme.muted)
        canvas.setFont(FONT_BODY, 7.5)
        footer_title = trim_for_canvas(self.report_title, 42)
        canvas.drawString(self.leftMargin, 8.5 * mm, footer_title)
        canvas.drawRightString(page_w - self.rightMargin, 8.5 * mm, f"{doc.page}")
        canvas.restoreState()


def register_fonts() -> None:
    global FONT_BODY, FONT_BODY_BOLD, FONT_SERIF, FONT_CODE

    body_regular = first_existing_path(
        [
            r"C:\Windows\Fonts\BIZ-UDGothicR.ttc",
            r"C:\Windows\Fonts\NotoSansJP-VF.ttf",
            r"C:\Windows\Fonts\meiryo.ttc",
            r"C:\Windows\Fonts\YuGothR.ttc",
        ]
    )
    body_bold = first_existing_path(
        [
            r"C:\Windows\Fonts\BIZ-UDGothicB.ttc",
            r"C:\Windows\Fonts\meiryob.ttc",
            r"C:\Windows\Fonts\YuGothB.ttc",
            r"C:\Windows\Fonts\NotoSansJP-VF.ttf",
        ]
    )
    serif_regular = first_existing_path(
        [
            r"C:\Windows\Fonts\BIZ-UDMinchoM.ttc",
            r"C:\Windows\Fonts\NotoSerifJP-VF.ttf",
            r"C:\Windows\Fonts\yumin.ttf",
        ]
    )
    code_regular = first_existing_path(
        [
            r"C:\Windows\Fonts\consola.ttf",
            r"C:\Windows\Fonts\CascadiaMono.ttf",
        ]
    )

    if body_regular:
        pdfmetrics.registerFont(TTFont(FONT_BODY, str(body_regular)))
        pdfmetrics.registerFont(TTFont(FONT_BODY_BOLD, str(body_bold or body_regular)))
        pdfmetrics.registerFontFamily(
            FONT_BODY,
            normal=FONT_BODY,
            bold=FONT_BODY_BOLD,
            italic=FONT_BODY,
            boldItalic=FONT_BODY_BOLD,
        )
    else:
        FONT_BODY = "HeiseiKakuGo-W5"
        FONT_BODY_BOLD = "HeiseiKakuGo-W5"
        pdfmetrics.registerFont(UnicodeCIDFont(FONT_BODY))

    if serif_regular:
        pdfmetrics.registerFont(TTFont(FONT_SERIF, str(serif_regular)))
    else:
        FONT_SERIF = "HeiseiMin-W3"
        try:
            pdfmetrics.registerFont(UnicodeCIDFont(FONT_SERIF))
        except Exception:
            pass

    if code_regular:
        FONT_CODE = "CodeMono"
        pdfmetrics.registerFont(TTFont(FONT_CODE, str(code_regular)))


def first_existing_path(candidates: list[str]) -> Path | None:
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return path
    return None


def split_for_canvas(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks = []
    current = ""
    for char in text:
        current += char
        if len(current) >= max_chars:
            chunks.append(current)
            current = ""
    if current:
        chunks.append(current)
    return chunks


def trim_for_canvas(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def parse_front_matter(markdown: str) -> tuple[dict[str, str], list[str]]:
    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, lines

    meta: dict[str, str] = {}
    end_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break
        if ":" in lines[index]:
            key, value = lines[index].split(":", 1)
            meta[key.strip().lower()] = value.strip().strip('"')

    if end_index is None:
        return {}, lines
    return meta, lines[end_index + 1 :]


def parse_markdown(markdown: str) -> tuple[dict[str, str], list[Block]]:
    meta, lines = parse_front_matter(markdown)
    blocks: list[Block] = []
    paragraph: list[str] = []
    index = 0

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            blocks.append(Block(kind="paragraph", text=" ".join(part.strip() for part in paragraph)))
            paragraph = []

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            index += 1
            continue

        fence = re.match(r"^```(\w+)?\s*$", stripped)
        if fence:
            flush_paragraph()
            language = fence.group(1) or ""
            code_lines: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            blocks.append(Block(kind="code", text="\n".join(code_lines), language=language))
            continue

        heading = re.match(r"^(#{1,4})\s+(.+?)\s*$", stripped)
        if heading:
            flush_paragraph()
            blocks.append(Block(kind="heading", level=len(heading.group(1)), text=heading.group(2).strip()))
            index += 1
            continue

        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", stripped):
            flush_paragraph()
            blocks.append(Block(kind="hr"))
            index += 1
            continue

        image = re.match(r"^!\[(.*?)\]\((.*?)\)\s*$", stripped)
        if image:
            flush_paragraph()
            blocks.append(Block(kind="image", alt=image.group(1), target=image.group(2)))
            index += 1
            continue

        if is_table_start(lines, index):
            flush_paragraph()
            rows = [split_table_row(lines[index])]
            index += 2
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                rows.append(split_table_row(lines[index]))
                index += 1
            blocks.append(Block(kind="table", rows=rows))
            continue

        if stripped.startswith(">"):
            flush_paragraph()
            quote_lines: list[str] = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote_lines.append(lines[index].strip().lstrip(">").strip())
                index += 1
            blocks.append(Block(kind="quote", text=" ".join(quote_lines)))
            continue

        list_match = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.+)$", line)
        if list_match:
            flush_paragraph()
            ordered = bool(re.match(r"\d+\.", list_match.group(2)))
            items: list[str] = []
            while index < len(lines):
                item_match = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.+)$", lines[index])
                if not item_match:
                    break
                marker_ordered = bool(re.match(r"\d+\.", item_match.group(2)))
                if marker_ordered != ordered:
                    break
                items.append(item_match.group(3).strip())
                index += 1
            blocks.append(Block(kind="list", ordered=ordered, items=items))
            continue

        paragraph.append(line)
        index += 1

    flush_paragraph()
    return meta, blocks


def is_table_start(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    if "|" not in lines[index]:
        return False
    separator = lines[index + 1].strip()
    if "|" not in separator:
        return False
    cells = [cell.strip() for cell in separator.strip("|").split("|")]
    return bool(cells) and all(re.match(r"^:?-{3,}:?$", cell) for cell in cells)


def split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def infer_title(meta: dict[str, str], blocks: Iterable[Block], fallback: str) -> str:
    if meta.get("title"):
        return meta["title"]
    for block in blocks:
        if block.kind == "heading" and block.level == 1:
            return strip_markdown_inline(block.text)
    return fallback


def strip_markdown_inline(text: str) -> str:
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text


def inline_markup(text: str, theme: Theme) -> str:
    escaped = html.escape(text)
    code_color = color_to_hex(theme.accent_dark)
    link_color = color_to_hex(theme.accent)

    escaped = re.sub(
        r"`([^`]+)`",
        lambda m: f'<font name="{FONT_CODE}" color="{code_color}">{m.group(1)}</font>',
        escaped,
    )
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", escaped)
    escaped = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'<a href="{m.group(2)}" color="{link_color}">{m.group(1)}</a>',
        escaped,
    )
    return escaped


def color_to_hex(color: colors.Color) -> str:
    return colors.toColor(color).hexval()


def make_styles(theme: Theme) -> dict[str, ParagraphStyle]:
    base = ParagraphStyle(
        "Base",
        fontName=FONT_BODY,
        fontSize=9.8,
        leading=16,
        textColor=theme.text,
        spaceAfter=4,
        alignment=TA_LEFT,
        wordWrap="CJK",
    )
    return {
        "body": base,
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base,
            fontSize=10,
            leading=15,
            textColor=theme.muted,
        ),
        "h1": ParagraphStyle(
            "Heading1",
            parent=base,
            fontSize=18,
            leading=25,
            textColor=theme.accent_dark,
            spaceBefore=12,
            spaceAfter=8,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "Heading2",
            parent=base,
            fontSize=14,
            leading=20,
            textColor=theme.accent_dark,
            spaceBefore=10,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "Heading3",
            parent=base,
            fontSize=11.5,
            leading=17,
            textColor=theme.text,
            spaceBefore=7,
            spaceAfter=3,
            keepWithNext=True,
        ),
        "h4": ParagraphStyle(
            "Heading4",
            parent=base,
            fontSize=10.2,
            leading=15,
            textColor=theme.muted,
            spaceBefore=6,
            spaceAfter=2,
            keepWithNext=True,
        ),
        "quote": ParagraphStyle(
            "Quote",
            parent=base,
            leftIndent=7 * mm,
            rightIndent=3 * mm,
            fontSize=9.2,
            leading=15,
            textColor=theme.accent_dark,
        ),
        "code": ParagraphStyle(
            "Code",
            parent=base,
            fontName=FONT_CODE,
            fontSize=7.8,
            leading=10.5,
            textColor=colors.HexColor("#111827"),
        ),
        "code_cjk": ParagraphStyle(
            "CodeCJK",
            parent=base,
            fontName=FONT_BODY,
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#111827"),
        ),
        "cell": ParagraphStyle(
            "Cell",
            parent=base,
            fontSize=8.4,
            leading=12,
            spaceAfter=0,
        ),
        "cell_header": ParagraphStyle(
            "CellHeader",
            parent=base,
            fontSize=8.4,
            leading=12,
            textColor=colors.white,
            spaceAfter=0,
        ),
        "image_caption": ParagraphStyle(
            "ImageCaption",
            parent=base,
            fontSize=8,
            leading=11,
            alignment=TA_CENTER,
            textColor=theme.muted,
        ),
        "list_item": ParagraphStyle(
            "ListItem",
            parent=base,
            leftIndent=11 * mm,
            firstLineIndent=0,
            bulletIndent=4 * mm,
            spaceAfter=1.5,
        ),
    }


def build_story(
    blocks: list[Block],
    meta: dict[str, str],
    input_path: Path,
    title: str,
    theme: Theme,
    include_cover: bool,
) -> list:
    styles = make_styles(theme)
    story: list = []
    subtitle = meta.get("subtitle", "")
    author = meta.get("author", "")
    published = meta.get("date", date.today().isoformat())
    meta_parts = [part for part in (author, published, f"theme: {theme.name}") if part]
    first_title_skipped = False

    if include_cover:
        story.append(AccentBlock(title, subtitle, " / ".join(meta_parts), theme))
        story.append(Spacer(1, 9 * mm))

    for block in blocks:
        if (
            include_cover
            and not first_title_skipped
            and block.kind == "heading"
            and block.level == 1
            and strip_markdown_inline(block.text) == title
        ):
            first_title_skipped = True
            continue

        if block.kind == "heading":
            level = min(max(block.level, 1), 4)
            story.append(Paragraph(inline_markup(block.text, theme), styles[f"h{level}"]))
            if level == 1:
                story.append(
                    HRFlowable(
                        width="100%",
                        thickness=0.8,
                        color=theme.line,
                        spaceBefore=0,
                        spaceAfter=5,
                    )
                )
            continue

        if block.kind == "paragraph":
            story.append(Paragraph(inline_markup(block.text, theme), styles["body"]))
            story.append(Spacer(1, 2.4 * mm))
            continue

        if block.kind == "quote":
            quote = Paragraph(inline_markup(block.text, theme), styles["quote"])
            story.append(
                Table(
                    [[quote]],
                    colWidths=["100%"],
                    style=[
                        ("BACKGROUND", (0, 0), (-1, -1), theme.quote_bg),
                        ("BOX", (0, 0), (-1, -1), 0.4, theme.line),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6 * mm),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                        ("TOPPADDING", (0, 0), (-1, -1), 3.5 * mm),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5 * mm),
                    ],
                )
            )
            story.append(Spacer(1, 4 * mm))
            continue

        if block.kind == "list":
            for number, item in enumerate(block.items, start=1):
                bullet = f"{number}." if block.ordered else "-"
                story.append(
                    Paragraph(
                        inline_markup(item, theme),
                        styles["list_item"],
                        bulletText=bullet,
                    )
                )
            story.append(Spacer(1, 3.5 * mm))
            continue

        if block.kind == "code":
            code_style = styles["code"] if is_ascii(block.text) else styles["code_cjk"]
            code = Preformatted(block.text or " ", code_style, maxLineLength=88)
            caption = f"code: {block.language}" if block.language else "code"
            story.append(Paragraph(html.escape(caption), styles["image_caption"]))
            story.append(
                Table(
                    [[code]],
                    colWidths=["100%"],
                    style=[
                        ("BACKGROUND", (0, 0), (-1, -1), theme.code_bg),
                        ("BOX", (0, 0), (-1, -1), 0.35, theme.line),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                        ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
                    ],
                )
            )
            story.append(Spacer(1, 4 * mm))
            continue

        if block.kind == "table":
            story.append(make_table(block.rows, styles, theme))
            story.append(Spacer(1, 5 * mm))
            continue

        if block.kind == "image":
            story.extend(make_image_flowables(block, input_path, styles, theme))
            story.append(Spacer(1, 4 * mm))
            continue

        if block.kind == "hr":
            story.append(HRFlowable(width="100%", thickness=0.7, color=theme.line, spaceBefore=5, spaceAfter=7))

    if not story:
        story.append(Paragraph("No content.", styles["body"]))
    return story


def make_table(rows: list[list[str]], styles: dict[str, ParagraphStyle], theme: Theme) -> Table:
    col_count = max(len(row) for row in rows)
    normalized = [row + [""] * (col_count - len(row)) for row in rows]
    data = []
    for row_index, row in enumerate(normalized):
        style = styles["cell_header"] if row_index == 0 else styles["cell"]
        data.append([Paragraph(inline_markup(cell, theme), style) for cell in row])

    table = Table(data, colWidths=[None] * col_count, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), theme.table_header_bg),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, theme.table_stripe_bg]),
                ("GRID", (0, 0), (-1, -1), 0.35, theme.line),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3.2 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3.2 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 2.3 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.3 * mm),
            ]
        )
    )
    return table


def make_image_flowables(
    block: Block,
    input_path: Path,
    styles: dict[str, ParagraphStyle],
    theme: Theme,
) -> list:
    target = block.target.strip()
    image_path = Path(target)
    if not image_path.is_absolute():
        image_path = input_path.parent / image_path

    if not image_path.exists():
        warning = f"Image not found: {target}"
        return [Paragraph(inline_markup(warning, theme), styles["quote"])]

    image = Image(str(image_path))
    max_width = A4[0] - 38 * mm
    scale = min(max_width / image.imageWidth, 1.0)
    image.drawWidth = image.imageWidth * scale
    image.drawHeight = image.imageHeight * scale
    flowables = [image]
    if block.alt:
        flowables.append(Spacer(1, 1.5 * mm))
        flowables.append(Paragraph(inline_markup(block.alt, theme), styles["image_caption"]))
    return flowables


def is_ascii(text: str) -> bool:
    try:
        text.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def render_pdf(
    input_path: Path,
    output_path: Path,
    theme_name: str,
    include_cover: bool,
) -> str:
    register_fonts()
    theme = THEMES[theme_name]
    markdown = input_path.read_text(encoding="utf-8")
    meta, blocks = parse_markdown(markdown)
    title = infer_title(meta, blocks, input_path.stem)
    story = build_story(blocks, meta, input_path, title, theme, include_cover)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = DesignedDocTemplate(str(output_path), title=title, theme=theme)
    doc.build(story)
    return title


def render_preview(pdf_path: Path, preview_dir: Path) -> list[Path]:
    pdftoppm = find_pdftoppm()
    if not pdftoppm:
        return []
    preview_dir.mkdir(parents=True, exist_ok=True)
    prefix = preview_dir / pdf_path.stem
    result = subprocess.run(
        [pdftoppm, "-png", "-r", "144", str(pdf_path), str(prefix)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"pdftoppm failed: {detail}")
    return sorted(preview_dir.glob(f"{pdf_path.stem}-*.png"))


def find_pdftoppm() -> str | None:
    found = shutil.which("pdftoppm")
    candidates: list[Path] = []
    if found:
        found_path = Path(found)
        if found_path.suffix.lower() == ".exe":
            candidates.append(found_path)
        candidates.extend(
            [
                found_path.parent / ".." / "native" / "poppler" / "Library" / "bin" / "pdftoppm.exe",
                found_path.parent / ".." / "Library" / "bin" / "pdftoppm.exe",
            ]
        )
        candidates.append(found_path)

    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.exists():
            return str(resolved)
    return found


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a Markdown file into a designed, human-readable PDF.",
    )
    parser.add_argument("input", type=Path, help="Input Markdown file encoded as UTF-8.")
    parser.add_argument("output", type=Path, help="Output PDF path.")
    parser.add_argument(
        "--theme",
        choices=sorted(THEMES),
        default="business",
        help="Design theme to apply.",
    )
    parser.add_argument(
        "--no-cover",
        action="store_true",
        help="Skip the designed opening title block.",
    )
    parser.add_argument(
        "--preview-dir",
        type=Path,
        default=None,
        help="Optional directory for PNG page previews rendered with pdftoppm.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if not args.input.exists():
        parser.error(f"Input file not found: {args.input}")

    try:
        title = render_pdf(
            input_path=args.input,
            output_path=args.output,
            theme_name=args.theme,
            include_cover=not args.no_cover,
        )
        print(f"Created PDF: {args.output}")
        print(f"Title: {title}")
        if args.preview_dir:
            previews = render_preview(args.output, args.preview_dir)
            if previews:
                print("Preview PNGs:")
                for preview in previews:
                    print(f"  {preview}")
            else:
                print("Preview skipped: pdftoppm was not found.")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
