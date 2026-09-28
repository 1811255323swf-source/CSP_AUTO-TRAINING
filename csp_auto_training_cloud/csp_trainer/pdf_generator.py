from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from csp_trainer.models import Question


PAGE_WIDTH = 595.28
PAGE_HEIGHT = 841.89
MARGIN_X = 48.0
MARGIN_TOP = 54.0
MARGIN_BOTTOM = 54.0
FONT_NAME = "STSong-Light"
FONT_ENCODING = "UniGB-UCS2-H"


@dataclass(frozen=True)
class TextItem:
    x: float
    y: float
    text: str
    size: float


class SimpleChinesePdf:
    """Small text-only PDF writer using the built-in STSong CJK font."""

    def __init__(self) -> None:
        self.pages: list[list[TextItem]] = []
        self.current_page: list[TextItem] = []
        self.y = PAGE_HEIGHT - MARGIN_TOP
        self.new_page()

    def new_page(self) -> None:
        if self.current_page:
            self.pages.append(self.current_page)
        self.current_page = []
        self.y = PAGE_HEIGHT - MARGIN_TOP

    def finish(self) -> None:
        if self.current_page:
            self.pages.append(self.current_page)
            self.current_page = []

    def add_spacer(self, height: float) -> None:
        if self.y - height < MARGIN_BOTTOM:
            self.new_page()
        self.y -= height

    def add_paragraph(
        self,
        text: str,
        *,
        size: float = 10.5,
        leading: float = 16.0,
        space_before: float = 0.0,
        space_after: float = 5.0,
        indent: float = 0.0,
    ) -> None:
        if space_before:
            self.add_spacer(space_before)

        max_width = PAGE_WIDTH - 2 * MARGIN_X - indent
        source_lines = text.splitlines() or [""]
        for source_line in source_lines:
            for line in wrap_text(source_line, max_width, size):
                self.add_line(line, size=size, leading=leading, indent=indent)

        if space_after:
            self.add_spacer(space_after)

    def add_centered(
        self,
        text: str,
        *,
        size: float,
        leading: float,
        space_after: float = 0.0,
    ) -> None:
        self._ensure_space(leading)
        width = estimate_text_width(text, size)
        x = max(MARGIN_X, (PAGE_WIDTH - width) / 2)
        self.current_page.append(TextItem(x=x, y=self.y, text=text, size=size))
        self.y -= leading
        if space_after:
            self.add_spacer(space_after)

    def add_line(
        self,
        text: str,
        *,
        size: float = 10.5,
        leading: float = 16.0,
        indent: float = 0.0,
    ) -> None:
        self._ensure_space(leading)
        self.current_page.append(
            TextItem(x=MARGIN_X + indent, y=self.y, text=text, size=size)
        )
        self.y -= leading

    def _ensure_space(self, height: float) -> None:
        if self.y - height < MARGIN_BOTTOM:
            self.new_page()

    def write(self, output_path: Path, title: str) -> None:
        self.finish()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(build_pdf_bytes(self.pages, title))


def estimate_text_width(text: str, size: float) -> float:
    width = 0.0
    for char in text:
        code = ord(char)
        if char == "\t":
            width += size * 2.2
        elif code < 128:
            width += size * 0.55
        else:
            width += size
    return width


def wrap_text(text: str, max_width: float, size: float) -> list[str]:
    if not text:
        return [""]

    lines: list[str] = []
    current = ""
    current_width = 0.0

    for char in text:
        char_width = estimate_text_width(char, size)
        if current and current_width + char_width > max_width:
            lines.append(current.rstrip())
            current = char.lstrip()
            current_width = estimate_text_width(current, size)
        else:
            current += char
            current_width += char_width

    if current:
        lines.append(current.rstrip())
    return lines or [""]


def _hex_text(text: str) -> str:
    return text.encode("utf-16-be").hex().upper()


def _content_stream(items: list[TextItem], page_number: int) -> bytes:
    commands: list[str] = ["BT"]
    for item in items:
        commands.append(f"/F1 {item.size:.2f} Tf")
        commands.append(f"1 0 0 1 {item.x:.2f} {item.y:.2f} Tm")
        commands.append(f"<{_hex_text(item.text)}> Tj")

    footer = f"第 {page_number} 页"
    footer_size = 8.5
    footer_x = (PAGE_WIDTH - estimate_text_width(footer, footer_size)) / 2
    commands.append(f"/F1 {footer_size:.2f} Tf")
    commands.append(f"1 0 0 1 {footer_x:.2f} 28.00 Tm")
    commands.append(f"<{_hex_text(footer)}> Tj")
    commands.append("ET")
    return ("\n".join(commands) + "\n").encode("ascii")


def _pdf_object(body: str | bytes) -> bytes:
    if isinstance(body, str):
        return body.encode("ascii")
    return body


