"""Build the complete Voltiq project documentation PDF.

Run from the repository root:
    .\\.venv\\Scripts\\python.exe docs/build_project_pdf.py

The generator uses ReportLab's Platypus layout engine, a two-level table of
contents, custom headers and footers, generated diagrams and real UI captures.
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Flowable,
    Frame,
    HRFlowable,
    Image as RLImage,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
)
from reportlab.platypus.tableofcontents import TableOfContents

BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_DIR = BASE_DIR / "docs"
ASSETS_DIR = DOCS_DIR / "_generated"
SCREENSHOT_DIR = ASSETS_DIR / "screenshots"
DIAGRAM_DIR = ASSETS_DIR / "diagrams"
OUTPUT_PDF = DOCS_DIR / "Voltiq-Project-Documentation.pdf"

PAGE_W, PAGE_H = A4
MARGIN_X = 46
CONTENT_WIDTH = PAGE_W - 2 * MARGIN_X

# Brand palette
NAVY = HexColor("#0B1220")
NAVY_2 = HexColor("#15223A")
BLUE = HexColor("#2563EB")
BLUE_DARK = HexColor("#1D4ED8")
BLUE_SOFT = HexColor("#E8F0FF")
AMBER = HexColor("#F59E0B")
AMBER_SOFT = HexColor("#FFF5E0")
GREEN = HexColor("#16A34A")
GREEN_SOFT = HexColor("#E9F9EF")
RED = HexColor("#DC2626")
RED_SOFT = HexColor("#FDECEC")
SLATE = HexColor("#475569")
MUTED = HexColor("#64748B")
INK = HexColor("#0F172A")
LINE = HexColor("#E2E8F0")
CANVAS = HexColor("#F5F7FB")
WHITE = HexColor("#FFFFFF")
CODE_BG = HexColor("#0F1A2E")
CODE_TEXT = HexColor("#DCE6F5")

# Register fonts from the local Windows installation. These are used only by
# the documentation generator and keep the PDF selectable and searchable.
FONT_DIR = Path("C:/Windows/Fonts")
for name, filename in {
    "Voltiq": "segoeui.ttf",
    "Voltiq-Bold": "segoeuib.ttf",
    "Voltiq-Semi": "segoeuisl.ttf",
    "Voltiq-Italic": "segoeuii.ttf",
    "Voltiq-Code": "consola.ttf",
    "Voltiq-Code-Bold": "consolab.ttf",
}.items():
    pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / filename)))


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
def style(name: str, **kwargs) -> ParagraphStyle:
    kwargs.setdefault("fontName", "Voltiq")
    return ParagraphStyle(name, **kwargs)


S = {
    "Body": style(
        "Body",
        fontSize=9.4,
        leading=14.2,
        textColor=HexColor("#334155"),
        spaceAfter=5,
        splitLongWords=1,
    ),
    "BodySmall": style(
        "BodySmall",
        fontSize=8.4,
        leading=12.4,
        textColor=HexColor("#475569"),
        spaceAfter=3,
        splitLongWords=1,
    ),
    "Bullet": style(
        "Bullet",
        fontSize=9.4,
        leading=13.8,
        textColor=HexColor("#334155"),
        leftIndent=13,
        bulletIndent=2,
        spaceAfter=2.5,
    ),
    "H1": style(
        "H1",
        fontName="Voltiq-Bold",
        fontSize=24,
        leading=28,
        textColor=NAVY,
        spaceBefore=0,
        spaceAfter=3,
        keepWithNext=1,
    ),
    "H2": style(
        "H2",
        fontName="Voltiq-Bold",
        fontSize=13.4,
        leading=17,
        textColor=BLUE_DARK,
        spaceBefore=13,
        spaceAfter=4,
        keepWithNext=1,
    ),
    "H3": style(
        "H3",
        fontName="Voltiq-Bold",
        fontSize=10.4,
        leading=13.5,
        textColor=NAVY,
        spaceBefore=9,
        spaceAfter=3,
        keepWithNext=1,
    ),
    "Lead": style(
        "Lead",
        fontSize=11.5,
        leading=17,
        textColor=SLATE,
        spaceBefore=2,
        spaceAfter=13,
    ),
    "Caption": style(
        "Caption",
        fontName="Voltiq-Italic",
        fontSize=7.7,
        leading=10.5,
        textColor=MUTED,
        alignment=TA_CENTER,
        spaceBefore=4,
        spaceAfter=7,
    ),
    "TableText": style(
        "TableText",
        fontSize=8.0,
        leading=11.0,
        textColor=HexColor("#334155"),
    ),
    "TableTextSmall": style(
        "TableTextSmall",
        fontSize=7.4,
        leading=10.1,
        textColor=HexColor("#475569"),
    ),
    "TableTextTiny": style(
        "TableTextTiny",
        fontSize=6.7,
        leading=9.1,
        textColor=HexColor("#475569"),
    ),
    "TableHead": style(
        "TableHead",
        fontName="Voltiq-Bold",
        fontSize=7.8,
        leading=10.5,
        textColor=WHITE,
    ),
    "TableMono": style(
        "TableMono",
        fontName="Voltiq-Code",
        fontSize=7.3,
        leading=10.0,
        textColor=HexColor("#334155"),
    ),
    "TableMonoTiny": style(
        "TableMonoTiny",
        fontName="Voltiq-Code",
        fontSize=6.5,
        leading=8.9,
        textColor=HexColor("#334155"),
    ),
    "TableHeadTiny": style(
        "TableHeadTiny",
        fontName="Voltiq-Bold",
        fontSize=7.1,
        leading=9.2,
        textColor=WHITE,
    ),
    "CalloutTitle": style(
        "CalloutTitle",
        fontName="Voltiq-Bold",
        fontSize=9.2,
        leading=12,
        textColor=NAVY,
        spaceAfter=2,
    ),
    "CalloutText": style(
        "CalloutText",
        fontSize=8.6,
        leading=12.5,
        textColor=HexColor("#334155"),
    ),
    "Code": style(
        "Code",
        fontName="Voltiq-Code",
        fontSize=7.8,
        leading=10.8,
        textColor=CODE_TEXT,
        spaceBefore=0,
        spaceAfter=0,
    ),
    "TOCTitle": style(
        "TOCTitle",
        fontName="Voltiq-Bold",
        fontSize=28,
        leading=32,
        textColor=NAVY,
        spaceAfter=6,
    ),
    "TOCLead": style(
        "TOCLead",
        fontSize=10,
        leading=15,
        textColor=SLATE,
        spaceAfter=14,
    ),
    "Quote": style(
        "Quote",
        fontName="Voltiq-Italic",
        fontSize=10.5,
        leading=16,
        textColor=HexColor("#1E3A5F"),
        leftIndent=16,
        rightIndent=16,
        spaceBefore=8,
        spaceAfter=8,
    ),
}


# ---------------------------------------------------------------------------
# Flowable helpers
# ---------------------------------------------------------------------------
def p(text: str, style_name: str = "Body") -> Paragraph:
    return Paragraph(text, S[style_name])


def h2(text: str) -> Paragraph:
    return Paragraph(text, S["H2"])


def h3(text: str) -> Paragraph:
    return Paragraph(text, S["H3"])


def bullets(items: list[str]) -> list[Paragraph]:
    return [Paragraph(f"<bullet>&bull;</bullet> {item}", S["Bullet"]) for item in items]


def numbered(items: list[str]) -> list[Paragraph]:
    return [
        Paragraph(f"<bullet>{index}.</bullet> {item}", S["Bullet"]) for index, item in enumerate(items, 1)
    ]


def code_block(text: str, caption: str | None = None) -> list[Flowable]:
    body = Preformatted(text.strip("\n"), S["Code"])
    box = Table([[body]], colWidths=[CONTENT_WIDTH])
    box.setStyle(
        [
            ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ]
    )
    result: list[Flowable] = [Spacer(1, 3), box]
    if caption:
        result.append(p(caption, "Caption"))
    else:
        result.append(Spacer(1, 6))
    return result


def callout(title: str, text: str, kind: str = "info") -> list[Flowable]:
    palette = {
        "info": (BLUE, BLUE_SOFT),
        "warning": (AMBER, AMBER_SOFT),
        "success": (GREEN, GREEN_SOFT),
        "danger": (RED, RED_SOFT),
    }
    accent, background = palette.get(kind, palette["info"])
    content = [Paragraph(title, S["CalloutTitle"]), Paragraph(text, S["CalloutText"])]
    tbl = Table([["", content]], colWidths=[4, CONTENT_WIDTH - 4])
    tbl.setStyle(
        [
            ("BACKGROUND", (0, 0), (0, 0), accent),
            ("BACKGROUND", (1, 0), (1, 0), background),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (0, 0), 0),
            ("RIGHTPADDING", (0, 0), (0, 0), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING", (1, 0), (1, 0), 10),
            ("RIGHTPADDING", (1, 0), (1, 0), 10),
            ("TOPPADDING", (1, 0), (1, 0), 8),
            ("BOTTOMPADDING", (1, 0), (1, 0), 8),
            ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ]
    )
    return [KeepTogether([Spacer(1, 5), tbl, Spacer(1, 7)])]


def data_table(
    rows: list[list[str]],
    widths: list[float] | None = None,
    header: bool = True,
    small: bool = False,
    tiny: bool = False,
    dense: bool = False,
    mono_columns: set[int] | None = None,
) -> Table:
    """Create a clean, repeating-header table from plain text or markup."""
    mono_columns = mono_columns or set()
    body_style = S["TableTextTiny"] if tiny else (S["TableTextSmall"] if small else S["TableText"])
    head_style = S["TableHeadTiny"] if tiny else S["TableHead"]
    mono_style = S["TableMonoTiny"] if tiny else S["TableMono"]
    padding = 3.8 if dense else 5
    data: list[list[Flowable]] = []
    for row_index, row in enumerate(rows):
        rendered: list[Flowable] = []
        for column_index, cell in enumerate(row):
            if isinstance(cell, Flowable):
                rendered.append(cell)
                continue
            cell_style = head_style if (header and row_index == 0) else (
                mono_style if column_index in mono_columns else body_style
            )
            rendered.append(Paragraph(str(cell), cell_style))
        data.append(rendered)

    if widths is None:
        widths = [1] * len(rows[0])
    total = sum(widths)
    col_widths = [CONTENT_WIDTH * value / total for value in widths]
    tbl = Table(data, colWidths=col_widths, repeatRows=1 if header else 0, splitByRow=1)
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5.5),
        ("TOPPADDING", (0, 0), (-1, -1), padding),
        ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
    ]
    if header:
        commands += [
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, NAVY),
        ]
        for row_index in range(1, len(data)):
            if row_index % 2 == 0:
                commands.append(("BACKGROUND", (0, row_index), (-1, row_index), HexColor("#F8FAFC")))
    tbl.setStyle(commands)
    return tbl


def table_with_caption(
    rows: list[list[str]],
    caption: str | None = None,
    widths: list[float] | None = None,
    small: bool = False,
    tiny: bool = False,
    dense: bool = False,
    mono_columns: set[int] | None = None,
) -> list[Flowable]:
    result: list[Flowable] = [
        Spacer(1, 4),
        data_table(rows, widths, small=small, tiny=tiny, dense=dense, mono_columns=mono_columns),
    ]
    if caption:
        result.append(p(caption, "Caption"))
    else:
        result.append(Spacer(1, 7))
    return result


def framed_image(path: Path, width: float, caption: str | None = None) -> list[Flowable]:
    image = RLImage(str(path))
    ratio = image.imageHeight / image.imageWidth
    image.drawWidth = width
    image.drawHeight = width * ratio
    image.hAlign = "CENTER"
    frame = Table([[image]], colWidths=[width + 8])
    frame.setStyle(
        [
            ("BACKGROUND", (0, 0), (-1, -1), WHITE),
            ("BOX", (0, 0), (-1, -1), 0.6, LINE),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
    )
    result: list[Flowable] = [Spacer(1, 6), frame]
    if caption:
        result.append(p(caption, "Caption"))
    else:
        result.append(Spacer(1, 8))
    return result


def screenshot(filename: str, caption: str, width: float = CONTENT_WIDTH - 8) -> list[Flowable]:
    return framed_image(SCREENSHOT_DIR / filename, width, caption)


def diagram(filename: str, caption: str) -> list[Flowable]:
    path = DIAGRAM_DIR / filename
    image = RLImage(str(path))
    ratio = image.imageHeight / image.imageWidth
    image.drawWidth = CONTENT_WIDTH
    image.drawHeight = CONTENT_WIDTH * ratio
    image.hAlign = "CENTER"
    result: list[Flowable] = [Spacer(1, 6), image]
    if caption:
        result.append(p(caption, "Caption"))
    else:
        result.append(Spacer(1, 7))
    return result


def chapter(number: str, title: str, lead: str | None = None) -> list[Flowable]:
    items: list[Flowable] = [
        PageBreak(),
        Paragraph(f"{number}. {title}", S["H1"]),
        HRFlowable(width="100%", thickness=2, color=BLUE, spaceBefore=3, spaceAfter=9),
    ]
    if lead:
        items.append(Paragraph(lead, S["Lead"]))
    return items


def rule(space_before: float = 6, space_after: float = 6) -> HRFlowable:
    return HRFlowable(width="100%", thickness=0.6, color=LINE, spaceBefore=space_before, spaceAfter=space_after)


# ---------------------------------------------------------------------------
# Document template, cover, header and footer
# ---------------------------------------------------------------------------
class VoltiqDocTemplate(BaseDocTemplate):
    def __init__(self, filename: str, **kwargs):
        super().__init__(filename, **kwargs)
        self._outline_index = 0
        frame = Frame(
            MARGIN_X,
            46,
            CONTENT_WIDTH,
            PAGE_H - 46 - 62,
            id="body",
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
        )
        self.addPageTemplates([PageTemplate(id="body", frames=[frame], onPage=on_page)])

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph):
            name = flowable.style.name
            if name in ("H1", "H2"):
                level = 0 if name == "H1" else 1
                text = flowable.getPlainText()
                self.notify("TOCEntry", (level, text, self.page))
                key = f"section-{self._outline_index}"
                self._outline_index += 1
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(text, key, level=level, closed=False)


def draw_brand_mark(c: pdfcanvas.Canvas, x: float, y: float, size: float = 32):
    c.setFillColor(BLUE)
    c.roundRect(x, y, size, size, 7, fill=1, stroke=0)
    c.setFillColor(WHITE)
    path = c.beginPath()
    path.moveTo(x + size * 0.55, y + size * 0.82)
    path.lineTo(x + size * 0.28, y + size * 0.45)
    path.lineTo(x + size * 0.47, y + size * 0.45)
    path.lineTo(x + size * 0.38, y + size * 0.17)
    path.lineTo(x + size * 0.72, y + size * 0.57)
    path.lineTo(x + size * 0.52, y + size * 0.57)
    path.close()
    c.drawPath(path, fill=1, stroke=0)


def draw_cover(c: pdfcanvas.Canvas, doc):
    c.saveState()
    c.setFillColor(NAVY)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # Deep vertical gradient
    for index in range(72):
        ratio = index / 71
        red = 11 + int(7 * ratio)
        green = 18 + int(13 * ratio)
        blue = 32 + int(24 * ratio)
        c.setFillColorRGB(red / 255, green / 255, blue / 255)
        c.rect(0, PAGE_H - (index + 1) * (PAGE_H / 72), PAGE_W, PAGE_H / 72 + 1, fill=1, stroke=0)

    # Soft glows
    c.setFillColor(BLUE)
    c.setFillAlpha(0.16)
    c.circle(PAGE_W - 55, PAGE_H - 34, 180, fill=1, stroke=0)
    c.setFillColor(AMBER)
    c.setFillAlpha(0.09)
    c.circle(20, 180, 150, fill=1, stroke=0)
    c.setFillAlpha(1)

    # Technical grid
    c.setStrokeColor(HexColor("#31527A"))
    c.setLineWidth(0.25)
    c.setStrokeAlpha(0.22)
    for x in range(0, int(PAGE_W), 36):
        c.line(x, 0, x, PAGE_H)
    for y in range(0, int(PAGE_H), 36):
        c.line(0, y, PAGE_W, y)
    c.setStrokeAlpha(1)

    # Brand
    draw_brand_mark(c, 46, PAGE_H - 82, 32)
    c.setFillColor(WHITE)
    c.setFont("Voltiq-Bold", 23)
    c.drawString(88, PAGE_H - 76, "VOLTIQ")
    c.setFont("Voltiq", 7.6)
    c.setFillColor(HexColor("#9FB0C8"))
    c.drawString(89, PAGE_H - 92, "PREMIUM ELECTRONICS  /  NEPAL")
    c.drawRightString(PAGE_W - 46, PAGE_H - 74, "PROJECT MANUAL")
    c.drawRightString(PAGE_W - 46, PAGE_H - 88, "VERSION 1.0  /  NOVEMBER 2026")

    # Title
    c.setFillColor(WHITE)
    c.setFont("Voltiq-Bold", 45)
    c.drawString(46, PAGE_H - 194, "Project")
    c.drawString(46, PAGE_H - 246, "Documentation")
    c.setFillColor(HexColor("#AFC0D8"))
    c.setFont("Voltiq", 12.5)
    c.drawString(46, PAGE_H - 278, "How the complete Voltiq platform works")
    c.setFont("Voltiq", 9.2)
    c.setFillColor(HexColor("#B9C8DC"))
    c.drawString(
        46,
        PAGE_H - 298,
        "Architecture, features, data model, payments, operations and deployment.",
    )

    # Accent line
    c.setFillColor(BLUE)
    c.rect(46, PAGE_H - 322, 74, 4, fill=1, stroke=0)
    c.setFillColor(AMBER)
    c.rect(124, PAGE_H - 322, 18, 4, fill=1, stroke=0)

    # Pills
    pills = ["Django 5.2", "Django REST Framework", "PostgreSQL / SQLite", "eSewa + Khalti", "Vanilla JS"]
    x = 46
    y = PAGE_H - 364
    c.setFont("Voltiq-Semi", 7.5)
    for text in pills:
        width = c.stringWidth(text, "Voltiq-Semi", 7.5) + 20
        c.setFillColor(HexColor("#12233D"))
        c.setStrokeColor(HexColor("#2B4A72"))
        c.setLineWidth(0.5)
        c.roundRect(x, y, width, 21, 10.5, fill=1, stroke=1)
        c.setFillColor(HexColor("#C9D7EA"))
        c.drawString(x + 10, y + 7, text)
        x += width + 7

    # Screenshot frame
    screenshot_path = SCREENSHOT_DIR / "home-desktop.png"
    if screenshot_path.exists():
        shot_x, shot_y, shot_w = 46, 88, PAGE_W - 92
        shot_h = shot_w * 950 / 1440
        c.setFillColor(HexColor("#07101F"))
        c.roundRect(shot_x - 2, shot_y - 2, shot_w + 4, shot_h + 4, 8, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.roundRect(shot_x, shot_y, shot_w, shot_h, 6, fill=1, stroke=0)
        c.drawImage(
            str(screenshot_path),
            shot_x + 4,
            shot_y + 4,
            width=shot_w - 8,
            height=shot_h - 8,
            preserveAspectRatio=True,
            anchor="c",
            mask="auto",
        )
        c.setFillColor(HexColor("#9FB0C8"))
        c.setFont("Voltiq", 7.2)
        c.drawString(shot_x + 2, shot_y - 12, "Storefront home page  /  live demonstration build")

    # Footer
    c.setFillColor(HexColor("#7C8DA5"))
    c.setFont("Voltiq", 7.4)
    c.drawString(46, 34, "Voltiq Electronics  /  Internal project documentation")
    c.drawRightString(PAGE_W - 46, 34, "Version 1.0  /  November 2026")
    c.setFillColor(BLUE)
    c.rect(0, 0, PAGE_W, 4, fill=1, stroke=0)
    c.setFillColor(AMBER)
    c.rect(0, 0, 106, 4, fill=1, stroke=0)
    c.restoreState()


def on_page(c: pdfcanvas.Canvas, doc):
    if doc.page == 1:
        draw_cover(c, doc)
        return
    c.saveState()
    # Header
    c.setFillColor(NAVY)
    c.rect(MARGIN_X, PAGE_H - 34, 4, 9, fill=1, stroke=0)
    c.setFillColor(MUTED)
    c.setFont("Voltiq-Semi", 7.0)
    c.drawString(MARGIN_X + 10, PAGE_H - 33, "VOLTIQ  /  PROJECT DOCUMENTATION")
    c.drawRightString(PAGE_W - MARGIN_X, PAGE_H - 33, "Complete technical and operations manual")
    c.setStrokeColor(LINE)
    c.setLineWidth(0.5)
    c.line(MARGIN_X, PAGE_H - 42, PAGE_W - MARGIN_X, PAGE_H - 42)
    # Footer
    c.line(MARGIN_X, 34, PAGE_W - MARGIN_X, 34)
    c.setFillColor(MUTED)
    c.setFont("Voltiq", 7.0)
    c.drawString(MARGIN_X, 22, "Voltiq Electronics  /  Version 1.0  /  November 2026")
    c.setFillColor(NAVY)
    c.setFont("Voltiq-Bold", 7.4)
    c.drawRightString(PAGE_W - MARGIN_X, 22, f"{doc.page:02d}")
    c.setFillColor(BLUE)
    c.rect(MARGIN_X, 34, 28, 1.5, fill=1, stroke=0)
    c.restoreState()


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------
def build_story() -> list[Flowable]:
    story: list[Flowable] = [Spacer(1, 1), PageBreak()]

    # Table of contents is populated by multiBuild.
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            name="TOCHeading1",
            fontName="Voltiq-Bold",
            fontSize=10.2,
            leading=14.6,
            leftIndent=0,
            firstLineIndent=0,
            spaceBefore=4,
            textColor=NAVY,
        ),
        ParagraphStyle(
            name="TOCHeading2",
            fontName="Voltiq",
            fontSize=8.7,
            leading=12.2,
            leftIndent=18,
            firstLineIndent=0,
            spaceBefore=0,
            textColor=HexColor("#475569"),
        ),
    ]
    toc.dotsMinLevel = 0
    story += [
        Paragraph("Contents", S["TOCTitle"]),
        Paragraph(
            "A complete reference for developers, reviewers and store operators. "
            "Every chapter describes behaviour that is present in the Voltiq codebase.",
            S["TOCLead"],
        ),
        HRFlowable(width="100%", thickness=2, color=BLUE, spaceBefore=0, spaceAfter=10),
        toc,
    ]

    # ------------------------------------------------------------------
    # 1. Project overview
    # ------------------------------------------------------------------
    story += chapter(
        "1",
        "Project overview",
        "Voltiq is a production-oriented electronics storefront for Nepal. It combines a premium "
        "customer shopping experience with a separate staff and administrator dashboard, while "
        "sharing one Django backend, database and service layer.",
    )

    story.append(h2("1.1 What Voltiq is"))
    story.append(
        p(
            "Voltiq is a full-stack e-commerce application built with Python, Django 5.2 and Django REST "
            "Framework. It is not a prototype or a front-end mock-up: catalogue data, carts, checkout, "
            "stock movements, orders, payment attempts, reviews, notifications, coupons, customer "
            "accounts and staff analytics are all persisted in a relational database and exercised by "
            "automated tests. The customer-facing interface is rendered with Django templates and "
            "vanilla JavaScript, with no React, Angular or Vue build step."
        )
    )
    story.append(
        p(
            "The product is designed around the Nepali market. Prices are stored in NPR and displayed "
            "with the <b>Rs.</b> prefix. The payment layer supports <b>eSewa</b>, <b>Khalti</b>, "
            "<b>cash on delivery</b> and <b>bank transfer</b>. Delivery addresses use Nepal's seven "
            "provinces, and the seeded catalogue uses realistic local pricing, brands and product mix."
        )
    )
    story += callout(
        "One backend, two distinct interfaces",
        "Shoppers use the storefront at <b>/</b>. Staff and administrators use the separate dashboard at "
        "<b>/dashboard/</b>. Django's own administration site remains available at <b>/django-admin/</b> "
        "for low-level data maintenance. The interfaces have separate templates, styles, JavaScript, "
        "permissions and navigation, but they share the same models and business services.",
        "info",
    )

    story.append(h2("1.2 Who the system serves"))
    story += table_with_caption(
        [
            ["Audience", "What they can do", "Entry point"],
            [
                "Visitor",
                "Browse the catalogue, search and filter products, view product details, manage a guest cart, "
                "subscribe to the newsletter and contact support.",
                "/  |  /products/",
            ],
            [
                "Registered customer",
                "Verify an email address, save delivery addresses, place orders, pay online, track orders, "
                "download invoices, manage wishlists and write verified-purchase reviews.",
                "/accounts/account/",
            ],
            [
                "Staff member",
                "Manage catalogue, categories, brands, specifications, orders, inventory, reviews, coupons, "
                "newsletter subscribers and support messages; view KPIs and reports; export CSV files.",
                "/dashboard/",
            ],
            [
                "Administrator",
                "Everything staff can do, plus customer suspension and role changes, store settings, shipping "
                "method configuration and Django admin access.",
                "/dashboard/  |  /django-admin/",
            ],
            [
                "Developer / operator",
                "Run migrations, seed demo data, run the 151-test suite, collect static files, configure email "
                "and gateways, deploy behind HTTPS and operate backups.",
                "manage.py  |  docs/",
            ],
        ],
        "Table 1.1 - Users of the Voltiq platform.",
        widths=[1.0, 3.35, 1.45],
        small=True,
    )

    story.append(h2("1.3 What is implemented"))
    story += table_with_caption(
        [
            ["Area", "Delivered capability"],
            [
                "Storefront",
                "Editorial home page, category tiles, trending, bestsellers, latest arrivals, deals, "
                "recommendations, brand showcase, verified testimonials, newsletter, rich footer.",
            ],
            [
                "Catalogue",
                "Category hierarchy, brands, product images, product specifications, dynamic per-category "
                "spec fields, denormalised facets, stock labels, quick view and related products.",
            ],
            [
                "Search and filtering",
                "AJAX search suggestions, full listing search, category and brand filters, price range, RAM, "
                "storage, processor, GPU, rating, availability, discount, condition and eight sort modes.",
            ],
            [
                "Cart and wishlist",
                "Session-backed guest cart that merges on login, authenticated carts, quantity limits, "
                "stock checks, coupon validation and wishlist-to-cart movement.",
            ],
            [
                "Checkout and orders",
                "Five-step checkout, address selection, delivery method, review, payment, transactional order "
                "creation, stock deduction, order tracking, cancellation, reorder and PDF invoices.",
            ],
            [
                "Payments",
                "eSewa ePay v2, Khalti ePayment v2, cash on delivery and bank transfer. Server-side "
                "verification, immutable attempt logs, one-success constraint, refund recording and a "
                "development simulator.",
            ],
            [
                "Accounts",
                "Email-based authentication, registration, email verification, password reset, profile, "
                "avatar, addresses, notifications and payment history.",
            ],
            [
                "Reviews",
                "One review per customer per product, verified-purchase badge, rating breakdown, helpful "
                "counts, staff moderation, automatic product rating refresh.",
            ],
            [
                "Staff dashboard",
                "KPI cards, revenue charts, order status and payment charts, top products, category sales, "
                "recent orders, payment feed, low stock, pending reviews, CSV exports.",
            ],
            [
                "Operations",
                "Environment-driven settings, PostgreSQL-first configuration with SQLite fallback, media "
                "validation, cache invalidation signals, custom error pages, health endpoint and robots.txt.",
            ],
            [
                "Quality",
                "151 automated tests, shared test factories, Django system checks and a documented deployment "
                "path for Gunicorn or Waitress behind Nginx.",
            ],
        ],
        "Table 1.2 - Feature coverage at a glance.",
        widths=[1.05, 4.3],
        small=True,
    )

    story.append(h2("1.4 The demo environment"))
    story.append(
        p(
            "The repository can be started with a realistic demo catalogue. The seed command is "
            "idempotent and creates verified accounts, categories, brands, products, images, stock "
            "history, orders, payments, reviews, coupons, shipping methods, newsletter subscribers and "
            "support messages. The counts below describe the seeded local database used to prepare this "
            "manual."
        )
    )
    story += table_with_caption(
        [
            ["Metric", "Seeded value", "Metric", "Seeded value"],
            ["Categories", "21", "Products", "26"],
            ["Brands", "18", "Orders", "14"],
            ["Reviews", "17", "Coupons", "3"],
            ["Shipping methods", "3", "Customer accounts", "7"],
            ["Django templates", "84", "Automated tests", "151"],
        ],
        "Table 1.3 - Demo data and implementation totals.",
        widths=[1.4, 1, 1.4, 1],
        small=True,
    )
    story += table_with_caption(
        [
            ["Account", "Email", "Password", "Role"],
            ["Administrator", "admin@voltiq.com", "Admin@12345", "Admin"],
            ["Staff", "staff@voltiq.com", "Staff@12345", "Staff"],
            ["Customer", "aarav.sharma@example.com", "Customer@12345", "Customer"],
        ],
        "Table 1.4 - Seeded demonstration accounts. The accounts are email-verified; change or remove them before launch.",
        widths=[1.1, 2.1, 1.1, 0.8],
        small=True,
    )

    story.append(h2("1.5 Scope, assumptions and honest limits"))
    story += bullets(
        [
            "<b>Currency:</b> all monetary values are NPR. The code stores amounts as decimals and never "
            "uses floating point for order totals.",
            "<b>Payments:</b> the local environment uses the development simulator because gateway secrets are "
            "blank. Production eSewa and Khalti integrations perform server-side verification; the simulator "
            "never contacts a real gateway.",
            "<b>Card data:</b> Voltiq does not collect or store card numbers, CVVs or gateway secrets. Online "
            "payments happen on the provider's page; Voltiq stores references, amounts, statuses and audit "
            "payloads only.",
            "<b>Background jobs:</b> the project uses Django signals and <b>transaction.on_commit</b> for email "
            "and notifications. A production deployment that needs durable retries should add a task queue; "
            "the current synchronous behaviour is intentional and documented.",
            "<b>Database:</b> PostgreSQL is the production target. SQLite is the default local fallback so the "
            "project can be evaluated without a database server. PostgreSQL has not been exercised on this "
            "particular machine because <b>psql</b> is not installed, but the settings and setup guide are "
            "complete.",
            "<b>Hosting:</b> the deployment guide describes a single-server architecture. It does not claim a "
            "multi-region, auto-scaling or container-orchestrated deployment that is not in the repository.",
        ]
    )

    story += screenshot(
        "home-desktop.png",
        "Figure 1.1 - The Voltiq storefront home page, captured from the running seeded application.",
    )

    # ------------------------------------------------------------------
    # 2. Technology stack
    # ------------------------------------------------------------------
    story += chapter(
        "2",
        "Technology stack",
        "The stack is deliberately conventional: a server-rendered Django application, a relational "
        "database, small amounts of progressive JavaScript and direct integrations with Nepali payment "
        "providers.",
    )

    story.append(h2("2.1 Stack at a glance"))
    story += table_with_caption(
        [
            ["Layer", "Technology", "Responsibility"],
            ["Language", "Python 3.11+ (tested on 3.14.6)", "Application code, management commands and tests."],
            ["Web framework", "Django 5.2.19", "Routing, ORM, sessions, authentication, templates, admin and security."],
            ["API layer", "Django REST Framework 3.18.3", "Search suggestion endpoint and JSON serialisation."],
            ["Database", "PostgreSQL 14+ / psycopg 3.3", "Production relational store with row-level locking."],
            ["Local database", "SQLite", "Zero-install development fallback selected by DB_ENGINE=sqlite."],
            ["Images", "Pillow 13.0", "Image validation, thumbnails and generated fallback artwork."],
            ["PDF invoices", "ReportLab 5.1", "Server-side order invoice PDF generation."],
            ["Configuration", "python-decouple 3.8", ".env parsing with typed booleans, CSV lists and defaults."],
            ["Static serving", "WhiteNoise 6.12", "Compressed and manifested static files in production."],
            ["HTTP client", "requests 2.34", "eSewa status verification and Khalti initiate/lookup calls."],
            ["Rate limiting", "django-ratelimit 4.1", "Newsletter, verification resend and other abuse-sensitive actions."],
            ["Front end", "HTML5, CSS3, vanilla JS", "Responsive storefront, AJAX interactions, toasts and modals."],
            ["Charts", "Chart.js (CDN)", "Revenue, order, status and payment charts in the staff dashboard."],
            ["Version control", "Git", "Local repository with attributes for cross-platform line endings."],
        ],
        "Table 2.1 - Technologies used by Voltiq and what each one does.",
        widths=[1.0, 1.55, 3.6],
        small=True,
    )

    story.append(h2("2.2 Why this stack"))
    story += bullets(
        [
            "<b>Django fits the domain.</b> Catalogue, customers, orders and payments are relational data with "
            "strong integrity requirements. The ORM, migrations, transactions and row locks are used directly.",
            "<b>Server rendering keeps the critical path simple.</b> Checkout, payment callbacks and order pages "
            "work without a client-side bundle or hydration step. The page still feels interactive because "
            "search, cart and filters use small AJAX requests.",
            "<b>PostgreSQL is production-first.</b> The settings select PostgreSQL when <b>DB_ENGINE=postgres</b> "
            "and fall back to SQLite for a quick local start. Row locking is used in order and stock services.",
            "<b>No SPA framework is required.</b> The project honours the HTML/CSS/vanilla-JS constraint and "
            "avoids an unnecessary Node build pipeline.",
            "<b>Nepali gateways are first-class.</b> eSewa and Khalti are implemented as dedicated gateway classes "
            "behind a common interface, so checkout code does not contain provider-specific conditionals.",
        ]
    )

    story.append(h2("2.3 Browser-side design"))
    story.append(
        p(
            "The browser receives ordinary HTML documents. CSS is split into tokens, layout, components, page "
            "styles, account styles, dashboard styles and responsive rules. JavaScript is split into a "
            "storefront file and a dashboard file. The storefront script handles the mobile drawer, search "
            "suggestions, AJAX filtering and pagination, quick view, cart updates, wishlist toggles, toasts, "
            "quantity controls, countdowns and accessible focus states. The dashboard script initialises "
            "Chart.js charts, sidebar behaviour and confirmation dialogs."
        )
    )
    story += table_with_caption(
        [
            ["File", "Purpose"],
            ["static/css/tokens.css", "Design tokens, reset, typography, utilities, buttons and form controls."],
            ["static/css/layout.css", "Announcement bar, header, category navigation, drawer, footer and overlays."],
            ["static/css/components.css", "Hero, product cards, badges, ratings, carousels, testimonials and newsletter."],
            ["static/css/pages.css", "Home, catalogue, product detail, cart, checkout, order and policy pages."],
            ["static/css/account.css", "Customer account, wishlist, order history, tracking and review screens."],
            ["static/css/dashboard.css", "Staff dashboard shell, KPI cards, tables, forms and charts."],
            ["static/css/responsive.css", "Breakpoints from large desktop down to small mobile."],
            ["static/js/app.js", "Storefront interactions, AJAX, toasts, modals, search and cart behaviour."],
            ["static/js/dashboard.js", "Dashboard charts, sidebar and admin interactions."],
        ],
        "Table 2.2 - Front-end assets and their responsibilities.",
        widths=[1.25, 4.2],
        small=True,
    )

    story.append(h2("2.4 Server-side structure"))
    story.append(
        p(
            "The backend is divided into Django apps by business capability rather than by technical layer. "
            "Views stay thin where money or stock is involved: order creation, stock movement and payment "
            "verification live in service modules with explicit transactions. Signals handle cross-cutting "
            "cleanup such as cache invalidation, image-file deletion and initial profile creation. Forms "
            "carry validation and consistent widget styling."
        )
    )
    story += callout(
        "The important rule",
        "Anything that changes money, stock or payment state must run inside a database transaction and must "
        "be verified on the server. The browser is never trusted to declare an order paid, a price valid or a "
        "stock level available.",
        "warning",
    )

    # ------------------------------------------------------------------
    # 3. Architecture
    # ------------------------------------------------------------------
    story += chapter(
        "3",
        "System architecture",
        "Voltiq uses a layered Django architecture: request handling at the edge, business services in the "
        "middle, and relational data plus external gateways at the boundary.",
    )

    story.append(h2("3.1 High-level architecture"))
    story += diagram(
        "architecture.png",
        "Figure 3.1 - Client, application and data/external-service layers. The same backend serves both interfaces.",
    )
    story.append(
        p(
            "The browser talks to a single Django application. In development the Django development server "
            "also serves static files. In production, Nginx or another reverse proxy serves TLS and can serve "
            "<b>/static/</b> and <b>/media/</b> directly; WhiteNoise is configured to serve compressed static "
            "assets from the Django process when a separate static server is not used. The application talks "
            "to PostgreSQL or SQLite, the filesystem for media, the local-memory cache, an SMTP provider and "
            "the eSewa/Khalti APIs."
        )
    )

    story.append(h2("3.2 Request lifecycle"))
    story.extend(
        numbered(
            [
                "<b>Browser request.</b> A shopper or staff member requests an HTML page, a JSON endpoint or a "
                "payment callback. CSRF, session and authentication cookies travel with the request.",
                "<b>Security and session middleware.</b> Django applies security headers, session loading, CSRF "
                "protection, authentication and message handling. The suspended-user middleware signs out "
                "suspended accounts immediately.",
                "<b>URL resolution.</b> <b>config/urls.py</b> mounts the storefront, account, product, cart, "
                "wishlist, checkout, order, payment, review and dashboard namespaces.",
                "<b>View and permission check.</b> The view validates the HTTP method, loads the relevant objects "
                "and applies customer, staff or administrator permissions. AJAX requests are detected by "
                "<b>X-Requested-With</b> or a <b>partial=1</b> parameter.",
                "<b>Form validation.</b> Forms normalise and validate input. Checkout state is written to the "
                "session; cart mutations are validated against live stock and price data.",
                "<b>Service layer.</b> Order creation, stock adjustment, payment initiation, payment verification "
                "and cancellation run inside transactions and may use <b>select_for_update</b>.",
                "<b>ORM and database.</b> The ORM reads or writes normalised tables. Constraints enforce unique "
                "emails, SKUs, cart items, reviews and successful payments.",
                "<b>Template or JSON response.</b> HTML pages render with the storefront or dashboard shell. "
                "AJAX endpoints return JSON fragments or data. Payment callbacks redirect to a confirmation or "
                "failure page.",
                "<b>Post-commit work.</b> Order confirmation email, notifications, cache invalidation and file "
                "cleanup run through signals or <b>transaction.on_commit</b> after the transaction succeeds.",
            ]
        )
    )

    story.append(h2("3.3 Application boundaries"))
    story += table_with_caption(
        [
            ["App", "Responsibility", "Key models / services"],
            ["apps.core", "Home page, newsletter, contact, policies, health, robots, errors, settings, validators, test factories.", "NewsletterSubscription, ContactMessage, SiteSetting"],
            ["apps.accounts", "Custom user, profile, addresses, verification, notifications, account pages, permissions.", "User, CustomerProfile, Address, EmailVerificationToken, Notification"],
            ["apps.categories", "Category hierarchy and brands.", "Category, Brand"],
            ["apps.products", "Catalogue, images, dynamic specifications, search, filtering, suggestions.", "Product, ProductImage, SpecificationField, ProductSpecification"],
            ["apps.cart", "Guest and customer carts, quantity limits, coupons, stock-aware mutations.", "Cart, CartItem; cart services"],
            ["apps.wishlist", "Saved products, restock alerts, move-to-cart.", "Wishlist, WishlistItem"],
            ["apps.orders", "Checkout steps, order creation, status flow, cancellation, invoices, coupons and shipping.", "Order, OrderItem, Coupon, CouponUsage, ShippingMethod, OrderStatusHistory"],
            ["apps.payments", "Gateway abstraction, eSewa and Khalti, simulator, COD, bank transfer, verification and refunds.", "Payment, PaymentTransaction; gateway classes"],
            ["apps.inventory", "Locked stock adjustments, stock history and restock alerts.", "StockHistory; adjust_stock"],
            ["apps.reviews", "Verified-purchase reviews, rating aggregation and moderation.", "Review"],
            ["apps.dashboard", "Staff and administrator dashboard, analytics, CRUD actions and CSV exports.", "Uses the models above; no separate dashboard database"],
        ],
        "Table 3.1 - Django apps and their responsibilities.",
        widths=[1.1, 3.55, 2.25],
        small=True,
        mono_columns={0},
    )

    story.append(h2("3.4 Interface separation"))
    story += table_with_caption(
        [
            ["Surface", "URL prefix", "Template shell", "Navigation", "Permissions"],
            ["Storefront", "/  /products/  /cart/  /checkout/  /orders/", "templates/base.html", "Storefront header, category nav, cart and account menu", "Public; authenticated and verified gates for checkout"],
            ["Customer account", "/accounts/account/", "Storefront shell with account sidebar", "Account navigation", "Signed-in customer; suspended accounts are rejected"],
            ["Staff dashboard", "/dashboard/", "templates/dashboard/base.html", "Dashboard sidebar and top bar", "is_staff; administrator-only actions additionally require admin role"],
            ["Django admin", "/django-admin/", "Django admin", "Django model administration", "is_staff / superuser"],
        ],
        "Table 3.2 - Four surfaces, one database.",
        widths=[0.9, 2.0, 1.55, 1.6, 2.25],
        small=True,
    )

    story.append(h2("3.5 Cross-cutting behaviour"))
    story += bullets(
        [
            "<b>Cache invalidation.</b> Home-page data, navigation categories and site settings are cached. "
            "Product, image, specification, category and brand signals delete the relevant cache keys.",
            "<b>File cleanup.</b> Deleting a product image, category image, brand logo or user avatar also deletes "
            "the stored file through post-delete signals.",
            "<b>Profile creation.</b> A new user automatically receives a CustomerProfile row.",
            "<b>Login IP.</b> Successful logins record the last login IP on the user record.",
            "<b>Guest cart merge.</b> A guest cart is merged into the user's cart on login. The session key is "
            "captured before Django rotates it so the merge remains reliable.",
            "<b>Customer communication.</b> Order placement sends a confirmation email and an in-app notification; "
            "cancellation and restock events create notifications.",
            "<b>Audit trails.</b> Stock changes, order status changes and payment gateway interactions are recorded "
            "as append-only rows rather than overwriting history.",
        ]
    )

    story.append(h2("3.6 Failure handling"))
    story.append(
        p(
            "The architecture is deliberately resilient for a single-server deployment. If an email provider is "
            "down, order placement still succeeds because confirmation mail is sent with a failure-tolerant "
            "helper after the transaction commits. If a gateway initiation fails, the order remains available "
            "for a retry and the failed attempt is logged. If stock becomes unavailable between cart and "
            "checkout, order creation aborts atomically and the customer is returned to the cart with an "
            "explanation. Custom 400, 403, 404 and 500 pages keep failures consistent with the storefront "
            "design."
        )
    )

    # ------------------------------------------------------------------
    # 4. Project structure
    # ------------------------------------------------------------------
    story += chapter(
        "4",
        "Project structure",
        "A conventional Django repository with explicit app boundaries, a shared template tree, modular "
        "CSS, two JavaScript files and a small documentation set.",
    )

    story.append(h2("4.1 Repository tree"))
    story += code_block(
        r"""
