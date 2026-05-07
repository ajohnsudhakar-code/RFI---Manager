"""
ui_analyse.py — Tab 3: Analyse Drawings
"""
import os, re, json, io, datetime
import streamlit as st

try:
    from streamlit_pdf_viewer import pdf_viewer as _pdf_viewer
    _pdf_viewer_ok = True
except ImportError:
    _pdf_viewer_ok = False

from data_layer import (
    load_cfg, _secret, track_usage, pdf_page_to_pil,
    load_project_cfg, save_project_approved, load_project_approved,
    load_project_sheet_map, save_project_sheet_map,
    get_rfi_num, resolve_pdf_path,
    load_project_scan_results, save_project_scan_results,
)

_PRIORITY_OPTS = ["Critical", "High", "Normal", "Low"]

_SYSTEM_PROMPT = (
    "You are an expert construction documents reviewer with deep knowledge across all "
    "disciplines — structural, architectural, civil, mechanical, electrical, and specifications.\n\n"
    "Review the provided drawing sheets and flag:\n"
    "- Conflicts between sheets (dimensions, details, or specifications that disagree)\n"
    "- Missing information (details, dimensions, notes, or references that are absent but required)\n"
    "- Ambiguous details (unclear or incomplete information that could be misinterpreted)\n"
    "- Coordination problems (items inconsistent across disciplines or between drawings)\n\n"
    "Do NOT flag:\n"
    "- Formatting, title block style, or presentation issues\n"
    "- Trivial notes, standard boilerplate, or general annotations\n"
    "- Items that are clearly intentional design choices with no coordination impact\n\n"
    "Output rule: Return ONLY a valid JSON array. No markdown fences, no preamble, no explanation.\n\n"
    'JSON format: [{"issue_number": 1, "sheets": "S101", "category": "Missing Information", '
    '"description": "...", "reason": "..."}]\n\n'
    "Valid categories: \"Missing Information\", \"Conflict Between Sheets\", "
    "\"Coordination Issue\", \"Ambiguous Detail\", \"Specification Conflict\", "
    "\"Structural Concern\", \"Architectural Concern\", \"Services Conflict\""
)

_USER_TEMPLATE = (
    "Use SHEET NUMBERS (not page numbers) when referencing locations.\n"
    "{focus_block}\n"
    "SHEETS TO REVIEW:\n"
    "{batch_txt}"
)


def _build_user_prompt(batch_txt: str, focus: str = "") -> str:
    if focus:
        focus_block = f"\nFOCUS AREA — pay particular attention to:\n{focus}\n"
    else:
        focus_block = ""
    return _USER_TEMPLATE.format(focus_block=focus_block, batch_txt=batch_txt)


def _next_rfi_number(pid: str, email: str = "") -> int:
    """Return the next RFI number for this project (max existing + 1, or 1)."""
    existing = load_project_approved(pid, email)
    if not existing:
        return 1
    nums = [get_rfi_num(r) for r in existing]
    return max(nums) + 1 if nums else 1


