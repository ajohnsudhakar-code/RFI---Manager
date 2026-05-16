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
    load_usage, load_scan_usage, increment_scan_usage,
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
    _PRIORITY_OPTS = ["Critical", "High", "Normal", "Low"]
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


        # ── Scan initiation ───────────────────────────────────────────────────
        if run_ai:
            _existing = st.session_state.get("analysis_results", [])
            if _existing:
                st.session_state["t3_show_rescan_confirm"] = True
            else:
                _today  = datetime.date.today().isoformat()
                _su     = load_scan_usage(email)
                _count  = 0 if _su["ai_scans_date"] != _today else _su["ai_scans_today"]
                _usage  = load_usage(email)
                _limit  = 20 if _usage.get("is_paid") else 3
                if _count >= _limit:
                    _tier = "paid" if _usage.get("is_paid") else "free"
                    st.error(
                        f"Daily scan limit reached ({_count}/{_limit} scans used today "
                        f"on your {_tier} plan). Limit resets tomorrow."
                    )
                else:
                    st.session_state["t3_do_scan"] = True

        # ── Protection 1: rescan confirmation ─────────────────────────────────
        if st.session_state.get("t3_rescan_limit_err"):
            st.error(st.session_state.pop("t3_rescan_limit_err"))
        if st.session_state.get("t3_show_rescan_confirm"):
            _n = len(st.session_state.get("analysis_results", []))
            st.warning(
                f"This project already has {_n} scan results from a previous scan. "
                f"Re-scanning will add to existing results and use AI credits."
            )
            _rc1, _rc2 = st.columns(2)
            with _rc1:
                if st.button("Use Existing Results", key="t3_use_existing",
                             use_container_width=True):
                    st.session_state.pop("t3_show_rescan_confirm", None)
                    st.rerun()
            with _rc2:
                if st.button("Re-scan Anyway", key="t3_rescan_anyway",
                             type="primary", use_container_width=True):
                    st.session_state.pop("t3_show_rescan_confirm", None)
                    _today  = datetime.date.today().isoformat()
                    _su     = load_scan_usage(email)
                    _count  = 0 if _su["ai_scans_date"] != _today else _su["ai_scans_today"]
                    _usage  = load_usage(email)
                    _limit  = 20 if _usage.get("is_paid") else 3
                    if _count >= _limit:
                        _tier = "paid" if _usage.get("is_paid") else "free"
                        st.session_state["t3_rescan_limit_err"] = (
                            f"Daily scan limit reached ({_count}/{_limit} scans used today "
                            f"on your {_tier} plan). Limit resets tomorrow."
                        )
                    else:
                        st.session_state["t3_do_scan"] = True
                    st.rerun()

        # ── AI SCAN ───────────────────────────────────────────────────────────
        if st.session_state.get("t3_do_scan"):
            st.session_state.pop("t3_do_scan", None)
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
                st.warning(
                    "This PDF appears to contain scanned images rather than digital text. "
                    "The AI cannot read image-based drawings directly.\n\n"
                    "**What to do:** Switch to the **Add Your Own Issue** tab above and describe "
                    "each issue you find manually. Your description will be formatted into a "
                    "proper RFI using AI."
                )
            else:
                # ── Protection 2: large PDF gate ──────────────────────────────
                _n_pages = len(pages_content)
                if _n_pages > 30 and not st.session_state.pop("t3_large_pdf_confirmed", False):
                    _n_batches = (_n_pages + 4) // 5
                    st.info(
                        f"This PDF has {_n_pages} pages ({_n_batches} batches). "
                        f"Large scans use more AI credits and take longer."
                    )
                    if st.button("Proceed with Full Scan", key="t3_large_pdf_go",
                                 type="primary", use_container_width=True):
                        st.session_state["t3_large_pdf_confirmed"] = True
                        st.session_state["t3_do_scan"] = True
                        st.rerun()
                else:
                    # ── Increment daily counter before first API call ─────────
                    increment_scan_usage(email)

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
                desc      = st.text_area("RFI Description", height=120, label_visibility="collapsed",
                                         placeholder="e.g. Sheet S101 shows SE62 mesh but Sheet S105 detail shows SE72.")
                manual_pri = st.selectbox("Priority", _PRIORITY_OPTS, index=2,
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
                        st.session_state["_analyse_do_rerun"] = True
                except json.JSONDecodeError:
                    st.error("Could not parse the AI response — please try again.")
                except Exception as e:
                    st.error(f"Error: {e}")
                if st.session_state.pop("_analyse_do_rerun", False):
                    st.rerun()

        # ── REVIEW RESULTS ────────────────────────────────────────────────────
        results = st.session_state.get("analysis_results", [])
        if results:
            if st.session_state.get("_t3_saved_ok"):
                st.success(st.session_state.pop("_t3_saved_ok"))
            st.markdown("---")
            n_app = sum(1 for r in results if r["status"] == "approved")
            n_rej = sum(1 for r in results if r["status"] == "rejected")
            n_pen = sum(1 for r in results if r["status"] == "pending")

            _pct = int((n_app / len(results)) * 100) if results else 0
            st.markdown(
                f'<div style="background:#ffffff;border:1px solid #e8eaed;border-radius:10px;'
                f'padding:14px 18px;margin-bottom:16px;">'
                f'<div style="display:flex;justify-content:space-between;margin-bottom:8px;">'
                f'<span style="font-size:12px;color:#374151;font-weight:500;">Review progress</span>'
                f'<span style="font-size:12px;color:#1d4ed8;font-weight:600;">'
                f'{n_app} of {len(results)} approved</span>'
                f'</div>'
                f'<div style="background:#f0f0f0;border-radius:20px;height:6px;margin-bottom:10px;">'
                f'<div style="background:linear-gradient(90deg,#1d4ed8,#3b82f6);'
                f'width:{_pct}%;height:6px;border-radius:20px;"></div>'
                f'</div>'
                f'<div style="display:flex;gap:16px;">'
                f'<span style="font-size:12px;color:#16a34a;">✓ {n_app} Approved</span>'
                f'<span style="font-size:12px;color:#dc2626;">✗ {n_rej} Rejected</span>'
                f'<span style="font-size:12px;color:#f59e0b;">● {n_pen} Pending</span>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True)

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

            if n_app > 0:
                st.markdown(
                    '<div class="info-box success" style="margin:8px 0 4px;">'
                    '✓ Issues marked as approved — click '
                    '<strong>💾 Save Approved RFIs</strong> below to confirm and proceed to '
                    'Crop &amp; Annotate.'
                    '</div>',
                    unsafe_allow_html=True)

            st.session_state.setdefault("t3_filter", "Pending")
            _filter = st.radio("Show:", ["All", "Approved", "Rejected", "Pending"],
                               horizontal=True, key="t3_filter",
                               label_visibility="collapsed")
            st.markdown('<div class="sec-lbl" style="margin-top:8px;">Review Each Issue</div>',
                        unsafe_allow_html=True)
            _EDIT_CATS = [
                "Missing Information", "Conflict Between Sheets",
                "Coordination Issue", "Ambiguous Detail",
                "Specification Conflict", "Structural Concern",
                "Architectural Concern", "Services Conflict",
            ]
            for _orig_idx, r in enumerate(results):
                if _filter != "All" and r["status"] != _filter.lower():
                    continue
                iss    = r["issue"]
                status = r["status"]
                color  = {"approved": "#059669", "rejected": "#dc2626", "pending": "#d97706"}[status]

                if status == "approved" and st.session_state.get("t3_edit_idx") == _orig_idx:
                    with st.form(key=f"edit_form_{pid}_{_orig_idx}"):
                        st.markdown(
                            f'<div style="color:#111111;font-size:13px;font-weight:600;'
                            f'margin-bottom:8px;">Editing Issue {iss.get("issue_number", _orig_idx+1)}</div>',
                            unsafe_allow_html=True)
                        new_desc = st.text_area("Description",
                                                value=iss.get("description", ""),
                                                height=100,
                                                key=f"edit_desc_{pid}_{_orig_idx}")
                        new_reason = st.text_area("Reason",
                                                  value=iss.get("reason", ""),
                                                  height=80,
                                                  key=f"edit_reason_{pid}_{_orig_idx}")
                        cur_cat = iss.get("category", _EDIT_CATS[0])
                        cat_idx = _EDIT_CATS.index(cur_cat) if cur_cat in _EDIT_CATS else 0
                        new_cat = st.selectbox("Category", _EDIT_CATS,
                                               index=cat_idx,
                                               key=f"edit_cat_{pid}_{_orig_idx}")
                        new_sheets = st.text_input("Sheets",
                                                   value=iss.get("sheets", ""),
                                                   key=f"edit_sheets_{pid}_{_orig_idx}")
                        cur_pri = iss.get("priority", _PRIORITY_OPTS[-1])
                        pri_idx = _PRIORITY_OPTS.index(cur_pri) if cur_pri in _PRIORITY_OPTS else 3
                        new_pri = st.selectbox("Priority", _PRIORITY_OPTS,
                                               index=pri_idx,
                                               key=f"edit_pri_{pid}_{_orig_idx}")
                        _rbd_str = iss.get("response_required_by", "")
                        _rbd_val = datetime.date.fromisoformat(_rbd_str) if _rbd_str else datetime.date.today()
                        new_rbd  = st.date_input("Response Required By",
                                                 value=_rbd_val,
                                                 key=f"edit_rbd_{pid}_{_orig_idx}")
                        fs1, fs2 = st.columns([1, 1])
                        with fs1:
                            save_clicked = st.form_submit_button("💾  Save Changes",
                                                                 type="primary",
                                                                 use_container_width=True)
                        with fs2:
                            cancel_clicked = st.form_submit_button("✕  Cancel",
                                                                   use_container_width=True)
                        if save_clicked:
                            st.session_state.analysis_results[_orig_idx]["issue"]["description"] = new_desc
                            st.session_state.analysis_results[_orig_idx]["issue"]["reason"]      = new_reason
                            st.session_state.analysis_results[_orig_idx]["issue"]["category"]             = new_cat
                            st.session_state.analysis_results[_orig_idx]["issue"]["sheets"]               = new_sheets
                            st.session_state.analysis_results[_orig_idx]["issue"]["priority"]             = new_pri
                            st.session_state.analysis_results[_orig_idx]["issue"]["response_required_by"] = str(new_rbd)
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
                    _pri = iss.get("priority", "")
                    _pri_color = {"Critical": "#dc2626", "High": "#d97706",
                                  "Normal": "#374151", "Low": "#6b7280"}.get(_pri, "#6b7280")
                    _badge_bg, _badge_fg, _badge_bd = {
                        "approved": ("#f0fdf4", "#15803d", "#bbf7d0"),
                        "rejected": ("#fff5f5", "#dc2626", "#fecaca"),
                        "pending":  ("#fffbeb", "#92400e", "#fde68a"),
                    }.get(status, ("#f8f9fa", "#374151", "#e8eaed"))
                    _due = iss.get("response_required_by", "") or "—"
                    st.markdown(
                        f'<div style="background:#ffffff;border:1px solid #e8eaed;'
                        f'border-left:3px solid {color};border-radius:10px;'
                        f'padding:14px 16px;margin-bottom:10px;">'
                        f'<div style="display:flex;justify-content:space-between;'
                        f'align-items:flex-start;gap:8px;">'
                        f'<div style="font-size:13px;color:#111111;font-weight:500;flex:1;'
                        f'display:-webkit-box;-webkit-line-clamp:2;'
                        f'-webkit-box-orient:vertical;overflow:hidden;">'
                        f'{iss.get("description","")}</div>'
                        f'<span style="background:{_badge_bg};color:{_badge_fg};'
                        f'border:1px solid {_badge_bd};font-size:10px;font-weight:700;'
                        f'text-transform:uppercase;letter-spacing:0.08em;'
                        f'padding:2px 8px;border-radius:4px;white-space:nowrap;">'
                        f'{status}</span>'
                        f'</div>'
                        f'<div style="font-size:11px;color:#6b7280;margin:8px 0 4px;'
                        f'display:flex;gap:12px;flex-wrap:wrap;">'
                        f'<span>#{iss.get("issue_number", _orig_idx+1)}</span>'
                        f'<span>{iss.get("sheets","—")}</span>'
                        f'<span>{iss.get("category","")}</span>'
                        f'<span style="color:{_pri_color};">{_pri or "—"}</span>'
                        f'<span>Due: {_due}</span>'
                        f'</div>'
                        f'<div style="font-size:11px;color:#9ca3af;font-style:italic;'
                        f'display:-webkit-box;-webkit-line-clamp:1;'
                        f'-webkit-box-orient:vertical;overflow:hidden;">'
                        f'{iss.get("reason","")}</div>'
                        f'</div>',
                        unsafe_allow_html=True)
                    bc1, bc2, bc3, _ = st.columns([1, 1, 1, 5])
                    with bc1:
                        if st.button("✓  Approve", key=f"app_{_orig_idx}",
                                     type=("primary" if status == "approved" else "secondary")):
                            st.session_state.analysis_results[_orig_idx]["status"] = "approved"
                            save_project_scan_results(pid,
                                st.session_state.analysis_results, email)
                            st.rerun()
                    with bc2:
                        if st.button("✗  Reject", key=f"rej_{_orig_idx}"):
                            st.session_state.analysis_results[_orig_idx]["status"] = "rejected"
                            save_project_scan_results(pid,
                                st.session_state.analysis_results, email)
                            st.rerun()
                    with bc3:
                        if status == "approved":
                            if st.button("✏️  Edit", key=f"edit_{_orig_idx}"):
                                st.session_state["t3_edit_idx"] = _orig_idx
                                st.rerun()

            if n_app > 0:
                st.markdown("---")
                _sv1, _sv2 = st.columns([3, 1])
                with _sv1:
                    st.markdown(
                        f'<div style="font-size:13px;color:#374151;padding-top:8px;">'
                        f'<strong style="color:#15803d;">{n_app} RFI(s) approved</strong>'
                        f' — ready to proceed to Crop &amp; Annotate</div>',
                        unsafe_allow_html=True)
                with _sv2:
                    if st.button("💾 Save Approved RFIs", type="primary",
                                 use_container_width=True, key="t3_save_rfis"):
                        next_rfi      = _next_rfi_number(pid, email)
                        approved_list = [r["issue"] for r in results if r["status"] == "approved"]
                        for i, iss in enumerate(approved_list):
                            if not iss.get("rfi_number"):
                                iss["rfi_number"] = next_rfi + i
                        save_project_approved(pid, approved_list, email)
                        save_project_scan_results(pid, st.session_state.analysis_results, email)
                        _nums = [get_rfi_num(iss) for iss in approved_list]
                        st.session_state["_t3_saved_ok"] = (
                            f"✓ {len(approved_list)} RFI(s) saved — "
                            f"RFI-{min(_nums):03d} through RFI-{max(_nums):03d}"
                        )
                        st.rerun()
        elif not run_ai:
            st.markdown(
                '<div class="info-box" style="margin-top:20px;">'
                'Use <strong style="color:#1d4ed8;">AI-Assisted Scan</strong> to automatically '
                'detect engineering issues, or describe one in the '
                '<strong style="color:#1d4ed8;">Add Your Own Issue</strong> card above.'
                '</div>',
                unsafe_allow_html=True)