ecommerce/
|-- manage.py
|-- requirements.txt
|-- README.md
|-- .env.example
|-- .gitignore / .gitattributes
|-- config/
|   |-- settings.py
|   |-- urls.py
|   |-- wsgi.py
|   `-- asgi.py
|-- apps/
|   |-- accounts/       custom user, addresses, verification, account pages
|   |-- cart/           guest + customer carts, cart services and merge signal
|   |-- categories/     category hierarchy and brands
|   |-- core/           home, policies, contact, settings, validators, test factories
|   |-- dashboard/      staff/admin pages, analytics and exports
|   |-- inventory/      stock history and locked stock adjustments
|   |-- orders/         checkout, orders, coupons, shipping, invoices
|   |-- payments/       gateway abstraction, eSewa, Khalti, simulator
|   |-- products/       catalogue, images, specifications and search
|   |-- reviews/        verified-purchase reviews and rating signals
|   `-- wishlist/       saved products, restock alerts and move-to-cart
|-- templates/
|   |-- base.html
|   |-- home/ accounts/ products/ cart/ checkout/ orders/ payments/
|   |-- reviews/ wishlist/ core/ errors/ emails/ dashboard/
|   `-- partials/
|-- static/
|   |-- css/            tokens, layout, components, pages, account, dashboard, responsive
|   |-- js/             app.js, dashboard.js
|   `-- images/         favicon
|-- docs/
|   |-- setup.md
|   |-- pgadmin.md
|   |-- deployment.md
|   |-- build_diagrams.py
|   |-- build_project_pdf.py
|   `-- Voltiq-Project-Documentation.pdf
|-- media/              uploaded and seeded product images (ignored)
|-- staticfiles/        collectstatic output (ignored)
|-- logs/               application log directory (ignored)
`-- db.sqlite3          local SQLite database (ignored)
""".strip(),
        "Code block 4.1 - Top-level repository layout.",
    )

    story.append(h2("4.2 What each app owns"))
    story += table_with_caption(
        [
            ["App", "Core files", "Notes"],
            ["accounts", "models.py, forms.py, views.py, urls.py, decorators.py, middleware.py, signals.py, utils.py", "Email is the login identifier; roles are customer, staff and admin."],
            ["products", "models.py, views.py, urls.py, signals.py", "Product facets, dynamic specifications and AJAX suggestions."],
            ["categories", "models.py, signals.py", "Self-referencing category tree and brand logos."],
            ["cart", "models.py, services.py, signals.py, views.py, urls.py", "Guest carts use a session key; cart mutations validate stock."],
            ["orders", "models.py, services.py, forms.py, views.py, checkout_urls.py, urls.py", "Checkout state machine, order snapshots, stock deduction."],
            ["payments", "models.py, services.py, views.py, gateways/, utils.py", "Payment attempts, verification, simulator, bank and COD."],
            ["inventory", "models.py, services.py", "Row-locked stock changes and an immutable StockHistory trail."],
            ["reviews", "models.py, forms.py, views.py, signals.py", "One review per product/user; rating fields refreshed on save/delete."],
            ["wishlist", "models.py, services.py, views.py", "Restock notifications and cart transfer."],
            ["dashboard", "views.py, forms.py, urls.py", "Staff and admin pages; no separate dashboard models."],
            ["core", "views.py, models.py, forms.py, context_processors.py, validators.py, testing.py", "Shared pages, settings, validation and test factories."],
        ],
        "Table 4.1 - Application ownership boundaries.",
        widths=[0.95, 3.2, 2.1],
        small=True,
        mono_columns={0, 1},
    )

    story.append(h2("4.3 Templates and partials"))
    story.append(
        p(
            "There are 84 HTML templates. The storefront uses <b>templates/base.html</b> with a shared header, "
            "category navigation, cart badge, account menu, notification panel, footer and toast container. The "
            "dashboard uses <b>templates/dashboard/base.html</b> with a completely separate sidebar and admin "
            "asset set. Reusable fragments live under <b>templates/partials/</b>, including product cards, "
            "pagination, empty states, form fields, rating stars and dashboard widgets. Email templates are "
            "plain text and HTML pairs."
        )
    )

    story.append(h2("4.4 Static assets"))
    story.append(
        p(
            "CSS is intentionally modular. <b>tokens.css</b> contains brand variables, resets, typography, "
            "buttons and form controls. <b>layout.css</b> owns the header, navigation and footer. "
            "<b>components.css</b> owns reusable cards and badges. Page-specific rules live in "
            "<b>pages.css</b>, <b>account.css</b> and <b>dashboard.css</b>. <b>responsive.css</b> contains all "
            "breakpoints so responsive changes can be reviewed in one place. There are no CSS frameworks and no "
            "build step."
        )
    )

    story.append(h2("4.5 Management commands"))
    story += table_with_caption(
        [
            ["Command", "Purpose"],
            ["python manage.py migrate", "Create or update the database schema."],
            ["python manage.py seed_store", "Create the complete demo catalogue, users, orders, reviews, coupons and content."],
            ["python manage.py seed_store --skip-images", "Seed quickly without downloading product images."],
            ["python manage.py test", "Run the full automated test suite."],
            ["python manage.py check", "Run Django system checks."],
            ["python manage.py collectstatic", "Build the static file tree for production."],
            ["python manage.py createsuperuser", "Create an additional Django superuser."],
        ],
        "Table 4.2 - Commands used most often.",
        widths=[2.0, 4.4],
        small=True,
        mono_columns={0},
    )

    story.append(h2("4.6 Documentation set"))
    story += bullets(
        [
            "<b>README.md</b> - product overview, quick start, demo accounts, payment notes and links to the guides.",
            "<b>docs/setup.md</b> - clean-machine setup with SQLite and PostgreSQL, seeding, email, payment simulation and troubleshooting.",
            "<b>docs/pgadmin.md</b> - creating the PostgreSQL database and user in pgAdmin 4, inspection queries, backups and restores.",
            "<b>docs/deployment.md</b> - production checklist, Gunicorn/Waitress, Nginx, HTTPS, cache, backups and go-live steps.",
            "<b>docs/Voltiq-Project-Documentation.pdf</b> - this complete manual.",
        ]
    )

    # ------------------------------------------------------------------
    # 5. Accounts and permissions
    # ------------------------------------------------------------------
    story += chapter(
        "5",
        "Accounts, authentication and permissions",
        "Voltiq uses a custom user model with email as the login identifier. The same account system "
        "supports customers, staff and administrators, with separate permissions for each surface.",
    )

    story.append(h2("5.1 The custom user model"))
    story.append(
        p(
            "The project sets <b>AUTH_USER_MODEL = accounts.User</b> and subclasses Django's "
            "<b>AbstractBaseUser</b> and <b>PermissionsMixin</b>. There is no username field. Email addresses "
            "are normalised to lowercase and are unique at the database level, so two accounts cannot share an "
            "address even if they differ only by case."
        )
    )
    story += table_with_caption(
        [
            ["Group", "Fields", "Purpose"],
            ["Identity", "email, first_name, last_name, phone, avatar", "Display, contact and account identity."],
            ["Access", "role, is_active, is_staff, is_superuser, is_suspended, suspension_reason", "Role-based access and administrative suspension."],
            ["Verification", "is_email_verified, email_verified_at", "Checkout gate and trust signal."],
            ["Preferences", "newsletter_opt_in, last_login_ip, date_joined", "Marketing consent and security context."],
            ["Related", "CustomerProfile, Address, Notification, orders, reviews, wishlist, cart", "One account owns the full customer history."],
        ],
        "Table 5.1 - The User model in groups.",
        widths=[0.85, 2.4, 3.3],
        small=True,
    )
    story.append(
        p(
            "A user's role is one of <b>customer</b>, <b>staff</b> or <b>admin</b>. Assigning staff or admin "
            "automatically sets <b>is_staff=True</b>, which is what Django's admin site checks. The "
            "<b>is_administrator</b> property also accepts a superuser, so a Django superuser created with "
            "<b>createsuperuser</b> can use administrator-only dashboard actions without changing the stored role."
        )
    )
    story += callout(
        "Email is the account key",
        "Login, registration, password reset, order lookup and staff customer search all use email. The "
        "manager lowercases the address before saving. This makes support conversations simpler, but it also "
        "means changing an email address is a sensitive account operation and should be reviewed carefully.",
        "info",
    )

    story.append(h2("5.2 Registration and email verification"))
    story += numbered(
        [
            "The visitor submits first name, last name, email, phone and a confirmed password. The registration "
            "form validates the duplicate email, password strength and Nepali-compatible phone format.",
            "The user row is created and a <b>CustomerProfile</b> is created automatically by a post-save signal.",
            "<b>issue_verification()</b> deletes any unused token for the account and creates a 32-byte URL-safe "
            "token that expires after three days.",
            "A multipart email with text and HTML alternatives is sent. With no SMTP host configured, Django's "
            "console email backend prints the message and verification link to the development terminal.",
            "The new user is logged in immediately but sees the verification-pending page. Checkout is blocked "
            "until <b>is_email_verified</b> is true.",
            "Opening a valid link marks the token used, sets <b>email_verified_at</b> and unlocks checkout. Used, "
            "invalid and expired links each produce a clear message.",
        ]
    )
    story += callout(
        "Development convenience",
        "When <b>DEBUG=True</b>, the verification-pending page shows the verification URL and a resend action "
        "repeats it in a message. This is deliberately disabled in production, where the link must arrive by "
        "email. Never enable DEBUG on a public host.",
        "warning",
    )

    story.append(h2("5.3 Login, logout and suspended accounts"))
    story.append(
        p(
            "Login uses the custom authentication form and accepts an optional safe <b>next</b> URL. Redirects "
            "are checked with Django's <b>url_has_allowed_host_and_scheme</b> to prevent open redirects. A "
            "successful login records the client IP on the user row through the <b>user_logged_in</b> signal."
        )
    )
    story.append(
        p(
            "<b>SuspendedUserMiddleware</b> runs after authentication on every request. If an authenticated "
            "account is suspended or inactive, the middleware logs it out, shows a suspension message and sends "
            "it to the login page. This is stronger than relying only on a decorator because a session that was "
            "created before suspension cannot continue browsing account pages."
        )
    )
    story.append(
        p(
            "Logout requires a POST request. The account menu submits a CSRF-protected form. This prevents "
            "accidental logout through a prefetched GET link and follows Django's recommended behaviour."
        )
    )

    story.append(h2("5.4 Password reset and password change"))
    story += bullets(
        [
            "Password reset uses Django's four-step views with Voltiq templates: request, sent confirmation, "
            "token confirmation and completion.",
            "<b>AccountPasswordResetView</b> always shows the same message whether or not the email exists. This "
            "avoids leaking which addresses have accounts.",
            "Reset emails are HTML and plain text, use the configured <b>DEFAULT_FROM_EMAIL</b> and include an "
            "expiring signed token generated by Django.",
            "Signed-in users change their password from the account area. The session hash is updated so the "
            "current browser stays logged in while other sessions are invalidated.",
            "All passwords pass Django's configured validators: minimum length 8, similarity, common password "
            "and numeric-only checks.",
        ]
    )

    story.append(h2("5.5 Customer account area"))
    story.append(
        p(
            "The account area lives under <b>/accounts/account/</b> and uses the storefront shell rather than the "
            "staff dashboard. It provides a dashboard summary, profile editing, password change, address book, "
            "notifications and payment history. The sidebar keeps navigation consistent across screens."
        )
    )
    story += table_with_caption(
        [
            ["Page", "URL", "What it shows"],
            ["Account dashboard", "/accounts/account/", "Recent orders, wishlist count, saved addresses, unread notifications and spend summary."],
            ["Profile", "/accounts/account/profile/", "Name, phone, avatar and marketing preferences."],
            ["Addresses", "/accounts/account/addresses/", "Create, edit, delete and set default delivery addresses."],
            ["Notifications", "/accounts/account/notifications/", "Order, payment, wishlist, account, promotion and system messages."],
            ["Payments", "/accounts/account/payments/", "Payment attempts, gateway references, statuses and linked orders."],
            ["Password", "/accounts/account/password/", "Current-password confirmation and a new password."],
        ],
        "Table 5.2 - Customer account screens.",
        widths=[1.25, 1.95, 3.35],
        small=True,
        mono_columns={1},
    )

    story.append(h2("5.6 Address book"))
    story.append(
        p(
            "Addresses are owned by a user and ordered by default status and recency. The model stores a label, "
            "full name, phone, alternate phone, street, landmark, city, district, province, postal code, country "
            "and address type. Province choices cover Koshi, Madhesh, Bagmati, Gandaki, Lumbini, Karnali and "
            "Sudurpaschim."
        )
    )
    story += bullets(
        [
            "Setting an address as default clears the previous default in the same user's address book.",
            "The first address created for a user becomes the default automatically.",
            "Deleting the default address does not automatically promote another address; the next address "
            "created or explicitly marked default becomes the new default.",
            "The checkout address step can create a new address inline, so a customer does not have to leave the "
            "checkout flow.",
        ]
    )

    story.append(h2("5.7 Roles and permissions"))
    story += table_with_caption(
        [
            ["Capability", "Visitor", "Customer", "Staff", "Administrator"],
            ["Browse catalogue and policies", "Yes", "Yes", "Yes", "Yes"],
            ["Use guest cart", "Yes", "Yes", "Yes", "Yes"],
            ["Checkout", "No", "Verified only", "Verified only", "Verified only"],
            ["View own orders and invoices", "No", "Yes", "Yes", "Yes"],
            ["Write a product review", "No", "Yes; badge if purchased", "Yes; badge if purchased", "Yes; badge if purchased"],
            ["Access /dashboard/", "No", "No", "Yes", "Yes"],
            ["Manage catalogue, orders, stock, reviews and coupons", "No", "No", "Yes", "Yes"],
            ["Change customer roles and suspend accounts", "No", "No", "No", "Yes"],
            ["Edit store settings and shipping methods", "No", "No", "No", "Yes"],
            ["Use /django-admin/", "No", "No", "If is_staff", "Yes"],
        ],
        "Table 5.3 - Access control matrix. Staff and admin actions are still checked on the server.",
        widths=[2.35, 0.7, 0.9, 0.7, 1.0],
        small=True,
    )
    story.append(
        p(
            "The <b>staff_required</b> decorator requires an active staff account and raises a 403 for a signed-in "
            "customer. The <b>admin_required</b> decorator additionally requires the administrator role or "
            "superuser status. Sensitive actions such as refunds, role changes, suspension and store settings are "
            "administrator-only. Decorators are applied to the view, not merely hidden in the navigation."
        )
    )

    story.append(h2("5.8 Notifications"))
    story.append(
        p(
            "Notifications are stored per user with a short title, message, optional URL, kind and read flag. "
            "The header shows an unread count. The kinds are order, payment, wishlist, account, promotion and "
            "system. Notifications are created for order placement, successful payment, cancellation, restock "
            "alerts and welcome messages. They are intentionally in-app records rather than a push service, so "
            "the customer sees the same event history after signing in on another device."
        )
    )
    story += screenshot(
        "customer-account.png",
        "Figure 5.1 - The authenticated customer account dashboard, with recent orders and account shortcuts.",
    )

    # ------------------------------------------------------------------
    # 6. Catalogue and discovery
    # ------------------------------------------------------------------
    story += chapter(
        "6",
        "Catalogue and product discovery",
        "The catalogue is a structured product database with a category tree, brands, images, dynamic "
        "specifications and denormalised facets that make filtering fast.",
    )

    story.append(h2("6.1 Catalogue hierarchy"))
    story.append(
        p(
            "Categories are self-referencing: a top-level category can contain children, and product list "
            "filtering includes the selected category plus its immediate active children. The home page shows "
            "featured top-level categories, while the storefront navigation builds a mega menu from the same "
            "tree. Categories carry an icon key, description, optional image, active flag, featured flag and sort "
            "order. Brands are a separate model with a unique slug, optional logo, website, description and "
            "featured flag."
        )
    )
    story += table_with_caption(
        [
            ["Model", "Important fields", "Behaviour"],
            ["Category", "name, slug, parent, image, icon, is_active, is_featured, sort_order", "Unlimited tree; slug generated from the name; child categories appear in listings."],
            ["Brand", "name, slug, logo, website, description, is_active, is_featured", "Brands are protected when products reference them."],
            ["Product", "name, slug, sku, brand, category, prices, stock, facets, media, SEO, counters", "The central catalogue row; price and stock are authoritative."],
            ["ProductImage", "product, image, alt_text, is_primary, sort_order", "One primary image per product is enforced in application code."],
            ["SpecificationField", "category, label, key, unit, input_type, options, is_filterable, sort_order", "Admin-defined specification schema per category."],
            ["ProductSpecification", "product, field, name, key, value, unit, sort_order", "Stores the actual specification values for a product."],
        ],
        "Table 6.1 - Catalogue models.",
        widths=[1.05, 3.0, 2.55],
        small=True,
    )

    story.append(h2("6.2 Product record anatomy"))
    story.append(
        p(
            "A product has a unique SKU and a unique slug generated from the name. The normal price is always "
            "stored; a discount price is optional and must be lower than the normal price or it is cleared on "
            "save. The current price, discount percentage and savings are computed properties, so the storefront "
            "does not have to repeat pricing logic. Cost price is for internal margin calculations and is never "
            "exposed on the storefront."
        )
    )
    story += bullets(
        [
            "<b>Content:</b> name, short description, long description, highlights, warranty information, colour "
            "and condition (new, refurbished or open box).",
            "<b>Pricing:</b> price, discount price and cost price, all stored as decimal values in NPR.",
            "<b>Stock:</b> stock quantity, low-stock threshold and allow-backorder flag. Stock is changed only "
            "through the inventory service or the order service, never by a raw form save.",
            "<b>Facets:</b> processor, RAM, storage, GPU, display size and operating system. These are "
            "denormalised fields used by the filter sidebar and sort options.",
            "<b>Social proof:</b> rating average, review count, sales count and view count. Rating fields are "
            "refreshed by review signals; sales and view counters are incremented by order and detail views.",
            "<b>Merchandising:</b> active, featured, free shipping and SEO title and description.",
        ]
    )
    story += callout(
        "Price snapshots protect history",
        "Cart items keep a price snapshot for display, but the current product price is authoritative when the "
        "order is created. Order items then store their own unit price, line total, product name, SKU and image "
        "URL. Later product edits cannot rewrite the financial history of an old order.",
        "success",
    )

    story.append(h2("6.3 Images and media validation"))
    story.append(
        p(
            "Product images are uploaded to <b>media/products/&lt;sku&gt;/</b> with a random filename, which avoids "
            "collisions and makes filenames non-guessable. The shared <b>validate_image_upload</b> validator "
            "checks extension, size and that Pillow can open the file. The dashboard limits a product to eight "
            "images. The first image becomes primary automatically; choosing another primary clears the previous "
            "one. Deleting an image removes the file through a post-delete signal."
        )
    )
    story += bullets(
        [
            "Allowed upload size is controlled by <b>MAX_UPLOAD_SIZE_MB</b>, default 5 MB.",
            "Django's in-memory upload limit is 5 MB and the total request limit is 15 MB.",
            "Category images, brand logos and avatars use the same validation helper.",
            "Development media is served by Django only when <b>DEBUG=True</b>; production must serve "
            "<b>/media/</b> from the reverse proxy or a storage service.",
        ]
    )

    story.append(h2("6.4 Dynamic specifications"))
    story.append(
        p(
            "Specifications are not hardcoded per product type. A staff member defines "
            "<b>SpecificationField</b> rows for a category, optionally with a unit, input type and select "
            "options. The product form then exposes the relevant fields for the selected category. The stored "
            "<b>ProductSpecification</b> keeps the label, key, value and unit so the product detail page remains "
            "readable even if the shared field is later renamed or removed."
        )
    )
    story += code_block(
        """
