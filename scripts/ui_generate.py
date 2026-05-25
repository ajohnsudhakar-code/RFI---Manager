"""
ui_generate.py — Tab 5: Generate RFI Document
"""
import os
import streamlit as st
from datetime import date, timedelta
from pathlib import Path

from data_layer import (
    load_cfg, load_usage, get_asset_bytes,
    get_rfi_num, increment_usage,
    FREE_LIMIT, _secret,
    load_project_cfg, load_project_approved, load_project_clients,
    proj_snapshots_dir, proj_output_dir, proj_dir,
    upsert_project_register_rows, resolve_pdf_path,
    upload_project_document, sync_snapshots_from_supabase,
    upload_project_snapshot, load_project_register,
    load_rfi_templates, save_rfi_templates,
    list_project_documents, download_project_document,
    SCRIPTS_PY_DIR,
)
from generate_rfi import generate_rfi_document

# ── Local snap helpers ────────────────────────────────────────────────────────

def _local_snaps(snaps_dir: Path, rfi_num: int, max_snaps: int) -> list:
    return [
        f"RFI_{rfi_num:03d}_snap{i}.png"
        for i in range(1, max_snaps + 1)
        if (snaps_dir / f"RFI_{rfi_num:03d}_snap{i}.png").exists()
    ]


# ─────────────────────────────────────────────────────────────────────────────