def build_pdf_bytes(pages: list[list[TextItem]], title: str) -> bytes:
    objects: dict[int, bytes] = {
        1: _pdf_object("<< /Type /Catalog /Pages 2 0 R >>"),
        3: _pdf_object(
            f"<< /Type /Font /Subtype /Type0 /BaseFont /{FONT_NAME} "
            f"/Encoding /{FONT_ENCODING} /DescendantFonts [4 0 R] >>"
        ),
        4: _pdf_object(
            f"<< /Type /Font /Subtype /CIDFontType0 /BaseFont /{FONT_NAME} "
            "/CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 2 >> "
            "/FontDescriptor 5 0 R /DW 1000 >>"
        ),
        5: _pdf_object(
            f"<< /Type /FontDescriptor /FontName /{FONT_NAME} /Flags 6 "
            "/FontBBox [-25 -254 1000 880] /ItalicAngle 0 /Ascent 880 "
            "/Descent -120 /CapHeight 880 /StemV 80 >>"
        ),
    }

    kids: list[str] = []
    next_id = 6
    for page_number, page_items in enumerate(pages, start=1):
        stream = _content_stream(page_items, page_number)
        content_id = next_id
        page_id = next_id + 1
        next_id += 2

        objects[content_id] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"endstream"
        )
        objects[page_id] = _pdf_object(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH:.2f} {PAGE_HEIGHT:.2f}] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
        )
        kids.append(f"{page_id} 0 R")

    objects[2] = _pdf_object(
        f"<< /Type /Pages /Count {len(pages)} /Kids [{' '.join(kids)}] >>"
    )

    info_id = next_id
    objects[info_id] = (
        b"<< /Title <" + title.encode("utf-16-be").hex().upper().encode("ascii") + b"> "
        b"/Producer (CSP Auto Training) >>"
    )

    max_id = info_id
    pdf = bytearray(b"%PDF-1.4\n%\xE2\xE3\xCF\xD3\n")
    offsets = [0] * (max_id + 1)

    for object_id in range(1, max_id + 1):
        offsets[object_id] = len(pdf)
        pdf.extend(f"{object_id} 0 obj\n".encode("ascii"))
        pdf.extend(objects[object_id])
        pdf.extend(b"\nendobj\n")

    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {max_id + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {max_id + 1} /Root 1 0 R /Info {info_id} 0 R >>\n"
        f"startxref\n{xref_start}\n%%EOF\n".encode("ascii")
    )
    return bytes(pdf)


def _add_section(pdf: SimpleChinesePdf, title: str) -> None:
    pdf.add_paragraph(title, size=12.0, leading=18.0, space_before=8.0, space_after=2.0)


def _add_question(pdf: SimpleChinesePdf, question: Question) -> None:
    pdf.add_paragraph(
        f"第 {question.slot} 题：{question.title}",
        size=14.0,
        leading=21.0,
        space_before=4.0,
        space_after=4.0,
    )
    tags = "、".join(question.tags) if question.tags else "无"
    pdf.add_paragraph(
        f"难度：{question.difficulty}    标签：{tags}",
        size=9.8,
        leading=14.5,
        space_after=0.0,
    )
    pdf.add_paragraph(
        f"时间限制：{question.time_limit}    内存限制：{question.memory_limit}",
        size=9.8,
        leading=14.5,
        space_after=5.0,
    )

    _add_section(pdf, "题目描述")
    pdf.add_paragraph(question.statement)
    _add_section(pdf, "输入格式")
    pdf.add_paragraph(question.input_format)
    _add_section(pdf, "输出格式")
    pdf.add_paragraph(question.output_format)

    for index, sample in enumerate(question.samples, start=1):
        _add_section(pdf, f"样例 {index} 输入")
        pdf.add_paragraph(sample.input, size=9.5, leading=14.0, indent=14.0)
        _add_section(pdf, f"样例 {index} 输出")
        pdf.add_paragraph(sample.output, size=9.5, leading=14.0, indent=14.0)
        if sample.explanation:
            _add_section(pdf, "样例说明")
            pdf.add_paragraph(sample.explanation)

    if question.hints:
        _add_section(pdf, "训练提示")
        for hint in question.hints:
            pdf.add_paragraph(f"- {hint}", space_after=1.0)


def generate_daily_pdf(
    questions: list[Question],
    output_path: Path,
    training_date: date,
    title: str,
) -> Path:
    if len(questions) != 3:
        raise ValueError("Daily training PDF expects exactly three questions.")

    pdf = SimpleChinesePdf()
    pdf.add_centered(title, size=20.0, leading=27.0, space_after=2.0)
    pdf.add_centered(
        f"训练日期：{training_date.isoformat()} | 语言：C++",
        size=10.5,
        leading=16.0,
        space_after=10.0,
    )
    pdf.add_paragraph(
        "建议节奏：第 1 题 15-20 分钟，第 2 题 25-35 分钟，第 3 题 40-60 分钟。"
        "先独立思考，再看提示。",
        size=10.5,
        leading=16.0,
        space_after=10.0,
    )

    for index, question in enumerate(questions, start=1):
        if index > 1:
            pdf.new_page()
        _add_question(pdf, question)

    pdf.write(output_path, f"{title} {training_date.isoformat()}")
    return output_path