Category: Laptops
  SpecificationField: Processor      key=processor      type=text
  SpecificationField: Memory         key=memory         unit=GB   type=select
  SpecificationField: Storage        key=storage        unit=GB   type=select
  SpecificationField: Graphics       key=graphics       type=text

Product: ThinkPad X1 Carbon
  ProductSpecification: Processor = Intel Core Ultra 7 155U
  ProductSpecification: Memory    = 32 GB
  ProductSpecification: Storage   = 1 TB
        """.strip(),
        "Code block 6.1 - A category schema and the values stored for one product.",
    )

    story.append(h2("6.5 Search"))
    story.append(
        p(
            "Catalogue search is deliberately simple and database-backed. The <b>ProductQuerySet.search()</b> "
            "method looks for the query in the product name, SKU, short description, description, brand name, "
            "category name, processor, GPU and specification values, then applies <b>distinct()</b>. The listing "
            "view accepts a query of up to 150 characters. The suggestion endpoint accepts up to 100 characters "
            "and returns nothing until at least two characters are typed."
        )
    )
    story += table_with_caption(
        [
            ["Endpoint", "Method", "Response"],
            ["/products/?q=...", "GET", "Full catalogue page, or the results partial for AJAX."],
            ["/products/search/suggestions/?q=...", "GET", "JSON with up to 6 products, 4 categories, 3 brands and an all-results URL."],
        ],
        "Table 6.2 - Search endpoints.",
        widths=[2.45, 0.7, 3.25],
        small=True,
        mono_columns={0},
    )
    story.append(
        p(
            "The suggestion response includes product name, URL, formatted current price, compare-at price, "
            "primary image, category, brand and rating. The client renders the panel with escaping and closes it "
            "on outside click or Escape. Suggestions are throttled by the DRF anonymous rate of 120 requests per "
            "minute and user rate of 300 per minute."
        )
    )

    story.append(h2("6.6 Filtering"))
    story += table_with_caption(
        [
            ["Parameter", "Accepted values", "Effect"],
            ["q", "Text up to 150 chars", "Multi-field search."],
            ["category", "Category slug", "Selected category plus immediate active children."],
            ["brand", "Repeated brand slugs, up to 12", "Brand filter."],
            ["ram, storage, processor, gpu", "Repeated facet values, up to 12 each", "Exact facet filters."],
            ["min_price, max_price", "Decimal amounts", "Filters the effective price; swapped if reversed."],
            ["rating", "1 to 5", "Minimum average rating."],
            ["availability", "in_stock or out_of_stock", "Stock quantity filter."],
            ["discount", "10, 20, 30, 40 or 50", "Minimum discount percentage."],
            ["condition", "new, refurbished or open_box", "Product condition."],
            ["sort", "Eight sort keys", "Ordering; recommended is the default."],
            ["page", "Integer", "24 products per page."],
            ["partial", "1", "Return only the results partial for AJAX."],
        ],
        "Table 6.3 - Catalogue query parameters.",
        widths=[1.5, 2.5, 2.6],
        small=True,
        mono_columns={0},
    )
    story.append(
        p(
            "Facets are computed from all active products rather than only the current page, so the sidebar does "
            "not collapse as the shopper filters. The view annotates an <b>effective_price</b> using the discount "
            "price when present and a <b>discount_pct</b> expression. Active filters are returned with a label and "
            "a remove URL, and the pagination partial preserves the query string. AJAX requests receive the "
            "<b>X-Total-Count</b> response header."
        )
    )

    story.append(h2("6.7 Sorting"))
    story += table_with_caption(
        [
            ["Sort key", "Ordering"],
            ["recommended", "Featured first, then sales count and rating."],
            ["price_asc", "Effective price ascending, then name."],
            ["price_desc", "Effective price descending, then name."],
            ["newest", "Newest created first."],
            ["bestselling", "Sales count, then rating."],
            ["rating", "Average rating, then review count."],
            ["popular", "View count, then sales count."],
            ["name", "Alphabetical by product name."],
        ],
        "Table 6.4 - Catalogue sort modes.",
        widths=[1.3, 4.7],
        small=True,
        mono_columns={0},
    )

    story.append(h2("6.8 Product detail page"))
    story.append(
        p(
            "The product detail page loads the product with its brand, category, images, specifications and "
            "approved reviews in a small number of queries. Each view increments the view counter. The page "
            "shows the gallery, price and discount, stock label, short description, highlights, specifications "
            "grouped by category, verified reviews with a rating breakdown, related products and recently viewed "
            "products stored in the session."
        )
    )
    story += bullets(
        [
            "The review form is pre-filled when the signed-in customer already has a review.",
            "<b>can_review</b> is true only when the customer has a non-cancelled, non-refunded order containing "
            "the product. The final check is repeated by the review view and model rules.",
            "The wishlist state is loaded per product so the heart button renders correctly on first paint.",
            "The quantity selector is limited by the cart service, not only by HTML attributes.",
            "Related products prefer the same category or brand, excluding the current product.",
        ]
    )
    story += screenshot(
        "products-desktop.png",
        "Figure 6.1 - The catalogue listing with filters, product cards and AJAX result count.",
    )
    story += screenshot(
        "product-detail-desktop.png",
        "Figure 6.2 - A product detail page with gallery, pricing, stock and purchase actions.",
    )

    story.append(h2("6.9 Home page merchandising"))
    story.append(
        p(
            "The home page is a curated storefront, not a raw product dump. It combines a hero featuring up to "
            "three featured products, featured category tiles, trending products, bestsellers, latest arrivals, "
            "deals ranked by discount percentage, top-rated recommendations, new arrivals, featured brands and "
            "approved four- and five-star testimonials. The home dataset is cached for 180 seconds and invalidated "
            "by product, image, category and brand signals."
        )
    )
    story += screenshot(
        "home-mobile.png",
        "Figure 6.3 - The responsive mobile home page at a 390 px layout width (captured at 2x scale).",
        width=150,
    )

    # ------------------------------------------------------------------
    # 7. Cart, wishlist and coupons
    # ------------------------------------------------------------------
    story += chapter(
        "7",
        "Cart, wishlist and coupons",
        "The cart is a persistent database object for both guests and signed-in customers. Wishlist and coupons "
        "are separate concerns, but all three meet in the checkout review step.",
    )

    story.append(h2("7.1 Two kinds of cart"))
    story.append(
        p(
            "A cart belongs either to a user or to a session key. Signed-in customers have a one-to-one cart. "
            "Guests get a cart keyed by the Django session identifier. The session also stores a "
            "<b>guest_cart_key</b> because Django rotates the session key at login; without that copy, the merge "
            "signal would lose track of the guest cart."
        )
    )
    story += numbered(
        [
            "The guest adds a product. <b>get_cart()</b> creates a session if necessary and stores the guest cart "
            "key.",
            "The item is written to <b>CartItem</b> with a price snapshot and a unique cart/product constraint.",
            "On login, the cart merge signal reads the remembered guest key, finds the guest cart and moves or "
            "combines its items into the user's cart.",
            "If both carts contain the same product, the quantities are combined within the stock and "
            "twenty-unit limits. The guest cart is then deleted.",
            "Checkout always reads the active cart through the same service, so the merge is invisible to the "
            "customer.",
        ]
    )
    story += callout(
        "Validation is server-side",
        "The browser can suggest a quantity, but <b>add_to_cart()</b> and <b>update_cart_item()</b> re-check the "
        "product's active flags, stock, backorder setting and the maximum of 20 units per line. An invalid "
        "quantity returns a clear message and never creates a partial cart row.",
        "info",
    )

    story.append(h2("7.2 Cart operations"))
    story += table_with_caption(
        [
            ["Action", "URL", "Method", "Behaviour"],
            ["View cart", "/cart/", "GET", "Items, totals, coupon, delivery estimate and recommendations."],
            ["Add item", "/cart/add/", "POST", "Creates or increments a line after stock validation."],
            ["Update quantity", "/cart/update/&lt;id&gt;/", "POST", "Sets quantity or removes at zero."],
            ["Remove item", "/cart/remove/&lt;id&gt;/", "POST", "Deletes the line."],
            ["Apply coupon", "/cart/coupon/apply/", "POST", "Validates and stores the coupon on the cart."],
            ["Remove coupon", "/cart/coupon/remove/", "POST", "Clears the coupon."],
            ["Cart summary", "/cart/summary/", "GET", "JSON totals used by AJAX header and drawer."],
        ],
        "Table 7.1 - Cart endpoints.",
        widths=[1.25, 1.9, 0.65, 3.2],
        small=True,
        mono_columns={1, 2},
    )
    story.append(
        p(
            "The cart summary exposes subtotal, discount, delivery fee, total and the amount remaining for free "
            "delivery. The header updates the item badge after an AJAX add, while a full page reload remains the "
            "fallback. Quantity controls use POST and CSRF protection; the remove action is not a GET link."
        )
    )

    story.append(h2("7.3 Totals and delivery charges"))
    story.append(
        p(
            "Cart totals are computed in this order: subtotal of line totals; coupon discount; delivery fee; "
            "grand total. The default free-shipping threshold is Rs. 10,000 and the default fee is Rs. 250, both "
            "configurable. A selected shipping method can override the default fee and can define its own "
            "free-over threshold. The cart total never includes tax unless a future tax rule is added; the order "
            "model already has a tax amount field for that extension."
        )
    )
    story += code_block(
        """
subtotal = sum(item.product.current_price * item.quantity)
discount = coupon.calculate_discount(subtotal) if coupon is valid
delivery = shipping_method.fee_for(subtotal) or default fee
total   = max(0, subtotal - discount + delivery + tax)
        """.strip(),
        "Code block 7.1 - The cart and order total formula.",
    )

    story.append(h2("7.4 Coupons"))
    story += table_with_caption(
        [
            ["Rule", "Implementation"],
            ["Code", "Unique, case-insensitive lookup, stored uppercase."],
            ["Type", "Percentage or fixed amount."],
            ["Minimum order", "Subtotal must meet the configured minimum."],
            ["Maximum discount", "Optional cap for percentage coupons."],
            ["Validity window", "Optional start and end timestamps; expired and future coupons are rejected."],
            ["Total usage limit", "Optional total redemption cap."],
            ["Per-customer limit", "Checked by user when signed in, otherwise by email."],
            ["Stacking", "One coupon per cart and one coupon per order; coupons do not stack."],
            ["Audit", "CouponUsage stores the coupon, user or email, order and timestamp."],
        ],
        "Table 7.2 - Coupon rules.",
        widths=[1.35, 4.65],
        small=True,
    )
    story.append(
        p(
            "A coupon is applied to the cart only after <b>validate_for()</b> passes. During order creation the "
            "coupon row is locked again inside the transaction, its rules are re-checked against the locked "
            "subtotal, and a <b>CouponUsage</b> is created. The coupon's <b>used_count</b> is incremented with an "
            "F expression, avoiding a lost update under concurrency."
        )
    )

    story.append(h2("7.5 Wishlist"))
    story.append(
        p(
            "Every signed-in customer has one wishlist. A wishlist item stores the product, a restock-notification "
            "flag and the time it was saved. Adding or removing is an idempotent toggle. The wishlist page shows "
            "availability, current price and a move-to-cart action. When an out-of-stock product is restocked "
            "above zero, the inventory service notifies customers who saved it and left restock alerts enabled."
        )
    )
    story += bullets(
        [
            "Wishlist actions require a signed-in account; guests are sent to login with a safe return URL.",
            "The same product cannot appear twice in a wishlist.",
            "Moving to cart goes through the cart service and therefore respects stock and quantity limits.",
            "Restock alerts are in-app notifications with a link to the product.",
        ]
    )
    story += screenshot(
        "cart.png",
        "Figure 7.1 - The cart page with line items, quantity controls, coupon entry and order summary.",
    )

    # ------------------------------------------------------------------
    # 8. Checkout and orders
    # ------------------------------------------------------------------
    story += chapter(
        "8",
        "Checkout and order lifecycle",
        "Checkout is a five-step, session-backed flow. Order creation is a single atomic service that revalidates "
        "stock, prices, coupons and delivery before writing anything.",
    )

    story.append(h2("8.1 Checkout prerequisites"))
    story += bullets(
        [
            "The customer must be signed in. A guest who clicks checkout is redirected to login with a safe "
            "<b>next</b> URL and the guest cart is merged after login.",
            "The email address must be verified. Unverified customers are sent to the verification-pending page.",
            "The cart must contain at least one active, in-stock product.",
            "The customer must have a delivery address; one can be created inline during checkout.",
            "At least one active shipping method must exist.",
        ]
    )

    story.append(h2("8.2 The five steps"))
    story += table_with_caption(
        [
            ["Step", "URL", "Stored state", "What happens"],
            ["1. Contact", "/checkout/", "contact", "Name, email and phone, pre-filled from the account."],
            ["2. Address", "/checkout/address/", "address_id", "Choose an existing address or create a new one."],
            ["3. Delivery", "/checkout/shipping/", "shipping_method_id", "Choose an active shipping method and see its estimate."],
            ["4. Review", "/checkout/review/", "reviewed", "Inspect items, coupon, delivery and totals; apply or remove a coupon."],
            ["5. Payment", "/checkout/payment/", "payment_method", "Choose eSewa, Khalti, cash on delivery or bank transfer."],
        ],
        "Table 8.1 - Checkout steps and session state.",
        widths=[0.9, 1.5, 1.3, 3.2],
        small=True,
        mono_columns={1, 2},
    )
    story.append(
        p(
            "Each step checks that the previous step's state exists. A direct request to the payment step without "
            "an address, delivery method or review redirects the customer back to the correct earlier step. The "
            "state is stored under the session key <b>checkout</b> and is cleared immediately after a successful "
            "order creation."
        )
    )
    story += screenshot(
        "checkout-payment.png",
        "Figure 8.1 - The payment step of checkout, showing the available methods and order summary.",
    )

    story.append(h2("8.3 Order creation service"))
    story.append(
        p(
            "The payment step calls <b>create_order_from_cart()</b>. It is wrapped in "
            "<b>transaction.atomic</b> and performs the following sequence:"
        )
    )
    story += numbered(
        [
            "Lock the cart row with <b>select_for_update</b> and load its items and products.",
            "Reject an empty cart. Lock every product row in the cart so two shoppers cannot both buy the last unit.",
            "Re-check that every product and category is active and that each requested quantity is available. "
            "The whole checkout aborts if any line fails.",
            "Recompute the subtotal from the current product prices, not the cart's display snapshot.",
            "Lock and revalidate the coupon, then calculate the discount.",
            "Calculate the delivery fee from the selected shipping method and compute the final total.",
            "Create the order with contact details, a full shipping-address snapshot, delivery name and fee, "
            "payment method, notes, IP address and user agent.",
            "Create order items with product name, SKU, image URL, unit price, quantity and line total snapshots.",
            "Deduct stock through <b>adjust_stock()</b>, which locks each product, writes a StockHistory row and "
            "increments the product's sales count.",
            "Record coupon usage and increment the coupon's used count.",
            "Write the initial Pending status history, clear the cart, create an in-app notification and schedule "
            "the confirmation email with <b>transaction.on_commit</b>.",
        ]
    )
    story += callout(
        "Why the order service exists",
        "The view never trusts the cart totals shown on the review page. Price, stock, coupon eligibility and "
        "delivery fee are all recalculated against locked rows. This is the difference between a demo checkout "
        "and a checkout that is safe under concurrent orders.",
        "success",
    )

    story.append(h2("8.4 Order numbers and snapshots"))
    story.append(
        p(
            "Order numbers use the format <b>VQ-YYMMDD-XXXXXX</b>, where the suffix is a cryptographically random "
            "hex value. The service retries on collision. The order stores the customer's email and phone, a full "
            "copy of the delivery address and the shipping method name, so later address-book or shipping-method "
            "changes do not alter historical orders. Order items preserve product name, SKU, image URL and unit "
            "price for the same reason."
        )
    )

    story.append(h2("8.5 Status lifecycle"))
    story += table_with_caption(
        [
            ["Status", "Meaning", "Who sets it", "Payment effect"],
            ["pending", "Order received, not yet confirmed.", "System at creation.", "Payment pending unless already paid."],
            ["confirmed", "Accepted for fulfilment.", "Online payment success or staff/COD acceptance.", "Paid for online; COD remains pending."],
            ["processing", "Being picked and packed.", "Staff.", "No change."],
            ["shipped", "Handed to courier.", "Staff; tracking number and courier can be added.", "No change."],
            ["out_for_delivery", "With the delivery rider.", "Staff.", "No change."],
            ["delivered", "Received by the customer.", "Staff.", "COD becomes paid."],
            ["cancelled", "Cancelled before delivery.", "Customer or staff.", "Pending attempts cancelled; stock restored."],
            ["refunded", "Paid order cancelled or refunded.", "Staff or administrator.", "Payment marked refunded."],
        ],
        "Table 8.2 - Order statuses.",
        widths=[1.05, 2.2, 1.8, 1.8],
        small=True,
        mono_columns={0},
    )
    story.append(
        p(
            "Every status change is recorded in <b>OrderStatusHistory</b> with the staff member, timestamp and "
            "optional note. The customer timeline reads the same rows. The status index property drives the "
            "progress tracker on the order detail and tracking pages. Cancellation is allowed only while pending, "
            "confirmed or processing."
        )
    )
    story += diagram(
        "order-lifecycle.png",
        "Figure 8.2 - The order lifecycle, including cancellation and the four payment paths.",
    )

    story.append(h2("8.6 Cancellation and refunds"))
    story.append(
        p(
            "<b>cancel_order()</b> locks the order, checks that it can still be cancelled, restocks every item "
            "through the inventory service, and marks the order cancelled. If the order was paid, the payment "
            "status and order status become refunded and the successful payment row is marked refunded with a "
            "timestamp. Pending gateway attempts are cancelled so a late callback cannot revive a cancelled "
            "order. A notification is pushed to the customer and a status-history row is written."
        )
    )
    story += bullets(
        [
            "Customers cancel from their order detail page with a POST action.",
            "Staff can cancel or refund from the dashboard, subject to role checks.",
            "Refunds are recorded, not automatically reversed at the gateway. A real gateway refund must be "
            "completed in the provider's merchant console and then recorded in Voltiq.",
            "Stock restoration is audited with the reason <b>cancellation</b> and a reference to the order.",
        ]
    )

    story.append(h2("8.7 Confirmation, tracking, reorder and invoice"))
    story += table_with_caption(
        [
            ["Feature", "URL", "Behaviour"],
            ["Confirmation", "/orders/&lt;number&gt;/confirmation/", "Thank-you page with order summary and next steps."],
            ["Tracking", "/orders/&lt;number&gt;/track/", "Status timeline, courier, tracking number and delivery estimate."],
            ["Reorder", "/orders/&lt;number&gt;/reorder/", "Adds available items back to the cart after stock checks."],
            ["Invoice", "/orders/&lt;number&gt;/invoice.pdf", "Server-generated PDF owned by the customer or staff."],
            ["Pay again", "/orders/&lt;number&gt;/payment/", "Starts a new attempt while the order remains payable."],
        ],
        "Table 8.3 - Post-purchase features.",
        widths=[1.2, 2.4, 3.4],
        small=True,
        mono_columns={1},
    )
    story.append(
        p(
            "Invoices are generated with ReportLab. The PDF contains the Voltiq identity, order number, dates, "
            "billing contact, delivery address, line items, totals, payment method and status. Access is checked "
            "against the order owner or staff membership before the file is streamed. The response uses an "
            "attachment filename based on the order number."
        )
    )

    # ------------------------------------------------------------------
    # 9. Payments
    # ------------------------------------------------------------------
    story += chapter(
        "9",
        "Payments and gateway verification",
        "Voltiq supports eSewa, Khalti, cash on delivery and bank transfer behind one gateway interface. "
        "Online orders are marked paid only after server-side verification.",
    )

    story.append(h2("9.1 Supported methods and the gateway abstraction"))
    story += table_with_caption(
        [
            ["Method", "Code", "Online", "How it completes"],
            ["eSewa ePay v2", "esewa", "Yes", "Signed form redirect; callback payload plus status API verification."],
            ["Khalti ePayment v2", "khalti", "Yes", "Server-initiated payment URL; lookup API verification."],
            ["Cash on delivery", "cod", "No", "Order is confirmed immediately; staff records cash at delivery."],
            ["Bank transfer", "bank", "No", "Customer receives account instructions and a reference; staff verifies the deposit."],
        ],
        "Table 9.1 - Payment methods exposed by the checkout.",
        widths=[1.5, 0.7, 0.6, 3.2],
        small=True,
        mono_columns={1},
    )
    story.append(
        p(
            "Each method is a small gateway class implementing a common interface. <b>start_payment()</b> and "
            "<b>verify_payment()</b> are gateway-agnostic; the provider-specific signing and API calls live in "
            "<b>apps/payments/gateways/</b>. The <b>Payment</b> model also has a Stripe enum for future "
            "extension, but there is no Stripe gateway class and Stripe is not offered at checkout. Do not "
            "describe it as a supported method."
        )
    )
    story += code_block(
        """
