import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json
import os
import re
from datetime import date, datetime

try:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_ALIGN_VERTICAL
    from docx.enum.section import WD_ORIENT
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
except ImportError:
    print("ERROR: python-docx not installed. Run: pip install python-docx")
    sys.exit(1)

try:
    from PIL import Image as PILImage
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install pillow")
    sys.exit(1)

# ── Stable module-level constant ─────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))

# ════════════════════════════════════════════════════════════
#  LAYOUT CONSTANTS  (A4 Landscape)
# ════════════════════════════════════════════════════════════
PAGE_W   = Inches(11.69)
PAGE_H   = Inches(8.27)
MARGIN_L = Inches(0.60)
MARGIN_R = Inches(0.60)
MARGIN_T = Inches(0.50)
MARGIN_B = Inches(0.50)
CW       = 10.49

C_ACCENT  = "1F497D"
C_INFOBG  = "D6E4F0"
C_CLIENTBG= "EBF3FB"
C_SIGBG   = "F0F4F8"
C_WHITE   = (0xFF, 0xFF, 0xFF)
C_RED     = RGBColor(0xC0, 0x00, 0x00)
C_BLUE    = RGBColor(0x1F, 0x49, 0x7D)
C_LINK    = RGBColor(0x00, 0x70, 0xC0)
C_GRAY    = RGBColor(0x66, 0x66, 0x66)
C_DARK    = RGBColor(0x44, 0x44, 0x44)

# ════════════════════════════════════════════════════════════
#  HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════
def set_cell_bg(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd  = OxmlElement('w:shd')
    shd.set(qn('w:val'),   'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'),  hex_color)
    tcPr.append(shd)

def set_cell_width(cell, inches):
    cell.width = Inches(inches)
    tcPr = cell._tc.get_or_add_tcPr()
    tcW  = OxmlElement('w:tcW')
    tcW.set(qn('w:w'),    str(int(inches * 1440)))
    tcW.set(qn('w:type'), 'dxa')
    ex = tcPr.find(qn('w:tcW'))
    if ex is not None:
        tcPr.remove(ex)
    tcPr.append(tcW)

def set_cell_margins(cell, top=60, bottom=60, left=100, right=100):
    tcPr  = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for side, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        el = OxmlElement(f'w:{side}')
        el.set(qn('w:w'),    str(val))
        el.set(qn('w:type'), 'dxa')
        tcMar.append(el)
    tcPr.append(tcMar)

def set_table_width(table, inches):
    tbl   = table._tbl
    tblPr = tbl.find(qn('w:tblPr'))
    if tblPr is None:
        tblPr = OxmlElement('w:tblPr')
        tbl.insert(0, tblPr)
    tblW = OxmlElement('w:tblW')
    tblW.set(qn('w:w'),    str(int(inches * 1440)))
    tblW.set(qn('w:type'), 'dxa')
    ex = tblPr.find(qn('w:tblW'))
    if ex is not None:
        tblPr.remove(ex)
    tblPr.append(tblW)

def para(cell, text='', bold=False, size=10, color=None,
         align=WD_ALIGN_PARAGRAPH.LEFT, italic=False, new=False):
    p = cell.add_paragraph() if new else cell.paragraphs[0]
    p.alignment = align
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after  = Pt(0)
    if text:
        r = p.add_run(text)
        r.bold = bold; r.italic = italic
        r.font.size = Pt(size)
        if color:
            r.font.color.rgb = color
    return p

def spacer(doc, pts=4):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after  = Pt(0)
    p.paragraph_format.line_spacing = Pt(pts)

def _impact_cell(cell, label: str, value: str):
    valid = {"Yes", "No", "TBD"}
    if value not in valid:
        value = "TBD"
    for _p in cell.paragraphs[1:]:
        _p._element.getparent().remove(_p._element)
    p0 = cell.paragraphs[0]
    p0.paragraph_format.space_before = Pt(0)
    p0.paragraph_format.space_after  = Pt(0)
    r0 = p0.add_run(label)
    r0.bold = True
    r0.font.size = Pt(9)
    for opt in ("Yes", "No", "TBD"):
        tick = "☑" if opt == value else "☐"
        text = f"{tick} {opt}"
        if opt == "TBD":
            text += "  _______________"
        p = cell.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after  = Pt(0)
        r = p.add_run(text)
        r.font.size = Pt(9)
    cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP

def _fit_image(iw, ih, max_w, max_h):
    """Return (display_w, display_h) in inches maintaining aspect ratio."""
    if ih == 0:
        return max_w, max_h
    ratio = iw / ih
    w = min(max_w, max_h * ratio)
    h = w / ratio
    return w, h

def _get_img_info(snapshots):
    """Return list of (path, pixel_w, pixel_h) for each snapshot."""
    info = []
    for path in snapshots:
        try:
            with PILImage.open(path) as img:
                info.append((path, img.width, img.height))
        except Exception:
            info.append((path, 800, 600))
    return info

def _estimate_snap_height(snap_info, avail_w):
    """Estimate total vertical inches the snapshots will occupy."""
    n = len(snap_info)
    if n == 0:
        return 0.0
    cell_w = (avail_w - 0.2) / 2
    caption_h = 0.25
    if n == 1:
        _, iw, ih = snap_info[0]
        _, dh = _fit_image(iw, ih, avail_w, 6.0)
        return dh + caption_h
    if n == 2:
        _, iw0, ih0 = snap_info[0]
        _, iw1, ih1 = snap_info[1]
        if (iw0 >= ih0) and (iw1 >= ih1):
            _, dh0 = _fit_image(iw0, ih0, avail_w, 3.5)
            _, dh1 = _fit_image(iw1, ih1, avail_w, 3.5)
            return dh0 + dh1 + caption_h * 2
        else:
            _, dh0 = _fit_image(iw0, ih0, cell_w, 5.0)
            _, dh1 = _fit_image(iw1, ih1, cell_w, 5.0)
            return max(dh0, dh1) + caption_h
    total = 0.0
    for i in range(0, n, 2):
        row_h = 0.0
        for j in range(min(2, n - i)):
            _, iw, ih = snap_info[i + j]
            _, dh = _fit_image(iw, ih, cell_w, 3.5)
            row_h = max(row_h, dh)
        total += row_h + caption_h
    return total

def _borderless_table(doc, ncols, avail_w):
    """Add a borderless ncols-column table to doc."""
    tbl = doc.add_table(rows=1, cols=ncols)
    tblPr = tbl._tbl.find(qn('w:tblPr'))
    if tblPr is None:
        tblPr = OxmlElement('w:tblPr')
        tbl._tbl.insert(0, tblPr)
    tblB = OxmlElement('w:tblBorders')
    for side in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        el = OxmlElement(f'w:{side}')
        el.set(qn('w:val'), 'none')
        el.set(qn('w:sz'), '0')
        tblB.append(el)
    tblPr.append(tblB)
    set_table_width(tbl, avail_w)
    return tbl

def _fill_img_cell(cell, path, dw):
    """Put image into a table cell."""
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after  = Pt(0)
    p.add_run().add_picture(path, width=Inches(dw))
    cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP

def _embed_snapshots(doc, snap_info, avail_w):
    """Embed snapshots using smart layout (full-width / side-by-side / grid)."""
    n = len(snap_info)
    if n == 0:
        return
    cell_w = (avail_w - 0.2) / 2

    if n == 1:
        path, iw, ih = snap_info[0]
        dw, _ = _fit_image(iw, ih, avail_w, 5.0)
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after  = Pt(0)
        p.add_run().add_picture(path, width=Inches(dw))
        return

    if n == 2:
        path0, iw0, ih0 = snap_info[0]
        path1, iw1, ih1 = snap_info[1]
        both_landscape = (iw0 >= ih0) and (iw1 >= ih1)
        if both_landscape:
            for path, iw, ih in [(path0, iw0, ih0), (path1, iw1, ih1)]:
                dw, _ = _fit_image(iw, ih, avail_w, 3.2)
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(4)
                p.paragraph_format.space_after  = Pt(0)
                p.add_run().add_picture(path, width=Inches(dw))
        else:
            tbl = _borderless_table(doc, 2, avail_w)
            c0, c1 = tbl.cell(0, 0), tbl.cell(0, 1)
            set_cell_width(c0, cell_w)
            set_cell_width(c1, cell_w)
            dw0, _ = _fit_image(iw0, ih0, cell_w - 0.1, 4.5)
            dw1, _ = _fit_image(iw1, ih1, cell_w - 0.1, 4.5)
            _fill_img_cell(c0, path0, dw0)
            _fill_img_cell(c1, path1, dw1)
        return

    for row_start in range(0, n, 2):
        row_items = snap_info[row_start:row_start + 2]
        ncols     = len(row_items)
        each_w    = avail_w / ncols
        tbl       = _borderless_table(doc, ncols, avail_w)
        for j, (path, iw, ih) in enumerate(row_items):
            cell = tbl.cell(0, j)
            set_cell_width(cell, each_w - 0.05)
            dw, _ = _fit_image(iw, ih, each_w - 0.15, 3.0)
            _fill_img_cell(cell, path, dw)