def render_tab_analyse(email: str):
    pid = st.session_state.get("current_project_id", "")
    if not pid:
        st.info("No project selected. Create or select a project from the sidebar first.")
        return

    cfg      = load_cfg(email)
    pcfg     = load_project_cfg(pid, email)
    if "analysis_results" not in st.session_state or \
       st.session_state.get("t3_loaded_pid") != pid:
        _saved = load_project_scan_results(pid, email)
        if _saved:
            st.session_state.analysis_results = _saved
        st.session_state["t3_loaded_pid"] = pid
    api_key  = _secret("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY", "") or cfg.get("api_key", "")

    st.markdown("## Analyse Drawings")

    pdf_path = resolve_pdf_path(pid, email)

    left_col, right_col = st.columns([3, 2])

    # ── RIGHT: PDF viewer ─────────────────────────────────────────────────────
    with right_col:
        if pdf_path:
            if _pdf_viewer_ok:
                _pdf_viewer(str(pdf_path), height=700, key="pdf_viewer_t3")
            else:
                try:
                    _prev_img = pdf_page_to_pil(pdf_path, 1, zoom=1.2)
                    st.image(_prev_img, caption="Page 1 preview", use_container_width=True)
                    st.caption("Install `streamlit-pdf-viewer` for full scrollable PDF viewing.")
                except Exception as _pe:
                    st.caption(f"PDF preview unavailable: {_pe}")
        else:
            st.markdown(
                '<div class="info-box">No drawing PDF uploaded — '
                'go to Project Setup to upload one.</div>',
                unsafe_allow_html=True)

    # ── LEFT: controls + results ──────────────────────────────────────────────
    with left_col:
        if not pdf_path:
            st.markdown(
                '<div class="info-box">No drawing PDF uploaded. '
                'You can still add issues manually below.</div>',
                unsafe_allow_html=True)

        if not api_key:
            st.markdown(
                '<div class="info-box warn">Please contact support to activate AI features.</div>',
                unsafe_allow_html=True)

        tab_ai, tab_manual = st.tabs(["🔍  AI-Assisted Scan",
                                       "✏️  Add Your Own Issue"])
        with tab_ai:
            if pdf_path:
                st.text_area(
                    "What issues should we look for?",
                    placeholder='Leave blank to scan everything, or be specific — e.g. "reinforcement bar conflicts", '
                                '"missing structural details on foundation sheets", '
                                '"inconsistencies between architectural and structural drawings"',
                    height=80,
                    key="t3_focus_prompt",
                    label_visibility="visible",
                )
                run_ai = st.button("🔍  Scan All Drawing Sheets",
                                   use_container_width=True, disabled=(not api_key), key="t3_ai_scan")
            else:
                run_ai = False


        # ── AI SCAN ───────────────────────────────────────────────────────────
        if run_ai:
            try:
                import fitz
            except ImportError:
                st.error("PyMuPDF not installed. Run: `pip install pymupdf`")
                st.stop()
            try:
                import anthropic as _ant
            except ImportError:
                st.error("anthropic not installed. Run: `pip install anthropic`")
                st.stop()

            track_usage("ai_scan", {"email": email, "pdf": os.path.basename(pdf_path)})

            sheet_map = load_project_sheet_map(pid, email)

            if not sheet_map:
                with st.spinner("Reading sheet numbers from title blocks…"):
                    doc      = fitz.open(pdf_path)
                    sm_build = {}
                    patterns = [
                        r"\b([A-Z]{1,3}[-–]\s*\d{3,5})\b",
                        r"\b([A-Z]{1,3}\s*\d{3,5})\b",
                        r"\b([A-Z]\s\d{3})\b",
                    ]
                    for i, page in enumerate(doc):
                        text = page.get_text()
                        sn   = None
                        for patt in patterns:
                            for m in re.findall(patt, text, re.IGNORECASE):
                                mc = m.strip().replace(" ", "")
                                if len(mc) <= 10 and not re.match(r"\d{8}", mc):
                                    sn = re.sub(r"^[A-Za-z](\d{3,5})$", r"\1", mc)
                                    break
                            if sn:
                                break
                        sm_build[i + 1] = sn or f"PG-{i+1:02d}"
                    doc.close()
                    sheet_map = sm_build
                    save_project_sheet_map(pid, sheet_map, email)

            with st.spinner("Reading drawing text…"):
                doc           = fitz.open(pdf_path)
                pages_content = []
                for i, page in enumerate(doc):
                    text = page.get_text().strip()
                    sn   = sheet_map.get(i + 1, f"PG-{i+1:02d}")
                    if text:
                        pages_content.append(f"SHEET {sn} (Page {i+1}):\n{text[:2000]}")
                doc.close()

            if not pages_content:
                st.warning("No text found in PDF — this may be a scanned drawing. Use Manual Entry.")
            else:
                all_issues    = []
                batch_size    = 5
                total_batches = (len(pages_content) + batch_size - 1) // batch_size
                prog          = st.progress(0, text="Analyzing with AI…")
                client        = _ant.Anthropic(api_key=api_key)
                _focus        = st.session_state.get("t3_focus_prompt", "").strip()

                for bi in range(0, len(pages_content), batch_size):
                    batch_txt = "\n\n---\n\n".join(pages_content[bi : bi + batch_size])
                    bn        = bi // batch_size + 1
                    prog.progress(bn / total_batches, text=f"Analysing batch {bn} of {total_batches}…")
                    try:
                        msg = client.messages.create(
                            model="claude-opus-4-6",
                            max_tokens=4096,
                            system=_SYSTEM_PROMPT,
                            messages=[{"role": "user", "content": _build_user_prompt(batch_txt, _focus)}],
                        )
                        resp         = re.sub(r"```(?:json)?|```", "", msg.content[0].text).strip()
                        batch_issues = json.loads(resp)
                        if isinstance(batch_issues, list):
                            for iss in batch_issues:
                                iss["issue_number"] = len(all_issues) + 1
                                all_issues.append(iss)
                    except json.JSONDecodeError:
                        pass
                    except Exception as e:
                        st.warning(f"Batch {bn} error: {e}")

                prog.empty()
                _existing = st.session_state.get("analysis_results", [])
                _new = [{"issue": iss, "status": "pending"} for iss in all_issues]
                _offset = len(_existing)
                for _item in _new:
                    _item["issue"]["issue_number"] += _offset
                st.session_state.analysis_results = _existing + _new
                save_project_scan_results(pid,
                    st.session_state.analysis_results, email)
                if all_issues:
                    st.success(f"✓ AI found **{len(all_issues)} issues**. Review and approve below.")
                else:
                    st.info("No issues detected — use Manual Entry if needed.")

        with tab_manual:
            sheet_map = load_project_sheet_map(pid, email)
            with st.form("manual_form"):
                desc      = st.text_area("", height=120, label_visibility="collapsed",
                                         placeholder="e.g. Sheet S101 shows SE62 mesh but Sheet S105 detail shows SE72.")
                manual_pri = st.selectbox("Priority", _PRIORITY_OPTS, index=3,
                                          key="manual_pri")
                manual_rbd = st.date_input("Response Required By", key="manual_rbd")
                submitted = st.form_submit_button("Format with AI →", type="primary")
            if submitted and desc.strip():
                try:
                    import anthropic as _ant
                    sheet_list = ", ".join(f"Page {p}={s}" for p, s in sheet_map.items())
                    with st.spinner("AI is formatting your RFI…"):
                        client = _ant.Anthropic(api_key=api_key)
                        msg    = client.messages.create(
                            model="claude-opus-4-6",
                            max_tokens=1024,
                            system=_SYSTEM_PROMPT,
                            messages=[{"role": "user", "content":
                                f"Sheet map: {sheet_list or 'unknown'}\n\n"
                                f"Format this engineer's description as a single RFI issue:\n{desc}"}],
                        )
                    resp       = re.sub(r"```(?:json)?|```", "", msg.content[0].text).strip()
                    new_issues = json.loads(resp)
                    if isinstance(new_issues, list):
                        existing = st.session_state.get("analysis_results", [])
                        for iss in new_issues:
                            iss["issue_number"]             = len(existing) + 1
                            iss["priority"]                 = manual_pri
                            iss["response_required_by"]     = str(manual_rbd)
                            existing.append({"issue": iss, "status": "pending"})
                        st.session_state.analysis_results = existing
                        save_project_scan_results(pid,
                            st.session_state.analysis_results, email)
                    st.rerun()
                except json.JSONDecodeError:
                    st.error("Could not parse the AI response — please try again.")
                except Exception as e:
                    st.error(f"Error: {e}")

        # ── REVIEW RESULTS ────────────────────────────────────────────────────
        results = st.session_state.get("analysis_results", [])
        if results:
            st.markdown("---")
            n_app = sum(1 for r in results if r["status"] == "approved")
            n_rej = sum(1 for r in results if r["status"] == "rejected")
            n_pen = sum(1 for r in results if r["status"] == "pending")

            rm1, rm2, rm3, rm4 = st.columns(4)
            rm1.metric("Total",    len(results))
            rm2.metric("Approved", n_app)
            rm3.metric("Rejected", n_rej)
            rm4.metric("Pending",  n_pen)

            if n_pen > 0:
                bulk1, bulk2, _ = st.columns([2, 2, 4])
                with bulk1:
                    if st.button("✅ Approve All Pending",
                                 use_container_width=True,
                                 key="t3_bulk_approve"):
                        for _r in st.session_state.analysis_results:
                            if _r["status"] == "pending":
                                _r["status"] = "approved"
                        save_project_scan_results(pid,
                            st.session_state.analysis_results, email)
                        st.rerun()
                with bulk2:
                    if st.button("❌ Reject All Pending",
                                 use_container_width=True,
                                 key="t3_bulk_reject"):
                        for _r in st.session_state.analysis_results:
                            if _r["status"] == "pending":
                                _r["status"] = "rejected"
                        save_project_scan_results(pid,
                            st.session_state.analysis_results, email)
                        st.rerun()

            st.markdown('<div class="sec-lbl" style="margin-top:24px;">Review Each Issue</div>',
                        unsafe_allow_html=True)
            _EDIT_CATS = [
                "Missing Information", "Conflict Between Sheets",
                "Coordination Issue", "Ambiguous Detail",
                "Specification Conflict", "Structural Concern",
                "Architectural Concern", "Services Conflict",
            ]
            for i, r in enumerate(results):
                iss    = r["issue"]
                status = r["status"]
                color  = {"approved": "#059669", "rejected": "#dc2626", "pending": "#d97706"}[status]

                if status == "approved" and st.session_state.get("t3_edit_idx") == i:
                    with st.form(key=f"edit_form_{i}"):
                        st.markdown(
                            f'<div style="color:#e8edf5;font-size:13px;font-weight:600;'
                            f'margin-bottom:8px;">Editing Issue {iss.get("issue_number", i+1)}</div>',
                            unsafe_allow_html=True)
                        new_desc = st.text_area("Description",
                                                value=iss.get("description", ""),
                                                height=100,
                                                key=f"edit_desc_{i}")
                        new_reason = st.text_area("Reason",
                                                  value=iss.get("reason", ""),
                                                  height=80,
                                                  key=f"edit_reason_{i}")
                        cur_cat = iss.get("category", _EDIT_CATS[0])
                        cat_idx = _EDIT_CATS.index(cur_cat) if cur_cat in _EDIT_CATS else 0
                        new_cat = st.selectbox("Category", _EDIT_CATS,
                                               index=cat_idx,
                                               key=f"edit_cat_{i}")
                        new_sheets = st.text_input("Sheets",
                                                   value=iss.get("sheets", ""),
                                                   key=f"edit_sheets_{i}")
                        cur_pri = iss.get("priority", _PRIORITY_OPTS[-1])
                        pri_idx = _PRIORITY_OPTS.index(cur_pri) if cur_pri in _PRIORITY_OPTS else 3
                        new_pri = st.selectbox("Priority", _PRIORITY_OPTS,
                                               index=pri_idx,
                                               key=f"edit_pri_{i}")
                        _rbd_str = iss.get("response_required_by", "")
                        _rbd_val = datetime.date.fromisoformat(_rbd_str) if _rbd_str else datetime.date.today()
                        new_rbd  = st.date_input("Response Required By",
                                                 value=_rbd_val,
                                                 key=f"edit_rbd_{i}")
                        fs1, fs2 = st.columns([1, 1])
                        with fs1:
                            save_clicked = st.form_submit_button("💾  Save Changes",
                                                                 type="primary",
                                                                 use_container_width=True)
                        with fs2:
                            cancel_clicked = st.form_submit_button("✕  Cancel",
                                                                   use_container_width=True)
                        if save_clicked:
                            st.session_state.analysis_results[i]["issue"]["description"] = new_desc
                            st.session_state.analysis_results[i]["issue"]["reason"]      = new_reason
                            st.session_state.analysis_results[i]["issue"]["category"]             = new_cat
                            st.session_state.analysis_results[i]["issue"]["sheets"]               = new_sheets
                            st.session_state.analysis_results[i]["issue"]["priority"]             = new_pri
                            st.session_state.analysis_results[i]["issue"]["response_required_by"] = str(new_rbd)
                            save_project_scan_results(pid,
                                st.session_state.analysis_results, email)
                            _approved_sync = [r["issue"] for r in st.session_state.analysis_results
                                              if r["status"] == "approved"]
                            save_project_approved(pid, _approved_sync, email)
                            st.session_state["t3_edit_idx"] = None
                            st.rerun()
                        if cancel_clicked:
                            st.session_state["t3_edit_idx"] = None
                            st.rerun()
                else:
                    st.markdown(f"""
<div class="rfi-card" style="border-left:3px solid {color};">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:6px;">
    <div>
      <strong style="color:#e8edf5;font-size:14px;">
        Issue {iss.get('issue_number',i+1)} &mdash; {iss.get('category','')}
      </strong>
      <span style="color:#374151;font-size:12px;margin-left:12px;">Sheets: {iss.get('sheets','')}</span>
      <span style="color:#374151;font-size:12px;margin-left:12px;">Priority: {iss.get('priority','—')}</span>
      <span style="color:#374151;font-size:12px;margin-left:12px;">Due: {iss.get('response_required_by','—')}</span>
    </div>
    <span style="color:{color};font-size:11px;font-weight:700;text-transform:uppercase;
                 letter-spacing:0.08em;padding:2px 8px;border:1px solid {color};
                 border-radius:4px;">{status}</span>
  </div>
  <p style="color:#8892a4;font-size:13px;margin:8px 0 4px;">{iss.get('description','')}</p>
  <p style="color:#374151;font-size:12px;font-style:italic;margin:0;">Reason: {iss.get('reason','')}</p>
</div>""", unsafe_allow_html=True)
                    bc1, bc2, bc3, _ = st.columns([1, 1, 1, 5])
                    with bc1:
                        if st.button("✓  Approve", key=f"app_{i}",
                                     type=("primary" if status == "approved" else "secondary")):
                            st.session_state.analysis_results[i]["status"] = "approved"
                            save_project_scan_results(pid,
                                st.session_state.analysis_results, email)
                            st.rerun()
                    with bc2:
                        if st.button("✗  Reject", key=f"rej_{i}"):
                            st.session_state.analysis_results[i]["status"] = "rejected"
                            save_project_scan_results(pid,
                                st.session_state.analysis_results, email)
                            st.rerun()
                    with bc3:
                        if status == "approved":
                            if st.button("✏️  Edit", key=f"edit_{i}"):
                                st.session_state["t3_edit_idx"] = i
                                st.rerun()

            st.markdown("---")
            if st.button("💾  Save Approved RFIs", type="primary", use_container_width=True, key="t3_save_rfis"):
                next_rfi      = _next_rfi_number(pid, email)
                approved_list = [r["issue"] for r in results if r["status"] == "approved"]
                for i, iss in enumerate(approved_list):
                    iss["rfi_number"] = next_rfi + i
                save_project_approved(pid, approved_list, email)
                last = next_rfi + len(approved_list) - 1
                st.success(
                    f"✓ {len(approved_list)} RFI(s) saved — "
                    f"RFI-{next_rfi:03d} through RFI-{last:03d}"
                )
                st.rerun()
        elif not run_ai:
            st.markdown(
                '<div class="info-box" style="margin-top:20px;">'
                'Use <strong style="color:#e8edf5;">AI-Assisted Scan</strong> to automatically '
                'detect engineering issues, or describe one in the '
                '<strong style="color:#e8edf5;">Add Your Own Issue</strong> card above.'
                '</div>',
                unsafe_allow_html=True)