class BaseGateway:
    code = ""
    display_name = ""
    is_online = True

    @property
    def is_configured(self): ...

    def initiate(self, payment, order, request) -> PaymentInitiation: ...

    def verify(self, payment, params, request) -> VerificationResult: ...
        """.strip(),
        "Code block 9.1 - The gateway contract. A result can be successful, failed or non-definitive.",
    )

    story.append(h2("9.2 Payment records and statuses"))
    story.append(
        p(
            "Every attempt creates a <b>Payment</b> row with the order, gateway, amount, currency, unique "
            "transaction reference, gateway reference, non-sensitive payloads, attempt number and timestamps. "
            "A separate <b>PaymentTransaction</b> row is appended for each event: initiation, callback, "
            "verification, success, failure, cancellation, refund or note. Payment attempts are never deleted or "
            "silently overwritten."
        )
    )
    story += table_with_caption(
        [
            ["Payment status", "Meaning"],
            ["initiated", "Row created; the gateway has not yet been contacted or has just been contacted."],
            ["pending", "The customer has been sent to the gateway or is expected to complete a manual transfer."],
            ["success", "Server verification passed and the order is paid."],
            ["failed", "A definitive failure was recorded. The order can normally be paid again."],
            ["cancelled", "The attempt was cancelled by the customer, staff or order cancellation."],
            ["expired", "A stale attempt was superseded by a new one."],
            ["refunded", "A successful payment was reversed and recorded."],
        ],
        "Table 9.2 - Payment attempt statuses.",
        widths=[1.2, 4.8],
        small=True,
        mono_columns={0},
    )
    story += callout(
        "The database enforces one success",
        "A partial unique constraint on <b>Payment(order)</b> where <b>status='success'</b> makes a second "
        "successful payment for the same order impossible, even if two callbacks race. The application also "
        "checks the order's paid state and returns an idempotent success for a duplicate callback.",
        "success",
    )

    story.append(h2("9.3 Starting a payment"))
    story += numbered(
        [
            "Lock the order row and return early if the order is already paid or is no longer payable.",
            "Resolve the gateway class. An unconfigured online gateway is rejected unless the development "
            "simulator is enabled.",
            "Mark any previous initiated or pending attempts as expired, so only the newest attempt is live.",
            "Create the Payment with the order total, increment the attempt number, and write an initiation audit row.",
            "If the gateway is online but unconfigured and simulation is on, send the customer to the simulator.",
            "Otherwise call <b>gateway.initiate()</b>. eSewa returns an auto-submitted form; Khalti returns a "
            "payment URL; COD and bank return a local redirect.",
            "Set the attempt to pending, store only non-secret gateway payload fields, set the order payment "
            "status to pending and write a note.",
        ]
    )

    story.append(h2("9.4 eSewa"))
    story.append(
        p(
            "The eSewa integration targets ePay v2. The server builds the signed field list "
            "<b>total_amount,transaction_uuid,product_code</b>, computes an HMAC-SHA256 signature with the "
            "merchant secret, base64-encodes it and renders an auto-submitting form to the configured eSewa "
            "endpoint. The amount is formatted with two decimals. The success and failure URLs both return to "
            "the Voltiq callback with the order number appended."
        )
    )
    story += bullets(
        [
            "The callback carries a base64-encoded JSON <b>data</b> parameter. Voltiq decodes it and extracts "
            "<b>transaction_uuid</b> to find the payment.",
            "The callback status must be <b>COMPLETE</b>, the transaction UUID must match and the signature must "
            "be present.",
            "The signature is recomputed over the callback's <b>signed_field_names</b> in the exact order and "
            "compared in constant time with <b>hmac.compare_digest</b>.",
            "Voltiq then calls the eSewa status API with product code, amount and transaction UUID. The status "
            "must be COMPLETE, the returned total must equal the payment amount and the transaction UUID must "
            "match.",
            "The gateway reference is the callback transaction code or the status API reference.",
        ]
    )
    story += callout(
        "Never trust the browser's status alone",
        "A callback that merely says success is not enough. The signature proves the payload came from eSewa, "
        "and the status API proves the transaction is complete and the amount is correct. If the status API is "
        "unreachable, the result is non-definitive: the attempt is not marked failed and the customer can retry "
        "verification.",
        "warning",
    )

    story.append(h2("9.5 Khalti"))
    story.append(
        p(
            "Khalti ePayment v2 is initiated server-to-server. Voltiq sends the return URL, website URL, amount "
            "in paisa, purchase order ID, purchase order name and customer information to the Khalti initiate "
            "endpoint using the merchant key in an Authorization header. Khalti returns a <b>pidx</b> and a "
            "<b>payment_url</b>; the pidx is stored on the payment and the customer is redirected."
        )
    )
    story += bullets(
        [
            "The callback carries the pidx and order reference. Voltiq matches the pidx to the payment, with an "
            "order-number fallback.",
            "If Khalti reports a status other than completed, pending or initiated, the attempt is failed "
            "immediately with the reported reason.",
            "Voltiq calls the lookup endpoint with the pidx. The returned status must be <b>Completed</b>.",
            "The purchase order ID must equal the Voltiq order number, the pidx must match and the total amount "
            "in paisa must equal the payment amount multiplied by 100.",
            "Only then is the payment marked successful; the Khalti transaction ID becomes the gateway reference.",
        ]
    )

    story.append(h2("9.6 Cash on delivery and bank transfer"))
    story.append(
        p(
            "Cash on delivery confirms the order immediately without an online payment. A COD payment attempt "
            "remains pending. When staff move the order to Delivered, the dashboard calls "
            "<b>mark_cod_collected()</b>, which marks the payment successful and records who collected the cash."
        )
    )
    story.append(
        p(
            "Bank transfer creates a payment attempt and sends the customer to an instructions page with the bank "
            "name, account name, account number, branch, SWIFT, support note and the order reference. The customer "
            "deposits the amount and sends the slip to support. Staff verify the deposit and use "
            "<b>Mark paid</b> in the dashboard, which records a manual payment with the staff member's identity. "
            "No bank credentials are stored in the application."
        )
    )

    story.append(h2("9.7 Verification, failure and idempotency"))
    story += numbered(
        [
            "The callback is logged before verification, including a truncated request payload and the client IP.",
            "The payment row and order are locked for the verification transaction.",
            "A payment already marked success returns success immediately. A paid order rejects a different "
            "attempt.",
            "The gateway verifies the payload and may call its status API. A non-definitive network failure "
            "leaves the attempt pending rather than falsely failing it.",
            "On success, <b>mark_success()</b> sets the payment to success, records the verification payload, "
            "marks the order paid and moves a pending order to confirmed.",
            "On a definitive failure, <b>mark_failed()</b> records the reason and marks the order's payment "
            "status failed. The customer can start a new attempt.",
            "A duplicate callback for a successful payment is idempotent; an IntegrityError from the unique "
            "constraint is caught and reported as already paid.",
        ]
    )

    story.append(h2("9.8 The development simulator"))
    story.append(
        p(
            "When <b>DEBUG=True</b> and <b>PAYMENT_SIMULATION=True</b>, an online gateway without credentials is "
            "still shown at checkout. Starting it creates a pending payment with gateway reference "
            "<b>SIMULATED</b>, writes a note that no real gateway was contacted and redirects to a clearly "
            "labelled sandbox page. The customer can choose success or failure. The success path calls "
            "<b>mark_success()</b>; the failure path records a simulated failure and returns the customer to the "
            "payment page."
        )
    )
    story += callout(
        "Simulator safety",
        "<b>simulate_payment()</b> refuses to run unless both DEBUG and PAYMENT_SIMULATION are true. The simulator "
        "route is hidden and returns 404 when simulation is disabled. It must never be enabled on a public "
        "production host. Real eSewa and Khalti credentials automatically take precedence over simulation.",
        "danger",
    )

    story.append(h2("9.9 Refunds and audit trail"))
    story.append(
        p(
            "Refunds are recorded manually. A gateway refund is completed in the provider's merchant console, "
            "then an administrator records it in Voltiq. The successful payment becomes refunded, the order "
            "becomes refunded, stock is restored if it has not already been restored, and a status-history row "
            "and customer notification are written. The dashboard restricts refund actions to administrators; "
            "staff can cancel an unpaid or paid order through the cancellation path, which also records a refund "
            "when the order was paid."
        )
    )
    story += table_with_caption(
        [
            ["Audit row", "What it captures"],
            ["Payment initiated", "Gateway, attempt number, amount and client IP."],
            ["Gateway callback", "Truncated parameters and the time received."],
            ["Verification", "Success or failure message and non-sensitive response payload."],
            ["Succeeded / failed", "Final status and confirmation."],
            ["Refunded", "Administrator note and refund timestamp."],
            ["Order status history", "Every fulfilment transition with staff member and note."],
        ],
        "Table 9.3 - Payment and order audit records.",
        widths=[1.8, 4.2],
        small=True,
    )
    story += diagram(
        "payment-verification.png",
        "Figure 9.1 - The five-stage online payment verification flow and the three gateway-specific checks.",
    )

    # ------------------------------------------------------------------
    # 10. Inventory
    # ------------------------------------------------------------------
    story += chapter(
        "10",
        "Inventory and stock control",
        "Stock is a transactional resource. Every change goes through one service, is guarded by a row lock and "
        "leaves an immutable history row.",
    )

    story.append(h2("10.1 One source of truth"))
    story.append(
        p(
            "The authoritative quantity is <b>Product.stock_quantity</b>. The product form can display stock, but "
            "routine changes should use the inventory dashboard or the order service. Direct edits in Django "
            "admin bypass the stock-history trail and should be reserved for emergency maintenance."
        )
    )
    story += callout(
        "Stock is not a display field",
        "Availability, low-stock labels, cart limits, checkout validation and restock alerts all read the same "
        "quantity. A stale or manually edited number can therefore block sales or oversell. Use the adjustment "
        "screen so the previous quantity, new quantity and reason are recorded.",
        "warning",
    )

    story.append(h2("10.2 The adjustment algorithm"))
    story += code_block(
        """
@transaction.atomic
def adjust_stock(product, change, reason, reference="", order=None, user=None):
    locked = Product.objects.select_for_update().get(pk=product.pk)
    previous = locked.stock_quantity
    new_quantity = previous + int(change)
    if new_quantity < 0:
        raise StockError(...)
    locked.stock_quantity = new_quantity
    locked.save(update_fields=["stock_quantity", "updated_at"])
    StockHistory.objects.create(
        product=locked, change=change, previous_quantity=previous,
        new_quantity=new_quantity, reason=reason, reference=reference,
        order=order, changed_by=user,
    )
    if previous <= 0 < new_quantity:
        notify_restock(locked)
        """.strip(),
        "Code block 10.1 - The core stock mutation. The caller owns the surrounding transaction.",
    )
    story.append(
        p(
            "<b>adjust_stock()</b> locks the product row, calculates the new quantity and refuses to go below "
            "zero. It then writes a StockHistory row and, when the product crosses from zero to a positive "
            "quantity, calls the wishlist restock notifier. It updates the in-memory product object so callers "
            "see the new value without a refresh. <b>set_stock()</b> is a convenience wrapper that converts an "
            "absolute target into a delta."
        )
    )

    story.append(h2("10.3 Stock history reasons"))
    story += table_with_caption(
        [
            ["Reason", "Created by", "Meaning"],
            ["seed", "seed_store", "Initial demo or migration stock."],
            ["restock", "Staff adjustment", "New units received from a supplier."],
            ["sale", "Order creation", "Units deducted for an order."],
            ["return", "Staff adjustment", "Customer return accepted back into stock."],
            ["cancellation", "Order cancellation or refund", "Reserved units released back to stock."],
            ["adjustment", "Staff", "Correction after a count or data fix."],
            ["damage", "Staff", "Damaged or lost units removed from stock."],
        ],
        "Table 10.1 - Stock history reasons.",
        widths=[1.1, 1.8, 3.1],
        small=True,
        mono_columns={0},
    )

    story.append(h2("10.4 Order deduction and restoration"))
    story.append(
        p(
            "After an order is created, each line calls <b>adjust_stock(product, -quantity, sale, ...)</b> with "
            "the order reference. Because the order service already holds a product row lock, the same "
            "transaction cannot interleave with another checkout. The product's <b>sales_count</b> is incremented "
            "with an F expression. Cancellation and refund use <b>restock_order()</b>, which loops through the "
            "order items and adjusts each product with the cancellation reason."
        )
    )
    story += bullets(
        [
            "The cart reserves nothing. Stock is checked when an item is added and rechecked at order creation.",
            "The checkout review shows stock conflicts and blocks progression when a line exceeds availability.",
            "Backordered products can be added within the 20-unit limit, but the order service still requires "
            "positive stock unless a future allocation workflow is added.",
            "If a product is deleted, its order item keeps the product snapshot and the product foreign key "
            "becomes null, so historical orders remain readable.",
        ]
    )

    story.append(h2("10.5 Dashboard inventory tools"))
    story.append(
        p(
            "The inventory list supports search, category and stock-state filters, pagination and a per-product "
            "adjust action. The adjustment form accepts a target quantity or a delta, a reason and a reference. "
            "The history screen shows every movement with the product, change, previous and new quantity, reason, "
            "reference, linked order and staff member. Low-stock and out-of-stock counts are also surfaced on the "
            "dashboard overview and in the quick-action strip."
        )
    )

    story.append(h2("10.6 Low stock and restock alerts"))
    story.append(
        p(
            "A product is low stock when its quantity is greater than zero and less than or equal to its "
            "<b>low_stock_threshold</b>, which defaults to 5. It is out of stock at zero. The storefront label is "
            "<b>Only N left</b>, <b>Out of stock</b> or <b>Backorder</b> when backorders are allowed. When a "
            "product moves from zero to positive, wishlist customers who left <b>notify_on_restock</b> enabled "
            "receive an in-app notification."
        )
    )

    story.append(h2("10.7 Concurrency notes"))
    story.append(
        p(
            "PostgreSQL provides real row-level locking for <b>select_for_update</b>. SQLite serialises writes and "
            "has weaker row-lock semantics, but it is adequate for local development and the test suite. The "
            "production deployment guide therefore requires PostgreSQL. The order service locks the cart, every "
            "product in the cart and the coupon before writing financial rows. The payment service locks the "
            "payment and order during verification. These locks are the reason the project can be described as "
            "transaction-safe rather than merely transactional."
        )
    )

    # ------------------------------------------------------------------
    # 11. Reviews
    # ------------------------------------------------------------------
    story += chapter(
        "11",
        "Reviews and ratings",
        "Reviews are tied to a product and a customer, with a verified-purchase badge based on real order "
        "history. Approved ratings are aggregated onto the product.",
    )

    story.append(h2("11.1 Review model and rules"))
    story += table_with_caption(
        [
            ["Field", "Rule"],
            ["product", "Required; deleting a product deletes its reviews."],
            ["user", "Required; one review per user per product."],
            ["rating", "Integer from 1 to 5."],
            ["title", "Up to 140 characters; trimmed."],
            ["body", "Up to 3000 characters; at least 15 characters after trimming."],
            ["is_verified_purchase", "Set by the server from qualifying order history."],
            ["is_approved", "Defaults to true; staff can unpublish."],
            ["helpful_count", "Stored and displayed in the dashboard; no public vote endpoint in this build."],
        ],
        "Table 11.1 - Review fields and validation.",
        widths=[1.5, 4.5],
        small=True,
        mono_columns={0},
    )
    story.append(
        p(
            "The public product page only shows the review call to action to customers who have purchased the "
            "product. The review endpoint itself requires a signed-in user and allows one review per product; the "
            "verified-purchase flag is computed by checking non-cancelled, non-refunded order items for that user "
            "and product. A review without a qualifying purchase is still possible through a direct request, but "
            "it is shown without the verified badge. If the business rule is meant to be 'verified buyers only', "
            "the view should enforce <b>_has_purchased()</b> as well as the template; that change is not present "
            "in this build."
        )
    )
    story += callout(
        "Honest documentation",
        "This manual describes the code that exists, not an idealised version. The review CTA is purchase-gated "
        "in the UI, but the add-review view is login-gated. This is a small but real gap to close before launch if "
        "verified-only reviews are a hard requirement.",
        "warning",
    )

    story.append(h2("11.2 Creating, editing and deleting"))
    story += numbered(
        [
            "A signed-in customer opens the product review form from the product page.",
            "The form validates the rating, title and body. A short body is rejected with a clear message.",
            "The view checks for an existing review and redirects with an explanation instead of creating a duplicate.",
            "The review is saved with the product, user, trimmed content and the server-calculated verified flag.",
            "Editing is limited to the owner; another user receives a 404. Deleting is a POST action and is also "
            "limited to the owner.",
            "Staff can approve or unpublish reviews and delete them from the dashboard.",
        ]
    )

    story.append(h2("11.3 Rating aggregation"))
    story.append(
        p(
            "Signals recalculate the product's rating on every review save or delete. Only approved reviews "
            "contribute. The aggregate writes <b>rating_avg</b> rounded to two decimals and <b>review_count</b> "
            "to the product row. This denormalisation avoids an aggregate query on every product card and keeps "
            "sorting by rating fast."
        )
    )
    story += code_block(
        """
def refresh_product_rating(product_id):
    stats = Review.objects.filter(product_id=product_id, is_approved=True).aggregate(
        avg=Avg("rating"), count=Count("id")
    )
    Product.objects.filter(pk=product_id).update(
        rating_avg=round(stats["avg"] or 0, 2),
        review_count=stats["count"] or 0,
    )