# ════════════════════════════════════════════════════════════
#  MAIN CALLABLE
# ════════════════════════════════════════════════════════════
def generate_rfi_document(config: dict) -> dict:
    """Generate the RFI Word document from a config dict.

    Returns a dict with keys:
        success      : bool
        output_path  : str  (empty on failure)
        message      : str
        logs         : list[str]
    """
    logs = []
    try:
        _BASE_EARLY = os.path.normpath(os.path.join(_HERE, ".."))

        # ── Extract config sections ───────────────────────────────────────────
        _project  = config.get("project", {})
        _co       = config.get("company", {})
        if not _co:
            _co = config.get("originator", {})
        _orig_cfg = config.get("originator", {})
        _client   = config.get("client", {})
        _paths    = config.get("paths", {})
        _settings = config.get("settings", {})
        _approved = config.get("approved_rfis", [])

        # ── Project / company / originator ───────────────────────────────────
        PROJECT_NAME    = _project.get("name", "")
        PROJECT_ADDRESS = _project.get("address", "")
        CONTRACT_NO     = _project.get("project_number", "")

        ORIGINATOR_NAME  = _orig_cfg.get("name",  _co.get("originator_name",  ""))
        ORIGINATOR_TITLE = _orig_cfg.get("title", _co.get("originator_title", ""))
        ORIGINATOR_PHONE = _orig_cfg.get("phone", _co.get("originator_phone", ""))
        ORIGINATOR_EMAIL = _orig_cfg.get("email", _co.get("originator_email", ""))
        COMPANY_NAME     = _co.get("name", _co.get("company_name", _co.get("company", "")))
        COMPANY_WEB      = _co.get("website", _co.get("company_website", ""))

        CLIENT_COMPANY = _client.get("company", "")
        CLIENT_ATTN    = _client.get("attn",    "")
        CLIENT_EMAIL   = _client.get("email",   "")
        CLIENT_PHONE   = _client.get("phone",   "")
        CLIENT_ROLE    = _client.get("role",    "")

        SNAPSHOTS_DIR = _paths.get("snapshots", "")
        OUTPUT_DIR    = _paths.get("output",    "")
        MAX_SNAPSHOTS = int(_settings.get("max_snapshots", 6))

        # ── Local helpers ─────────────────────────────────────────────────────
        def _abs(p):
            """Return absolute path; search SNAPSHOTS_DIR, _HERE, _BASE_EARLY."""
            if not p:
                return ""
            if os.path.isabs(p) and os.path.exists(p):
                return p
            if SNAPSHOTS_DIR:
                c = os.path.join(SNAPSHOTS_DIR, p)
                if os.path.exists(c):
                    return c
            return p

        def get_snapshots(rfi_num):
            snaps = []
            for i in range(1, MAX_SNAPSHOTS + 1):
                path = os.path.join(SNAPSHOTS_DIR, f"RFI_{rfi_num:03d}_snap{i}.png")
                if os.path.exists(path):
                    snaps.append(path)
            return snaps

        # ── Logo / signature ──────────────────────────────────────────────────
        LOGO_IMG      = _abs(_paths.get("logo",      _co.get("company_logo",    "")))
        SIGNATURE_IMG = _abs(_paths.get("signature", _co.get("signature_image", "")))

        if not LOGO_IMG or not os.path.exists(LOGO_IMG):
            LOGO_IMG = ""
        if not SIGNATURE_IMG or not os.path.exists(SIGNATURE_IMG):
            SIGNATURE_IMG = ""

        # ── Dates / filename ──────────────────────────────────────────────────
        today     = date.today()
        today_str = today.strftime("%d %B %Y")
        if len(_approved) == 1:
            _rfi0 = _approved[0].get('rfi_number', 1)
            if isinstance(_rfi0, str):
                _m = re.search(r'\d+', _rfi0)
                _rfi0 = int(_m.group()) if _m else 1
            filename = f"RFI_{_rfi0:03d}_{PROJECT_NAME.replace(' ', '_')}_{today.strftime('%d%m%Y')}.docx"
        else:
            filename = f"RFI_{PROJECT_NAME.replace(' ', '_')}_{today.strftime('%d%m%Y')}.docx"

        # ── Directories ───────────────────────────────────────────────────────
        if SNAPSHOTS_DIR:
            os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
        if OUTPUT_DIR:
            os.makedirs(OUTPUT_DIR, exist_ok=True)

        # ── Output path ───────────────────────────────────────────────────────
        out_path = os.path.join(OUTPUT_DIR, filename)
        logs.append(f"Building {len(_approved)} RFIs - A4 Landscape")

        # ════════════════════════════════════════════════════════════
        #  DOCUMENT GENERATION
        # ════════════════════════════════════════════════════════════
        doc = Document()
        doc.styles['Normal'].font.name = 'Arial'
        doc.styles['Normal'].font.size = Pt(10)

        for idx, issue in enumerate(_approved):

            def _set_row_min_height(row, inches):
                trPr = row._tr.get_or_add_trPr()
                trHeight = OxmlElement('w:trHeight')
                trHeight.set(qn('w:val'), str(int(inches * 1440)))
                trHeight.set(qn('w:hRule'), 'atLeast')
                trPr.append(trHeight)

            rfi_num = issue.get('rfi_number', idx + 1)
            if isinstance(rfi_num, str):
                m = re.search(r'\d+', rfi_num)
                rfi_num = int(m.group()) if m else idx + 1
            rfi_ref    = f"RFI-{rfi_num:03d}"
            sheets_str  = issue.get('sheets', issue.get('pages', ''))
            priority    = issue.get('priority', '')
            response_by = issue.get('response_required_by', '')
            try:
                response_by = datetime.strptime(response_by, "%Y-%m-%d").strftime("%d %B %Y")
            except (ValueError, TypeError):
                pass

            logs.append(f"  Building {rfi_ref}...")

            # ── Load snapshots early so we can pick orientation ───────────
            snapshots = get_snapshots(rfi_num)
            snap_info = _get_img_info(snapshots)

            est_h        = _estimate_snap_height(snap_info, 9.5)
            use_portrait = est_h > 4.5

            if use_portrait:
                pg_w   = Inches(8.27)
                pg_h   = Inches(11.69)
                cw     = 7.07
                orient = WD_ORIENT.PORTRAIT
                logs.append(f"    Portrait layout (estimated snap height {est_h:.1f}\")")
            else:
                pg_w   = PAGE_W
                pg_h   = PAGE_H
                cw     = CW
                orient = WD_ORIENT.LANDSCAPE

            s            = cw / CW
            snap_avail_w = round(cw - 0.4, 3)

            # ── Section setup ─────────────────────────────────────────────
            if idx == 0:
                section = doc.sections[0]
            else:
                section = doc.add_section()

            section.orientation   = orient
            section.page_width    = pg_w
            section.page_height   = pg_h
            section.left_margin   = MARGIN_L
            section.right_margin  = MARGIN_R
            section.top_margin    = MARGIN_T
            section.bottom_margin = MARGIN_B

            # ── Logo (standalone paragraphs) ──────────────────────────────
            if LOGO_IMG and os.path.exists(LOGO_IMG):
                lp = doc.add_paragraph()
                lp.paragraph_format.space_before = Pt(0)
                lp.paragraph_format.space_after  = Pt(2)
                lp.add_run().add_picture(LOGO_IMG, height=Inches(0.5))
            cn_p = doc.add_paragraph()
            cn_p.paragraph_format.space_before = Pt(0)
            cn_p.paragraph_format.space_after  = Pt(4)
            cn_r = cn_p.add_run(COMPANY_NAME)
            cn_r.bold = True; cn_r.font.size = Pt(13)

            # ── TABLE 1: Job Header ───────────────────────────────────────
            t1 = doc.add_table(rows=1, cols=2)
            t1.style = 'Table Grid'
            set_table_width(t1, cw)
            t1_lw = round(cw / 2, 3)
            t1_rw = round(cw - t1_lw, 3)
            t1_lc = t1.cell(0, 0); t1_rc = t1.cell(0, 1)
            set_cell_width(t1_lc, t1_lw); set_cell_width(t1_rc, t1_rw)
            set_cell_margins(t1_lc, 60, 60, 100, 100)
            set_cell_margins(t1_rc, 60, 60, 100, 100)
            set_cell_bg(t1_lc, C_INFOBG); set_cell_bg(t1_rc, C_INFOBG)
            t1_lc.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            t1_rc.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            t1_lp = t1_lc.paragraphs[0]
            t1_lp.paragraph_format.space_before = Pt(0)
            t1_lp.paragraph_format.space_after  = Pt(0)
            t1_rl = t1_lp.add_run("Job No:  "); t1_rl.bold = True; t1_rl.font.size = Pt(9)
            t1_rv = t1_lp.add_run(CONTRACT_NO); t1_rv.font.size = Pt(9)
            t1_rp = t1_rc.paragraphs[0]
            t1_rp.paragraph_format.space_before = Pt(0)
            t1_rp.paragraph_format.space_after  = Pt(0)
            t1_rl2 = t1_rp.add_run("Contract Name:  "); t1_rl2.bold = True; t1_rl2.font.size = Pt(9)
            t1_rv2 = t1_rp.add_run(PROJECT_NAME); t1_rv2.font.size = Pt(9)

            spacer(doc, 4)

            # ── TABLE 2: Document Header ──────────────────────────────────
            t2 = doc.add_table(rows=6, cols=4)
            t2.style = 'Table Grid'
            set_table_width(t2, cw)
            t2_cw = [
                round(1.5 * s, 3),
                round(4.0 * s, 3),
                round(1.5 * s, 3),
                round(cw - (1.5 + 4.0 + 1.5) * s, 3),
            ]

            # Row 0: Subject Description | value | Document No | rfi_ref
            for ci, (content, is_lbl) in enumerate([
                ("Subject Description:", True),
                (issue['description'],   False),
                ("Document No:",         True),
                (rfi_ref,                False),
            ]):
                cell = t2.cell(0, ci)
                set_cell_width(cell, t2_cw[ci])
                set_cell_margins(cell, 60, 60, 100, 100)
                cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                if is_lbl:
                    set_cell_bg(cell, C_INFOBG)
                    para(cell, content, bold=True, size=9)
                else:
                    para(cell, content, size=9)

            # Row 1: Revision | 0Q | Date | today_str
            for ci, (lbl, val, is_lbl) in enumerate([
                ("Revision:", "0Q", True),
                (None, "0Q", False),
                ("Date:", today_str, True),
                (None, today_str, False),
            ]):
                cell = t2.cell(1, ci)
                set_cell_width(cell, t2_cw[ci])
                set_cell_margins(cell, 60, 60, 100, 100)
                cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                if is_lbl:
                    set_cell_bg(cell, C_INFOBG)
                    para(cell, lbl, bold=True, size=9)
                else:
                    para(cell, val, size=9)

            # Row 2: From (Originator) | merged value
            t2_r2_lc = t2.cell(2, 0)
            t2_r2_vc = t2.cell(2, 1).merge(t2.cell(2, 3))
            for _p in t2_r2_vc.paragraphs[1:]:
                _p._element.getparent().remove(_p._element)
            set_cell_width(t2_r2_lc, t2_cw[0])
            set_cell_margins(t2_r2_lc, 60, 60, 100, 100)
            set_cell_margins(t2_r2_vc, 60, 60, 100, 100)
            set_cell_bg(t2_r2_lc, C_INFOBG)
            t2_r2_lc.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            t2_r2_vc.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            para(t2_r2_lc, "From (Originator):", bold=True, size=9)
            para(t2_r2_vc, f"{ORIGINATOR_NAME} — {COMPANY_NAME}", size=9)

            # Row 3: To (Recipient) | merged value
            t2_r3_lc = t2.cell(3, 0)
            t2_r3_vc = t2.cell(3, 1).merge(t2.cell(3, 3))
            for _p in t2_r3_vc.paragraphs[1:]:
                _p._element.getparent().remove(_p._element)
            set_cell_width(t2_r3_lc, t2_cw[0])
            set_cell_margins(t2_r3_lc, 60, 60, 100, 100)
            set_cell_margins(t2_r3_vc, 60, 60, 100, 100)
            set_cell_bg(t2_r3_lc, C_INFOBG)
            t2_r3_lc.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            t2_r3_vc.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            para(t2_r3_lc, "To (Recipient):", bold=True, size=9)
            para(t2_r3_vc, f"{CLIENT_ATTN} — {CLIENT_COMPANY}", size=9)

            # Row 4: Instructions (merged full width)
            t2_r4 = t2.cell(4, 0).merge(t2.cell(4, 3))
            for _p in t2_r4.paragraphs[1:]:
                _p._element.getparent().remove(_p._element)
            set_cell_margins(t2_r4, 60, 60, 100, 100)
            set_cell_bg(t2_r4, "F2F2F2")
            t2_r4_p = t2_r4.paragraphs[0]
            t2_r4_p.paragraph_format.space_before = Pt(0)
            t2_r4_p.paragraph_format.space_after  = Pt(0)
            t2_r4_lbl = t2_r4_p.add_run("Instructions:"); t2_r4_lbl.bold = True; t2_r4_lbl.font.size = Pt(8)
            instructions_text = config.get("instructions_text", "")
            if instructions_text:
                t2_r4_vp = t2_r4.add_paragraph()
                t2_r4_vp.paragraph_format.space_before = Pt(2)
                t2_r4_vp.paragraph_format.space_after  = Pt(0)
                t2_r4_vp.add_run(instructions_text).font.size = Pt(8)

            # Row 5: Superintendent Note (merged full width)
            t2_r5 = t2.cell(5, 0).merge(t2.cell(5, 3))
            for _p in t2_r5.paragraphs[1:]:
                _p._element.getparent().remove(_p._element)
            set_cell_margins(t2_r5, 60, 60, 100, 100)
            set_cell_bg(t2_r5, "F2F2F2")
            t2_r5_p = t2_r5.paragraphs[0]
            t2_r5_p.paragraph_format.space_before = Pt(0)
            t2_r5_p.paragraph_format.space_after  = Pt(0)
            t2_r5_lbl = t2_r5_p.add_run("Superintendent Note:"); t2_r5_lbl.bold = True; t2_r5_lbl.font.size = Pt(8)
            superintendent_text = config.get("superintendent_text", "")
            if superintendent_text:
                t2_r5_vp = t2_r5.add_paragraph()
                t2_r5_vp.paragraph_format.space_before = Pt(2)
                t2_r5_vp.paragraph_format.space_after  = Pt(0)
                t2_r5_vp.add_run(superintendent_text).font.size = Pt(8)

            spacer(doc, 4)

            # ── TABLE 3: REV 0Q (Question) ────────────────────────────────
            t3_col_w = [round(cw * 0.40, 3), round(cw * 0.30, 3), round(cw - cw * 0.40 - cw * 0.30, 3)]
            t3 = doc.add_table(rows=3, cols=3)
            t3.style = 'Table Grid'
            set_table_width(t3, cw)

            # Row 0: header
            t3_h0 = t3.cell(0, 0); t3_h1 = t3.cell(0, 1); t3_h2 = t3.cell(0, 2)
            set_cell_width(t3_h0, t3_col_w[0])
            set_cell_width(t3_h1, t3_col_w[1])
            set_cell_width(t3_h2, t3_col_w[2])
            set_cell_margins(t3_h0, 60, 60, 100, 100)
            set_cell_margins(t3_h1, 60, 60, 100, 100)
            set_cell_margins(t3_h2, 60, 60, 100, 100)
            set_cell_bg(t3_h0, C_ACCENT)
            t3_h0.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            t3_h1.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            t3_h2.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            t3_hp = para(t3_h0, "RFI REV 0Q", bold=True, size=10)
            t3_hp.runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            para(t3_h1, f"Date Sent:  {today_str}", size=9)
            para(t3_h2, f"Response Due Date:  {response_by}", size=9)

            # Row 1: Question (merged full width)
            t3_q = t3.cell(1, 0).merge(t3.cell(1, 2))
            for _p in t3_q.paragraphs[1:]:
                _p._element.getparent().remove(_p._element)
            set_cell_margins(t3_q, 80, 80, 100, 100)
            t3_q.vertical_alignment = WD_ALIGN_VERTICAL.TOP
            t3_qp1 = t3_q.paragraphs[0]
            t3_qp1.paragraph_format.space_before = Pt(0)
            t3_qp1.paragraph_format.space_after  = Pt(4)
            t3_ql = t3_qp1.add_run("Question:"); t3_ql.bold = True; t3_ql.font.size = Pt(10)
            t3_qp2 = t3_q.add_paragraph()
            t3_qp2.paragraph_format.space_before = Pt(0)
            t3_qp2.paragraph_format.space_after  = Pt(0)
            t3_qp2.add_run(issue.get("question", issue.get("description", ""))).font.size = Pt(10)
            _set_row_min_height(t3.rows[1], 1.0)

            # Row 2: Reference Document No
            t3_r2_lc = t3.cell(2, 0)
            t3_r2_vc = t3.cell(2, 1).merge(t3.cell(2, 2))
            for _p in t3_r2_vc.paragraphs[1:]:
                _p._element.getparent().remove(_p._element)
            set_cell_width(t3_r2_lc, t3_col_w[0])
            set_cell_margins(t3_r2_lc, 60, 60, 100, 100)
            set_cell_margins(t3_r2_vc, 60, 60, 100, 100)
            set_cell_bg(t3_r2_lc, C_INFOBG)
            t3_r2_lc.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            t3_r2_vc.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            para(t3_r2_lc, "Reference Document No:", bold=True, size=9)
            para(t3_r2_vc, issue.get("reference_doc", ""), size=9)

            # ── Snapshots ─────────────────────────────────────────────────
            if snap_info:
                _embed_snapshots(doc, snap_info, snap_avail_w)
                for i, (path, iw, ih) in enumerate(snap_info, 1):
                    logs.append(f"    Snap {i}: {os.path.basename(path)}  ({iw}x{ih}px)")
                spacer(doc, 4)
            else:
                logs.append(f"    WARNING: No snapshots found for {rfi_ref}")

            spacer(doc, 4)

            # ── TABLE 4: REV 0R (Response — blank) ───────────────────────
            t4 = doc.add_table(rows=3, cols=3)
            t4.style = 'Table Grid'
            set_table_width(t4, cw)

            # Row 0: header
            t4_h0 = t4.cell(0, 0); t4_h1 = t4.cell(0, 1); t4_h2 = t4.cell(0, 2)
            set_cell_width(t4_h0, t3_col_w[0])
            set_cell_width(t4_h1, t3_col_w[1])
            set_cell_width(t4_h2, t3_col_w[2])
            set_cell_margins(t4_h0, 60, 60, 100, 100)
            set_cell_margins(t4_h1, 60, 60, 100, 100)
            set_cell_margins(t4_h2, 60, 60, 100, 100)
            set_cell_bg(t4_h0, C_ACCENT)
            t4_h0.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            t4_h1.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            t4_h2.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            t4_hp = para(t4_h0, "RFI REV 0R", bold=True, size=10)
            t4_hp.runs[0].font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            para(t4_h1, "Date Sent:  ", size=9)
            para(t4_h2, "Response Due Date:  ", size=9)

            # Row 1: Response (merged full width, blank — tall)
            t4_r = t4.cell(1, 0).merge(t4.cell(1, 2))
            for _p in t4_r.paragraphs[1:]:
                _p._element.getparent().remove(_p._element)
            set_cell_margins(t4_r, 80, 80, 100, 100)
            t4_r.vertical_alignment = WD_ALIGN_VERTICAL.TOP
            t4_rp = t4_r.paragraphs[0]
            t4_rp.paragraph_format.space_before = Pt(0)
            t4_rp.paragraph_format.space_after  = Pt(0)
            t4_rl = t4_rp.add_run("Response:"); t4_rl.bold = True; t4_rl.font.size = Pt(10)
            _set_row_min_height(t4.rows[1], 1.5)

            # Row 2: Reference Document No (blank)
            t4_r2_lc = t4.cell(2, 0)
            t4_r2_vc = t4.cell(2, 1).merge(t4.cell(2, 2))
            for _p in t4_r2_vc.paragraphs[1:]:
                _p._element.getparent().remove(_p._element)
            set_cell_width(t4_r2_lc, t3_col_w[0])
            set_cell_margins(t4_r2_lc, 60, 60, 100, 100)
            set_cell_margins(t4_r2_vc, 60, 60, 100, 100)
            set_cell_bg(t4_r2_lc, C_INFOBG)
            t4_r2_lc.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            t4_r2_vc.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            para(t4_r2_lc, "Reference Document No:", bold=True, size=9)
            para(t4_r2_vc, "", size=9)

            spacer(doc, 4)

            # ── TABLE 5: Impact and Approval ──────────────────────────────
            t5_lw = round(1.5 * s, 3)
            t5_vw = round((cw - t5_lw) / 4, 3)
            t5 = doc.add_table(rows=3, cols=5)
            t5.style = 'Table Grid'
            set_table_width(t5, cw)

            # Row 0: Impact
            t5_r0_cells = [t5.cell(0, ci) for ci in range(5)]
            set_cell_width(t5_r0_cells[0], t5_lw)
            for ci in range(1, 5):
                set_cell_width(t5_r0_cells[ci], t5_vw)
            for ci in range(5):
                set_cell_margins(t5_r0_cells[ci], 60, 60, 100, 100)
            set_cell_bg(t5_r0_cells[0], C_INFOBG)
            t5_r0_cells[0].vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            para(t5_r0_cells[0], "Impact to:", bold=True, size=9)
            _impact_cell(t5_r0_cells[1], "Cost",                      issue.get('cost_impact',          'TBD'))
            _impact_cell(t5_r0_cells[2], "Schedule",                   issue.get('schedule_impact',      'TBD'))
            _impact_cell(t5_r0_cells[3], "Environmental / Regulatory", issue.get('environmental_impact', 'TBD'))
            _impact_cell(t5_r0_cells[4], "Public Affairs",             issue.get('public_affairs_impact','TBD'))
            _set_row_min_height(t5.rows[0], 0.9)

            # Row 1: Employer's Instruction (merged, blank)
            t5_r1 = t5.cell(1, 0).merge(t5.cell(1, 4))
            for _p in t5_r1.paragraphs[1:]:
                _p._element.getparent().remove(_p._element)
            set_cell_margins(t5_r1, 80, 80, 100, 100)
            t5_r1.vertical_alignment = WD_ALIGN_VERTICAL.TOP
            t5_r1_p = t5_r1.paragraphs[0]
            t5_r1_p.paragraph_format.space_before = Pt(0)
            t5_r1_p.paragraph_format.space_after  = Pt(0)
            t5_r1_l = t5_r1_p.add_run("Employer's Instruction:"); t5_r1_l.bold = True; t5_r1_l.font.size = Pt(9)
            _set_row_min_height(t5.rows[1], 0.8)

            # Row 2: Approval Signature (merged)
            t5_r2 = t5.cell(2, 0).merge(t5.cell(2, 4))
            for _p in t5_r2.paragraphs[1:]:
                _p._element.getparent().remove(_p._element)
            set_cell_margins(t5_r2, 80, 80, 100, 100)
            t5_r2.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            t5_r2_p1 = t5_r2.paragraphs[0]
            t5_r2_p1.paragraph_format.space_before = Pt(0)
            t5_r2_p1.paragraph_format.space_after  = Pt(4)
            t5_r2_lbl = t5_r2_p1.add_run("Approval Signature:"); t5_r2_lbl.bold = True; t5_r2_lbl.font.size = Pt(9)
            t5_r2_p2 = t5_r2.add_paragraph()
            t5_r2_p2.paragraph_format.space_before = Pt(0)
            t5_r2_p2.paragraph_format.space_after  = Pt(0)
            t5_r2_p2.add_run(f"Name: {ORIGINATOR_NAME}     Signature: ________________________     Date: {today_str}").font.size = Pt(9)
            if SIGNATURE_IMG and os.path.exists(SIGNATURE_IMG):
                try:
                    t5_r2_p2.runs[0].text = f"Name: {ORIGINATOR_NAME}     Signature: "
                    t5_r2_p2.add_run().add_picture(SIGNATURE_IMG, height=Inches(0.30))
                    t5_r2_p2.add_run(f"     Date: {today_str}").font.size = Pt(9)
                    logs.append("    Signature embedded")
                except Exception as e:
                    logs.append(f"    Signature warning: {e}")

            logs.append(f"  {rfi_ref} done - OK")

        # ── Save ──────────────────────────────────────────────────────────────
        doc.save(out_path)

        return {
            "success":     True,
            "output_path": out_path,
            "message":     f"SUCCESS - File: {out_path} - RFIs: {len(_approved)}",
            "logs":        logs,
        }

    except Exception as e:
        return {
            "success":     False,
            "output_path": "",
            "message":     f"ERROR: {type(e).__name__}: {e}",
            "logs":        logs,
        }
