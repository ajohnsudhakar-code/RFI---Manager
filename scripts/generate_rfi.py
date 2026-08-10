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
    valid = {"Yes", "No"}
    if value not in valid:
        value = ""
    for _p in cell.paragraphs[1:]:
        _p._element.getparent().remove(_p._element)
    p0 = cell.paragraphs[0]
    p0.paragraph_format.space_before = Pt(0)
    p0.paragraph_format.space_after  = Pt(0)
    r0 = p0.add_run(label)
    r0.bold = True
    r0.font.size = Pt(9)
    for opt in ("Yes", "No"):
        tick = "☑" if opt == value else "☐"
        p = cell.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after  = Pt(0)
        r = p.add_run(f"{tick} {opt}")
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
        COMPANY_ADDRESS  = _co.get("address", "")
        COMPANY_CITY     = _co.get("city", "")
        COMPANY_COUNTRY  = _co.get("country", "")
        COMPANY_POSTCODE = _co.get("postcode", "")

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
            import glob as _glob
            pattern = os.path.join(SNAPSHOTS_DIR, f"RFI_{rfi_num:03d}_*_snap*.png")
            return sorted(_glob.glob(pattern))

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

            # ── Section setup — Page 1 ────────────────────────────────────
            if idx == 0:
                section_p1 = doc.sections[0]
            else:
                section_p1 = doc.add_section()
            section_p1.orientation   = orient
            section_p1.page_width    = pg_w
            section_p1.page_height   = pg_h
            section_p1.left_margin   = MARGIN_L
            section_p1.right_margin  = MARGIN_R
            section_p1.top_margin    = MARGIN_T
            section_p1.bottom_margin = MARGIN_B

            # ── PAGE 1: Header table ──────────────────────────────────────
            cw_p1_lw = round(cw * 0.55, 3)
            cw_p1_rw = round(cw - cw_p1_lw, 3)
            t_hdr = _borderless_table(doc, 2, cw)
            t_hdr_lc = t_hdr.cell(0, 0)
            t_hdr_rc = t_hdr.cell(0, 1)
            set_cell_width(t_hdr_lc, cw_p1_lw)
            set_cell_width(t_hdr_rc, cw_p1_rw)
            set_cell_margins(t_hdr_lc, 40, 40, 60, 60)
            set_cell_margins(t_hdr_rc, 40, 40, 60, 60)
            t_hdr_lc.vertical_alignment = WD_ALIGN_VERTICAL.TOP
            t_hdr_rc.vertical_alignment = WD_ALIGN_VERTICAL.TOP

            # Left cell: logo + company info
            if LOGO_IMG and os.path.exists(LOGO_IMG):
                _lp = t_hdr_lc.paragraphs[0]
                _lp.paragraph_format.space_before = Pt(0)
                _lp.paragraph_format.space_after  = Pt(2)
                _lp.add_run().add_picture(LOGO_IMG, height=Inches(0.45))
                _cn_p = t_hdr_lc.add_paragraph()
            else:
                _cn_p = t_hdr_lc.paragraphs[0]
            _cn_p.paragraph_format.space_before = Pt(0)
            _cn_p.paragraph_format.space_after  = Pt(0)
            _cn_r = _cn_p.add_run(COMPANY_NAME)
            _cn_r.bold = True; _cn_r.font.size = Pt(12); _cn_r.font.color.rgb = C_BLUE

            _city_postcode = " ".join(p for p in [COMPANY_CITY, COMPANY_POSTCODE] if p)
            _addr_parts = [p for p in [COMPANY_ADDRESS, _city_postcode, COMPANY_COUNTRY] if p]
            _addr_str = ", ".join(_addr_parts)
            _addr_p = t_hdr_lc.add_paragraph()
            _addr_p.paragraph_format.space_before = Pt(0)
            _addr_p.paragraph_format.space_after  = Pt(0)
            if _addr_str:
                _addr_r = _addr_p.add_run(_addr_str)
                _addr_r.font.size = Pt(8); _addr_r.font.color.rgb = C_GRAY
            _web_p = t_hdr_lc.add_paragraph()
            _web_p.paragraph_format.space_before = Pt(0)
            _web_p.paragraph_format.space_after  = Pt(0)
            if COMPANY_WEB:
                _web_r = _web_p.add_run(COMPANY_WEB)
                _web_r.font.size = Pt(8); _web_r.font.color.rgb = C_GRAY

            # Right cell: RFI title + meta
            _rfi_title_p = t_hdr_rc.paragraphs[0]
            _rfi_title_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            _rfi_title_p.paragraph_format.space_before = Pt(0)
            _rfi_title_p.paragraph_format.space_after  = Pt(2)
            _rfi_title_r = _rfi_title_p.add_run("REQUEST FOR INFORMATION")
            _rfi_title_r.bold = True; _rfi_title_r.font.size = Pt(14); _rfi_title_r.font.color.rgb = C_BLUE
            _rfi_meta_p = t_hdr_rc.add_paragraph()
            _rfi_meta_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            _rfi_meta_p.paragraph_format.space_before = Pt(0)
            _rfi_meta_p.paragraph_format.space_after  = Pt(0)
            _rfi_meta_r = _rfi_meta_p.add_run(f"Document No: {rfi_ref}  |  Revision: 0Q  |  Date: {today_str}")
            _rfi_meta_r.font.size = Pt(9); _rfi_meta_r.font.color.rgb = C_GRAY

            # Navy divider line
            _div = doc.add_paragraph()
            _div.paragraph_format.space_before = Pt(0)
            _div.paragraph_format.space_after  = Pt(4)
            _div_pPr = _div._p.get_or_add_pPr()
            _div_pBdr = OxmlElement('w:pBdr')
            _div_bot = OxmlElement('w:bottom')
            _div_bot.set(qn('w:val'), 'single')
            _div_bot.set(qn('w:sz'), '12')
            _div_bot.set(qn('w:space'), '1')
            _div_bot.set(qn('w:color'), '1A3A6B')
            _div_pBdr.append(_div_bot)
            _div_pPr.append(_div_pBdr)

            spacer(doc, 4)

            # ── TABLE A: Project Info (1 row, 4 cols) ─────────────────────
            _ta_cw = [round(cw*0.20,3), round(cw*0.45,3), round(cw*0.18,3),
                      round(cw - cw*0.20 - cw*0.45 - cw*0.18, 3)]
            t_a = doc.add_table(rows=1, cols=4)
            t_a.style = 'Table Grid'
            set_table_width(t_a, cw)
            _ta_data = [
                ("Job no.",      CONTRACT_NO,  False),
                ("Project name", PROJECT_NAME, False),
                ("Date raised",  today_str,    False),
                ("Response due", response_by,  True),
            ]
            for ci, (lbl, val, is_red) in enumerate(_ta_data):
                _c = t_a.cell(0, ci)
                set_cell_width(_c, _ta_cw[ci])
                set_cell_margins(_c, 60, 60, 100, 100)
                set_cell_bg(_c, C_INFOBG)
                _c.vertical_alignment = WD_ALIGN_VERTICAL.TOP
                _lp = _c.paragraphs[0]
                _lp.paragraph_format.space_before = Pt(0)
                _lp.paragraph_format.space_after  = Pt(0)
                _lr = _lp.add_run(lbl)
                _lr.bold = True; _lr.font.size = Pt(8); _lr.font.color.rgb = C_BLUE
                _vp = _c.add_paragraph()
                _vp.paragraph_format.space_before = Pt(0)
                _vp.paragraph_format.space_after  = Pt(0)
                _vr = _vp.add_run(val)
                _vr.font.size = Pt(9)
                if is_red:
                    _vr.bold = True; _vr.font.color.rgb = C_RED

            spacer(doc, 4)

            # ── TABLE B: Identification (6 rows, 4 equal cols) ────────────
            _tb_cw = round(cw / 4, 3)
            t_b = doc.add_table(rows=6, cols=4)
            t_b.style = 'Table Grid'
            set_table_width(t_b, cw)

            # Row 0: "IDENTIFICATION" header (merged, navy)
            _tb_r0 = t_b.cell(0, 0).merge(t_b.cell(0, 3))
            for _p in _tb_r0.paragraphs[1:]: _p._element.getparent().remove(_p._element)
            set_cell_bg(_tb_r0, C_ACCENT)
            set_cell_margins(_tb_r0, 60, 60, 100, 100)
            _tb_r0.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            _tb_r0_p = _tb_r0.paragraphs[0]
            _tb_r0_p.paragraph_format.space_before = Pt(0)
            _tb_r0_p.paragraph_format.space_after  = Pt(0)
            _tb_r0_r = _tb_r0_p.add_run("Identification")
            _tb_r0_r.bold = True; _tb_r0_r.font.size = Pt(10)
            _tb_r0_r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

            # Row 1: Subject (merged full width)
            _tb_r1 = t_b.cell(1, 0).merge(t_b.cell(1, 3))
            for _p in _tb_r1.paragraphs[1:]: _p._element.getparent().remove(_p._element)
            set_cell_margins(_tb_r1, 80, 80, 100, 100)
            _tb_r1_p1 = _tb_r1.paragraphs[0]
            _tb_r1_p1.paragraph_format.space_before = Pt(0)
            _tb_r1_p1.paragraph_format.space_after  = Pt(2)
            _tb_r1_lbl = _tb_r1_p1.add_run("Subject")
            _tb_r1_lbl.bold = True; _tb_r1_lbl.font.size = Pt(8); _tb_r1_lbl.font.color.rgb = C_BLUE
            _tb_r1_p2 = _tb_r1.add_paragraph()
            _tb_r1_p2.paragraph_format.space_before = Pt(0)
            _tb_r1_p2.paragraph_format.space_after  = Pt(0)
            _tb_r1_p2.add_run(issue.get('description', '')).font.size = Pt(10)

            # Row 2: Meta (4 separate cols)
            _tb_r2_data = [
                ("Document no.",       rfi_ref,                   False),
                ("Drawing ref.",       sheets_str,                False),
                ("Priority",           priority,                  True),
                ("Category",           issue.get('category', ''), False),
            ]
            for ci, (lbl, val, is_red) in enumerate(_tb_r2_data):
                _c = t_b.cell(2, ci)
                set_cell_width(_c, _tb_cw)
                set_cell_margins(_c, 60, 60, 100, 100)
                set_cell_bg(_c, C_INFOBG)
                _c.vertical_alignment = WD_ALIGN_VERTICAL.TOP
                _lp = _c.paragraphs[0]
                _lp.paragraph_format.space_before = Pt(0)
                _lp.paragraph_format.space_after  = Pt(0)
                _lr = _lp.add_run(lbl)
                _lr.bold = True; _lr.font.size = Pt(8); _lr.font.color.rgb = C_BLUE
                _vp = _c.add_paragraph()
                _vp.paragraph_format.space_before = Pt(0)
                _vp.paragraph_format.space_after  = Pt(0)
                _vr = _vp.add_run(val); _vr.font.size = Pt(9)
                if is_red:
                    _vr.bold = True; _vr.font.color.rgb = C_RED

            # Row 3: From/To (col 0+1 merged | col 2+3 merged)
            _tb_r3_left  = t_b.cell(3, 0).merge(t_b.cell(3, 1))
            _tb_r3_right = t_b.cell(3, 2).merge(t_b.cell(3, 3))
            for _merged in [_tb_r3_left, _tb_r3_right]:
                for _p in _merged.paragraphs[1:]: _p._element.getparent().remove(_p._element)
                set_cell_margins(_merged, 80, 80, 100, 100)
                _merged.vertical_alignment = WD_ALIGN_VERTICAL.TOP
            _tb_r3l_p = _tb_r3_left.paragraphs[0]
            _tb_r3l_p.paragraph_format.space_before = Pt(0)
            _tb_r3l_p.paragraph_format.space_after  = Pt(2)
            _tb_r3l_lbl = _tb_r3l_p.add_run("From")
            _tb_r3l_lbl.bold = True; _tb_r3l_lbl.font.size = Pt(8); _tb_r3l_lbl.font.color.rgb = C_BLUE
            _tb_r3l_vp = _tb_r3_left.add_paragraph()
            _tb_r3l_vp.paragraph_format.space_before = Pt(0)
            _tb_r3l_vp.paragraph_format.space_after  = Pt(0)
            _tb_r3l_vr = _tb_r3l_vp.add_run(ORIGINATOR_NAME)
            _tb_r3l_vr.bold = True; _tb_r3l_vr.font.size = Pt(10)
            _tb_r3l_cp = _tb_r3_left.add_paragraph()
            _tb_r3l_cp.paragraph_format.space_before = Pt(0)
            _tb_r3l_cp.paragraph_format.space_after  = Pt(0)
            _tb_r3l_cr = _tb_r3l_cp.add_run(COMPANY_NAME)
            _tb_r3l_cr.font.size = Pt(8); _tb_r3l_cr.font.color.rgb = C_GRAY
            _tb_r3r_p = _tb_r3_right.paragraphs[0]
            _tb_r3r_p.paragraph_format.space_before = Pt(0)
            _tb_r3r_p.paragraph_format.space_after  = Pt(2)
            _tb_r3r_lbl = _tb_r3r_p.add_run("To")
            _tb_r3r_lbl.bold = True; _tb_r3r_lbl.font.size = Pt(8); _tb_r3r_lbl.font.color.rgb = C_BLUE
            _tb_r3r_vp = _tb_r3_right.add_paragraph()
            _tb_r3r_vp.paragraph_format.space_before = Pt(0)
            _tb_r3r_vp.paragraph_format.space_after  = Pt(0)
            _tb_r3r_vr = _tb_r3r_vp.add_run(CLIENT_ATTN)
            _tb_r3r_vr.bold = True; _tb_r3r_vr.font.size = Pt(10)
            _tb_r3r_cp = _tb_r3_right.add_paragraph()
            _tb_r3r_cp.paragraph_format.space_before = Pt(0)
            _tb_r3r_cp.paragraph_format.space_after  = Pt(0)
            _tb_r3r_cr = _tb_r3r_cp.add_run(CLIENT_COMPANY)
            _tb_r3r_cr.font.size = Pt(8); _tb_r3r_cr.font.color.rgb = C_GRAY

            # Row 4: Instructions (merged, F2F2F2)
            instructions_text = config.get("instructions_text", "")
            _DEFAULT_INS = ("Originator shall complete Revision 0Q of this form and send to "
                            "the recipient for response within the specified period.")
            _tb_r4 = t_b.cell(4, 0).merge(t_b.cell(4, 3))
            for _p in _tb_r4.paragraphs[1:]: _p._element.getparent().remove(_p._element)
            set_cell_margins(_tb_r4, 80, 80, 100, 100)
            set_cell_bg(_tb_r4, "F2F2F2")
            _tb_r4_p1 = _tb_r4.paragraphs[0]
            _tb_r4_p1.paragraph_format.space_before = Pt(0)
            _tb_r4_p1.paragraph_format.space_after  = Pt(2)
            _tb_r4_lbl = _tb_r4_p1.add_run("Instructions")
            _tb_r4_lbl.bold = True; _tb_r4_lbl.font.size = Pt(8); _tb_r4_lbl.font.color.rgb = C_BLUE
            _tb_r4_p2 = _tb_r4.add_paragraph()
            _tb_r4_p2.paragraph_format.space_before = Pt(0)
            _tb_r4_p2.paragraph_format.space_after  = Pt(0)
            _tb_r4_p2.add_run(instructions_text if instructions_text else _DEFAULT_INS).font.size = Pt(8)

            # Row 5: Note (merged, F2F2F2)
            superintendent_text = config.get("superintendent_text", "")
            _DEFAULT_NOTE = ("Should the Superintendent consider this RFI to be a Change, the "
                             "Superintendent shall issue an Employer's Instruction.")
            _tb_r5 = t_b.cell(5, 0).merge(t_b.cell(5, 3))
            for _p in _tb_r5.paragraphs[1:]: _p._element.getparent().remove(_p._element)
            set_cell_margins(_tb_r5, 80, 80, 100, 100)
            set_cell_bg(_tb_r5, "F2F2F2")
            _tb_r5_p1 = _tb_r5.paragraphs[0]
            _tb_r5_p1.paragraph_format.space_before = Pt(0)
            _tb_r5_p1.paragraph_format.space_after  = Pt(2)
            _tb_r5_lbl = _tb_r5_p1.add_run("Note")
            _tb_r5_lbl.bold = True; _tb_r5_lbl.font.size = Pt(8); _tb_r5_lbl.font.color.rgb = C_BLUE
            _tb_r5_p2 = _tb_r5.add_paragraph()
            _tb_r5_p2.paragraph_format.space_before = Pt(0)
            _tb_r5_p2.paragraph_format.space_after  = Pt(0)
            _tb_r5_p2.add_run(superintendent_text if superintendent_text else _DEFAULT_NOTE).font.size = Pt(8)

            spacer(doc, 4)

            # ── TABLE C: REV 0Q Question (4 rows, 3 cols) ────────────────
            _tc_cw = [round(cw*0.38, 3), round(cw*0.31, 3),
                      round(cw - cw*0.38 - cw*0.31, 3)]
            t_c = doc.add_table(rows=4, cols=3)
            t_c.style = 'Table Grid'
            set_table_width(t_c, cw)

            # Row 0: header
            for ci, _tc_hc in enumerate([t_c.cell(0, ci) for ci in range(3)]):
                set_cell_width(_tc_hc, _tc_cw[ci])
                set_cell_margins(_tc_hc, 60, 60, 100, 100)
                _tc_hc.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            set_cell_bg(t_c.cell(0, 0), C_ACCENT)
            _tc_h0_p = t_c.cell(0, 0).paragraphs[0]
            _tc_h0_p.paragraph_format.space_before = Pt(0)
            _tc_h0_p.paragraph_format.space_after  = Pt(0)
            _tc_h0_r = _tc_h0_p.add_run("RFI Rev 0Q")
            _tc_h0_r.bold = True; _tc_h0_r.font.size = Pt(10)
            _tc_h0_r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            para(t_c.cell(0, 1), f"Date Sent:  {today_str}", size=9)
            _tc_h2_p = t_c.cell(0, 2).paragraphs[0]
            _tc_h2_p.paragraph_format.space_before = Pt(0)
            _tc_h2_p.paragraph_format.space_after  = Pt(0)
            _tc_h2_r = _tc_h2_p.add_run(f"Response Due Date:  {response_by}")
            _tc_h2_r.font.size = Pt(9)

            # Row 1: Question (merged full width)
            _tc_q = t_c.cell(1, 0).merge(t_c.cell(1, 2))
            for _p in _tc_q.paragraphs[1:]: _p._element.getparent().remove(_p._element)
            set_cell_margins(_tc_q, 80, 80, 100, 100)
            _tc_q.vertical_alignment = WD_ALIGN_VERTICAL.TOP
            _tc_qp1 = _tc_q.paragraphs[0]
            _tc_qp1.paragraph_format.space_before = Pt(0)
            _tc_qp1.paragraph_format.space_after  = Pt(4)
            _tc_ql = _tc_qp1.add_run("Question")
            _tc_ql.bold = True; _tc_ql.font.size = Pt(10); _tc_ql.font.color.rgb = C_BLUE
            _tc_qp2 = _tc_q.add_paragraph()
            _tc_qp2.paragraph_format.space_before = Pt(0)
            _tc_qp2.paragraph_format.space_after  = Pt(0)
            _tc_qp2.add_run(issue.get("question", issue.get("description", ""))).font.size = Pt(10)
            _set_row_min_height(t_c.rows[1], 1.2)

            # Row 2: Snapshots placeholder (zero-height if snaps exist, else "no snaps" message)
            _tc_s = t_c.cell(2, 0).merge(t_c.cell(2, 2))
            for _p in _tc_s.paragraphs[1:]: _p._element.getparent().remove(_p._element)
            set_cell_margins(_tc_s, 60, 60, 100, 100)
            if not snap_info:
                set_cell_bg(_tc_s, "F5F5F5")
                _tc_sp = _tc_s.paragraphs[0]
                _tc_sp.paragraph_format.space_before = Pt(0)
                _tc_sp.paragraph_format.space_after  = Pt(0)
                _tc_sp.alignment = WD_ALIGN_PARAGRAPH.CENTER
                _tc_sr = _tc_sp.add_run("[ No drawing snapshots attached ]")
                _tc_sr.italic = True; _tc_sr.font.size = Pt(9); _tc_sr.font.color.rgb = C_GRAY
            else:
                _tc_s.paragraphs[0].paragraph_format.space_before = Pt(0)
                _tc_s.paragraphs[0].paragraph_format.space_after  = Pt(0)

            # Row 3: Reference footer
            _tc_ref_left  = t_c.cell(3, 0).merge(t_c.cell(3, 1))
            _tc_ref_right = t_c.cell(3, 2)
            for _p in _tc_ref_left.paragraphs[1:]: _p._element.getparent().remove(_p._element)
            set_cell_bg(_tc_ref_left, C_INFOBG); set_cell_bg(_tc_ref_right, C_INFOBG)
            set_cell_margins(_tc_ref_left, 60, 60, 100, 100)
            set_cell_margins(_tc_ref_right, 60, 60, 100, 100)
            _tc_ref_left.vertical_alignment  = WD_ALIGN_VERTICAL.CENTER
            _tc_ref_right.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            _tc_rl_p = _tc_ref_left.paragraphs[0]
            _tc_rl_p.paragraph_format.space_before = Pt(0)
            _tc_rl_p.paragraph_format.space_after  = Pt(0)
            _tc_rl_lbl = _tc_rl_p.add_run("Reference document")
            _tc_rl_lbl.bold = True; _tc_rl_lbl.font.size = Pt(8); _tc_rl_lbl.font.color.rgb = C_BLUE
            _tc_rl_vp = _tc_ref_left.add_paragraph()
            _tc_rl_vp.paragraph_format.space_before = Pt(0)
            _tc_rl_vp.paragraph_format.space_after  = Pt(0)
            _tc_rl_vp.add_run(issue.get('reference_doc', '')).font.size = Pt(9)
            _tc_rr_p = _tc_ref_right.paragraphs[0]
            _tc_rr_p.paragraph_format.space_before = Pt(0)
            _tc_rr_p.paragraph_format.space_after  = Pt(0)
            _tc_rr_lbl = _tc_rr_p.add_run("Sheet ref.")
            _tc_rr_lbl.bold = True; _tc_rr_lbl.font.size = Pt(8); _tc_rr_lbl.font.color.rgb = C_BLUE
            _tc_rr_vp = _tc_ref_right.add_paragraph()
            _tc_rr_vp.paragraph_format.space_before = Pt(0)
            _tc_rr_vp.paragraph_format.space_after  = Pt(0)
            _tc_rr_vp.add_run(sheets_str).font.size = Pt(9)

            # Snapshots outside table (after Table C)
            _snaps_to_embed = snap_info[:5]
            if _snaps_to_embed:
                spacer(doc, 4)
                _total_snaps = len(_snaps_to_embed)
                for _si, (_spath, _siw, _sih) in enumerate(_snaps_to_embed, 1):
                    _sdw, _ = _fit_image(_siw, _sih, snap_avail_w, 3.5)
                    _sp = doc.add_paragraph()
                    _sp.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    _sp.paragraph_format.space_before = Pt(4)
                    _sp.paragraph_format.space_after  = Pt(0)
                    _sp.add_run().add_picture(_spath, width=Inches(_sdw))
                    _cap = doc.add_paragraph()
                    _cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    _cap.paragraph_format.space_before = Pt(0)
                    _cap.paragraph_format.space_after  = Pt(4)
                    _cap_r = _cap.add_run(
                        f"Attachment {_si} of {_total_snaps} — Sheet ref. {sheets_str}")
                    _cap_r.font.size = Pt(8); _cap_r.font.color.rgb = C_GRAY
                    logs.append(
                        f"    Snap {_si}: {os.path.basename(_spath)}  ({_siw}x{_sih}px)")
                spacer(doc, 4)
            else:
                _no_snap_p = doc.add_paragraph()
                _no_snap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                _no_snap_p.paragraph_format.space_before = Pt(4)
                _no_snap_p.paragraph_format.space_after  = Pt(4)
                _no_snap_r = _no_snap_p.add_run("[ No drawing snapshots attached ]")
                _no_snap_r.italic = True
                _no_snap_r.font.size = Pt(9)
                _no_snap_r.font.color.rgb = C_GRAY
                logs.append(f"    WARNING: No snapshots found for {rfi_ref}")

            # ── PAGE BREAK ────────────────────────────────────────────────
            _pb = doc.add_paragraph()
            _pb.paragraph_format.space_before = Pt(0)
            _pb.paragraph_format.space_after  = Pt(0)
            _pbr = OxmlElement('w:br')
            _pbr.set(qn('w:type'), 'page')
            _pb.runs[0]._r.append(_pbr) if _pb.runs else _pb.add_run()._r.append(_pbr)

            # ── Section setup — Page 2 (always portrait) ──────────────────
            cw_p2 = 7.07
            section_p2 = doc.add_section()
            section_p2.orientation   = WD_ORIENT.PORTRAIT
            section_p2.page_width    = Inches(8.27)
            section_p2.page_height   = Inches(11.69)
            section_p2.left_margin   = MARGIN_L
            section_p2.right_margin  = MARGIN_R
            section_p2.top_margin    = MARGIN_T
            section_p2.bottom_margin = MARGIN_B

            # ── PAGE 2: Mini header table ─────────────────────────────────
            _mh_lw = round(cw_p2 * 0.55, 3)
            _mh_rw = round(cw_p2 - _mh_lw, 3)
            t_mh = _borderless_table(doc, 2, cw_p2)
            _mh_lc = t_mh.cell(0, 0); _mh_rc = t_mh.cell(0, 1)
            set_cell_width(_mh_lc, _mh_lw); set_cell_width(_mh_rc, _mh_rw)
            set_cell_margins(_mh_lc, 40, 40, 60, 60)
            set_cell_margins(_mh_rc, 40, 40, 60, 60)
            _mh_lp = _mh_lc.paragraphs[0]
            _mh_lp.paragraph_format.space_before = Pt(0)
            _mh_lp.paragraph_format.space_after  = Pt(0)
            _mh_lr = _mh_lp.add_run(COMPANY_NAME)
            _mh_lr.bold = True; _mh_lr.font.size = Pt(10); _mh_lr.font.color.rgb = C_BLUE
            _mh_rp = _mh_rc.paragraphs[0]
            _mh_rp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            _mh_rp.paragraph_format.space_before = Pt(0)
            _mh_rp.paragraph_format.space_after  = Pt(0)
            _mh_rr = _mh_rp.add_run(f"{rfi_ref}  ·  {PROJECT_NAME}  ·  Response Page")
            _mh_rr.font.size = Pt(9); _mh_rr.font.color.rgb = C_GRAY

            # Navy divider line (Page 2)
            _div2 = doc.add_paragraph()
            _div2.paragraph_format.space_before = Pt(0)
            _div2.paragraph_format.space_after  = Pt(4)
            _div2_pPr = _div2._p.get_or_add_pPr()
            _div2_pBdr = OxmlElement('w:pBdr')
            _div2_bot = OxmlElement('w:bottom')
            _div2_bot.set(qn('w:val'), 'single')
            _div2_bot.set(qn('w:sz'), '12')
            _div2_bot.set(qn('w:space'), '1')
            _div2_bot.set(qn('w:color'), '1A3A6B')
            _div2_pBdr.append(_div2_bot)
            _div2_pPr.append(_div2_pBdr)

            spacer(doc, 4)

            # ── TABLE D: REV 0R Response (3 rows, 3 cols) ────────────────
            _td_cw = [round(cw_p2*0.38, 3), round(cw_p2*0.31, 3),
                      round(cw_p2 - cw_p2*0.38 - cw_p2*0.31, 3)]
            t_d = doc.add_table(rows=3, cols=3)
            t_d.style = 'Table Grid'
            set_table_width(t_d, cw_p2)

            # Row 0: header
            for ci, _td_hc in enumerate([t_d.cell(0, ci) for ci in range(3)]):
                set_cell_width(_td_hc, _td_cw[ci])
                set_cell_margins(_td_hc, 60, 60, 100, 100)
                _td_hc.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            set_cell_bg(t_d.cell(0, 0), C_ACCENT)
            _td_h0_p = t_d.cell(0, 0).paragraphs[0]
            _td_h0_p.paragraph_format.space_before = Pt(0)
            _td_h0_p.paragraph_format.space_after  = Pt(0)
            _td_h0_r = _td_h0_p.add_run("RFI Rev 0R — Response")
            _td_h0_r.bold = True; _td_h0_r.font.size = Pt(10)
            _td_h0_r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            para(t_d.cell(0, 1), "Date:  ", size=9)
            _td_h2_p = t_d.cell(0, 2).paragraphs[0]
            _td_h2_p.paragraph_format.space_before = Pt(0)
            _td_h2_p.paragraph_format.space_after  = Pt(0)
            _td_h2_r = _td_h2_p.add_run(f"Response Due Date:  {response_by}")
            _td_h2_r.font.size = Pt(9)

            # Row 1: Response (merged, blank, min height 1.8)
            _td_r = t_d.cell(1, 0).merge(t_d.cell(1, 2))
            for _p in _td_r.paragraphs[1:]: _p._element.getparent().remove(_p._element)
            set_cell_margins(_td_r, 80, 80, 100, 100)
            set_cell_bg(_td_r, "FFFEF5")
            _td_r.vertical_alignment = WD_ALIGN_VERTICAL.TOP
            _td_rp = _td_r.paragraphs[0]
            _td_rp.paragraph_format.space_before = Pt(0)
            _td_rp.paragraph_format.space_after  = Pt(0)
            _td_rl = _td_rp.add_run("Response")
            _td_rl.bold = True; _td_rl.font.size = Pt(10); _td_rl.font.color.rgb = C_BLUE
            _set_row_min_height(t_d.rows[1], 1.8)

            # Row 2: Reference (col 0+1 merged, blank)
            _td_r2_left  = t_d.cell(2, 0).merge(t_d.cell(2, 1))
            _td_r2_right = t_d.cell(2, 2)
            for _p in _td_r2_left.paragraphs[1:]: _p._element.getparent().remove(_p._element)
            set_cell_bg(_td_r2_left, C_INFOBG); set_cell_bg(_td_r2_right, C_INFOBG)
            set_cell_margins(_td_r2_left, 60, 60, 100, 100)
            set_cell_margins(_td_r2_right, 60, 60, 100, 100)
            _td_r2l_p = _td_r2_left.paragraphs[0]
            _td_r2l_p.paragraph_format.space_before = Pt(0)
            _td_r2l_p.paragraph_format.space_after  = Pt(0)
            _td_r2l_lbl = _td_r2l_p.add_run("Reference document")
            _td_r2l_lbl.bold = True; _td_r2l_lbl.font.size = Pt(8); _td_r2l_lbl.font.color.rgb = C_BLUE

            spacer(doc, 4)

            # ── TABLE E: Impact (2 rows, 5 cols) ─────────────────────────
            _te_col0_w = 1.2
            _te_rest_w = round((cw_p2 - _te_col0_w) / 4, 3)
            t_e = doc.add_table(rows=2, cols=5)
            t_e.style = 'Table Grid'
            set_table_width(t_e, cw_p2)

            # Row 0: Impact checkboxes
            _te_r0 = [t_e.cell(0, ci) for ci in range(5)]
            set_cell_width(_te_r0[0], _te_col0_w)
            for ci in range(1, 5):
                set_cell_width(_te_r0[ci], _te_rest_w)
            for ci in range(5):
                set_cell_margins(_te_r0[ci], 60, 60, 100, 100)
            set_cell_bg(_te_r0[0], C_ACCENT)
            _te_r0[0].vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            _te_r0_p = _te_r0[0].paragraphs[0]
            _te_r0_p.paragraph_format.space_before = Pt(0)
            _te_r0_p.paragraph_format.space_after  = Pt(0)
            _te_r0_r = _te_r0_p.add_run("Impact to:")
            _te_r0_r.bold = True; _te_r0_r.font.size = Pt(9)
            _te_r0_r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            _impact_cell(_te_r0[1], "Cost",                       issue.get('cost_impact',          'TBD'))
            _impact_cell(_te_r0[2], "Schedule",                    issue.get('schedule_impact',      'TBD'))
            _impact_cell(_te_r0[3], "Environmental /\nRegulatory", issue.get('environmental_impact', 'TBD'))
            _impact_cell(_te_r0[4], "Public Affairs",              issue.get('public_affairs_impact','TBD'))
            _set_row_min_height(t_e.rows[0], 0.9)

            # Row 1: Employer's Instruction (merged, blank)
            _te_r1 = t_e.cell(1, 0).merge(t_e.cell(1, 4))
            for _p in _te_r1.paragraphs[1:]: _p._element.getparent().remove(_p._element)
            set_cell_margins(_te_r1, 80, 80, 100, 100)
            set_cell_bg(_te_r1, "FFFEF5")
            _te_r1.vertical_alignment = WD_ALIGN_VERTICAL.TOP
            _te_r1_p = _te_r1.paragraphs[0]
            _te_r1_p.paragraph_format.space_before = Pt(0)
            _te_r1_p.paragraph_format.space_after  = Pt(0)
            _te_r1_l = _te_r1_p.add_run("Employer's instruction")
            _te_r1_l.bold = True; _te_r1_l.font.size = Pt(9); _te_r1_l.font.color.rgb = C_BLUE
            _set_row_min_height(t_e.rows[1], 0.9)

            spacer(doc, 4)

            # ── TABLE F: Approval (2 rows, 3 cols) ────────────────────────
            _tf_cw = [round(cw_p2*0.35, 3), round(cw_p2*0.35, 3),
                      round(cw_p2 - cw_p2*0.35 - cw_p2*0.35, 3)]
            t_f = doc.add_table(rows=2, cols=3)
            t_f.style = 'Table Grid'
            set_table_width(t_f, cw_p2)

            # Row 0: header (merged, navy)
            _tf_r0 = t_f.cell(0, 0).merge(t_f.cell(0, 2))
            for _p in _tf_r0.paragraphs[1:]: _p._element.getparent().remove(_p._element)
            set_cell_bg(_tf_r0, C_ACCENT)
            set_cell_margins(_tf_r0, 60, 60, 100, 100)
            _tf_r0_p = _tf_r0.paragraphs[0]
            _tf_r0_p.paragraph_format.space_before = Pt(0)
            _tf_r0_p.paragraph_format.space_after  = Pt(0)
            _tf_r0_r = _tf_r0_p.add_run("Approval & signature")
            _tf_r0_r.bold = True; _tf_r0_r.font.size = Pt(10)
            _tf_r0_r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

            # Row 1: Name | Signature | Date
            _tf_r1 = [t_f.cell(1, ci) for ci in range(3)]
            for ci, _c in enumerate(_tf_r1):
                set_cell_width(_c, _tf_cw[ci])
                set_cell_margins(_c, 80, 80, 100, 100)
                _c.vertical_alignment = WD_ALIGN_VERTICAL.TOP

            # Col 0: Name
            _tf_n_p = _tf_r1[0].paragraphs[0]
            _tf_n_p.paragraph_format.space_before = Pt(0)
            _tf_n_p.paragraph_format.space_after  = Pt(2)
            _tf_n_lbl = _tf_n_p.add_run("Name")
            _tf_n_lbl.bold = True; _tf_n_lbl.font.size = Pt(8); _tf_n_lbl.font.color.rgb = C_BLUE
            _tf_n_vp = _tf_r1[0].add_paragraph()
            _tf_n_vp.paragraph_format.space_before = Pt(0)
            _tf_n_vp.paragraph_format.space_after  = Pt(0)
            _tf_n_vr = _tf_n_vp.add_run(ORIGINATOR_NAME)
            _tf_n_vr.bold = True; _tf_n_vr.font.size = Pt(10)
            _tf_n_cp = _tf_r1[0].add_paragraph()
            _tf_n_cp.paragraph_format.space_before = Pt(0)
            _tf_n_cp.paragraph_format.space_after  = Pt(0)
            _tf_n_cr = _tf_n_cp.add_run(
                f"{ORIGINATOR_TITLE} — {COMPANY_NAME}" if ORIGINATOR_TITLE else COMPANY_NAME)
            _tf_n_cr.font.size = Pt(8); _tf_n_cr.font.color.rgb = C_GRAY

            # Col 1: Signature
            _tf_s_p = _tf_r1[1].paragraphs[0]
            _tf_s_p.paragraph_format.space_before = Pt(0)
            _tf_s_p.paragraph_format.space_after  = Pt(2)
            _tf_s_lbl = _tf_s_p.add_run("Signature")
            _tf_s_lbl.bold = True; _tf_s_lbl.font.size = Pt(8); _tf_s_lbl.font.color.rgb = C_BLUE
            _tf_s_vp = _tf_r1[1].add_paragraph()
            _tf_s_vp.paragraph_format.space_before = Pt(0)
            _tf_s_vp.paragraph_format.space_after  = Pt(0)
            if SIGNATURE_IMG and os.path.exists(SIGNATURE_IMG):
                try:
                    _tf_s_vp.add_run().add_picture(SIGNATURE_IMG, height=Inches(0.35))
                    logs.append("    Signature embedded")
                except Exception as _sig_e:
                    logs.append(f"    Signature warning: {_sig_e}")
                    _tf_s_vp.add_run("________________________").font.size = Pt(9)
            else:
                _tf_s_vp.add_run("________________________").font.size = Pt(9)

            # Col 2: Date
            _tf_d_p = _tf_r1[2].paragraphs[0]
            _tf_d_p.paragraph_format.space_before = Pt(0)
            _tf_d_p.paragraph_format.space_after  = Pt(2)
            _tf_d_lbl = _tf_d_p.add_run("Date")
            _tf_d_lbl.bold = True; _tf_d_lbl.font.size = Pt(8); _tf_d_lbl.font.color.rgb = C_BLUE
            _tf_d_vp = _tf_r1[2].add_paragraph()
            _tf_d_vp.paragraph_format.space_before = Pt(0)
            _tf_d_vp.paragraph_format.space_after  = Pt(0)
            _tf_d_vp.add_run(today_str).font.size = Pt(9)

            spacer(doc, 6)

            # ── Footer paragraph (navy bg, white text) ────────────────────
            _ft = f"{COMPANY_NAME}  ·  {rfi_ref}  ·  {PROJECT_NAME}  ·  {today_str}  ·  CONFIDENTIAL"
            footer_para = doc.add_paragraph()
            footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            footer_para.paragraph_format.space_before = Pt(0)
            footer_para.paragraph_format.space_after  = Pt(0)
            _ft_r = footer_para.add_run(_ft)
            _ft_r.font.size = Pt(9)
            _ft_r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            _fp_pPr = footer_para._p.get_or_add_pPr()
            _fp_shd = OxmlElement('w:shd')
            _fp_shd.set(qn('w:val'), 'clear')
            _fp_shd.set(qn('w:color'), 'auto')
            _fp_shd.set(qn('w:fill'), '1A3A6B')
            _fp_pPr.append(_fp_shd)

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