@receiver([post_save, post_delete], sender=Review)
def review_changed(sender, instance, **kwargs):
    refresh_product_rating(instance.product_id)
        """.strip(),
        "Code block 11.1 - The rating signal.",
    )

    story.append(h2("11.4 Display and moderation"))
    story.append(
        p(
            "The product page shows the average score, a five-row rating breakdown with counts and percentages, "
            "the review list and a verified-purchase badge. The dashboard review list supports status filtering, "
            "approval toggling and deletion. The overview shows the number of pending reviews so staff can act on "
            "them. Rating summaries are also used on product cards and in the home page recommendation section."
        )
    )

    story.append(h2("11.5 What is intentionally simple"))
    story += bullets(
        [
            "No image uploads on reviews; the model and form focus on text.",
            "No nested replies or threaded discussions.",
            "No public helpful-vote action, despite the stored helpful count.",
            "No automatic profanity or spam classifier; moderation is staff-driven.",
            "Reviews are auto-approved by default so the demo storefront has content, but staff can unpublish.",
        ]
    )

    # ------------------------------------------------------------------
    # 12. Staff dashboard
    # ------------------------------------------------------------------
    story += chapter(
        "12",
        "Staff and administrator dashboard",
        "The dashboard is a separate operational interface at /dashboard/. It shares the database and services "
        "with the storefront but has its own shell, navigation, styles and permissions.",
    )

    story.append(h2("12.1 A different product surface"))
    story.append(
        p(
            "The staff dashboard is not a skinned copy of the customer account. It uses "
            "<b>templates/dashboard/base.html</b>, a dark sidebar, a top bar, data-dense cards and tables, "
            "Chart.js widgets and its own <b>dashboard.css</b> and <b>dashboard.js</b>. The storefront header, "
            "category mega menu, cart drawer and marketing footer are not present. This keeps operational screens "
            "focused and prevents staff actions from being mixed with customer navigation."
        )
    )
    story += table_with_caption(
        [
            ["Module", "URL", "Main actions"],
            ["Overview", "/dashboard/", "KPI cards, revenue and order charts, status mix, top products, recent orders and payments, low stock, pending reviews."],
            ["Products", "/dashboard/products/", "Create, edit, delete, toggle active, upload images, set primary image, edit specifications."],
            ["Categories", "/dashboard/categories/", "Create, edit, delete category tree nodes; protected when products reference them."],
            ["Brands", "/dashboard/brands/", "Create, edit and delete brands; protected when products reference them."],
            ["Specification fields", "/dashboard/spec-fields/", "Define per-category specification schemas."],
            ["Orders", "/dashboard/orders/", "Search, filter, inspect, change status, add tracking, mark paid, download invoice."],
            ["Customers", "/dashboard/customers/", "Search, inspect order history and spend, suspend, change role."],
            ["Inventory", "/dashboard/inventory/", "Adjust stock, inspect history, filter low and out of stock."],
            ["Reports", "/dashboard/reports/", "Date-range revenue, orders, AOV, units, top products, categories, payment mix, top customers."],
            ["Reviews", "/dashboard/reviews/", "Approve, unpublish and delete reviews."],
            ["Coupons", "/dashboard/coupons/", "Create, edit and delete coupons; inspect usage counts."],
            ["Newsletter", "/dashboard/newsletter/", "Inspect subscribers and export CSV."],
            ["Messages", "/dashboard/messages/", "Read contact messages and update their status."],
            ["Settings", "/dashboard/settings/", "Store identity, contact details, social links, shipping methods."],
        ],
        "Table 12.1 - Dashboard modules.",
        widths=[1.1, 1.7, 3.2],
        small=True,
        mono_columns={1},
    )

    story.append(h2("12.2 Permissions and audit"))
    story.append(
        p(
            "Every dashboard view is wrapped in <b>staff_required</b>, which redirects anonymous users to login "
            "and raises 403 for authenticated non-staff users. Administrator-only views use <b>admin_required</b>. "
            "Role and suspension changes cannot target superusers or other administrators, and administrators "
            "cannot suspend themselves through the customer screen. Order status changes, refunds, stock "
            "adjustments, review moderation and customer role changes are recorded with the acting user where the "
            "model supports it."
        )
    )

    story.append(h2("12.3 Overview analytics"))
    story += bullets(
        [
            "<b>Revenue:</b> total paid revenue, today, the last seven days and the current month.",
            "<b>Orders:</b> total, pending and delivered counts.",
            "<b>Customers and catalogue:</b> customer count, active product count, low-stock count and out-of-stock count.",
            "<b>Average order value:</b> total paid revenue divided by the number of paid orders.",
            "<b>Charts:</b> 30-day revenue and order series, plus order-status distribution.",
            "<b>Top products and categories:</b> grouped order items from paid orders, ranked by revenue.",
            "<b>Recent activity:</b> latest orders, successful payments, low-stock products and pending reviews.",
        ]
    )
    story += screenshot(
        "dashboard-overview.png",
        "Figure 12.1 - The staff dashboard overview with KPIs, charts, order activity and inventory alerts.",
    )

    story.append(h2("12.4 Catalogue operations"))
    story.append(
        p(
            "Product management is the most complex dashboard form. It combines core product fields, pricing, "
            "stock, facets, SEO, flags, images and dynamic specifications. Selecting a category loads the relevant "
            "specification fields through <b>/dashboard/api/category-specs/&lt;pk&gt;/</b>. A product can have up "
            "to eight images; staff can upload, delete and choose the primary image. Category and brand deletion "
            "is protected when products reference them, so the catalogue cannot be silently broken."
        )
    )

    story.append(h2("12.5 Orders and payments"))
    story.append(
        p(
            "The order list supports text search and filters for status, payment status, payment method and date "
            "range. The detail page shows customer and delivery snapshots, line items, totals, payment attempts, "
            "status history and internal notes. Staff can move an order through the fulfilment statuses, attach a "
            "courier and tracking number, mark a COD or bank payment paid, cancel an order or, as an "
            "administrator, record a refund. Every transition sends a customer notification and a "
            "failure-tolerant status email."
        )
    )
    story += callout(
        "Status changes are not free text",
        "The dashboard uses the same status choices as the order model and the customer timeline. A status change "
        "is written through <b>Order.set_status()</b> or the cancellation/refund services, not by editing a raw "
        "database column.",
        "info",
    )

    story.append(h2("12.6 Customers"))
    story.append(
        p(
            "The customer list annotates each account with order count and paid spend. The detail page shows "
            "contact information, join date, verification and suspension state, recent orders and total spend. "
            "Administrators can suspend or reactivate a customer and change a customer's role between customer, "
            "staff and admin. Suspension immediately logs the account out on its next request."
        )
    )

    story.append(h2("12.7 Reports and CSV exports"))
    story.append(
        p(
            "The reports page accepts a date range, defaults to the last 30 days and caps the range at 365 days. "
            "It calculates revenue, order count, average order value, units sold and new customers, plus a daily "
            "series, top products, category revenue, payment-method mix, status breakdown and top customers. The "
            "orders and newsletter exports stream CSV with a filename suitable for spreadsheets. Text values that "
            "begin with <b>=</b>, <b>+</b>, <b>-</b> or <b>@</b> are prefixed with an apostrophe to reduce CSV "
            "formula injection risk."
        )
    )
    story += screenshot(
        "dashboard-reports.png",
        "Figure 12.2 - The reports page with date-range controls, revenue summary and analytical charts.",
    )

    story.append(h2("12.8 Store settings"))
    story.append(
        p(
            "Administrators can edit the site name, tagline, announcement bar, support phone, support email, "
            "address and social URLs. The singleton <b>SiteSetting</b> is exposed to every template through the "
            "site context processor. Shipping methods are managed from the same settings screen: name, code, "
            "description, charge, free-over threshold, delivery-day range, active flag and sort order."
        )
    )

    # ------------------------------------------------------------------
    # 13. Content and communication
    # ------------------------------------------------------------------
    story += chapter(
        "13",
        "Content, email and notifications",
        "Voltiq is not only a catalogue and checkout. It also carries store identity, editorial pages, customer "
        "messages, newsletter consent and the email and in-app messages that keep customers informed.",
    )

    story.append(h2("13.1 Store identity and the site context processor"))
    story.append(
        p(
            "A singleton <b>SiteSetting</b> row stores the store name, tagline, announcement bar, support phone, "
            "support email, physical address and social links. The <b>site_context</b> processor loads it once per "
            "request and exposes it to every template as <b>site</b>. If the row does not exist, "
            "<b>SiteSetting.load()</b> creates it with sensible defaults. This means the header announcement, "
            "footer contact block, invoice header and storefront copy all read from one editable place."
        )
    )
    story += table_with_caption(
        [
            ["Setting", "Default", "Where it appears"],
            ["store_name", "Voltiq", "Header, footer, invoice, email and page titles."],
            ["tagline", "Premium electronics, powered for life.", "Hero and footer brand block."],
            ["announcement", "Free delivery across Nepal on orders over Rs. 10,000", "Top announcement bar."],
            ["support_phone", "+977 980-000-0000", "Header, footer, contact page and checkout help."],
            ["support_email", "support@voltiq.com.np", "Footer, contact page and policy pages."],
            ["address", "Durbar Marg, Kathmandu 44600, Nepal", "Footer and invoice issuer block."],
            ["social URLs", "Empty", "Footer social icons when configured."],
        ],
        "Table 13.1 - SiteSetting fields.",
        widths=[1.3, 2.7, 2.6],
        small=True,
        mono_columns={0},
    )

    story.append(h2("13.2 Editorial and policy pages"))
    story += table_with_caption(
        [
            ["Page", "URL", "Implementation"],
            ["About", "/about/", "Template with brand story, values, showroom information and calls to action."],
            ["FAQ", "/faq/", "Accordion-style answers covering delivery, payments, returns, warranty and accounts."],
            ["Privacy", "/privacy/", "Policy content dictionary with sections for collection, use, cookies, retention and rights."],
            ["Terms", "/terms/", "Terms of sale, account responsibilities, pricing and limitation language."],
            ["Shipping", "/shipping/", "Delivery coverage, charges, timelines and free-shipping threshold."],
            ["Returns", "/returns/", "Return window, condition requirements, exclusions, refund timing and process."],
            ["Contact", "/contact/", "Validated contact form stored in the database and emailed to support."],
        ],
        "Table 13.2 - Public content pages.",
        widths=[1.0, 1.2, 4.4],
        small=True,
        mono_columns={1},
    )
    story.append(
        p(
            "The policy pages are intentionally simple dictionaries in <b>apps/core/views.py</b>. They are easy "
            "to review with legal counsel and do not require a CMS. The copy is written for a Nepali store and "
            "mentions NPR, Kathmandu delivery, local warranty and the absence of stored card data."
        )
    )

    story.append(h2("13.3 Newsletter"))
    story.append(
        p(
            "The footer and dedicated sections collect an email address and an optional hidden name. The view is "
            "rate-limited to five POSTs per IP per minute. It validates the address, filters duplicates by "
            "case-insensitive email and creates a subscription with a random unsubscribe token. A welcome email "
            "is sent with <b>fail_silently=True</b> so a mail outage does not break the storefront. AJAX requests "
            "receive JSON; ordinary form posts receive a message and a redirect."
        )
    )
    story += bullets(
        [
            "Unsubscribe uses the token in a GET link and records <b>unsubscribed_at</b>.",
            "Staff can inspect and export subscribers from the dashboard.",
            "The subscription is separate from the user account. A customer may have an account without marketing consent.",
            "The welcome email uses the plain Django mailer, not a marketing automation platform.",
        ]
    )

    story.append(h2("13.4 Contact messages"))
    story.append(
        p(
            "The contact form collects name, email, optional phone, subject and message. The message must be at "
            "least ten characters. A successful submission stores a <b>ContactMessage</b> with status New, emails "
            "the support address with the sender's details and shows a confirmation. Staff can move the message "
            "to In progress or Resolved in the dashboard. The form is not a live chat and does not create a "
            "customer account."
        )
    )

    story.append(h2("13.5 Email"))
    story.append(
        p(
            "Email configuration is environment-driven. If <b>EMAIL_HOST</b> is empty, Django uses the console "
            "backend; this is the default for local development and prints verification and reset links in the "
            "terminal. When a host is set, Voltiq uses SMTP with TLS or SSL and a ten-second timeout. The default "
            "sender is <b>Voltiq &lt;no-reply@voltiq.com.np&gt;</b> and the support address is separate."
        )
    )
    story += table_with_caption(
        [
            ["Message", "Trigger", "Template or format"],
            ["Verify email", "Registration and resend", "emails/verify_email.txt and .html"],
            ["Password reset", "Forgot-password request", "Django subject, emails/password_reset.txt and .html"],
            ["Order confirmation", "Successful order creation", "Plain-text message with line items and totals"],
            ["Status update", "Staff status change", "Failure-tolerant plain-text message"],
            ["Newsletter welcome", "New subscription", "Plain-text welcome"],
            ["Contact notification", "Contact form", "Plain-text message to the support inbox"],
        ],
        "Table 13.3 - Outgoing email.",
        widths=[1.25, 2.0, 3.35],
        small=True,
    )
    story += callout(
        "Email is not a transaction",
        "Order creation commits the database first and uses <b>transaction.on_commit</b> for the confirmation "
        "email. If the mail provider is down, the order still exists. Staff can resend or contact the customer "
        "from the order details. The application does not retry failed messages automatically, so a production "
        "deployment should monitor the mail provider and the application log.",
        "info",
    )

    story.append(h2("13.6 In-app notifications"))
    story.append(
        p(
            "The <b>Notification</b> model stores a title, message, optional URL, kind and read flag per user. "
            "Notifications are pushed for order placement, payment success, cancellation, refund, restock and "
            "welcome events. The header shows the unread count, and the account page lists all messages with a "
            "mark-all-read action. Because notifications are database rows, they survive sessions and are "
            "visible on every device. They are not emails and do not require a background worker."
        )
    )

    story.append(h2("13.7 Errors and health"))
    story.append(
        p(
            "Custom handlers render branded 400, 403, 404 and 500 pages. CSRF failures use a dedicated view that "
            "explains an expired form and offers a safe way back. The <b>/health/</b> endpoint runs a trivial "
            "database query and returns JSON <b>{\"status\": \"ok\"}</b> with HTTP 200, or <b>degraded</b> with "
            "HTTP 503 if the database is unreachable. It is intended for a load balancer or uptime monitor."
        )
    )
    story += callout(
        "Sitemap reference is currently incomplete",
        "<b>/robots.txt</b> advertises <b>/sitemap.xml</b>, but this build does not register a sitemap route. "
        "Search engines will receive a 404 for that line. Before launch, either add a Django sitemap for static "
        "pages, categories and active products, or remove the Sitemap line. This is listed again in the launch "
        "checklist.",
        "warning",
    )

    # ------------------------------------------------------------------
    # 14. Design system
    # ------------------------------------------------------------------
    story += chapter(
        "14",
        "Design system and front-end behaviour",
        "The storefront and dashboard are built with hand-written HTML, CSS and vanilla JavaScript. There is no "
        "Node build step, no React and no CSS framework.",
    )

    story.append(h2("14.1 Brand direction"))
    story.append(
        p(
            "Voltiq uses a deep navy foundation, electric blue as the action colour and amber as the energy and "
            "offer accent. The storefront is editorial and premium: large type, generous whitespace, product "
            "photography and restrained borders. The dashboard is denser and more utilitarian, but shares the "
            "same colour language and type scale. Prices are always shown in NPR with the <b>Rs.</b> prefix."
        )
    )
    story += table_with_caption(
        [
            ["Token", "Value", "Use"],
            ["--navy-950", "#060b16", "Footer and deepest surfaces."],
            ["--navy-900", "#0b1220", "Dashboard sidebar and dark sections."],
            ["--brand", "#2563eb", "Primary buttons, links and active states."],
            ["--electric", "#3b82f6", "Highlights and focus rings."],
            ["--amber", "#f59e0b", "Deals, ratings and accent badges."],
            ["--green", "#16a34a", "Success, in-stock and paid."],
            ["--red", "#dc2626", "Errors, destructive actions and out-of-stock."],
            ["--canvas", "#f5f7fb", "Page background."],
        ],
        "Table 14.1 - Core colour tokens.",
        widths=[1.2, 1.2, 4.2],
        small=True,
        mono_columns={0, 1},
    )

    story.append(h2("14.2 Type and spacing"))
    story.append(
        p(
            "Headings use Plus Jakarta Sans and body copy uses Inter, loaded from Google Fonts with a system-font "
            "fallback. The type scale is fluid, with clamp-based display sizes for hero headings and fixed "
            "sizes for dense dashboard tables. Spacing follows a consistent 4 px base scale exposed as CSS "
            "variables. Radii range from 6 px for small controls to 28 px for hero panels. Shadows are soft and "
            "used sparingly."
        )
    )

    story.append(h2("14.3 CSS architecture"))
    story += table_with_caption(
        [
            ["File", "Responsibility"],
            ["tokens.css", "Design tokens, reset, typography, utilities, buttons, forms and base components."],
            ["layout.css", "Header, announcement bar, mega menu, mobile navigation, footer and page shells."],
            ["components.css", "Product cards, badges, ratings, tabs, modals, toasts, pagination and empty states."],
            ["pages.css", "Home, catalogue, product detail, cart, checkout and order pages."],
            ["account.css", "Customer account sidebar, profile, addresses and notifications."],
            ["dashboard.css", "Staff shell, KPI cards, charts, data tables and dashboard forms."],
            ["responsive.css", "Breakpoints at 1180, 1024, 860 and 620 px."],
            ["app.css", "Small compatibility layer loaded after the main sheets."],
        ],
        "Table 14.2 - Stylesheet responsibilities.",
        widths=[1.3, 4.7],
        small=True,
        mono_columns={0},
    )

    story.append(h2("14.4 JavaScript behaviour"))
    story.append(
        p(
            "The storefront script is one progressive-enhancement file. Every feature has a working server-rendered "
            "fallback; JavaScript upgrades the interaction rather than owning the page. The dashboard script is "
            "smaller and focuses on charts, the sidebar and confirmation prompts."
        )
    )
    story += bullets(
        [
            "<b>Navigation:</b> mobile drawer, accessible dropdowns, sticky header state and back-to-top.",
            "<b>Search:</b> debounced suggestions, keyboard navigation, escaped rendering and outside-click close.",
            "<b>Catalogue:</b> AJAX filters, sort and pagination, history pushState and a results partial.",
            "<b>Cart:</b> add/update/remove, optimistic badge updates, cart drawer refresh and toast feedback.",
            "<b>Wishlist:</b> toggle without a page reload and a graceful login redirect for guests.",
            "<b>Product page:</b> gallery thumbnails, tabs, quantity controls and review form feedback.",
            "<b>Checkout:</b> address selection, shipping updates and double-submit protection.",
            "<b>General:</b> password visibility, confirm dialogs, dismissible messages and CSRF-aware fetch calls.",
        ]
    )

    story.append(h2("14.5 AJAX contracts"))
    story += table_with_caption(
        [
            ["Interaction", "Request", "Response"],
            ["Search suggestions", "GET /products/search/suggestions/?q=...", "JSON groups and an all-results URL."],
            ["Filtered catalogue", "GET /products/?...&amp;partial=1", "HTML partial plus X-Total-Count."],
            ["Add to cart", "POST /cart/add/", "JSON summary or redirect fallback."],
            ["Update cart", "POST /cart/update/&lt;id&gt;/", "JSON totals and stock messages."],
            ["Cart summary", "GET /cart/summary/", "JSON subtotal, discount, delivery and total."],
            ["Wishlist toggle", "POST /wishlist/toggle/", "JSON state and count."],
            ["Newsletter", "POST /newsletter/subscribe/", "JSON message or redirect."],
        ],
        "Table 14.3 - AJAX contracts.",
        widths=[1.3, 2.7, 2.5],
        small=True,
        mono_columns={1},
    )
    story.append(
        p(
            "Fetch calls read the CSRF cookie, send <b>X-CSRFToken</b> and use <b>X-Requested-With: "
            "XMLHttpRequest</b>. Views decide whether to return JSON or HTML; they do not rely on a separate API "
            "namespace. The JSON renderer is DRF, but the AJAX endpoints are ordinary Django views for carts, "
            "wishlists and newsletter actions."
        )
    )

    story.append(h2("14.6 Responsive design"))
    story.append(
        p(
            "The desktop grid collapses to two columns below 1180 px, a single column below 860 px and a compact "
            "mobile layout below 620 px. The catalogue filter sidebar becomes a drawer, the header navigation "
            "becomes a menu, tables become horizontally scrollable, and dashboard cards stack. Touch targets are "
            "at least 40 px where practical. The mobile home capture in Figure 6.3 was taken at a true 390 px "
            "layout width using Chrome device emulation."
        )
    )

    story.append(h2("14.7 Accessibility"))
    story += bullets(
        [
            "Semantic landmarks, heading order and skip-to-content link.",
            "Visible focus styles on links, buttons, inputs and custom controls.",
            "Labels associated with inputs; errors announced next to the field.",
            "ARIA attributes on tabs, drawers, search suggestions and dismissible messages.",
            "Keyboard support for Escape, arrow keys in search and Enter activation.",
            "Colour is not the only signal: stock, payment and order states include text labels.",
            "Images use alt text; decorative images use empty alt where appropriate.",
        ]
    )
    story += callout(
        "Accessibility is not certified",
        "The interface follows accessible patterns, but this project has not undergone a formal WCAG audit or "
        "assistive-technology test matrix. Treat the list above as implemented practice, not a compliance claim.",
        "info",
    )

    # ------------------------------------------------------------------
    # 15. Security
    # ------------------------------------------------------------------
    story += chapter(
        "15",
        "Security model",
        "Voltiq handles accounts, addresses, orders and payment attempts. The security model assumes a hostile "
        "browser and an untrusted network, and keeps payment credentials and card data out of the application.",
    )

    story.append(h2("15.1 Threats that matter"))
    story += table_with_caption(
        [
            ["Threat", "Primary control"],
            ["Account takeover", "Password validators, email verification, secure sessions, suspension middleware."],
            ["Privilege escalation", "Role checks in decorators, ownership checks, administrator-only refunds and role changes."],
            ["Price or stock manipulation", "Server-side cart and order recalculation under row locks."],
            ["Payment forgery", "Signature checks plus gateway status API and exact amount matching."],
            ["Card data exposure", "No card fields, no card storage, hosted gateway pages only."],
            ["Cross-site scripting", "Django autoescaping and explicit escaping in JavaScript-rendered suggestions."],
            ["Cross-site request forgery", "CSRF middleware and POST-only state changes."],
            ["Clickjacking", "X-Frame-Options DENY and frame-ancestors policy at the proxy."],
            ["File upload abuse", "Extension, size and Pillow verification; randomised filenames."],
            ["Brute force and scraping", "DRF throttles, newsletter and resend limits, proxy-level rate limits recommended."],
            ["Data leakage in logs", "No passwords or card data; payment payloads are non-sensitive and truncated."],
        ],
        "Table 15.1 - Threat and control summary.",
        widths=[2.0, 4.0],
        small=True,
    )

    story.append(h2("15.2 Authentication and sessions"))
    story.append(
        p(
            "Passwords are hashed with Django's default PBKDF2 hasher. The validators require at least eight "
            "characters and reject common, numeric-only and user-similar passwords. Sessions are stored in the "
            "database, expire after 14 days and are saved on every request so activity extends the session. The "
            "session cookie is HttpOnly and SameSite=Lax. The CSRF cookie is intentionally not HttpOnly because "
            "the AJAX layer reads it, but it is protected by SameSite and the CSRF token check."
        )
    )
    story.append(
        p(
            "Login redirects use a validated <b>next</b> URL. Logout is POST-only. A suspended or inactive "
            "account is logged out by middleware on its next request, not merely blocked from selected pages. "
            "Email verification is required for checkout, which reduces fake orders and gives support a verified "
            "contact channel."
        )
    )

    story.append(h2("15.3 Authorisation and object ownership"))
    story += bullets(
        [
            "Customer order views filter by the signed-in user; a different customer receives 404, not another "
            "customer's order.",
            "Invoice downloads check ownership or staff membership before streaming the PDF.",
            "Address edit, delete and default actions check that the address belongs to the current user.",
            "Review edit and delete compare the review owner; staff moderation uses the dashboard permission.",
            "Dashboard views are wrapped in staff or admin decorators, including POST actions and CSV exports.",
            "Administrators cannot suspend themselves or change another administrator's role through the customer screen.",
        ]
    )

    story.append(h2("15.4 Payment security"))
    story.append(
        p(
            "The application never accepts or stores card numbers, CVVs, expiry dates or gateway secrets in the "
            "database. eSewa and Khalti are hosted flows. The eSewa signature is computed server-side and compared "
            "with <b>hmac.compare_digest</b>; the Khalti key is sent only in the server-to-server Authorization "
            "header. Both flows verify the amount and order reference against the database and call the provider's "
            "status API. A browser-supplied status alone is never enough. The simulator is disabled unless both "
            "DEBUG and PAYMENT_SIMULATION are true."
        )
    )

    story.append(h2("15.5 Input, output and files"))
    story.append(
        p(
            "All database access goes through the Django ORM, so user input is parameterised. Templates "
            "autoescape by default; the search suggestion renderer builds HTML strings in JavaScript and "
            "explicitly escapes product and category text. Form and model validation covers email, phone, "
            "postal code, prices, quantities and image types. Uploads are size-limited and opened with Pillow "
            "before being accepted. Filenames are randomised to prevent collisions and predictable paths."
        )
    )
    story += callout(
        "Uploads are not a virus scanner",
        "Pillow verifies that a file is a readable image, and extension and size checks reduce abuse, but there "
        "is no antivirus or content disarm service. If untrusted staff uploads are a concern, add a scanning "
        "step or restrict uploads to trusted operators.",
        "info",
    )

    story.append(h2("15.6 Transport and browser hardening"))
    story += table_with_caption(
        [
            ["Setting", "Local default", "Production target"],
            ["DEBUG", "True", "False"],
            ["SECURE_SSL_REDIRECT", "False", "True behind HTTPS"],
            ["SESSION_COOKIE_SECURE", "False", "True"],
            ["CSRF_COOKIE_SECURE", "False", "True"],
            ["SECURE_HSTS_SECONDS", "0", "31536000 after HTTPS is proven"],
            ["SECURE_CONTENT_TYPE_NOSNIFF", "True", "True"],
            ["SECURE_REFERRER_POLICY", "strict-origin-when-cross-origin", "Keep"],
            ["X_FRAME_OPTIONS", "DENY", "Keep"],
            ["SECURE_PROXY_SSL_HEADER", "X-Forwarded-Proto https", "Set by the reverse proxy"],
        ],
        "Table 15.2 - Browser and transport settings.",
        widths=[1.8, 2.1, 2.1],
        small=True,
        mono_columns={0},
    )

    story.append(h2("15.7 Rate limiting and abuse"))
    story += bullets(
        [
            "Newsletter subscription: 5 POSTs per IP per minute.",
            "Verification resend: 5 POSTs per user per hour.",
            "DRF endpoints: 120 requests per minute anonymous and 300 per minute authenticated.",
            "Catalogue suggestions require at least two characters and return at most six products.",
            "The login view itself has no application-level rate limit in this build. Put a proxy limit or "
            "django-axes in front of it before exposing the site publicly.",
            "The contact form is not rate-limited. A public deployment should add a challenge or proxy limit.",
        ]
    )

    story.append(h2("15.8 Secrets and deployment checks"))
    story.append(
        p(
            "Secrets live in <b>.env</b>, which is ignored by Git. The development fallback secret starts with "
            "<b>django-insecure-</b> and must never be used in production. Generate a 64-byte URL-safe key and "
            "store it in the host's secret manager or a permission-restricted environment file. The local "
            "<b>manage.py check --deploy</b> reports six expected warnings because DEBUG, HSTS, SSL redirect, the "
            "development secret and secure cookies are intentionally local-only. Fix all six before launch."
        )
    )
    story += code_block(
        """
WARNINGS reported locally by check --deploy:
  W004  SECURE_HSTS_SECONDS is 0
  W008  SECURE_SSL_REDIRECT is not True
  W009  SECRET_KEY is the development fallback
  W012  SESSION_COOKIE_SECURE is not True
  W016  CSRF_COOKIE_SECURE is not True
  W018  DEBUG is True
        """.strip(),
        "Code block 15.1 - The six deployment warnings expected on a local machine.",
    )

    story.append(h2("15.9 Known security gaps"))
    story += bullets(
        [
            "No application-level login throttling or account lockout.",
            "No two-factor authentication.",
            "No Content-Security-Policy header by default; add one at the proxy after auditing inline scripts and Google Fonts.",
            "No antivirus scanning for uploaded images.",
            "No automated secret rotation.",
            "No formal penetration test or vulnerability disclosure process.",
            "The review endpoint is login-gated rather than purchase-gated, as noted in Chapter 11.",
        ]
    )

    # ------------------------------------------------------------------
    # 16. Performance and reliability
    # ------------------------------------------------------------------
    story += chapter(
        "16",
        "Performance, caching and reliability",
        "The application is deliberately modest: a relational database, server-rendered pages, small vanilla "
        "scripts and a process-local cache. This chapter explains what is optimised and where the limits are.",
    )

    story.append(h2("16.1 Query design"))
    story += bullets(
        [
            "<b>select_related</b> is used for category and brand joins on product listings and for order users, "
            "coupons and shipping methods.",
            "<b>prefetch_related</b> loads images, specifications, approved reviews and status history in batches.",
            "Product cards use denormalised rating, sales and discount values instead of aggregate subqueries.",
            "The catalogue annotates effective price and discount percentage in SQL, so sorting happens in the "
            "database rather than in Python.",
            "Pagination is 24 products per page; dashboard tables are paginated at 20 rows.",
            "The order detail page loads items, payments, status history and stock changes with related objects.",
        ]
    )

    story.append(h2("16.2 Caching"))
    story.append(
        p(
            "The home page dataset is cached for 180 seconds under a versioned key. Product, image, category, "
            "brand and review signals clear the relevant cache entries. The default cache is Django's "
            "process-local memory cache with a 300-second timeout. This is fast for a single process but is not "
            "shared between Gunicorn workers."
        )
    )
    story += callout(
        "Use Redis before scaling workers",
        "With LocMemCache, each Gunicorn worker has its own cache and invalidation only affects the worker that "
        "handles the change. For multi-worker production, configure Redis or Memcached as Django's cache backend "
        "and keep the same invalidation signals. The current code does not read a cache URL from the "
        "environment, so this is a deployment change, not a settings toggle.",
        "warning",
    )

    story.append(h2("16.3 Static and media"))
    story.append(
        p(
            "With <b>DEBUG=False</b>, WhiteNoise serves compressed, hashed static files from the manifest storage "
            "backend. <b>collectstatic</b> must run on every deploy that changes CSS, JavaScript or static images. "
            "Uploaded product images live under <b>media/</b> and are served by Nginx in the reference deployment. "
            "The application does not generate thumbnails or convert images to WebP; original uploads are served."
        )
    )

    story.append(h2("16.4 Concurrency and transactions"))
    story.append(
        p(
            "The order, payment, inventory and cancellation paths use database transactions and row locks. "
            "PostgreSQL is the production target because it provides real <b>select_for_update</b> semantics. "
            "SQLite is suitable for development and tests but serialises writes and is not the production "
            "recommendation. The unique successful-payment constraint and the stock non-negative rule provide "
            "database-level backstops even if application logic is changed later."
        )
    )

    story.append(h2("16.5 Known performance limits"))
    story += bullets(
        [
            "No asynchronous task queue. Order and status emails are sent in the request process after commit.",
            "No Redis or shared cache in the default configuration.",
            "No image resizing or CDN integration for user uploads.",
            "No full-text search engine; search is <b>icontains</b> over several columns and will slow down at "
            "very large catalogue sizes.",
            "No database read replica or connection pooler.",
            "No load, stress or soak test results are included in this manual.",
        ]
    )
    story.append(
        p(
            "The scaling path is straightforward: move the cache to Redis, move email to a queue, add a CDN or "
            "object storage for media, add a search index for large catalogues and put PgBouncer in front of "
            "PostgreSQL. None of those changes are required for a small Nepali store, but they are the correct "
            "next steps when traffic grows."
        )
    )

    # ------------------------------------------------------------------
    # 17. Configuration
    # ------------------------------------------------------------------
    story += chapter(
        "17",
        "Configuration and environment variables",
        "All deployment-specific values come from environment variables read by python-decouple. No secrets are "
        "committed to the repository.",
    )

    story.append(h2("17.1 How configuration is loaded"))
    story.append(
        p(
            "The settings module reads the project-root <b>.env</b> file through <b>python-decouple</b>. "
            "Comma-separated values use <b>Csv()</b>, booleans accept common truthy strings and integers are cast. "
            "The committed <b>.env.example</b> targets PostgreSQL; the local <b>.env</b> used for development "
            "sets <b>DB_ENGINE=sqlite</b>, <b>DEBUG=True</b> and <b>PAYMENT_SIMULATION=True</b>. Never commit the "
            "real <b>.env</b>."
        )
    )
    story += code_block(
        """
# Local development profile (SQLite, simulator enabled)
DEBUG=True
SECRET_KEY=local-development-only
ALLOWED_HOSTS=localhost,127.0.0.1,[::1],testserver
SITE_URL=http://127.0.0.1:8000
DB_ENGINE=sqlite
PAYMENT_SIMULATION=True
EMAIL_HOST=
        """.strip(),
        "Code block 17.1 - A minimal local .env.",
    )

    story.append(h2("17.2 Full variable reference"))
    story += table_with_caption(
        [
            ["Variable", "Default", "Purpose"],
            ["SECRET_KEY", "Development fallback", "Cryptographic signing; replace in production."],
            ["DEBUG", "True", "Debug pages and development behaviour; false in production."],
            ["ALLOWED_HOSTS", "localhost,127.0.0.1,[::1],testserver", "Accepted Host headers."],
            ["SITE_NAME", "Voltiq", "Brand name used in templates and email."],
            ["SITE_URL", "http://127.0.0.1:8000", "Absolute links in email and robots.txt."],
            ["SUPPORT_EMAIL", "support@voltiq.com.np", "Support address in content and invoices."],
            ["DEFAULT_FROM_EMAIL", "Voltiq no-reply address", "Outgoing sender."],
            ["DB_ENGINE", "sqlite", "sqlite or postgres."],
            ["DB_NAME", "voltiq", "PostgreSQL database name."],
            ["DB_USER", "postgres", "PostgreSQL user."],
            ["DB_PASSWORD", "postgres", "PostgreSQL password."],
            ["DB_HOST", "127.0.0.1", "PostgreSQL host."],
            ["DB_PORT", "5432", "PostgreSQL port."],
            ["DB_CONN_MAX_AGE", "60", "Persistent connection seconds."],
            ["CSRF_TRUSTED_ORIGINS", "localhost:8000 origins", "Trusted HTTPS origins for CSRF."],
            ["SECURE_SSL_REDIRECT", "False", "Redirect HTTP to HTTPS."],
            ["SESSION_COOKIE_SECURE", "False", "Secure-only session cookie."],
            ["CSRF_COOKIE_SECURE", "False", "Secure-only CSRF cookie."],
            ["SECURE_HSTS_SECONDS", "0", "HSTS max-age."],
            ["SECURE_HSTS_INCLUDE_SUBDOMAINS", "False", "HSTS subdomain coverage."],
            ["SECURE_HSTS_PRELOAD", "False", "HSTS preload flag."],
            ["MAX_UPLOAD_SIZE_MB", "5", "Image upload size limit."],
            ["EMAIL_HOST", "empty", "SMTP host; empty uses console email."],
            ["EMAIL_PORT", "587", "SMTP port."],
            ["EMAIL_USE_TLS", "True", "STARTTLS."],
            ["EMAIL_USE_SSL", "False", "Implicit TLS."],
            ["EMAIL_HOST_USER", "empty", "SMTP username."],
            ["EMAIL_HOST_PASSWORD", "empty", "SMTP password."],
            ["FREE_SHIPPING_THRESHOLD", "10000", "Default free-shipping subtotal."],
            ["DEFAULT_SHIPPING_FEE", "250", "Default delivery fee."],
            ["PAYMENT_TIMEOUT_MINUTES", "30", "Stale payment attempt threshold."],
            ["PAYMENT_SIMULATION", "DEBUG", "Enable the sandbox simulator."],
            ["ESEWA_MODE", "sandbox", "Label for the eSewa environment."],
            ["ESEWA_PRODUCT_CODE", "EPAYTEST", "eSewa merchant product code."],
            ["ESEWA_SECRET_KEY", "empty", "eSewa HMAC secret."],
            ["ESEWA_INIT_URL", "sandbox form URL", "eSewa payment form endpoint."],
            ["ESEWA_STATUS_URL", "sandbox status URL", "eSewa transaction status endpoint."],
            ["KHALTI_MODE", "sandbox", "Label for the Khalti environment."],
            ["KHALTI_SECRET_KEY", "empty", "Khalti merchant key."],
            ["KHALTI_INIT_URL", "sandbox initiate URL", "Khalti initiate endpoint."],
            ["KHALTI_LOOKUP_URL", "sandbox lookup URL", "Khalti lookup endpoint."],
            ["KHALTI_WEBSITE_URL", "SITE_URL", "Website URL sent to Khalti."],
            ["BANK_NAME", "Nabil Bank", "Bank instruction heading."],
            ["BANK_ACCOUNT_NAME", "Voltiq Electronics Pvt. Ltd.", "Account holder."],
            ["BANK_ACCOUNT_NUMBER", "empty", "Account number shown to customers."],
            ["BANK_BRANCH", "Durbar Marg, Kathmandu", "Branch shown to customers."],
            ["BANK_SWIFT", "empty", "SWIFT code."],
            ["BANK_SUPPORT_NOTE", "Email the deposit slip...", "Bank transfer instructions."],
            ["STRIPE_SECRET_KEY", "empty", "Reserved; no Stripe gateway is implemented."],
            ["STRIPE_PUBLISHABLE_KEY", "empty", "Reserved; no Stripe gateway is implemented."],
        ],
        "Table 17.1 - Environment variables read by config/settings.py.",
        widths=[1.75, 2.0, 2.25],
        small=True,
        mono_columns={0},
    )

    story.append(h2("17.3 Environment profiles"))
    story += table_with_caption(
        [
            ["Concern", "Local development", "Production"],
            ["Database", "SQLite file", "PostgreSQL with a dedicated user"],
            ["Debug", "True", "False"],
            ["Payments", "Simulator on; no credentials needed", "Real eSewa/Khalti credentials; simulation off"],
            ["Email", "Console backend", "SMTP provider with a verified sender"],
            ["Static", "Django static serving", "WhiteNoise plus Nginx"],
            ["Media", "Django media serving", "Nginx or object storage"],
            ["Cache", "LocMemCache", "Redis or Memcached recommended"],
            ["HTTPS", "HTTP localhost", "TLS with secure cookies and HSTS"],
            ["Logs", "Console", "Console plus rotating file or log service"],
        ],
        "Table 17.2 - Local and production profiles.",
        widths=[1.2, 2.6, 2.2],
        small=True,
    )

    story.append(h2("17.4 Generating a production secret"))
    story += code_block(
        """