def render_tab_generate(email: str):
    pid = st.session_state.get("current_project_id", "")
    if not pid:
        st.info("No project selected. Create or select a project from the sidebar first.")
        return

    cfg      = load_cfg(email)
    pcfg     = load_project_cfg(pid, email)
    approved = load_project_approved(pid, email)
    clients  = load_project_clients(pid, email)
    reg_rows = load_project_register(pid, email)

    # ── Always set up variables the rest of the function needs ───────────────
    orig      = cfg.get("originator", {})
    co        = cfg.get("company", {})
    max_snaps = int(cfg["settings"].get("max_snapshots", 5))
    snaps_dir = proj_snapshots_dir(pid, email)
    sync_snapshots_from_supabase(pid, email, snaps_dir)
    out_dir   = proj_output_dir(pid, email)

    _usage   = load_usage(email)
    _rfi_cnt = _usage.get("rfi_count", 0)
    _is_paid = _usage.get("is_paid", False)

    _scripts = SCRIPTS_PY_DIR
    _tmp_dir = proj_dir(pid, email)

    st.markdown("## Generate RFI Document")
    st.markdown(
        '<div style="font-size:12px;color:#6b7280;'
        'margin-top:-8px;margin-bottom:8px;">'
        'Generate a Word document for each approved '
        'RFI and send to your recipient</div>',
        unsafe_allow_html=True)

    # ── Summary strip ────────────────────────────────────────────────────────
    gm1, gm2, gm3 = st.columns(3)
    _sb_doc_names = list_project_documents(email, pid)
    _total_rfis   = len(_sb_doc_names)
    gm1.metric("RFIs", _total_rfis)
    gm2.metric("Project",    pcfg.get("name", "—"))
    gm3.metric("Recipients", len(clients))

    # ── Guard: no clients (warn but continue) ────────────────────────────────
    if not clients:
        st.markdown(
            '<div class="info-box warn">Please add recipients in '
            '<strong>Project Setup</strong> first.</div>',
            unsafe_allow_html=True)

    # ── Usage limit check (hard paywall — early return is intentional) ───────
    if _rfi_cnt >= FREE_LIMIT and not _is_paid:
        st.error(
            f"**You have used your {FREE_LIMIT} free RFIs.** "
            "Contact us at **ajohnsudhakar@gmail.com** to upgrade."
        )
        return

    if not _is_paid:
        st.markdown(
            f'<p style="color:#374151;font-size:12px;margin:12px 0 0;">'
            f'Free RFIs remaining: <strong style="color:#1d4ed8;">'
            f'{FREE_LIMIT - _rfi_cnt}</strong> of {FREE_LIMIT}</p>',
            unsafe_allow_html=True)

    # ── Latest-generation download strip ─────────────────────────────────────
    _last_path = st.session_state.get(f"t5_last_generated_{pid}", "")
    if _last_path and os.path.exists(_last_path):
        _last_name = os.path.basename(_last_path)
        st.markdown(
            f'<div style="background:#f0fdf4;border:1px solid #bbf7d0;'
            f'border-radius:8px;padding:12px 16px;margin-bottom:12px;'
            f'display:flex;justify-content:space-between;align-items:center;">'
            f'<span style="color:#166534;font-size:13px;font-weight:600;">'
            f'✓ Document ready — {_last_name}</span>'
            f'</div>',
            unsafe_allow_html=True)
        with open(_last_path, "rb") as _dl_f:
            st.download_button(
                "↓ Download Latest Document",
                data=_dl_f,
                file_name=_last_name,
                mime="application/vnd.openxmlformats-officedocument"
                     ".wordprocessingml.document",
                key=f"t5_latest_dl_{pid}",
                type="primary",
                use_container_width=False,
            )

    # ── Two-panel layout ──────────────────────────────────────────────────────────
    st.session_state.setdefault(f"t5_selected_rfi_{pid}", None)
    _lp_col, _rp_col = st.columns([1, 3])

    with _lp_col:
        st.markdown(
            '<div style="font-size:12px;font-weight:700;color:#374151;'
            'margin-bottom:8px;">RFI List</div>',
            unsafe_allow_html=True)

        if st.button("+ New Manual RFI", key=f"t5_lp_new_{pid}",
                     type="primary", use_container_width=True):
            st.session_state[f"t5_selected_rfi_{pid}"] = "new"
            st.rerun()

        _lp_cards_shown = 0
        for _lp_issue in approved:
            _lp_rfi_n = get_rfi_num(_lp_issue, 1)
            _rfi_tag = f"RFI_{_lp_rfi_n:03d}"
            _in_local = any(_rfi_tag in p.name for p in out_dir.glob("*.docx"))
            _in_cloud = any(_rfi_tag in n for n in _sb_doc_names)
            if _in_local or _in_cloud:
                continue
            _lp_cards_shown += 1
            _lp_snaps = _local_snaps(snaps_dir, _lp_rfi_n, max_snaps)
            _lp_desc  = _lp_issue.get("description", "")
            _lp_short = _lp_desc[:80] + ("…" if len(_lp_desc) > 80 else "")
            _lp_snap_lbl = f"🖼 {len(_lp_snaps)}" if _lp_snaps else "⚠ No snaps"
            _lp_snap_bg  = "#f0fdf4" if _lp_snaps else "#fffbeb"
            _lp_snap_bd  = "#bbf7d0" if _lp_snaps else "#fde68a"
            _lp_snap_fg  = "#15803d" if _lp_snaps else "#92400e"
            st.markdown(
                f'<div style="border:1px solid #e5e7eb;border-radius:6px;'
                f'padding:8px 10px;margin-bottom:4px;">'
                f'<div style="font-size:12px;font-weight:700;color:#1d4ed8;">'
                f'RFI-{_lp_rfi_n:03d}</div>'
                f'<div style="font-size:11px;color:#374151;margin:2px 0;">'
                f'{_lp_short}</div>'
                f'<div style="display:flex;gap:4px;flex-wrap:wrap;margin-top:4px;">'
                f'<span style="background:#eff6ff;border:1px solid #bfdbfe;'
                f'color:#1d4ed8;font-size:10px;padding:1px 6px;border-radius:8px;">AI</span>'
                f'<span style="background:{_lp_snap_bg};border:1px solid {_lp_snap_bd};'
                f'color:{_lp_snap_fg};font-size:10px;padding:1px 6px;border-radius:8px;">'
                f'{_lp_snap_lbl}</span>'
                f'</div></div>',
                unsafe_allow_html=True)
            if st.button("→ Create RFI", key=f"t5_lp_ai_{_lp_rfi_n}_{pid}",
                         use_container_width=True):
                st.session_state[f"t5_selected_rfi_{pid}"] = _lp_rfi_n
                st.rerun()

        if _lp_cards_shown == 0:
            st.markdown(
                '<div style="font-size:11px;color:#6b7280;padding:8px 0;">'
                'No pending RFIs. Find your documents in Previously generated '
                'documents below.</div>',
                unsafe_allow_html=True)

    with _rp_col:
        # ── Setup vars needed by the form ────────────────────────────────────
        st.session_state.setdefault(f"t5_new_reset_{pid}", 0)
        _reset_ctr = st.session_state.get(f"t5_new_reset_{pid}", 0)

        _existing_nums = (
            [get_rfi_num(iss, 1) for iss in approved] +
            [int(r["rfi_number"]) for r in reg_rows if r.get("rfi_number")]
        )
        _suggested_rfi_num = max(_existing_nums) + 1 if _existing_nums else 1
        _rfi_templates = load_rfi_templates(email)

        st.session_state.setdefault(f"t5_new_saved_{pid}", False)
        _sel_rfi = st.session_state.get(f"t5_selected_rfi_{pid}")

        if _sel_rfi is None:
            st.markdown(
                '<div style="display:flex;align-items:center;justify-content:center;'
                'min-height:180px;background:#f9fafb;border-radius:8px;'
                'border:1px dashed #d1d5db;margin-top:16px;padding:24px;">'
                '<span style="color:#9ca3af;font-size:14px;">'
                '← Select an RFI from the list, or click + New Manual RFI to begin.'
                '</span></div>',
                unsafe_allow_html=True)
        else:
            # ── Edit / View mode ──────────────────────────────────────────────
            _is_saved    = st.session_state.get(f"t5_new_saved_{pid}", False)
            _has_content = bool(st.session_state.get(f"t5_new_subject_{pid}", "").strip())
            _gen_disabled = not bool(clients)

            if not _is_saved or not _has_content:
                # ─── EDIT MODE ────────────────────────────────────────────────

                # ── SECTION 1 — RFI Identification ───────────────────────────
                st.markdown('<div class="sec-lbl">RFI Identification</div>',
                            unsafe_allow_html=True)
                _id1, _id2, _id3 = st.columns(3)
                with _id1:
                    st.number_input(
                        "RFI Number",
                        min_value=1,
                        value=_suggested_rfi_num,
                        step=1,
                        key=f"t5_new_rfi_num_{pid}",
                        help="Auto-suggested — edit if needed",
                    )
                with _id2:
                    st.selectbox(
                        "Priority",
                        ["Normal", "Critical", "High", "Low"],
                        index=0,
                        key=f"t5_new_priority_{pid}",
                    )
                with _id3:
                    st.selectbox(
                        "Category",
                        [
                            "Missing Information",
                            "Conflict Between Sheets",
                            "Coordination Issue",
                            "Ambiguous Detail",
                            "Specification Conflict",
                            "Structural Concern",
                            "Architectural Concern",
                            "Services Conflict",
                        ],
                        index=0,
                        key=f"t5_new_category_{pid}",
                    )

                # ── SECTION 2 — RFI Content ───────────────────────────────────
                st.markdown('<div class="sec-lbl" style="margin-top:16px;">RFI Content</div>',
                            unsafe_allow_html=True)
                _subj_col, _subj_ai_col = st.columns([5, 1])
                with _subj_col:
                    st.text_input("Subject *", key=f"t5_new_subject_{pid}")
                with _subj_ai_col:
                    st.markdown("<div style='margin-top:28px;'></div>",
                                unsafe_allow_html=True)
                    if st.button("Format\nwith AI", key=f"t5_new_ai_subj_{pid}",
                                 use_container_width=True):
                        _subj_api_key = _secret("ANTHROPIC_API_KEY")
                        if not st.session_state.get(f"t5_new_subject_{pid}", "").strip():
                            st.warning("Enter a subject first before formatting.")
                        elif not _subj_api_key:
                            st.warning("AI formatting is not configured. Check ANTHROPIC_API_KEY in secrets.")
                        else:
                            try:
                                import anthropic as _anth_subj
                                _subj_ai_client = _anth_subj.Anthropic(api_key=_subj_api_key)
                                _subj_ai_resp = _subj_ai_client.messages.create(
                                    model="claude-opus-4-6",
                                    max_tokens=200,
                                    system=(
                                        "You are a construction RFI writing assistant. Rewrite the engineer's "
                                        "rough subject into a concise one-line professional RFI subject. "
                                        "Return only the rewritten subject line, nothing else."
                                    ),
                                    messages=[{"role": "user", "content": st.session_state.get(f"t5_new_subject_{pid}", "")}],
                                )
                                st.session_state[f"t5_new_subject_{pid}"] = _subj_ai_resp.content[0].text
                            except Exception as _subj_ai_err:
                                st.warning(f"AI formatting error: {_subj_ai_err}")
                            else:
                                st.rerun()

                _qn_col, _ai_col2 = st.columns([5, 1])
                with _qn_col:
                    st.text_area("Question *", key=f"t5_new_question_{pid}", height=160)
                with _ai_col2:
                    st.markdown("<div style='margin-top:28px;'></div>",
                                unsafe_allow_html=True)
                    if st.button("Format\nwith AI", key=f"t5_new_ai_fmt_{pid}",
                                 use_container_width=True):
                        _new_api_key = _secret("ANTHROPIC_API_KEY")
                        if not _new_api_key:
                            st.warning("AI formatting is not configured. Check ANTHROPIC_API_KEY in secrets.")
                        else:
                            try:
                                import anthropic as _anth
                                _new_ai_client = _anth.Anthropic(api_key=_new_api_key)
                                _new_ai_resp = _new_ai_client.messages.create(
                                    model="claude-opus-4-6",
                                    max_tokens=1000,
                                    system=(
                                        "You are a construction RFI writing assistant. Rewrite the "
                                        "engineer's rough notes into a clear, professional RFI question "
                                        "using formal construction industry language. Keep it factual. "
                                        "Return only the rewritten question text, nothing else."
                                    ),
                                    messages=[{"role": "user", "content": st.session_state.get(f"t5_new_question_{pid}", "")}],
                                )
                                st.session_state[f"t5_new_question_{pid}"] = _new_ai_resp.content[0].text
                            except Exception as _new_ai_err:
                                st.warning(f"AI formatting error: {_new_ai_err}")
                            else:
                                st.rerun()

                _rf1, _rf2 = st.columns(2)
                with _rf1:
                    st.text_input("Drawing Reference", key=f"t5_new_sheets_{pid}")
                with _rf2:
                    st.text_input(
                        "Reference Document No.",
                        key=f"t5_new_ref_doc_{pid}",
                        placeholder="e.g. Spec clause 3.4.2 / Drawing S-101",
                    )
                st.date_input(
                    "Response Required By",
                    value=date.today() + timedelta(days=14),
                    key=f"t5_new_rbd_{pid}",
                )

                if clients:
                    st.selectbox(
                        "Send to",
                        range(len(clients)),
                        format_func=lambda i: clients[i].get("company", "?"),
                        index=0,
                        key=f"t5_new_client_idx_{pid}",
                    )
                else:
                    st.warning("No recipients configured — add recipients in Project Setup first.")

                # ── SECTION 3 — Instructions and Notes ───────────────────────
                st.markdown(
                    '<div class="sec-lbl" style="margin-top:16px;">Instructions and Notes</div>',
                    unsafe_allow_html=True)

                _ins_col, _ins_tmpl_col = st.columns([4, 1.5])
                with _ins_col:
                    _ins_stage = f"t5_new_instructions_stage_{pid}"
                    if _ins_stage in st.session_state:
                        st.session_state[f"t5_new_instructions_{pid}"] = st.session_state.pop(_ins_stage)
                    st.text_area(
                        "Instructions",
                        height=120,
                        key=f"t5_new_instructions_{pid}",
                    )
                    if st.button("Format\nwith AI", key=f"t5_new_ai_ins_{pid}",
                                 use_container_width=True):
                        _ins_api_key = _secret("ANTHROPIC_API_KEY")
                        if not st.session_state.get(f"t5_new_instructions_{pid}", "").strip():
                            st.warning("Enter instructions first before formatting.")
                        elif not _ins_api_key:
                            st.warning("AI formatting is not configured. Check ANTHROPIC_API_KEY in secrets.")
                        else:
                            try:
                                import anthropic as _anth_ins
                                _ins_ai_client = _anth_ins.Anthropic(api_key=_ins_api_key)
                                _ins_ai_resp = _ins_ai_client.messages.create(
                                    model="claude-opus-4-6",
                                    max_tokens=500,
                                    system=(
                                        "You are a construction RFI writing assistant. Rewrite the engineer's "
                                        "instructions into professional construction contract language. "
                                        "Return only the rewritten text, nothing else."
                                    ),
                                    messages=[{"role": "user", "content": st.session_state.get(f"t5_new_instructions_{pid}", "")}],
                                )
                                st.session_state[f"t5_new_instructions_{pid}"] = _ins_ai_resp.content[0].text
                            except Exception as _ins_ai_err:
                                st.warning(f"AI formatting error: {_ins_ai_err}")
                            else:
                                st.rerun()
                with _ins_tmpl_col:
                    st.markdown("**Saved templates**")
                    _ins_tmpls = _rfi_templates.get("instructions", {})
                    if _ins_tmpls:
                        for _tname, _ttext in _ins_tmpls.items():
                            _ti1, _ti2 = st.columns([3, 1])
                            with _ti1:
                                st.write(_tname)
                            with _ti2:
                                if st.button("←", key=f"t5_new_ins_load_{_tname}_{pid}",
                                             use_container_width=True):
                                    st.session_state[f"t5_new_instructions_stage_{pid}"] = _ttext
                                    st.rerun()
                    else:
                        st.markdown(
                            '<span style="font-size:11px;color:#6b7280;">No saved templates yet</span>',
                            unsafe_allow_html=True)
                    st.markdown("---")
                    _ins_tname_col, _ins_save_col = st.columns([3, 1])
                    with _ins_tname_col:
                        st.text_input("", placeholder="Template name...",
                                      key=f"t5_new_ins_tname_{pid}",
                                      label_visibility="collapsed")
                    with _ins_save_col:
                        if st.button("Save", key=f"t5_new_ins_save_{pid}",
                                     use_container_width=True):
                            _ins_save_name = st.session_state.get(f"t5_new_ins_tname_{pid}", "").strip()
                            _ins_save_text = st.session_state.get(f"t5_new_instructions_{pid}", "").strip()
                            if not _ins_save_name or not _ins_save_text:
                                st.warning("Enter a template name and some instructions text before saving.")
                            else:
                                _ins_tmpl_data = load_rfi_templates(email)
                                _ins_tmpl_data["instructions"][_ins_save_name] = _ins_save_text
                                save_rfi_templates(email, _ins_tmpl_data)
                                st.success(f"Template '{_ins_save_name}' saved.")
                                st.session_state.pop(f"t5_new_ins_tname_{pid}", None)
                                st.rerun()

                st.markdown("---")

                _note_col, _note_tmpl_col = st.columns([4, 1.5])
                with _note_col:
                    _note_stage = f"t5_new_note_stage_{pid}"
                    if _note_stage in st.session_state:
                        st.session_state[f"t5_new_note_{pid}"] = st.session_state.pop(_note_stage)
                    st.text_area(
                        "Note",
                        height=120,
                        key=f"t5_new_note_{pid}",
                    )
                    if st.button("Format\nwith AI", key=f"t5_new_ai_note_{pid}",
                                 use_container_width=True):
                        _note_api_key = _secret("ANTHROPIC_API_KEY")
                        if not st.session_state.get(f"t5_new_note_{pid}", "").strip():
                            st.warning("Enter a note first before formatting.")
                        elif not _note_api_key:
                            st.warning("AI formatting is not configured. Check ANTHROPIC_API_KEY in secrets.")
                        else:
                            try:
                                import anthropic as _anth_note
                                _note_ai_client = _anth_note.Anthropic(api_key=_note_api_key)
                                _note_ai_resp = _note_ai_client.messages.create(
                                    model="claude-opus-4-6",
                                    max_tokens=500,
                                    system=(
                                        "You are a construction RFI writing assistant. Rewrite the engineer's "
                                        "note into professional construction contract language. "
                                        "Return only the rewritten text, nothing else."
                                    ),
                                    messages=[{"role": "user", "content": st.session_state.get(f"t5_new_note_{pid}", "")}],
                                )
                                st.session_state[f"t5_new_note_{pid}"] = _note_ai_resp.content[0].text
                            except Exception as _note_ai_err:
                                st.warning(f"AI formatting error: {_note_ai_err}")
                            else:
                                st.rerun()
                with _note_tmpl_col:
                    st.markdown("**Saved templates**")
                    _note_tmpls = _rfi_templates.get("note", {})
                    if _note_tmpls:
                        for _tname, _ttext in _note_tmpls.items():
                            _tn1, _tn2 = st.columns([3, 1])
                            with _tn1:
                                st.write(_tname)
                            with _tn2:
                                if st.button("←", key=f"t5_new_note_load_{_tname}_{pid}",
                                             use_container_width=True):
                                    st.session_state[f"t5_new_note_stage_{pid}"] = _ttext
                                    st.rerun()
                    else:
                        st.markdown(
                            '<span style="font-size:11px;color:#6b7280;">No saved templates yet</span>',
                            unsafe_allow_html=True)
                    st.markdown("---")
                    _note_tname_col, _note_save_col = st.columns([3, 1])
                    with _note_tname_col:
                        st.text_input("", placeholder="Template name...",
                                      key=f"t5_new_note_tname_{pid}",
                                      label_visibility="collapsed")
                    with _note_save_col:
                        if st.button("Save", key=f"t5_new_note_save_{pid}",
                                     use_container_width=True):
                            _note_save_name = st.session_state.get(f"t5_new_note_tname_{pid}", "").strip()
                            _note_save_text = st.session_state.get(f"t5_new_note_{pid}", "").strip()
                            if not _note_save_name or not _note_save_text:
                                st.warning("Enter a template name and some note text before saving.")
                            else:
                                _note_tmpl_data = load_rfi_templates(email)
                                _note_tmpl_data["note"][_note_save_name] = _note_save_text
                                save_rfi_templates(email, _note_tmpl_data)
                                st.success(f"Template '{_note_save_name}' saved.")
                                st.session_state.pop(f"t5_new_note_tname_{pid}", None)
                                st.rerun()

                # ── SECTION 4 — Impact Assessment ────────────────────────────
                st.markdown(
                    '<div class="sec-lbl" style="margin-top:16px;">Impact Assessment</div>',
                    unsafe_allow_html=True)
                _ni1, _ni2, _ni3, _ni4 = st.columns(4)
                with _ni1:
                    st.radio("Cost Impact",     ["TBD", "Yes", "No"], index=0, key=f"t5_new_cost_{pid}")
                with _ni2:
                    st.radio("Schedule Impact", ["TBD", "Yes", "No"], index=0, key=f"t5_new_schedule_{pid}")
                with _ni3:
                    st.radio("Environmental",   ["TBD", "Yes", "No"], index=0, key=f"t5_new_env_{pid}")
                with _ni4:
                    st.radio("Public Affairs",  ["TBD", "Yes", "No"], index=0, key=f"t5_new_pub_{pid}")

                # ── SECTION 5 — Attachments ───────────────────────────────────
                st.markdown(
                    '<div class="sec-lbl" style="margin-top:16px;">Attachments</div>',
                    unsafe_allow_html=True)
                st.file_uploader(
                    "Upload screenshots or site photos",
                    type=["png", "jpg", "jpeg"],
                    accept_multiple_files=True,
                    key=f"t5_new_uploads_{pid}_{_reset_ctr}",
                )
                st.markdown(
                    '<div style="font-size:11px;color:#6b7280;margin-top:4px;">'
                    'These will appear as snapshots in the generated Word document</div>',
                    unsafe_allow_html=True)

                # ── Save / Cancel buttons ─────────────────────────────────────
                _nb1, _nb2 = st.columns([2, 1])
                with _nb1:
                    _new_save = st.button(
                        "💾 Save RFI",
                        type="primary",
                        key=f"t5_new_save_{pid}",
                        use_container_width=True,
                    )
                with _nb2:
                    _new_cancel = st.button(
                        "Cancel",
                        key=f"t5_new_cancel_{pid}",
                        use_container_width=True,
                    )

                if _new_cancel:
                    _prev_reset = st.session_state.get(f"t5_new_reset_{pid}", 0)
                    for _ck in list(st.session_state.keys()):
                        if _ck.startswith("t5_new_") and _ck.endswith(f"_{pid}"):
                            st.session_state.pop(_ck, None)
                    st.session_state[f"t5_new_reset_{pid}"] = _prev_reset + 1
                    st.session_state[f"t5_new_saved_{pid}"] = False
                    st.session_state[f"t5_selected_rfi_{pid}"] = None
                    st.rerun()

                if _new_save:
                    _subj = st.session_state.get(f"t5_new_subject_{pid}", "").strip()
                    _qst  = st.session_state.get(f"t5_new_question_{pid}", "").strip()
                    if not _subj or not _qst:
                        st.error("Subject and Question are both required.")
                    else:
                        _up_files = st.session_state.get(f"t5_new_uploads_{pid}_{_reset_ctr}") or []
                        _num = int(st.session_state.get(f"t5_new_rfi_num_{pid}", _suggested_rfi_num))
                        for _fi, _uf in enumerate(_up_files[:5], start=1):
                            _fname = f"RFI_{_num:03d}_snap{_fi}.png"
                            _fdata = _uf.read()
                            _fpath = snaps_dir / _fname
                            _fpath.parent.mkdir(parents=True, exist_ok=True)
                            _fpath.write_bytes(_fdata)
                            upload_project_snapshot(email, pid, _fname, _fdata)

                        _new_issue = {
                            "rfi_number":            _num,
                            "description":           _subj,
                            "question":              _qst,
                            "sheets":                st.session_state.get(f"t5_new_sheets_{pid}", ""),
                            "reference_doc":         st.session_state.get(f"t5_new_ref_doc_{pid}", ""),
                            "response_required_by":  str(st.session_state.get(f"t5_new_rbd_{pid}", "")),
                            "priority":              st.session_state.get(f"t5_new_priority_{pid}", "Normal"),
                            "category":              st.session_state.get(f"t5_new_category_{pid}", ""),
                            "cost_impact":           st.session_state.get(f"t5_new_cost_{pid}", "TBD"),
                            "schedule_impact":       st.session_state.get(f"t5_new_schedule_{pid}", "TBD"),
                            "environmental_impact":  st.session_state.get(f"t5_new_env_{pid}", "TBD"),
                            "public_affairs_impact": st.session_state.get(f"t5_new_pub_{pid}", "TBD"),
                        }
                        upsert_project_register_rows(pid, [_new_issue], pcfg.get("name", ""), email)
                        st.session_state[f"t5_new_saved_{pid}"] = True
                        st.rerun()

            else:
                # ─── VIEW MODE ────────────────────────────────────────────────
                _rfi_num = int(st.session_state.get(f"t5_new_rfi_num_{pid}", 1))
                st.markdown(
                    f'<div style="background:#f0fdf4;border:1px solid #bbf7d0;'
                    f'border-radius:8px;padding:16px 20px;margin-bottom:16px;">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                    f'<div>'
                    f'<div style="font-size:16px;font-weight:700;color:#166534;">'
                    f'RFI-{_rfi_num:03d} — Saved</div>'
                    f'<div style="font-size:12px;color:#15803d;margin-top:4px;">'
                    f'Review details below, then generate the Word document</div>'
                    f'</div>'
                    f'<span style="background:#dcfce7;color:#15803d;font-size:12px;'
                    f'font-weight:600;padding:4px 12px;border-radius:12px;">✓ Saved</span>'
                    f'</div></div>',
                    unsafe_allow_html=True)

                def _ro(_label, _value, _gray_if_empty=False):
                    _v = _value or ""
                    if _gray_if_empty and not _v:
                        st.markdown(
                            f'<div style="font-size:11px;color:#6b7280;">{_label}</div>'
                            f'<div style="font-size:12px;color:#9ca3af;font-style:italic;">'
                            f'Using default</div>',
                            unsafe_allow_html=True)
                    else:
                        st.markdown(
                            f'<div style="font-size:11px;color:#6b7280;">{_label}</div>'
                            f'<div style="font-size:13px;color:#111827;font-weight:500;">'
                            f'{_v or "—"}</div>',
                            unsafe_allow_html=True)

                # Section: Identification
                st.markdown('<div class="sec-lbl">Identification</div>', unsafe_allow_html=True)
                _vi1, _vi2, _vi3 = st.columns(3)
                with _vi1:
                    _ro("RFI Number", str(_rfi_num))
                with _vi2:
                    _ro("Priority", st.session_state.get(f"t5_new_priority_{pid}", "Normal"))
                with _vi3:
                    _ro("Category", st.session_state.get(f"t5_new_category_{pid}", ""))
                _ro("Subject", st.session_state.get(f"t5_new_subject_{pid}", ""))

                # Section: Question
                st.markdown('<div class="sec-lbl" style="margin-top:12px;">Question</div>',
                            unsafe_allow_html=True)
                _ro("Question", st.session_state.get(f"t5_new_question_{pid}", ""))
                _vq1, _vq2 = st.columns(2)
                with _vq1:
                    _ro("Drawing Reference", st.session_state.get(f"t5_new_sheets_{pid}", ""))
                with _vq2:
                    _ro("Reference Document No.", st.session_state.get(f"t5_new_ref_doc_{pid}", ""))
                _vq3, _vq4 = st.columns(2)
                with _vq3:
                    _rbd_val = str(st.session_state.get(f"t5_new_rbd_{pid}", "") or "")
                    if _rbd_val:
                        st.markdown(
                            f'<div style="font-size:11px;color:#6b7280;">Response Required By</div>'
                            f'<div style="font-size:13px;color:#dc2626;font-weight:700;">{_rbd_val}</div>',
                            unsafe_allow_html=True)
                    else:
                        _ro("Response Required By", "")
                with _vq4:
                    _ci_v = st.session_state.get(f"t5_new_client_idx_{pid}", 0)
                    if not isinstance(_ci_v, int) or _ci_v < 0 or _ci_v >= len(clients):
                        _ci_v = 0
                    _send_to = clients[_ci_v].get("company", "—") if clients else "—"
                    _ro("Send To", _send_to)

                # Section: Instructions & Note
                st.markdown('<div class="sec-lbl" style="margin-top:12px;">Instructions & Note</div>',
                            unsafe_allow_html=True)
                _vin1, _vin2 = st.columns(2)
                with _vin1:
                    _ro("Instructions", st.session_state.get(f"t5_new_instructions_{pid}", ""),
                        _gray_if_empty=True)
                with _vin2:
                    _ro("Note", st.session_state.get(f"t5_new_note_{pid}", ""),
                        _gray_if_empty=True)

                # Section: Impact Assessment
                st.markdown('<div class="sec-lbl" style="margin-top:12px;">Impact Assessment</div>',
                            unsafe_allow_html=True)
                _vim1, _vim2, _vim3, _vim4 = st.columns(4)
                with _vim1:
                    _ro("Cost Impact",     st.session_state.get(f"t5_new_cost_{pid}", "TBD"))
                with _vim2:
                    _ro("Schedule Impact", st.session_state.get(f"t5_new_schedule_{pid}", "TBD"))
                with _vim3:
                    _ro("Environmental",   st.session_state.get(f"t5_new_env_{pid}", "TBD"))
                with _vim4:
                    _ro("Public Affairs",  st.session_state.get(f"t5_new_pub_{pid}", "TBD"))

                # Section: Attachments
                st.markdown('<div class="sec-lbl" style="margin-top:12px;">Attachments</div>',
                            unsafe_allow_html=True)
                _att_files = sorted(snaps_dir.glob(f"RFI_{_rfi_num:03d}_snap*.png"))
                if _att_files:
                    for _af in _att_files:
                        st.markdown(
                            f'<div style="font-size:12px;color:#374151;">\U0001f5bc {_af.name}</div>',
                            unsafe_allow_html=True)
                else:
                    st.markdown(
                        '<div style="font-size:12px;color:#9ca3af;">No attachments</div>',
                        unsafe_allow_html=True)

                # ── Generate / Edit buttons ───────────────────────────────────
                st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)
                _vb1, _vb2 = st.columns([2, 1])
                with _vb1:
                    _view_gen = st.button(
                        "▶ Generate Word Document",
                        type="primary",
                        disabled=_gen_disabled,
                        key=f"t5_new_gen_{pid}",
                        use_container_width=True,
                    )
                with _vb2:
                    _view_edit = st.button(
                        "✏ Edit",
                        key=f"t5_new_edit_{pid}",
                        use_container_width=True,
                    )

                if _view_edit:
                    st.session_state[f"t5_new_saved_{pid}"] = False
                    st.rerun()

                if _view_gen:
                    _subj = st.session_state.get(f"t5_new_subject_{pid}", "").strip()
                    _qst  = st.session_state.get(f"t5_new_question_{pid}", "").strip()
                    if not _subj or not _qst:
                        st.error("Subject and Question are both required.")
                    else:
                        _up_files = st.session_state.get(f"t5_new_uploads_{pid}_{_reset_ctr}") or []
                        _num = int(st.session_state.get(f"t5_new_rfi_num_{pid}", _suggested_rfi_num))
                        for _fi, _uf in enumerate(_up_files[:5], start=1):
                            _fname = f"RFI_{_num:03d}_snap{_fi}.png"
                            _fdata = _uf.read()
                            _fpath = snaps_dir / _fname
                            _fpath.parent.mkdir(parents=True, exist_ok=True)
                            _fpath.write_bytes(_fdata)
                            upload_project_snapshot(email, pid, _fname, _fdata)

                        _new_issue = {
                            "rfi_number":            _num,
                            "description":           _subj,
                            "question":              _qst,
                            "sheets":                st.session_state.get(f"t5_new_sheets_{pid}", ""),
                            "reference_doc":         st.session_state.get(f"t5_new_ref_doc_{pid}", ""),
                            "response_required_by":  str(st.session_state.get(f"t5_new_rbd_{pid}", "")),
                            "priority":              st.session_state.get(f"t5_new_priority_{pid}", "Normal"),
                            "category":              st.session_state.get(f"t5_new_category_{pid}", ""),
                            "cost_impact":           st.session_state.get(f"t5_new_cost_{pid}", "TBD"),
                            "schedule_impact":       st.session_state.get(f"t5_new_schedule_{pid}", "TBD"),
                            "environmental_impact":  st.session_state.get(f"t5_new_env_{pid}", "TBD"),
                            "public_affairs_impact": st.session_state.get(f"t5_new_pub_{pid}", "TBD"),
                        }

                        _ci = st.session_state.get(f"t5_new_client_idx_{pid}", 0)
                        if not isinstance(_ci, int) or _ci < 0 or _ci >= len(clients):
                            _ci = 0
                        _new_sel_client = clients[_ci]

                        _new_logo_path = ""
                        _new_sig_path  = ""
                        for _asset, _attr in (("company_logo.png", "logo"), ("signature.png", "sig")):
                            _adata = get_asset_bytes(email, _asset)
                            if _adata:
                                _tmp_path = _tmp_dir / _asset
                                try:
                                    _tmp_path.parent.mkdir(parents=True, exist_ok=True)
                                    _tmp_path.write_bytes(_adata)
                                    if _attr == "logo":
                                        _new_logo_path = str(_tmp_path)
                                    else:
                                        _new_sig_path = str(_tmp_path)
                                except Exception:
                                    pass
                            if not _new_logo_path and _attr == "logo":
                                _local = _scripts / _asset
                                if _local.exists():
                                    _new_logo_path = str(_local)
                            if not _new_sig_path and _attr == "sig":
                                _local = _scripts / _asset
                                if _local.exists():
                                    _new_sig_path = str(_local)

                        _new_pdf = resolve_pdf_path(pid, email)

                        config = {
                            "project": {
                                "name":           pcfg.get("name", ""),
                                "address":        pcfg.get("address", ""),
                                "project_number": pcfg.get("project_number", ""),
                                "pdf":            str(_new_pdf) if _new_pdf else "",
                            },
                            "company":    co,
                            "originator": orig,
                            "client": {
                                "company": _new_sel_client.get("company", ""),
                                "attn":    _new_sel_client.get("attn",    ""),
                                "email":   _new_sel_client.get("email",   ""),
                                "phone":   _new_sel_client.get("phone",   ""),
                                "role":    _new_sel_client.get("role",    ""),
                            },
                            "paths": {
                                "logo":      _new_logo_path,
                                "signature": _new_sig_path,
                                "snapshots": str(snaps_dir),
                                "output":    str(out_dir),
                            },
                            "settings":         cfg.get("settings", {"max_snapshots": 5}),
                            "approved_rfis":    [_new_issue],
                            "instructions_text":   st.session_state.get(f"t5_new_instructions_{pid}", ""),
                            "superintendent_text": st.session_state.get(f"t5_new_note_{pid}", ""),
                        }

                        with st.spinner("Building Word document…"):
                            result = generate_rfi_document(config)

                        if result["success"]:
                            out_path = result["output_path"]
                            if out_path and os.path.exists(out_path):
                                with open(out_path, "rb") as _nfh:
                                    _ndoc_bytes = _nfh.read()
                                if not upload_project_document(email, pid, os.path.basename(out_path), _ndoc_bytes):
                                    st.warning("⚠ Cloud backup failed — document saved locally. Check your connection.")
                                st.session_state[f"t5_new_last_doc_{pid}"] = out_path
                                st.session_state[f"t5_last_generated_{pid}"] = out_path
                                if isinstance(_sel_rfi, int):
                                    st.session_state[f"t5_doc_path_{_sel_rfi}_{pid}"] = out_path
                            increment_usage(email)
                            upsert_project_register_rows(pid, [_new_issue], pcfg.get("name", ""), email)
                            st.session_state[f"t5_selected_rfi_{pid}"] = None
                            st.session_state.pop(f"t5_new_subject_{pid}", None)
                            st.rerun()
                        else:
                            st.error(result["message"])

    # ── Previous documents ───────────────────────────────────────────────────
    st.markdown("---")
    _all_names = _sb_doc_names
    if _all_names:
        with st.expander(f"📂  Previously generated documents ({len(_all_names)})"):
            st.markdown(
                '<style>details:has(.rfi-doc-list-marker) > div {'
                'max-height:400px;overflow-y:auto;'
                'border:1px solid #e5e7eb;border-radius:6px;'
                '}</style>'
                '<div class="rfi-doc-list-marker" style="display:none;"></div>'
                '<div style="display:grid;grid-template-columns:5fr 1fr;'
                'background:#fafafa;border-bottom:1px solid #f0f0f0;'
                'padding:4px 0;font-size:10.5px;color:#9ca3af;'
                'text-transform:uppercase;font-weight:600;">'
                '<span>Filename</span><span>Download</span></div>',
                unsafe_allow_html=True)
            for _doc_name in _all_names:
                dc1, dc2 = st.columns([5, 1])
                dc1.markdown(
                    f'<span style="color:#374151;font-size:13px;">{_doc_name}</span>',
                    unsafe_allow_html=True)
                with dc2:
                    _local_path = out_dir / _doc_name
                    if _local_path.exists():
                        with open(_local_path, "rb") as fh:
                            _doc_bytes = fh.read()
                    else:
                        with st.spinner("Loading…"):
                            _doc_bytes = download_project_document(email, pid, _doc_name)
                    if _doc_bytes:
                        st.download_button(
                            "↓ Download",
                            data=_doc_bytes,
                            file_name=_doc_name,
                            mime="application/vnd.openxmlformats-officedocument"
                                 ".wordprocessingml.document",
                            use_container_width=True,
                            key=f"dl_{_doc_name.replace('.docx', '')}",
                        )