python -c "import secrets; print(secrets.token_urlsafe(64))"
        """.strip(),
        "Code block 17.2 - Generate a strong SECRET_KEY. Store it in the host secret manager, not in Git.",
    )
    story.append(
        p(
            "Changing <b>SECRET_KEY</b> invalidates sessions and password-reset links. Rotate it during a "
            "maintenance window if possible. Changing <b>SITE_URL</b> changes email links under the console "
            "backend and the robots sitemap line, so update it together with <b>ALLOWED_HOSTS</b> and "
            "<b>CSRF_TRUSTED_ORIGINS</b>."
        )
    )

    # ------------------------------------------------------------------
    # 18. Local setup
    # ------------------------------------------------------------------
    story += chapter(
        "18",
        "Local setup",
        "This chapter takes a clean Windows machine to a working Voltiq storefront with demo data, using SQLite "
        "so PostgreSQL is not required for the first run.",
    )

    story.append(h2("18.1 Prerequisites"))
    story += table_with_caption(
        [
            ["Requirement", "Recommended", "Check"],
            ["Python", "3.12 or newer", "python --version"],
            ["pip", "Bundled with Python", "python -m pip --version"],
            ["Git", "Latest", "git --version"],
            ["PowerShell", "Windows PowerShell 5.1 or PowerShell 7", "Automatic activation may be blocked by policy."],
            ["PostgreSQL", "Optional for local SQLite run; required for production", "psql --version"],
            ["Internet", "Needed to download packages and demo product images", "Only for setup."],
        ],
        "Table 18.1 - Local prerequisites.",
        widths=[1.35, 2.75, 1.9],
        small=True,
    )

    story.append(h2("18.2 Create the virtual environment"))
    story += code_block(
        """
cd C:\\Users\\Krijan\\Desktop\\ecommerce
py -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
        """.strip(),
        "Code block 18.1 - Create and activate the virtual environment on Windows.",
    )
    story.append(
        p(
            "If PowerShell blocks activation, run <b>Set-ExecutionPolicy -Scope CurrentUser "
            "RemoteSigned</b> once, or call the interpreter directly as "
            "<b>.\\.venv\\Scripts\\python.exe</b> without activating. The project commands in this manual use the "
            "direct interpreter path so they work in either case."
        )
    )

    story.append(h2("18.3 Configure the environment"))
    story += code_block(
        """
Copy-Item .env.example .env
# Edit .env and set:
DEBUG=True
DB_ENGINE=sqlite
PAYMENT_SIMULATION=True
EMAIL_HOST=
        """.strip(),
        "Code block 18.2 - Create the local .env. The example file defaults to PostgreSQL.",
    )
    story.append(
        p(
            "The local profile deliberately uses SQLite. It also enables the payment simulator so the checkout can "
            "be demonstrated without eSewa or Khalti credentials. The console email backend prints verification "
            "and password-reset links in the terminal. The development secret in the example is not safe for "
            "production."
        )
    )

    story.append(h2("18.4 Migrate and seed"))
    story += code_block(
        """
.\\.venv\\Scripts\\python.exe manage.py migrate
.\\.venv\\Scripts\\python.exe manage.py seed_store
.\\.venv\\Scripts\\python.exe manage.py runserver 127.0.0.1:8000 --noreload
        """.strip(),
        "Code block 18.3 - Create the schema, load demo data and start the development server.",
    )
    story.append(
        p(
            "Open <b>http://127.0.0.1:8000/</b>. The seed command prints the demo accounts and catalogue counts. "
            "The first request may be slower while Django compiles templates and the home page cache fills. "
            "Product images are downloaded during seeding; if the download fails, the command generates a "
            "placeholder so the storefront still renders."
        )
    )
    story += callout(
        "Use --noreload for screenshots and debugging",
        "The auto-reloader can restart the process in the middle of a headless screenshot or a long test. "
        "<b>--noreload</b> keeps one process alive. Restart manually after changing Python code.",
        "info",
    )

    story.append(h2("18.5 Verify the installation"))
    story += code_block(
        """
.\\.venv\\Scripts\\python.exe manage.py check
.\\.venv\\Scripts\\python.exe manage.py showmigrations
.\\.venv\\Scripts\\python.exe manage.py test
.\\.venv\\Scripts\\python.exe manage.py collectstatic --noinput
        """.strip(),
        "Code block 18.4 - Quality and asset checks.",
    )
    story.append(
        p(
            "A healthy local installation reports zero issues from <b>check</b>, all migrations applied, the full "
            "test suite passing and 165 static files copied. The exact static count can change when assets are "
            "added. <b>collectstatic</b> is not required for the development server, but running it catches "
            "manifest and missing-file problems early."
        )
    )

    story.append(h2("18.6 First sign-in"))
    story += table_with_caption(
        [
            ["Role", "Email", "Password", "Landing page"],
            ["Administrator", "admin@voltiq.com", "Admin@12345", "/dashboard/"],
            ["Staff", "staff@voltiq.com", "Staff@12345", "/dashboard/"],
            ["Customer", "aarav.sharma@example.com", "Customer@12345", "/accounts/account/"],
        ],
        "Table 18.2 - Demo accounts created by seed_store.",
        widths=[1.0, 2.0, 1.4, 1.6],
        small=True,
        mono_columns={1, 2, 3},
    )
    story.append(
        p(
            "All seeded accounts are email-verified so checkout works immediately. The administrator can access "
            "both <b>/dashboard/</b> and <b>/django-admin/</b>. Staff can use the dashboard but cannot change "
            "roles, suspend customers or issue refunds. The customer account has addresses, orders, reviews, "
            "notifications and wishlist data."
        )
    )

    story.append(h2("18.7 Common setup problems"))
    story += table_with_caption(
        [
            ["Symptom", "Cause", "Fix"],
            ["python is not recognized", "Python is not on PATH.", "Reinstall Python with the PATH option, or use the py launcher."],
            ["Activate.ps1 cannot be loaded", "PowerShell execution policy.", "Set RemoteSigned for the current user, or call the interpreter directly."],
            ["No module named django", "The virtual environment is not active or packages were installed globally.", "Activate .venv and run pip install -r requirements.txt."],
            ["No such table", "Migrations were not applied.", "Run migrate."],
            ["Empty storefront", "Seed data was not loaded.", "Run seed_store."],
            ["Images are missing", "Seed download failed or media was deleted.", "Re-run seed_store, or inspect media/products."],
            ["Payment page has no online methods", "No credentials and simulation is off.", "Set PAYMENT_SIMULATION=True locally, or configure credentials."],
            ["Verification email did not arrive", "No SMTP host is configured.", "Use the link printed in the terminal, or configure SMTP."],
        ],
        "Table 18.3 - Local setup troubleshooting.",
        widths=[1.6, 2.5, 1.9],
        small=True,
    )

    # ------------------------------------------------------------------
    # 19. PostgreSQL and pgAdmin
    # ------------------------------------------------------------------
    story += chapter(
        "19",
        "PostgreSQL and pgAdmin",
        "SQLite is the local fallback. Production uses PostgreSQL, and pgAdmin is a convenient way to create the "
        "database, inspect tables and take backups.",
    )

    story.append(h2("19.1 Install PostgreSQL"))
    story.append(
        p(
            "Install the official PostgreSQL bundle, which includes the server, pgAdmin 4 and the command-line "
            "tools <b>psql</b>, <b>pg_dump</b> and <b>pg_restore</b>. Remember the <b>postgres</b> superuser "
            "password and the port, usually 5432. Keep the service running and add the <b>bin</b> directory to "
            "PATH if you want short commands."
        )
    )

    story.append(h2("19.2 Create a dedicated database and user"))
    story += code_block(
        """
CREATE USER voltiq_user WITH PASSWORD 'choose-a-strong-password';
CREATE DATABASE voltiq OWNER voltiq_user ENCODING 'UTF8';

-- If the schema is not owned by the application user:
\\c voltiq
GRANT ALL ON SCHEMA public TO voltiq_user;
ALTER SCHEMA public OWNER TO voltiq_user;
        """.strip(),
        "Code block 19.1 - SQL for a dedicated Voltiq database. Do not use the postgres superuser for the app.",
    )
    story.append(
        p(
            "In pgAdmin, expand <b>Servers</b>, open the local server, right-click <b>Login/Group Roles</b> and "
            "create a login role with <b>Can login?</b> enabled. Then right-click <b>Databases</b>, create "
            "<b>voltiq</b> with <b>voltiq_user</b> as owner, encoding UTF8. The GUI is equivalent to the SQL above."
        )
    )

    story.append(h2("19.3 Connect Django"))
    story += code_block(
        """
DB_ENGINE=postgres
DB_NAME=voltiq
DB_USER=voltiq_user
DB_PASSWORD=choose-a-strong-password
DB_HOST=127.0.0.1
DB_PORT=5432
DB_CONN_MAX_AGE=60
        """.strip(),
        "Code block 19.2 - PostgreSQL section of .env.",
    )
    story += code_block(
        """
.\\.venv\\Scripts\\python.exe manage.py migrate
.\\.venv\\Scripts\\python.exe manage.py seed_store
.\\.venv\\Scripts\\python.exe manage.py check
        """.strip(),
        "Code block 19.3 - Create the schema and demo data in PostgreSQL.",
    )
    story.append(
        p(
            "After migration, pgAdmin should show tables such as <b>accounts_user</b>, <b>products_product</b>, "
            "<b>orders_order</b>, <b>orders_orderitem</b>, <b>payments_payment</b> and "
            "<b>payments_paymenttransaction</b>. Table names follow Django's default "
            "<b>&lt;app&gt;_&lt;model&gt;</b> convention. The custom user table is <b>accounts_user</b>, not "
            "<b>auth_user</b>."
        )
    )

    story.append(h2("19.4 Useful pgAdmin queries"))
    story += code_block(
        """
-- Recent orders
SELECT order_number, status, payment_status, payment_method, total, created_at
FROM orders_order
ORDER BY created_at DESC
LIMIT 20;

-- Low-stock products
SELECT sku, name, stock_quantity, low_stock_threshold
FROM products_product
WHERE stock_quantity <= low_stock_threshold
ORDER BY stock_quantity;

-- Successful payments
SELECT p.transaction_ref, p.gateway, p.amount, p.status, o.order_number
FROM payments_payment p
JOIN orders_order o ON o.id = p.order_id
WHERE p.status = 'success'
ORDER BY p.completed_at DESC;
        """.strip(),
        "Code block 19.4 - Operational queries in the pgAdmin Query Tool.",
    )

    story.append(h2("19.5 Backup and restore"))
    story.append(
        p(
            "A database backup does not include uploaded product images. Back up both the database and the "
            "media directory. The custom or tar format preserves the schema and data and can be restored with "
            "pg_restore."
        )
    )
    story += code_block(
        """
# Backup
& "C:\\Program Files\\PostgreSQL\\16\\bin\\pg_dump.exe" `
  -h 127.0.0.1 -p 5432 -U voltiq_user -F c `
  -f "C:\\backups\\voltiq-2026-11-18.backup" voltiq

# Restore into an empty database
& "C:\\Program Files\\PostgreSQL\\16\\bin\\pg_restore.exe" `
  -h 127.0.0.1 -p 5432 -U voltiq_user `
  -d voltiq --clean --if-exists "C:\\backups\\voltiq-2026-11-18.backup"
        """.strip(),
        "Code block 19.5 - Command-line backup and restore.",
    )
    story.append(
        p(
            "In pgAdmin, right-click the database and choose <b>Backup...</b> or <b>Restore...</b>. Use a secure "
            "location, verify the backup file size and test a restore at least once before relying on the "
            "procedure. After a restore, run <b>migrate</b> to apply any newer migrations and <b>check</b> to "
            "confirm the application starts cleanly."
        )
    )

    story.append(h2("19.6 Production database rules"))
    story += bullets(
        [
            "Use a dedicated application user, not the postgres superuser.",
            "Use a long, unique password stored in .env or a secret manager.",
            "Restrict network access; never expose PostgreSQL directly to the internet.",
            "Require TLS for remote connections and allow only the application server IP.",
            "Schedule daily backups, keep several generations and monitor backup failures.",
            "Run <b>VACUUM</b> and <b>ANALYZE</b> as needed, and monitor slow queries and connection counts.",
            "Test the restore procedure, not only the backup command.",
        ]
    )

    # ------------------------------------------------------------------
    # 20. Demo data
    # ------------------------------------------------------------------
    story += chapter(
        "20",
        "Seeding and demo data",
        "The seed_store management command builds a coherent demo store: catalogue, people, orders, payments, "
        "reviews, wishlists, coupons and marketing records.",
    )

    story.append(h2("20.1 What the command creates"))
    story += table_with_caption(
        [
            ["Domain", "Current seed content"],
            ["Catalogue", "21 categories, 18 brands, 26 products and per-category specification values."],
            ["Media", "One primary product image per product, downloaded or generated as a placeholder."],
            ["People", "9 users: 1 administrator, 1 staff member and 7 customers, all email-verified."],
            ["Addresses", "Kathmandu, Lalitpur, Bhaktapur, Pokhara and other Nepali addresses."],
            ["Sales", "14 orders across statuses and payment methods, with items, status history, payments and coupon usage."],
            ["Reviews", "17 approved reviews, including verified-purchase badges."],
            ["Engagement", "Wishlist entries, newsletter subscribers, contact messages and notifications."],
            ["Commerce rules", "3 shipping methods and 3 coupons."],
            ["Content", "Site settings, announcement text and store contact details."],
        ],
        "Table 20.1 - Demo data domains.",
        widths=[1.2, 4.8],
        small=True,
    )
    story.append(
        p(
            "Amounts, dates and statuses are internally consistent. The overview charts show realistic movement "
            "because order timestamps are spread across recent weeks. Product sales counts and ratings are "
            "updated from the seeded orders and reviews, so bestseller and top-rated sections have content."
        )
    )

    story.append(h2("20.2 Command options and idempotency"))
    story += code_block(
        """
.\\.venv\\Scripts\\python.exe manage.py seed_store
.\\.venv\\Scripts\\python.exe manage.py seed_store --skip-images
        """.strip(),
        "Code block 20.1 - Seed with or without remote image downloads.",
    )
    story.append(
        p(
            "The command is idempotent for catalogue, brands, specification fields, shipping, coupons and users: "
            "it uses <b>update_or_create</b> and updates stale demo content. Orders are identified by an internal "
            "seed marker and skipped on a second run. Images are only downloaded when a product has no image. "
            "The whole seed runs inside a transaction, so a failure does not leave a half-built catalogue."
        )
    )
    story += callout(
        "Seeding is not a migration",
        "Never run seed_store automatically in a production deployment. It is for development, staging and "
        "demonstrations. On production, create an administrator with <b>createsuperuser</b> and load the real "
        "catalogue through the dashboard or a controlled import.",
        "warning",
    )

    story.append(h2("20.3 Demo accounts"))
    story += table_with_caption(
        [
            ["Account", "Password", "Use"],
            ["admin@voltiq.com", "Admin@12345", "Full dashboard, Django admin, roles, refunds and settings."],
            ["staff@voltiq.com", "Staff@12345", "Fulfilment, catalogue, inventory, reviews and reports without admin-only actions."],
            ["aarav.sharma@example.com", "Customer@12345", "Customer with orders, addresses, reviews and notifications."],
        ],
        "Table 20.2 - Primary demo accounts.",
        widths=[2.1, 1.3, 2.6],
        small=True,
        mono_columns={0, 1},
    )
    story.append(
        p(
            "The remaining customers use the same <b>Customer@12345</b> password. All demo credentials are "
            "published in the README and this manual, so they must be removed or rotated before a public launch. "
            "The seed command intentionally does not create a hidden backdoor; it creates ordinary accounts with "
            "known passwords."
        )
    )

    story.append(h2("20.4 Resetting a demo database"))
    story.append(
        p(
            "To rebuild the SQLite demo from scratch, stop the server, delete the database file and the generated "
            "product media, then migrate and seed again. This destroys all local data and should only be done in "
            "development."
        )
    )
    story += code_block(
        """
# Destructive: local development only
Remove-Item db.sqlite3
Remove-Item -Recurse -Force media\\products
.\\.venv\\Scripts\\python.exe manage.py migrate
.\\.venv\\Scripts\\python.exe manage.py seed_store
        """.strip(),
        "Code block 20.2 - Rebuild the SQLite demo. Back up anything you need first.",
    )
    story.append(
        p(
            "For PostgreSQL, drop and recreate the database in pgAdmin, or use <b>DROP DATABASE voltiq</b> "
            "followed by <b>CREATE DATABASE voltiq OWNER voltiq_user</b>. Migrating after a drop recreates the "
            "schema. Never run this against a database that contains real orders."
        )
    )

    # ------------------------------------------------------------------
    # 21. Testing
    # ------------------------------------------------------------------
    story += chapter(
        "21",
        "Testing and quality assurance",
        "Voltiq ships with a Django test suite covering the business rules that are most expensive to get wrong: "
        "stock, totals, coupons, permissions, payment verification and order state.",
    )

    story.append(h2("21.1 Running the suite"))
    story += code_block(
        """
.\\.venv\\Scripts\\python.exe manage.py test
.\\.venv\\Scripts\\python.exe manage.py test apps.orders --verbosity 2
.\\.venv\\Scripts\\python.exe manage.py test --keepdb
        """.strip(),
        "Code block 21.1 - Run all tests, one app or reuse the test database.",
    )
    story.append(
        p(
            "The current suite contains <b>151 tests</b> and passes against SQLite. Django creates a temporary "
            "test database, applies migrations and tears it down. <b>--keepdb</b> speeds up repeated runs but can "
            "hide migration problems; use a clean run before a release. Tests must not depend on the development "
            "database or on the seeded demo data."
        )
    )

    story.append(h2("21.2 What is covered"))
    story += table_with_caption(
        [
            ["Area", "Representative coverage"],
            ["Accounts", "Registration, duplicate email, email verification, login redirect safety, profile and address permissions."],
            ["Catalogue", "Product model pricing and slug rules, active/in-stock queries, search, filters, sorting, detail access."],
            ["Cart", "Guest and user carts, add/update/remove, quantity limits, stock conflicts, coupon application and merge."],
            ["Checkout and orders", "Step guards, totals, coupon revalidation, atomic stock deduction, cancellation, reorder and invoice access."],
            ["Payments", "Initiation, simulation gating, duplicate success, amount mismatch, COD collection and refund recording."],
            ["Inventory", "Adjustment audit, negative-stock rejection, restock notification and cancellation restoration."],
            ["Reviews", "One review per user, verified-purchase flag, rating aggregation, edit/delete ownership."],
            ["Dashboard", "Staff and admin permissions, analytics access, product and order actions, CSV exports."],
            ["Core", "Home, policy pages, newsletter, contact, health endpoint, error handlers and SEO files."],
        ],
        "Table 21.1 - Test coverage by domain.",
        widths=[1.35, 4.65],
        small=True,
    )

    story.append(h2("21.3 Test helpers"))
    story.append(
        p(
            "Shared factories live in <b>apps/core/testing.py</b>. <b>make_user()</b>, <b>make_product()</b> and "
            "<b>make_order()</b> create the minimum coherent objects for a test, including verified users and "
            "order items. Tests use Django's <b>TestCase</b> transactions, <b>force_login</b> and the test client. "
            "They assert both the HTTP response and the database state, because a redirect alone does not prove "
            "that the right rows were written."
        )
    )

    story.append(h2("21.4 Quality gates"))
    story += code_block(
        """
.\\.venv\\Scripts\\python.exe manage.py check
.\\.venv\\Scripts\\python.exe manage.py makemigrations --check --dry-run
.\\.venv\\Scripts\\python.exe manage.py test
.\\.venv\\Scripts\\python.exe manage.py collectstatic --noinput
.\\.venv\\Scripts\\python.exe manage.py check --deploy
        """.strip(),
        "Code block 21.2 - Commands to run before a release.",
    )
    story += bullets(
        [
            "<b>check</b> must report zero issues.",
            "<b>makemigrations --check</b> must report no missing migrations.",
            "The full test suite must pass.",
            "collectstatic must succeed with DEBUG=False, because the manifest storage raises on missing files.",
            "check --deploy must be reviewed; the six local warnings must be resolved in production.",
        ]
    )

    story.append(h2("21.5 Manual acceptance pass"))
    story += numbered(
        [
            "Register a new account, open the console verification link and confirm the pending banner clears.",
            "Add a product as a guest, sign in, and confirm the guest cart merged rather than disappearing.",
            "Apply a valid and an invalid coupon; confirm the discount and the error copy.",
            "Complete checkout with the simulator, then open the order, invoice and tracking pages.",
            "Cancel an eligible order and confirm stock returns and the status history records it.",
            "Submit a review as a purchaser and confirm the verified badge and rating change.",
            "Sign in as staff and move an order through processing, shipped and delivered.",
            "Sign in as a customer and confirm the order is not visible to another customer.",
            "Open the dashboard reports, change the date range and export CSV.",
            "Visit /health/ and confirm JSON ok; temporarily stop the database to confirm degraded.",
        ]
    )

    story.append(h2("21.6 What is not tested"))
    story += bullets(
        [
            "No browser end-to-end suite such as Playwright or Selenium.",
            "No live eSewa or Khalti sandbox test in the repository; the simulator covers the local flow.",
            "No PostgreSQL-specific test run in the default suite; production SQL behaviour is documented but "
            "not exercised locally.",
            "No load, stress or soak test.",
            "No formal accessibility audit or cross-browser matrix.",
            "No automated screenshot regression for the storefront or dashboard.",
        ]
    )
    story.append(
        p(
            "These gaps do not invalidate the suite; they define the boundary of the evidence. A production "
            "launch should add a PostgreSQL CI job, a payment sandbox smoke test and a small browser smoke suite "
            "for registration, checkout and dashboard login."
        )
    )

    # ------------------------------------------------------------------
    # 22. Deployment
    # ------------------------------------------------------------------
    story += chapter(
        "22",
        "Deployment",
        "The reference deployment is a single Linux server running PostgreSQL, Gunicorn and Nginx. The application "
        "is stateless apart from the database and uploaded media, so it can also run on a managed platform.",
    )

    story.append(h2("22.1 Production topology"))
    story += code_block(
        """
Internet
   | HTTPS
   v
Nginx / reverse proxy
   |-- /static/  -> /srv/voltiq/staticfiles/
   |-- /media/   -> /srv/voltiq/media/
   |-- /         -> Gunicorn -> Django (WSGI)
                              |-- PostgreSQL
                              |-- SMTP provider
                              |-- eSewa / Khalti APIs
        """.strip(),
        "Code block 22.1 - Reference production topology. No WebSocket or Channels service is required.",
    )
    story.append(
        p(
            "Nginx terminates TLS, redirects HTTP, serves static and media files and proxies application requests "
            "to Gunicorn on a loopback port. PostgreSQL, the SMTP provider and the payment gateways are outbound "
            "dependencies. The application itself does not store sessions in memory, so multiple Gunicorn "
            "workers can run behind the proxy."
        )
    )

    story.append(h2("22.2 Server preparation"))
    story += code_block(
        """
sudo apt update
sudo apt install -y python3 python3-venv python3-pip postgresql nginx git
sudo useradd --system --create-home --shell /bin/bash voltiq
sudo mkdir -p /srv/voltiq
sudo chown voltiq:voltiq /srv/voltiq
        """.strip(),
        "Code block 22.2 - Ubuntu packages and application user.",
    )
    story.append(
        p(
            "Deploy the code to <b>/srv/voltiq</b> with Git, rsync or a CI artifact. Create a virtual environment "
            "owned by the application user, install <b>requirements.txt</b> and add Gunicorn. Keep the "
            "<b>.env</b> outside version control and readable only by the application user."
        )
    )

    story.append(h2("22.3 Production environment"))
    story += code_block(
        """
DEBUG=False
SECRET_KEY=replace-with-a-64-byte-random-secret
ALLOWED_HOSTS=voltiq.com.np,www.voltiq.com.np
SITE_NAME=Voltiq
SITE_URL=https://voltiq.com.np
CSRF_TRUSTED_ORIGINS=https://voltiq.com.np,https://www.voltiq.com.np

DB_ENGINE=postgres
DB_NAME=voltiq
DB_USER=voltiq_app
DB_PASSWORD=replace-with-a-strong-password
DB_HOST=127.0.0.1
DB_PORT=5432
DB_CONN_MAX_AGE=60

EMAIL_HOST=smtp.yourprovider.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-smtp-user
EMAIL_HOST_PASSWORD=your-smtp-password

PAYMENT_SIMULATION=False
ESEWA_MODE=production
ESEWA_PRODUCT_CODE=your-product-code
ESEWA_SECRET_KEY=your-esewa-secret
KHALTI_MODE=production
KHALTI_SECRET_KEY=your-khalti-secret

SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=False
        """.strip(),
        "Code block 22.3 - A production .env skeleton. Fill every placeholder and keep the file private.",
    )
    story += callout(
        "HSTS is a one-way door",
        "Do not enable a one-year HSTS policy until HTTPS works correctly for the apex domain, the www host and "
        "any subdomain you intend to keep. If a subdomain is still HTTP-only, leave "
        "<b>SECURE_HSTS_INCLUDE_SUBDOMAINS=False</b> until it is migrated. Start with a short max-age while "
        "testing, then raise it.",
        "warning",
    )

    story.append(h2("22.4 Database, schema and static files"))
    story += code_block(
        """
cd /srv/voltiq
source .venv/bin/activate
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
python manage.py check --deploy
        """.strip(),
        "Code block 22.4 - First production build. Do not run seed_store on production.",
    )
    story.append(
        p(
            "The custom user model requires an email address for <b>createsuperuser</b>. The first administrator "
            "can then create staff accounts and load the real catalogue through the dashboard. <b>collectstatic</b> "
            "must succeed with <b>DEBUG=False</b>; the manifest storage will fail the build if a template "
            "references a missing asset. Review every remaining <b>check --deploy</b> warning before continuing."
        )
    )

    story.append(h2("22.5 Gunicorn and systemd"))
    story += code_block(
        """
[Unit]
Description=Voltiq Django application
After=network.target postgresql.service

[Service]
User=voltiq
Group=voltiq
WorkingDirectory=/srv/voltiq
EnvironmentFile=/srv/voltiq/.env
ExecStart=/srv/voltiq/.venv/bin/gunicorn config.wsgi:application \\
    --bind 127.0.0.1:8000 --workers 3 --timeout 60 \\
    --access-logfile - --error-logfile -
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
        """.strip(),
        "Code block 22.5 - /etc/systemd/system/voltiq.service. Adjust workers to the server.",
    )
    story += code_block(
        """
sudo systemctl daemon-reload
sudo systemctl enable --now voltiq
sudo systemctl status voltiq
sudo journalctl -u voltiq -f
        """.strip(),
        "Code block 22.6 - Enable, start and inspect the service.",
    )
    story.append(
        p(
            "A starting point for workers is <b>(2 x CPU cores) + 1</b>. Each worker loads the application "
            "separately, and LocMemCache is per worker, which is another reason to move to Redis before scaling "
            "out. Increase the timeout if PDF invoice generation or large image uploads are slow on the host."
        )
    )

    story.append(h2("22.6 Nginx and TLS"))
    story += code_block(
        """
upstream voltiq_app { server 127.0.0.1:8000; }

server {
    listen 80;
    server_name voltiq.com.np www.voltiq.com.np;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name voltiq.com.np www.voltiq.com.np;

    ssl_certificate     /etc/letsencrypt/live/voltiq.com.np/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/voltiq.com.np/privkey.pem;

    client_max_body_size 15m;

    location /static/ {
        alias /srv/voltiq/staticfiles/;
        expires 30d;
        access_log off;
    }
    location /media/ {
        alias /srv/voltiq/media/;
        expires 7d;
    }
    location / {
        proxy_pass http://voltiq_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 70s;
    }
}
        """.strip(),
        "Code block 22.7 - Nginx virtual host. Use Certbot or your certificate manager for the TLS files.",
    )
    story.append(
        p(
            "<b>client_max_body_size</b> must be at least the Django total upload limit. The application sets "
            "<b>DATA_UPLOAD_MAX_MEMORY_SIZE</b> to 15 MB and individual images to 5 MB. The "
            "<b>X-Forwarded-Proto</b> header is what lets Django's <b>SECURE_PROXY_SSL_HEADER</b> recognise "
            "HTTPS behind the proxy. Set <b>X-Forwarded-For</b> so payment audit rows and rate limits see the "
            "real client address."
        )
    )
    story += code_block(
        """
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d voltiq.com.np -d www.voltiq.com.np
        """.strip(),
        "Code block 22.8 - Validate the configuration and obtain a certificate.",
    )

    story.append(h2("22.7 Payment and email go-live"))
    story += table_with_caption(
        [
            ["Step", "Details"],
            ["eSewa", "Set the production product code and secret, verify the form and status URLs with the provider, and register the success/failure callback URLs for the live domain."],
            ["Khalti", "Set the live secret, confirm initiate and lookup URLs, and register the return URL. Test a small live payment before announcing the launch."],
            ["Bank", "Set the real account name, number, branch and SWIFT. Confirm the instructions page shows the correct reference."],
            ["SIM", "Set PAYMENT_SIMULATION=False. Confirm the simulator route returns 404."],
            ["Email", "Send verification, reset and order emails to a real mailbox. Check SPF, DKIM and DMARC."],
            ["Support", "Confirm the support inbox and phone are monitored."],
        ],
        "Table 22.1 - External service launch checks.",
        widths=[1.1, 4.9],
        small=True,
    )
    story += callout(
        "Real gateway testing is mandatory",
        "The local build has been exercised with the simulator and unit tests, not with live eSewa or Khalti "
        "money. Before launch, run a small sandbox transaction through each gateway, inspect the callback and "
        "status lookup, and reconcile the payment row against the order. A successful local simulation is not "
        "evidence that production credentials, callback URLs and signatures are correct.",
        "warning",
    )

    story.append(h2("22.8 Deployment sequence"))
    story += numbered(
        [
            "Back up the database and media, or confirm that the environment is new.",
            "Pull the release, create or update the virtual environment and install requirements.",
            "Run <b>migrate</b> and <b>collectstatic --noinput</b>.",
            "Restart the application service and reload Nginx.",
            "Check <b>/health/</b>, the home page, a product page, login and the dashboard.",
            "Run a small checkout in a staging environment or with a live test payment.",
            "Watch the application log, web server log and payment audit rows for errors.",
            "Record the release commit and the database backup identifier.",
        ]
    )

    story.append(h2("22.9 Rollback"))
    story.append(
        p(
            "Keep the previous release directory or artifact and its virtual environment until the new release is "
            "verified. If the application is broken, point the service back to the previous release, reload and "
            "restart. If a migration changed the schema incompatibly, restoring the database backup may be the "
            "only safe rollback. Test this procedure on staging, not during an outage."
        )
    )
    story += bullets(
        [
            "Code-only rollback: previous release plus the same database.",
            "Schema rollback: restore the pre-deploy database backup and media if needed.",
            "Static rollback: re-run collectstatic from the previous release.",
            "Payment rollback: never delete payment rows; record the incident and reconcile with the provider.",
        ]
    )

    story.append(h2("22.10 Windows Server alternative"))
    story.append(
        p(
            "For a Windows host, install the dependencies into a virtual environment and run Waitress behind IIS "
            "or Nginx. Waitress does not provide process supervision, so use NSSM or a Windows service wrapper. "
            "The Windows path is acceptable for a small internal deployment, but the Linux Gunicorn and systemd "
            "recipe is the primary reference."
        )
    )
    story += code_block(
        """
pip install waitress
waitress-serve --listen=127.0.0.1:8000 config.wsgi:application
        """.strip(),
        "Code block 22.9 - Minimal Waitress launch.",
    )

    # ------------------------------------------------------------------
    # 23. Operations
    # ------------------------------------------------------------------
    story += chapter(
        "23",
        "Operations, backups and logging",
        "A store is not finished at deploy. This chapter is the runbook for the people who process orders, "
        "reconcile payments, watch the logs and keep the data recoverable.",
    )

    story.append(h2("23.1 Daily opening checklist"))
    story += numbered(
        [
            "Open <b>/health/</b> and confirm HTTP 200 with status ok.",
            "Open the dashboard overview and check new orders, failed payments and low-stock counts.",
            "Review the payment attempts from the last 24 hours; confirm every paid order has a successful payment.",
            "Open the contact inbox and the dashboard messages; triage anything customer-facing.",
            "Check that the previous night's database and media backup completed.",
            "Review the application log for 500 errors, payment exceptions and email failures.",
        ]
    )

    story.append(h2("23.2 Order processing"))
    story += table_with_caption(
        [
            ["Stage", "Staff action", "Customer signal"],
            ["New order", "Review stock, address and payment. Confirm or cancel.", "Order received; status pending."],
            ["Paid online", "Payment success moves the order to confirmed automatically.", "Payment successful notification."],
            ["Processing", "Pick and pack; move status to processing.", "Status history and optional email."],
            ["Shipped", "Add courier and tracking number; move to shipped.", "Tracking page shows courier and number."],
            ["Out for delivery", "Move to out_for_delivery when the rider leaves.", "Timeline updates."],
            ["Delivered", "Move to delivered; for COD, record cash collection.", "Delivered status; COD payment becomes paid."],
            ["Cancelled", "Cancel before delivery; stock returns automatically.", "Cancellation notification and refund record if paid."],
        ],
        "Table 23.1 - Fulfilment runbook.",
        widths=[1.1, 3.0, 1.9],
        small=True,
    )
    story.append(
        p(
            "Do not edit order totals or payment status directly in the database. Use the dashboard actions so "
            "status history, notifications, stock movements and audit rows stay consistent. If a correction is "
            "unavoidable, record an internal note explaining the change and who approved it."
        )
    )

    story.append(h2("23.3 Payment reconciliation"))
    story += bullets(
        [
            "Reconcile successful gateway payments against the provider's settlement report daily or weekly.",
            "For eSewa and Khalti, match transaction reference, gateway reference, amount and order number.",
            "For COD, match the courier's collected-cash report to orders marked delivered and paid.",
            "For bank transfer, keep the deposit slip reference in the order note or payment reference.",
            "Record refunds after the provider refund is actually completed, and include the provider reference.",
            "Investigate any paid order without a successful payment or any successful payment for a cancelled order.",
        ]
    )

    story.append(h2("23.4 Backups"))
    story += table_with_caption(
        [
            ["Asset", "Frequency", "Retention", "Notes"],
            ["PostgreSQL database", "Daily, plus before every deployment", "At least 30 daily, 12 monthly", "Use pg_dump custom format and test restore."],
            ["media/ directory", "Daily or after catalogue changes", "At least 30 days", "Contains product images, logos and avatars."],
            [".env and secrets", "On change", "Secure archive", "Store in a password manager or secret manager, not in the web root."],
            ["Application code", "Every release", "Git history or release artifacts", "Tag production releases."],
            ["Logs", "Continuous", "30 to 90 days", "Keep longer for security incidents if required."],
        ],
        "Table 23.2 - Backup schedule.",
        widths=[1.4, 1.4, 1.5, 1.7],
        small=True,
    )
    story.append(
        p(
            "A backup is only useful if it can be restored. Restore the latest database and media into a staging "
            "environment at least quarterly, run migrations and the smoke checklist, and record the result. Store "
            "backups outside the application server so a disk loss does not destroy both copies."
        )
    )

    story.append(h2("23.5 Logging and monitoring"))
    story.append(
        p(
            "The application logs to the console in every environment and adds <b>logs/voltiq.log</b> when "
            "<b>DEBUG=False</b>. The <b>apps</b> logger records order, payment and inventory events. Nginx logs "
            "access and errors separately. A production deployment should ship logs to a central service, rotate "
            "them and alert on sustained 5xx responses, failed gateway callbacks, database connection errors and "
            "disk usage."
        )
    )
    story += table_with_caption(
        [
            ["Signal", "Where", "Suggested alert"],
            ["HTTP 5xx rate", "Nginx and Django", "More than a few in five minutes."],
            ["/health/ failure", "Uptime monitor", "Two consecutive failures."],
            ["Payment verification failure", "PaymentTransaction rows and logs", "Any unexpected spike or repeated amount mismatch."],
            ["Email failure", "SMTP provider and logs", "Bounce or delivery failure above baseline."],
            ["Disk usage", "Host monitor", "Above 80 percent."],
            ["Backup missing", "Backup job", "Any missed daily run."],
            ["Order backlog", "Dashboard", "Pending orders older than the service promise."],
        ],
        "Table 23.3 - Operational monitoring.",
        widths=[1.8, 2.0, 2.2],
        small=True,
    )

    story.append(h2("23.6 Security maintenance"))
    story += bullets(
        [
            "Apply Django, Python, PostgreSQL, Nginx and OS security updates on a monthly cadence, sooner for critical advisories.",
            "Review staff accounts quarterly and remove people who no longer need access.",
            "Rotate payment and SMTP credentials after staff changes or suspected exposure.",
            "Review failed login patterns and proxy rate limits.",
            "Keep the secret key, database password and gateway secrets out of tickets, screenshots and chat.",
            "Re-run <b>check --deploy</b> after changing security settings.",
        ]
    )

    story.append(h2("23.7 Incident response"))
    story += numbered(
        [
            "Protect people and money first: stop new payments if the gateway is compromised or misconfigured.",
            "Preserve evidence: do not delete logs, payment rows or order rows.",
            "Contain: rotate exposed secrets, disable compromised staff accounts and block abusive traffic at the proxy.",
            "Assess: identify affected orders, customers and payment references.",
            "Recover: restore from a verified backup if data integrity is in doubt.",
            "Communicate: inform affected customers and the payment providers with facts, not speculation.",
            "Review: document the root cause, the fix and the monitoring change that prevents recurrence.",
        ]
    )
    story += callout(
        "No maintenance mode is built in",
        "There is no application-level maintenance switch. For planned work, put a maintenance page at the "
        "reverse proxy, keep the database available, and stop the application service cleanly. Do not deploy "
        "during a payment settlement window if it can be avoided.",
        "info",
    )

    story.append(h2("23.8 Data retention and privacy"))
    story.append(
        p(
            "Order and payment records should be retained for accounting and tax obligations. Customer accounts, "
            "addresses, marketing consent and support messages should be retained only as long as needed. A "
            "deletion request should remove or anonymise personal data that is not required for a legal or "
            "accounting record, while preserving the financial order record. The policy page documents a "
            "30-day response target, but the operational procedure must be owned by a named person."
        )
    )

    # ------------------------------------------------------------------
    # 24. Troubleshooting
    # ------------------------------------------------------------------
    story += chapter(
        "24",
        "Troubleshooting",
        "Start with the symptom, then check the layer that can produce it: database, application, static files, "
        "email, gateway or proxy. With DEBUG=False, the browser shows a branded 500 page; the traceback is in the log.",
    )

    story.append(h2("24.1 First diagnostics"))
    story += code_block(
        """
.\\.venv\\Scripts\\python.exe manage.py check
.\\.venv\\Scripts\\python.exe manage.py showmigrations
.\\.venv\\Scripts\\python.exe manage.py shell
Get-Content logs\\voltiq.log -Tail 80
        """.strip(),
        "Code block 24.1 - First commands on a failing local or server installation.",
    )

    story.append(h2("24.2 Symptom and fix reference"))
    story += table_with_caption(
        [
            ["Symptom", "Likely cause", "Fix"],
            ["Server will not start", "Import error, bad settings or missing package", "Read the first traceback; run check; reinstall requirements."],
            ["Port 8000 already in use", "Another development server is running", "Stop it or start on a different port."],
            ["database is locked", "SQLite write contention", "Stop other processes; use PostgreSQL for real concurrency."],
            ["connection refused (PostgreSQL)", "Service stopped or wrong host/port", "Start PostgreSQL; verify DB_HOST and DB_PORT."],
            ["password authentication failed", "Wrong DB password or pg_hba rule", "Reset the password and update .env; check pg_hba.conf."],
            ["No such table", "Migrations not applied", "Run migrate against the intended database."],
            ["Static files 404 in production", "collectstatic not run or Nginx alias wrong", "Run collectstatic; verify the alias and file permissions."],
            ["Manifest missing error", "Template references a file not collected", "Fix the path or run collectstatic with DEBUG=False."],
            ["Media images 404", "Nginx alias wrong or media volume missing", "Check /srv/voltiq/media and the Nginx location."],
            ["400 Bad Request / CSRF", "Expired session, missing token or wrong origin", "Reload the form; verify CSRF_TRUSTED_ORIGINS and proxy headers."],
            ["403 Forbidden", "Customer hit staff route or account suspended", "Use the correct role; review suspension state."],
            ["404 on a valid product", "Inactive product/category or wrong slug", "Check is_active and the slug in the dashboard."],
            ["500 on invoice", "Font, image or file permission problem", "Check ReportLab fonts and media access; inspect the log."],
            ["Email not sent", "No SMTP host or bad credentials", "Configure SMTP; test with a real mailbox."],
            ["Verification link invalid", "Token used, expired or deleted", "Request a resend; check the latest email."],
            ["Online methods missing", "No credentials and simulation off", "Configure gateway credentials or enable simulation locally."],
            ["Simulator returns 404", "Simulation disabled", "Set DEBUG=True and PAYMENT_SIMULATION=True locally only."],
            ["eSewa signature failure", "Wrong secret, field order or callback data", "Compare signed_field_names and the exact secret; log the callback."],
            ["eSewa amount mismatch", "Wrong amount format or stale payment", "Compare payment.amount, callback total and status API total."],
            ["Khalti lookup failure", "Wrong key, pidx or environment URL", "Use matching sandbox/production keys and URLs."],
            ["Payment pending after callback", "Status API unreachable or non-definitive result", "Retry verification; inspect PaymentTransaction."],
            ["Order stuck pending", "Payment not verified or staff not confirmed", "Check payment rows, then confirm manually if appropriate."],
            ["Coupon rejected", "Expired, minimum not met or per-user limit reached", "Check coupon rules and CouponUsage."],
            ["Stock went negative", "Direct database edit or bypassed service", "Adjust through inventory; audit StockHistory."],
            ["Home page stale", "LocMem cache per worker", "Wait for timeout or move to shared cache; clear cache in shell."],
        ],
        "Table 24.1 - Common symptoms and fixes.",
        widths=[1.55, 2.25, 2.2],
        small=True,
    )

    story.append(h2("24.3 Payment-specific debugging"))
    story.append(
        p(
            "For any payment problem, start with the <b>Payment</b> row and its <b>PaymentTransaction</b> audit "
            "rows. Confirm the gateway, amount, transaction reference, status and gateway reference. Then confirm "
            "the order payment status and the provider's own transaction report. Never mark an order paid solely "
            "because the customer says the money left their wallet; verify with the provider or the bank."
        )
    )
    story += code_block(
        """
from apps.payments.models import Payment
p = Payment.objects.filter(transaction_ref="...").first()
print(p.order.order_number, p.gateway, p.amount, p.status, p.gateway_ref)
for row in p.transactions.all():
    print(row.created_at, row.event, row.status, row.message)
        """.strip(),
        "Code block 24.2 - Inspect a payment attempt in the Django shell.",
    )

    story.append(h2("24.4 Email debugging"))
    story.append(
        p(
            "With <b>EMAIL_HOST</b> empty, messages go to the console and never reach a mailbox. With SMTP "
            "configured, verify host, port, TLS mode and credentials. Check the provider's suppression list, SPF, "
            "DKIM and DMARC. A failed order email does not roll back the order, so look for the log entry and "
            "contact the customer through another channel."
        )
    )

    story.append(h2("24.5 Performance debugging"))
    story += bullets(
        [
            "Enable query logging temporarily or use Django Debug Toolbar in a local environment only.",
            "Check for N+1 queries on product cards, order items and dashboard tables.",
            "If the home page is slow, inspect the cached home dataset and image sizes.",
            "If checkout is slow, check product row locks and payment gateway latency.",
            "If the dashboard reports are slow, narrow the date range and add database indexes only after measuring.",
            "Do not run DEBUG=True on production to diagnose performance; it adds memory and exposes details.",
        ]
    )

    # ------------------------------------------------------------------
    # 25. Acceptance and go-live
    # ------------------------------------------------------------------
    story += chapter(
        "25",
        "Acceptance, known gaps and go-live",
        "This chapter states what is complete, what is deliberately limited and what must happen before a real "
        "store takes real money.",
    )

    story.append(h2("25.1 Feature acceptance"))
    story += table_with_caption(
        [
            ["Capability", "Status", "Evidence"],
            ["Responsive storefront and editorial home", "Complete", "Home, catalogue, product and mobile captures."],
            ["Search, filters, sort and AJAX pagination", "Complete", "Catalogue views and app.js; 24 per page."],
            ["Accounts, verification and profiles", "Complete", "Custom user, token emails, account screens."],
            ["Guest cart and login merge", "Complete", "Cart service and merge signal."],
            ["Wishlist and restock alerts", "Complete", "Wishlist models and inventory notifier."],
            ["Coupons and delivery rules", "Complete", "Coupon validation and shipping methods."],
            ["Multi-step checkout", "Complete", "Five session-backed steps with guards."],
            ["Transactional order creation", "Complete", "Atomic service with product and coupon locks."],
            ["COD and bank transfer", "Complete", "Payment attempts and staff recording."],
            ["eSewa and Khalti integration", "Implemented; live sandbox sign-off pending", "Signature and lookup code; simulator tested."],
            ["Order tracking, reorder and PDF invoice", "Complete", "Order routes and ReportLab invoice."],
            ["Verified-purchase review badge", "Complete", "Order-item check and rating signals."],
            ["Staff dashboard and reports", "Complete", "Overview, orders, inventory, customers, CSV."],
            ["Custom error pages and health check", "Complete", "Handlers and /health/."],
            ["Test suite", "151 tests passing", "Django test runner."],
            ["Production deployment", "Documented; not performed in this environment", "Deployment chapter and docs/deployment.md."],
        ],
        "Table 25.1 - Feature acceptance summary.",
        widths=[2.3, 1.5, 2.2],
        small=True,
    )

    story.append(h2("25.2 Known gaps and launch decisions"))
    story += table_with_caption(
        [
            ["Gap", "Impact", "Recommendation"],
            ["Sitemap line in robots.txt points to a missing route", "Search engines get a 404 for /sitemap.xml", "Implement a Django sitemap or remove the line before launch."],
            ["Review endpoint is login-gated, not purchase-gated", "A signed-in non-buyer can post an unverified review through a direct request", "Enforce purchase in the view if verified-only reviews are required."],
            ["No login or contact rate limit", "Credential stuffing and form spam are easier", "Add proxy limits, django-axes or a challenge before public launch."],
            ["LocMemCache is per process", "Cache invalidation is inconsistent across Gunicorn workers", "Move to Redis or Memcached for multi-worker production."],
            ["No image thumbnails or WebP conversion", "Large originals increase page weight", "Add a thumbnail pipeline or an image CDN."],
            ["No asynchronous email queue", "Slow SMTP can delay a request", "Use a task queue for email and retries as volume grows."],
            ["No live gateway E2E in the repo", "Credential and callback mistakes may appear only in production", "Run a sandbox transaction through both gateways before launch."],
            ["No formal accessibility or browser audit", "Unknown edge-case failures", "Run an accessibility scan and a small device matrix."],
            ["No built-in maintenance mode", "Planned downtime needs proxy handling", "Add a proxy maintenance page and a runbook."],
            ["No tax engine", "Tax amount exists but is zero in normal checkout", "Add tax rules if the business requires VAT."],
        ],
        "Table 25.2 - Known gaps. These are launch decisions, not hidden defects.",
        widths=[2.05, 2.05, 1.9],
        small=True,
    )

    story.append(h2("25.3 Go-live checklist"))
    story += table_with_caption(
        [
            ["Area", "Must be true"],
            ["Security", "DEBUG=False; strong secret; HTTPS; secure cookies; HSTS reviewed; check --deploy clean."],
            ["Data", "PostgreSQL migrated; demo data removed or isolated; real administrator created; backups tested."],
            ["Catalogue", "Real products, prices, stock, categories, brands and images loaded; no placeholder content."],
            ["Payments", "Live/sandbox eSewa and Khalti verified end to end; COD and bank instructions correct; simulation off."],
            ["Email", "SMTP tested; SPF, DKIM and DMARC pass; support inbox monitored."],
            ["Shipping", "Methods, charges, free-over thresholds and delivery estimates match the business."],
            ["Legal", "Privacy, terms, returns and shipping policies reviewed for the operating jurisdiction."],
            ["Operations", "Backups scheduled and restore-tested; logs monitored; on-call owner named."],
            ["Staff", "Accounts created with least privilege; fulfilment and refund runbook walked through."],
            ["Performance", "Home, catalogue, product, cart and checkout measured on a phone-class connection."],
            ["Content", "Broken links, placeholder copy, demo testimonials and fake contact details removed."],
            ["Support", "Refund, cancellation, lost parcel and payment-failure macros ready."],
        ],
        "Table 25.3 - Launch gate.",
        widths=[1.1, 4.9],
        small=True,
    )

    story.append(h2("25.4 Launch and first 24 hours"))
    story += numbered(
        [
            "Deploy during a low-traffic window and keep the previous release ready.",
            "Run the smoke pass: home, search, product, register, verify, cart, checkout, payment, order, invoice.",
            "Place one small real order and one refund test according to the provider's rules.",
            "Watch payment callbacks, order creation, stock movements and email delivery for the first hour.",
            "Check the 5xx rate, response time, database connections and disk usage.",
            "Confirm the first real customer communications look correct.",
            "Record incidents, fixes and any manual reconciliations in an operations log.",
        ]
    )

    story.append(h2("25.5 Future roadmap"))
    story += bullets(
        [
            "Add a real sitemap and structured product data for search.",
            "Move cache to Redis and email to a background worker.",
            "Add image thumbnails, WebP conversion and a CDN.",
            "Add PostgreSQL CI and browser smoke tests.",
            "Add verified-only review enforcement if that is the business rule.",
            "Add VAT/tax rules, partial refunds and credit notes.",
            "Add a courier integration for tracking updates.",
            "Add two-factor authentication for staff and administrators.",
            "Add a content security policy and a formal security review.",
        ]
    )

    story.append(h2("25.6 Closing statement"))
    story.append(
        p(
            "Voltiq is a complete, coherent e-commerce application rather than a collection of screens. The "
            "catalogue, cart, checkout, payment verification, inventory, review and dashboard paths share one "
            "database and one service layer. The project is honest about its limits: it has strong transactional "
            "rules and a meaningful test suite, but it has not been load-tested, formally audited or exercised "
            "against live payment money in this environment. Treat this manual as the operating contract and the "
            "launch checklist as the gate, not as a substitute for real sandbox verification and a careful "
            "production rehearsal."
        )
    )

    # ------------------------------------------------------------------
    # Glossary
    # ------------------------------------------------------------------
    story += chapter(
        "G",
        "Glossary",
        "Terms used throughout the manual, written for a mixed audience of developers, staff and store owners.",
    )
    glossary = [
        ("AOV", "Average order value: paid revenue divided by the number of paid orders."),
        ("AJAX", "A browser request that updates part of a page without a full reload."),
        ("Atomic transaction", "A group of database writes that either all commit or all roll back."),
        ("Callback", "The return request a payment provider sends or redirects the customer to after payment."),
        ("COD", "Cash on delivery: the customer pays the courier when the order arrives."),
        ("Coupon usage", "A record that a specific coupon was redeemed on a specific order."),
        ("CSRF", "Cross-site request forgery; Django's token check prevents another site from submitting state-changing forms."),
        ("DRF", "Django REST Framework, used here for JSON renderers, throttles and search suggestions."),
        ("eSewa", "A Nepali digital wallet and payment gateway."),
        ("Gateway reference", "The provider's own transaction identifier, stored alongside the Voltiq reference."),
        ("HSTS", "HTTP Strict Transport Security; tells browsers to use HTTPS for future visits."),
        ("Idempotent", "An operation that can be repeated without changing the result beyond the first success."),
        ("Invoice", "The PDF document generated for an order with items, totals and payment details."),
        ("Khalti", "A Nepali digital wallet and payment gateway."),
        ("LocMemCache", "Django's process-local in-memory cache; fast but not shared between workers."),
        ("Migration", "A versioned database schema change managed by Django."),
        ("NPR", "Nepalese rupee, the currency used throughout the store."),
        ("ORM", "Object-relational mapper; Django's Python interface to the database."),
        ("pidx", "Khalti's payment identifier returned when a payment is initiated."),
        ("Race condition", "Two requests trying to change the same resource at the same time."),
        ("Rate limit", "A cap on how many requests a client may make in a time window."),
        ("Reverse proxy", "A web server such as Nginx that sits in front of the application server."),
        ("Row lock", "A database lock that prevents two transactions from changing the same row concurrently."),
        ("Sandbox", "A provider test environment that does not move real money."),
        ("Snapshot", "A copied value stored on an order so later catalogue edits do not rewrite history."),
        ("SQLite", "A file-based database used for local development and tests."),
        ("PostgreSQL", "The production relational database used by the reference deployment."),
        ("Systemd", "The Linux service manager used to supervise Gunicorn."),
        ("TOC", "Table of contents."),
        ("Webhook", "A server-to-server notification from a provider. Voltiq primarily uses browser callbacks plus status lookups."),
        ("WhiteNoise", "The static-file server used by Django when DEBUG=False."),
        ("WSGI", "The Python web server interface used by Gunicorn and Waitress."),
    ]
    story += table_with_caption(
        [["Term", "Meaning"]] + [[term, meaning] for term, meaning in glossary],
        "Table G.1 - Glossary.",
        widths=[1.3, 4.7],
        small=True,
        dense=True,
        mono_columns={0},
    )

    # ------------------------------------------------------------------
    # Appendix A - Data dictionary
    # ------------------------------------------------------------------
    story += chapter(
        "A",
        "Data dictionary",
        "The database contains 28 application models across ten Django apps. This appendix lists their fields, "
        "relationships and important constraints.",
    )

    story.append(h2("A.1 Conventions"))
    story += bullets(
        [
            "Every concrete model has an implicit <b>BigAutoField</b> primary key named <b>id</b> unless stated otherwise.",
            "<b>created_at</b> and <b>updated_at</b> are listed only when they carry operational meaning.",
            "Money fields are <b>Decimal</b> values in NPR with two decimal places. They are never floats.",
            "Foreign keys use <b>PROTECT</b> for catalogue structure and <b>SET_NULL</b> or <b>CASCADE</b> where history must survive.",
            "Table names follow Django's <b>app_model</b> convention, for example <b>orders_orderitem</b>.",
        ]
    )

    story.append(h2("A.2 Identity and catalogue"))
    story += table_with_caption(
        [
            ["Model", "Fields", "Relationships and notes"],
            ["User", "email, password, first_name, last_name, phone, avatar, role, is_email_verified, email_verified_at, is_suspended, suspension_reason, is_active, is_staff, is_superuser, date_joined, last_login, last_login_ip, newsletter_opt_in", "Email is the login identifier and is unique. Role is customer, staff or admin. Staff and admin roles force is_staff."],
            ["CustomerProfile", "user, date_of_birth, marketing_opt_in, preferred_payment, loyalty_points, notes, created_at, updated_at", "One-to-one with User; created by signal."],
            ["Address", "user, label, full_name, phone, alternate_phone, street_address, landmark, city, district, province, postal_code, country, address_type, is_default, created_at, updated_at", "Many per user. Setting default clears the previous default. Province choices cover all seven provinces."],
            ["EmailVerificationToken", "user, token, created_at, expires_at, used_at", "Token is unique. Unused tokens are deleted when a new one is issued."],
            ["Notification", "user, title, message, url, kind, is_read, created_at", "Kind is order, payment, wishlist, account, promo or system. Indexed by user and read state."],
            ["Category", "name, slug, parent, description, image, icon, is_active, is_featured, sort_order, created_at, updated_at", "Self-referencing tree. Name and slug are unique. Products are protected from category deletion."],
            ["Brand", "name, slug, logo, description, website, is_active, is_featured, created_at, updated_at", "Name and slug are unique. Products are protected from brand deletion."],
            ["Product", "name, slug, sku, brand, category, short_description, description, highlights, price, discount_price, cost_price, stock_quantity, low_stock_threshold, warranty_info, condition, color, processor, ram, storage, gpu, display_size, operating_system, is_active, is_featured, free_shipping, allow_backorder, rating_avg, review_count, sales_count, view_count, meta_title, meta_description, created_at, updated_at", "SKU and slug are unique. Brand and category use PROTECT. Price properties are computed; stock is authoritative."],
            ["ProductImage", "product, image, alt_text, is_primary, sort_order, created_at", "Many per product. First image becomes primary; choosing a new primary clears the old one."],
            ["SpecificationField", "category, label, key, unit, input_type, options, is_filterable, sort_order", "Per-category schema. Category and key are unique together. Input type is text, number or select."],
            ["ProductSpecification", "product, field, name, key, value, unit, sort_order", "Stored values keep a label and unit snapshot. Field can be null if the schema is later removed."],
        ],
        "Table A.1 - Identity, people and catalogue models.",
        widths=[1.15, 3.35, 1.5],
        small=True,
        tiny=True,
        mono_columns={0},
    )

    story.append(CondPageBreak(120))
    story.append(h2("A.3 Cart, wishlist and orders"))
    story += table_with_caption(
        [
            ["Model", "Fields", "Relationships and notes"],
            ["Cart", "user, session_key, coupon, shipping_method, created_at, updated_at", "User is a nullable one-to-one. Session key is unique and nullable. One cart per user or guest session."],
            ["CartItem", "cart, product, quantity, price_snapshot, added_at, updated_at", "Cart and product are unique together. Quantity is capped at 20 by the service."],
            ["Wishlist", "user, created_at, updated_at", "One-to-one with User. Created on demand."],
            ["WishlistItem", "wishlist, product, notify_on_restock, created_at", "Wishlist and product are unique together. Restock flag defaults to true."],
            ["Coupon", "code, description, discount_type, value, minimum_order_amount, maximum_discount, valid_from, valid_to, usage_limit, per_user_limit, used_count, is_active, created_at, updated_at", "Code is unique and uppercase. Discount is percentage or fixed. One coupon per cart or order."],
            ["CouponUsage", "coupon, user, email, order, created_at", "Audit of redemption. User may be null; email is kept for guest or historical matching."],
            ["ShippingMethod", "name, code, description, charge, free_over, min_days, max_days, is_active, sort_order, created_at", "Code is unique. fee_for() applies the free-over threshold."],
            ["Order", "order_number, user, email, phone, full_name, shipping_full_name, shipping_phone, shipping_street, shipping_city, shipping_district, shipping_province, shipping_postal_code, shipping_country, shipping_method, shipping_method_name, shipping_fee, subtotal, coupon, coupon_code, discount_amount, tax_amount, total, currency, status, payment_status, payment_method, customer_notes, internal_notes, tracking_number, courier, ip_address, user_agent, created_at, updated_at, confirmed_at, shipped_at, delivered_at, cancelled_at", "Order number is unique. User is SET_NULL to preserve history. Address and shipping method are snapshotted. Status and payment status are indexed."],
            ["OrderItem", "order, product, product_name, sku, image_url, unit_price, quantity, line_total, is_reviewed", "Product is SET_NULL. Name, SKU, image and price are snapshots. line_total is recalculated on save."],
            ["OrderStatusHistory", "order, status, note, changed_by, created_at", "Append-only timeline. changed_by is SET_NULL if the staff account is removed."],
        ],
        "Table A.2 - Cart, wishlist, coupon and order models.",
        widths=[1.15, 3.35, 1.5],
        small=True,
        tiny=True,
        mono_columns={0},
    )

    story.append(h2("A.4 Payments, inventory, reviews and content"))
    story += table_with_caption(
        [
            ["Model", "Fields", "Relationships and notes"],
            ["Payment", "order, gateway, amount, currency, status, transaction_ref, gateway_ref, gateway_payload, verification_payload, is_verified, attempt_number, initiated_at, updated_at, completed_at, failed_reason, refunded_at", "transaction_ref is unique. A partial unique constraint allows only one success per order. Gateway payloads contain no card data."],
            ["PaymentTransaction", "payment, event, status, message, request_data, response_data, ip_address, created_at", "Append-only audit. Event is initiated, callback, verified, succeeded, failed, cancelled, refunded or note."],
            ["StockHistory", "product, change, previous_quantity, new_quantity, reason, reference, order, changed_by, created_at", "Change is signed. Reasons are restock, sale, return, adjustment, damage, cancellation and seed."],
            ["Review", "product, user, rating, title, body, is_verified_purchase, is_approved, helpful_count, created_at, updated_at", "Product and user are unique together. Rating is 1 to 5. Public queries filter is_approved."],
            ["NewsletterSubscription", "email, name, is_active, token, source, created_at, unsubscribed_at", "Email is unique. Token drives the unsubscribe link."],
            ["ContactMessage", "name, email, phone, subject, message, status, created_at", "Status is new, in_progress or resolved. Messages are read in the dashboard."],
            ["SiteSetting", "store_name, tagline, announcement, support_phone, support_email, address, facebook_url, instagram_url, youtube_url, tiktok_url, updated_at", "Singleton loaded as pk=1 with get_or_create."],
        ],
        "Table A.3 - Payment, inventory, review and content models.",
        widths=[1.35, 3.15, 1.5],
        small=True,
        tiny=True,
        mono_columns={0},
    )

    story.append(h2("A.5 Key constraints"))
    story += table_with_caption(
        [
            ["Constraint", "Purpose"],
            ["User.email unique", "One account per email address."],
            ["Product.sku and Product.slug unique", "Stable product identity and URLs."],
            ["Category.name and Category.slug unique; Brand.name and Brand.slug unique", "Unambiguous catalogue navigation."],
            ["SpecificationField (category, key) unique", "One schema field per key per category."],
            ["Cart.user one-to-one and Cart.session_key unique", "One active cart per owner."],
            ["CartItem (cart, product) unique", "No duplicate product lines in a cart."],
            ["Wishlist.user one-to-one and WishlistItem (wishlist, product) unique", "No duplicate wishlist entries."],
            ["Coupon.code unique", "Case-normalised coupon lookup."],
            ["ShippingMethod.code unique", "Stable method identifier."],
            ["Order.order_number unique", "Public and internal order identity."],
            ["Payment.transaction_ref unique", "Idempotent gateway reference lookup."],
            ["Payment(order) unique where status=success", "At most one successful payment per order."],
            ["Review (product, user) unique", "One review per customer per product."],
            ["NewsletterSubscription.email unique", "One subscription per address."],
        ],
        "Table A.4 - Database-level invariants.",
        widths=[2.7, 3.3],
        small=True,
    )

    # ------------------------------------------------------------------
    # Appendix B - Route map
    # ------------------------------------------------------------------
    story += chapter(
        "B",
        "Route map",
        "The complete URL surface, grouped by audience. URLs use braces for path parameters. State-changing routes "
        "are POST unless the table says otherwise.",
    )

    story.append(h2("B.1 Core and account routes"))
    story += table_with_caption(
        [
            ["URL", "Name", "Purpose"],
            ["/", "core:home", "Home page with cached merchandising data."],
            ["/newsletter/subscribe/", "core:newsletter_subscribe", "POST subscription; JSON or redirect."],
            ["/newsletter/unsubscribe/{token}/", "core:newsletter_unsubscribe", "GET unsubscribe link."],
            ["/contact/", "core:contact", "Contact form and support message."],
            ["/about/", "core:about", "Brand story and showroom content."],
            ["/faq/", "core:faq", "Frequently asked questions."],
            ["/privacy/", "core:privacy", "Privacy policy."],
            ["/terms/", "core:terms", "Terms of sale."],
            ["/shipping/", "core:shipping", "Delivery and shipping policy."],
            ["/returns/", "core:returns", "Returns and refund policy."],
            ["/robots.txt", "core:robots", "Crawler rules. References a sitemap that is not implemented."],
            ["/health/", "core:health", "Database health probe returning JSON."],
            ["/accounts/register/", "accounts:register", "Create a customer account."],
            ["/accounts/login/", "accounts:login", "Email and password sign-in."],
            ["/accounts/logout/", "accounts:logout", "POST logout."],
            ["/accounts/verify-email/", "accounts:verify_pending", "Verification-pending page."],
            ["/accounts/verify-email/resend/", "accounts:resend_verification", "POST resend, 5 per user per hour."],
            ["/accounts/verify-email/{token}/", "accounts:verify_email", "Consume a verification token."],
            ["/accounts/password-reset/", "accounts:password_reset", "Request a reset email."],
            ["/accounts/password-reset/sent/", "accounts:password_reset_done", "Reset email sent confirmation."],
            ["/accounts/password-reset/{uidb64}/{token}/", "accounts:password_reset_confirm", "Set a new password."],
            ["/accounts/password-reset/complete/", "accounts:password_reset_complete", "Reset completion."],
            ["/accounts/account/", "accounts:dashboard", "Customer account dashboard."],
            ["/accounts/account/profile/", "accounts:profile", "Edit profile and avatar."],
            ["/accounts/account/password/", "accounts:password_change", "Change password."],
            ["/accounts/account/addresses/", "accounts:addresses", "Address book."],
            ["/accounts/account/addresses/add/", "accounts:address_create", "Create an address."],
            ["/accounts/account/addresses/{pk}/edit/", "accounts:address_edit", "Edit an owned address."],
            ["/accounts/account/addresses/{pk}/delete/", "accounts:address_delete", "Delete an owned address."],
            ["/accounts/account/addresses/{pk}/default/", "accounts:address_set_default", "Set default address."],
            ["/accounts/account/notifications/", "accounts:notifications", "Notification list."],
            ["/accounts/account/notifications/read-all/", "accounts:notifications_read_all", "Mark all read."],
            ["/accounts/account/payments/", "accounts:payments", "Customer payment history."],
        ],
        "Table B.1 - Core and account routes.",
        widths=[2.5, 2.0, 1.5],
        small=True,
        tiny=True,
        mono_columns={0, 1},
    )

    story.append(h2("B.2 Catalogue, commerce and payment routes"))
    story += table_with_caption(
        [
            ["URL", "Name", "Purpose"],
            ["/products/", "products:list", "Catalogue with search, filters, sort and pagination."],
            ["/products/search/suggestions/", "products:suggestions", "JSON search suggestions, minimum two characters."],
            ["/products/{slug}/", "products:detail", "Product detail, reviews, related products and view counter."],
            ["/cart/", "cart:detail", "Cart page."],
            ["/cart/add/", "cart:add", "POST add or increment a line."],
            ["/cart/update/{item_id}/", "cart:update", "POST set quantity."],
            ["/cart/remove/{item_id}/", "cart:remove", "POST remove a line."],
            ["/cart/coupon/apply/", "cart:apply_coupon", "POST validate and apply a coupon."],
            ["/cart/coupon/remove/", "cart:remove_coupon", "POST clear the coupon."],
            ["/cart/summary/", "cart:summary", "JSON totals for the header and drawer."],
            ["/wishlist/", "wishlist:detail", "Wishlist page; login required."],
            ["/wishlist/toggle/", "wishlist:toggle", "POST toggle a product."],
            ["/wishlist/remove/{item_id}/", "wishlist:remove", "POST remove an item."],
            ["/wishlist/move-to-cart/{item_id}/", "wishlist:move_to_cart", "POST move an item to the cart."],
            ["/checkout/", "checkout:contact", "Step 1: contact details."],
            ["/checkout/address/", "checkout:address", "Step 2: delivery address."],
            ["/checkout/shipping/", "checkout:shipping", "Step 3: shipping method."],
            ["/checkout/review/", "checkout:review", "Step 4: review totals and coupon."],
            ["/checkout/payment/", "checkout:payment", "Step 5: choose method and place order."],
            ["/orders/", "orders:list", "Customer order history."],
            ["/orders/{order_number}/", "orders:detail", "Order detail and status timeline."],
            ["/orders/{order_number}/confirmation/", "orders:confirmation", "Thank-you page."],
            ["/orders/{order_number}/track/", "orders:track", "Customer tracking view."],
            ["/orders/{order_number}/cancel/", "orders:cancel", "POST cancel while eligible."],
            ["/orders/{order_number}/reorder/", "orders:reorder", "POST add available items to the cart."],
            ["/orders/{order_number}/payment/", "orders:payment", "Start another payment attempt."],
            ["/orders/{order_number}/invoice.pdf", "orders:invoice", "PDF invoice; owner or staff."],
            ["/payments/esewa/callback/", "payments:esewa_callback", "eSewa success and failure callback."],
            ["/payments/khalti/callback/", "payments:khalti_callback", "Khalti return callback."],
            ["/payments/simulate/{transaction_ref}/", "payments:simulate", "Development simulator; disabled in production."],
            ["/payments/failure/{order_number}/", "payments:failure", "Payment failure page."],
            ["/payments/bank/{transaction_ref}/", "payments:bank_instructions", "Bank transfer instructions."],
            ["/reviews/product/{slug}/add/", "reviews:add", "POST create a review; login required."],
            ["/reviews/{pk}/edit/", "reviews:edit", "POST edit an owned review."],
            ["/reviews/{pk}/delete/", "reviews:delete", "POST delete an owned review."],
        ],
        "Table B.2 - Catalogue, cart, checkout, order, payment and review routes.",
        widths=[2.5, 2.0, 1.5],
        small=True,
        tiny=True,
        mono_columns={0, 1},
    )

    story.append(h2("B.3 Dashboard and admin routes"))
    story += table_with_caption(
        [
            ["URL", "Name", "Purpose"],
            ["/dashboard/", "dashboard:overview", "KPIs, charts and recent activity. Staff."],
            ["/dashboard/products/", "dashboard:product_list", "Product list and filters. Staff."],
            ["/dashboard/products/add/", "dashboard:product_create", "Create a product. Staff."],
            ["/dashboard/products/{pk}/edit/", "dashboard:product_edit", "Edit product, specs and images. Staff."],
            ["/dashboard/products/{pk}/delete/", "dashboard:product_delete", "Delete a product. Staff."],
            ["/dashboard/products/{pk}/toggle/", "dashboard:product_toggle", "Toggle active state. Staff."],
            ["/dashboard/products/{pk}/images/upload/", "dashboard:product_image_upload", "Upload an image. Staff."],
            ["/dashboard/products/{pk}/images/{image_id}/delete/", "dashboard:product_image_delete", "Delete an image. Staff."],
            ["/dashboard/products/{pk}/images/{image_id}/primary/", "dashboard:product_image_primary", "Set primary image. Staff."],
            ["/dashboard/api/category-specs/{pk}/", "dashboard:category_specs_api", "JSON spec fields for a category. Staff."],
            ["/dashboard/categories/", "dashboard:category_list", "Category tree. Staff."],
            ["/dashboard/categories/add/", "dashboard:category_create", "Create category. Staff."],
            ["/dashboard/categories/{pk}/edit/", "dashboard:category_edit", "Edit category. Staff."],
            ["/dashboard/categories/{pk}/delete/", "dashboard:category_delete", "Delete if unprotected. Staff."],
            ["/dashboard/brands/", "dashboard:brand_list", "Brand list. Staff."],
            ["/dashboard/brands/add/", "dashboard:brand_create", "Create brand. Staff."],
            ["/dashboard/brands/{pk}/edit/", "dashboard:brand_edit", "Edit brand. Staff."],
            ["/dashboard/brands/{pk}/delete/", "dashboard:brand_delete", "Delete if unprotected. Staff."],
            ["/dashboard/spec-fields/", "dashboard:specfield_list", "Specification schemas. Staff."],
            ["/dashboard/spec-fields/add/", "dashboard:specfield_create", "Create schema field. Staff."],
            ["/dashboard/spec-fields/{pk}/edit/", "dashboard:specfield_edit", "Edit schema field. Staff."],
            ["/dashboard/spec-fields/{pk}/delete/", "dashboard:specfield_delete", "Delete schema field. Staff."],
            ["/dashboard/orders/", "dashboard:order_list", "Search and filter orders. Staff."],
            ["/dashboard/orders/{order_number}/", "dashboard:order_detail", "Order detail, payment and history. Staff."],
            ["/dashboard/orders/{order_number}/status/", "dashboard:order_update_status", "POST status change; refunds admin-only."],
            ["/dashboard/orders/{order_number}/mark-paid/", "dashboard:order_mark_paid", "POST record manual or COD payment. Staff."],
            ["/dashboard/orders/{order_number}/invoice.pdf", "dashboard:order_invoice", "Staff invoice download. Staff."],
            ["/dashboard/customers/", "dashboard:customer_list", "Customer list with spend. Staff."],
            ["/dashboard/customers/{pk}/", "dashboard:customer_detail", "Customer profile and orders. Staff."],
            ["/dashboard/customers/{pk}/suspend/", "dashboard:customer_toggle_suspension", "POST suspend or reactivate. Admin."],
            ["/dashboard/customers/{pk}/role/", "dashboard:customer_set_role", "POST change role. Admin."],
            ["/dashboard/inventory/", "dashboard:inventory_list", "Stock levels and filters. Staff."],
            ["/dashboard/inventory/{pk}/adjust/", "dashboard:inventory_adjust", "POST adjust stock with reason. Staff."],
            ["/dashboard/inventory/history/", "dashboard:stock_history", "Stock movement audit. Staff."],
            ["/dashboard/reports/", "dashboard:reports", "Date-range analytics. Staff."],
            ["/dashboard/reports/orders.csv", "dashboard:export_orders_csv", "Order CSV export. Staff."],
            ["/dashboard/reports/newsletter.csv", "dashboard:export_newsletter_csv", "Newsletter CSV export. Staff."],
            ["/dashboard/reviews/", "dashboard:review_list", "Review moderation. Staff."],
            ["/dashboard/reviews/{pk}/toggle/", "dashboard:review_toggle", "POST approve or unpublish. Staff."],
            ["/dashboard/reviews/{pk}/delete/", "dashboard:review_delete", "POST delete. Staff."],
            ["/dashboard/coupons/", "dashboard:coupon_list", "Coupon list. Staff."],
            ["/dashboard/coupons/add/", "dashboard:coupon_create", "Create coupon. Staff."],
            ["/dashboard/coupons/{pk}/edit/", "dashboard:coupon_edit", "Edit coupon. Staff."],
            ["/dashboard/coupons/{pk}/delete/", "dashboard:coupon_delete", "Delete coupon. Staff."],
            ["/dashboard/newsletter/", "dashboard:newsletter_list", "Subscriber list. Staff."],
            ["/dashboard/messages/", "dashboard:contact_messages", "Contact messages. Staff."],
            ["/dashboard/messages/{pk}/status/", "dashboard:contact_message_status", "POST update message status. Staff."],
            ["/dashboard/settings/", "dashboard:store_settings", "Store identity and shipping settings. Admin."],
            ["/dashboard/settings/shipping/{pk}/edit/", "dashboard:shipping_edit", "Edit shipping method. Admin."],
            ["/dashboard/settings/shipping/{pk}/delete/", "dashboard:shipping_delete", "Delete shipping method. Admin."],
            ["/django-admin/", "admin:index", "Django admin. Staff with permission or superuser."],
        ],
        "Table B.3 - Staff and administrator routes.",
        widths=[2.5, 2.0, 1.5],
        small=True,
        tiny=True,
        mono_columns={0, 1},
    )

    # ------------------------------------------------------------------
    # Appendix C - Commands
    # ------------------------------------------------------------------
    story += chapter(
        "C",
        "Command reference",
        "The commands used to run, check, seed, test and package the project. Run them from the repository root.",
    )

    story.append(h2("C.1 Django management commands"))
    story += table_with_caption(
        [
            ["Command", "What it does"],
            ["python manage.py check", "Run Django system checks."],
            ["python manage.py check --deploy", "Run deployment security checks."],
            ["python manage.py migrate", "Apply database migrations."],
            ["python manage.py makemigrations", "Create migrations after model changes."],
            ["python manage.py makemigrations --check --dry-run", "Fail if model changes have no migration."],
            ["python manage.py showmigrations", "List migrations and applied state."],
            ["python manage.py sqlmigrate app 0001", "Print the SQL for a migration."],
            ["python manage.py createsuperuser", "Create an email-based administrator."],
            ["python manage.py seed_store", "Load the demo store and accounts."],
            ["python manage.py seed_store --skip-images", "Seed without downloading product images."],
            ["python manage.py test", "Run the full test suite."],
            ["python manage.py test apps.orders --verbosity 2", "Run one app with detailed output."],
            ["python manage.py collectstatic --noinput", "Build the static files directory."],
            ["python manage.py runserver 127.0.0.1:8000 --noreload", "Start the development server."],
            ["python manage.py shell", "Open the Django shell."],
            ["python manage.py shell -c \"...\"", "Run a one-line shell command."],
            ["python manage.py dbshell", "Open the database client for the configured database."],
            ["python manage.py changepassword EMAIL", "Change a user's password."],
            ["python manage.py clearsessions", "Delete expired sessions."],
            ["python manage.py flush", "Delete all data but keep the schema. Destructive."],
        ],
        "Table C.1 - Management commands. Use the .venv interpreter on Windows.",
        widths=[3.1, 2.9],
        small=True,
        tiny=True,
        mono_columns={0},
    )

    story.append(h2("C.2 PDF and diagram build"))
    story += code_block(
        """
.\\.venv\\Scripts\\python.exe docs\\build_project_pdf.py
.\\.venv\\Scripts\\python.exe docs\\build_diagrams.py
        """.strip(),
        "Code block C.1 - Regenerate this manual and the four diagrams.",
    )
    story.append(
        p(
            "The PDF build uses ReportLab, the Segoe UI and Consolas fonts and the PNG files under "
            "<b>docs/_generated/</b>. PyMuPDF is used only to render preview pages for visual inspection; it is "
            "not required to produce the PDF. The diagrams are generated with Pillow from "
            "<b>docs/build_diagrams.py</b>."
        )
    )

    story.append(CondPageBreak(120))
    story.append(h2("C.3 Useful shell snippets"))
    story += code_block(
        """
# Count objects
from apps.orders.models import Order
from apps.products.models import Product
print(Order.objects.count(), Product.objects.count())

# Inspect a cart
from apps.cart.models import Cart
c = Cart.objects.filter(user__email="aarav.sharma@example.com").first()
print(c.items.values_list("product__name", "quantity") if c else "no cart")

# Inspect a payment
from apps.payments.models import Payment
p = Payment.objects.filter(status="success").first()
print(p.order.order_number, p.amount, p.gateway_ref)

# Clear the whole cache
from django.core.cache import cache
cache.clear()
        """.strip(),
        "Code block C.2 - Read-only and maintenance snippets for the Django shell.",
    )

    story.append(h2("C.4 PostgreSQL backup commands"))
    story += code_block(
        """
# Custom-format backup
pg_dump -h 127.0.0.1 -U voltiq_user -F c -f voltiq.backup voltiq

# Restore
pg_restore -h 127.0.0.1 -U voltiq_user -d voltiq --clean --if-exists voltiq.backup
        """.strip(),
        "Code block C.3 - Short forms if PostgreSQL bin is on PATH.",
    )

    # ------------------------------------------------------------------
    # Appendix D - Project map
    # ------------------------------------------------------------------
    story += chapter(
        "D",
        "Project map and documentation build",
        "Where the code, templates, assets, tests and generated documentation live.",
    )

    story.append(h2("D.1 Repository layout"))
    story += code_block(
        """
ecommerce/
  manage.py
  requirements.txt
  README.md
  .env.example
  config/                 settings, root URLs, WSGI/ASGI
  apps/
    accounts/             custom user, profiles, addresses, notifications
    categories/           category tree and brands
    products/             catalogue, images, specifications, search
    cart/                 guest and user carts, coupon application
    wishlist/             saved products and restock flags
    orders/               coupons, shipping, order lifecycle, invoices
    payments/             gateways, verification, simulator, audit
    inventory/            stock service and history
    reviews/              ratings, verified badge, moderation
    dashboard/            staff and administrator interface
    core/                 home, content, newsletter, health, errors
  templates/              storefront, account, dashboard, email, errors
  static/css/             tokens, layout, components, pages, account, dashboard
  static/js/              app.js and dashboard.js
  media/                  uploaded images (ignored by Git)
  docs/                   setup, pgAdmin, deployment, PDF generator, assets
  logs/                   application log when DEBUG=False
        """.strip(),
        "Code block D.1 - Top-level repository map.",
    )

    story.append(h2("D.2 Where to change what"))
    story += table_with_caption(
        [
            ["Change", "Primary files"],
            ["Brand colours or type scale", "static/css/tokens.css"],
            ["Header, footer or navigation", "templates/base.html, templates/partials/, static/css/layout.css"],
            ["Home page sections", "apps/core/views.py, templates/core/home.html, static/css/pages.css"],
            ["Product card or listing", "templates/products/, templates/partials/, static/js/app.js"],
            ["Cart rules", "apps/cart/services.py, apps/cart/models.py"],
            ["Checkout steps", "apps/orders/views.py, apps/orders/forms.py, templates/checkout/"],
            ["Order totals or creation", "apps/orders/services.py, apps/orders/models.py"],
            ["Payment gateway", "apps/payments/gateways/, apps/payments/services.py"],
            ["Stock movement", "apps/inventory/services.py"],
            ["Review rules", "apps/reviews/views.py, apps/reviews/models.py, apps/reviews/signals.py"],
            ["Dashboard analytics", "apps/dashboard/views.py, templates/dashboard/"],
            ["Email copy", "templates/emails/, apps/orders/services.py"],
            ["Store settings", "apps/core/models.py, apps/core/context_processors.py"],
            ["Security headers", "config/settings.py, reverse proxy configuration"],
        ],
        "Table D.1 - Change guide.",
        widths=[2.2, 3.8],
        small=True,
    )

    story.append(h2("D.3 Documentation assets"))
    story += table_with_caption(
        [
            ["Asset", "Path", "Purpose"],
            ["Manual generator", "docs/build_project_pdf.py", "Builds this PDF with ReportLab."],
            ["Diagram generator", "docs/build_diagrams.py", "Produces architecture, order, payment and data-model PNGs."],
            ["Diagrams", "docs/_generated/diagrams/", "Embedded in Chapters 1, 8 and 9."],
            ["Screenshots", "docs/_generated/screenshots/", "Real storefront and dashboard captures."],
            ["PDF previews", "docs/_generated/pdf-preview/", "Page renders used for visual inspection."],
            ["Output PDF", "docs/Voltiq-Project-Documentation.pdf", "This manual."],
            ["Setup guide", "docs/setup.md", "Markdown setup companion."],
            ["pgAdmin guide", "docs/pgadmin.md", "Database creation, backup and restore."],
            ["Deployment guide", "docs/deployment.md", "Linux and Windows production notes."],
        ],
        "Table D.2 - Documentation assets.",
        widths=[1.5, 2.3, 2.2],
        small=True,
        mono_columns={1},
    )

    story.append(h2("D.4 Rebuilding the manual"))
    story += numbered(
        [
            "Activate the virtual environment and install requirements.",
            "Ensure Segoe UI and Consolas fonts are available to ReportLab, or adjust the font paths in the generator.",
            "Run docs/build_diagrams.py if diagrams changed.",
            "Run docs/build_project_pdf.py.",
            "Open the PDF, check the table of contents page numbers and inspect the diagram and screenshot pages.",
            "Commit the generator, diagrams, screenshots and PDF together so the manual and its sources stay in sync.",
        ]
    )
    story += callout(
        "Keep the manual honest",
        "This document describes the code at the time of generation. If you change review gating, add a sitemap, "
        "move to Redis, add a queue or deploy to production, update the relevant chapter and the known-gaps "
        "table. A manual that silently drifts from the code is worse than no manual.",
        "info",
    )

    story.append(Spacer(1, 18))
    story.append(
        p(
            "End of manual. Voltiq Electronics - Version 1.0 - November 2026.",
            "Caption",
        )
    )

    return story


def build() -> Path:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    doc = VoltiqDocTemplate(
        str(OUTPUT_PDF),
        pagesize=A4,
        leftMargin=MARGIN_X,
        rightMargin=MARGIN_X,
        topMargin=62,
        bottomMargin=46,
        title="Voltiq - Complete Project Documentation",
        author="Voltiq project",
        subject="Architecture, features, data model, payments, operations and deployment",
        creator="Voltiq documentation generator",
    )
    story = build_story()
    doc.multiBuild(story)
    return OUTPUT_PDF


if __name__ == "__main__":
    result = build()
    print(f"Wrote {result} ({result.stat().st_size:,} bytes)")
