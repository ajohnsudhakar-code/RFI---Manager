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
    gm1.metric("RFIs",       len(approved))
    gm2.metric("Project",    pcfg.get("name", "—"))
    gm3.metric("Recipients", len(clients))

    # ── Guard: no approved issues ────────────────────────────────────────────
    if not approved:
        st.info(
            "No AI issues have been identified yet. "
            "Use the Analyse Drawings tab to scan your drawings, "
            "or create an RFI manually using the form below."
        )

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

    # ── RFI checklist with per-RFI generate buttons ──────────────────────────
    if approved:
        st.markdown('<div class="sec-lbl" style="margin-top:24px;">RFI Contents</div>',
                    unsafe_allow_html=True)

        for issue in approved:
            rfi_n  = get_rfi_num(issue, 1)
            snaps  = _local_snaps(snaps_dir, rfi_n, max_snaps)
            has_s  = len(snaps) > 0
            border = "#059669" if has_s else "#dc2626"
            badge  = (f'<span style="background:#f0fdf4;padding:2px 8px;border-radius:10px;border:1px solid #bbf7d0;color:#15803d;font-size:12px;">🖼 {len(snaps)} snapshot(s)</span>'
                      if has_s else
                      '<span style="background:#fffbeb;padding:2px 8px;border-radius:10px;border:1px solid #fde68a;color:#92400e;font-size:12px;">⚠ No snapshots</span>')
            st.markdown(f"""
<div class="rfi-card" style="border-left:3px solid {border};">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">
    <strong style="color:#1d4ed8;">RFI-{rfi_n:03d}</strong>
    <div style="display:flex;gap:12px;align-items:center;">
      <span style="color:#374151;font-size:12px;">Sheet: {issue.get('sheets','?')}</span>
      {badge}
    </div>
  </div>
  <p style="color:#374151;font-size:13px;margin:8px 0 0;">{issue.get('description','')[:200]}</p>
</div>""", unsafe_allow_html=True)

            _clicked = False
            with st.expander("Fill in RFI details before generating", expanded=False):

                # Subject (read-only)
                st.markdown('<span style="font-size:11px;color:#6b7280;font-weight:600;">SUBJECT</span>', unsafe_allow_html=True)
                st.markdown(f'<p style="color:#374151;font-size:13px;margin:0 0 12px;">{issue.get("description","")}</p>', unsafe_allow_html=True)

                # Question text area + Format with AI
                _q_key = f"t5_question_{rfi_n}_{pid}"
                if _q_key not in st.session_state:
                    st.session_state[_q_key] = (
                        issue.get('description', '') + '\n\n' + issue.get('reason', '')
                    )
                _q_col, _ai_col = st.columns([5, 1])
                with _q_col:
                    st.text_area("Question", key=_q_key, height=160)
                with _ai_col:
                    st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
                    if st.button("Format\nwith AI", key=f"t5_ai_fmt_{rfi_n}_{pid}",
                                 use_container_width=True):
                        _api_key = _secret("ANTHROPIC_API_KEY")
                        if not _api_key:
                            st.warning("AI formatting is not configured. Check ANTHROPIC_API_KEY in secrets.")
                        else:
                            try:
                                import anthropic
                                _ai_client = anthropic.Anthropic(api_key=_api_key)
                                _ai_resp = _ai_client.messages.create(
                                    model="claude-opus-4-6",
                                    max_tokens=1000,
                                    system=(
                                        "You are a construction RFI writing assistant. Rewrite the "
                                        "engineer's rough notes into a clear, professional RFI question "
                                        "using formal construction industry language. Keep it factual. "
                                        "Return only the rewritten question text, nothing else."
                                    ),
                                    messages=[{"role": "user", "content": st.session_state.get(_q_key, "")}],
                                )
                                st.session_state[_q_key] = _ai_resp.content[0].text
                            except Exception as _ai_err:
                                st.warning(f"AI formatting error: {_ai_err}")
                            else:
                                st.rerun()

                # Reference Document No.
                st.text_input(
                    "Reference Document No.",
                    key=f"t5_ref_doc_{rfi_n}_{pid}",
                    placeholder="e.g. Spec clause 3.4.2 / Drawing S-101",
                )

                # Drawing Reference (pre-filled)
                _s_key = f"t5_sheets_{rfi_n}_{pid}"
                if _s_key not in st.session_state:
                    st.session_state[_s_key] = issue.get('sheets', '')
                st.text_input("Drawing Reference", key=_s_key)

                # Response Required By (pre-filled)
                _rbd_key = f"t5_rbd_{rfi_n}_{pid}"
                if _rbd_key not in st.session_state:
                    _rbd_raw = issue.get('response_required_by', '')
                    try:
                        st.session_state[_rbd_key] = date.fromisoformat(_rbd_raw) if _rbd_raw else date.today() + timedelta(days=14)
                    except (ValueError, TypeError):
                        st.session_state[_rbd_key] = date.today() + timedelta(days=14)
                st.date_input("Response Required By", key=_rbd_key)

                # Impact radios
                _ic1, _ic2, _ic3, _ic4 = st.columns(4)
                with _ic1:
                    st.radio("Cost Impact",     ["TBD", "Yes", "No"], index=0, key=f"t5_cost_{rfi_n}_{pid}")
                with _ic2:
                    st.radio("Schedule Impact", ["TBD", "Yes", "No"], index=0, key=f"t5_schedule_{rfi_n}_{pid}")
                with _ic3:
                    st.radio("Environmental",   ["TBD", "Yes", "No"], index=0, key=f"t5_env_{rfi_n}_{pid}")
                with _ic4:
                    st.radio("Public Affairs",  ["TBD", "Yes", "No"], index=0, key=f"t5_pub_{rfi_n}_{pid}")

                # Send to + Generate + Download
                _sel_col, _gen_col, _dl_col = st.columns([3, 2, 2])
                with _sel_col:
                    _sel_client_idx = st.selectbox(
                        "Send to",
                        range(len(clients)),
                        format_func=lambda i: clients[i].get("company", "?"),
                        index=0,
                        key=f"t5_client_{rfi_n}_{pid}",
                        label_visibility="collapsed",
                    ) if clients else None
                    _sel_client = clients[_sel_client_idx] if clients and _sel_client_idx is not None else {}
                with _gen_col:
                    _clicked = st.button("▶ Generate", type="primary",
                                         use_container_width=True, key=f"gen_{rfi_n}_{pid}",
                                         disabled=not clients)
                with _dl_col:
                    _doc_path = st.session_state.get(f"t5_doc_path_{rfi_n}_{pid}", "")
                    if _doc_path and os.path.exists(_doc_path):
                        with open(_doc_path, "rb") as _dl_fh:
                            st.download_button(
                                "↓ Download",
                                data=_dl_fh,
                                file_name=os.path.basename(_doc_path),
                                mime="application/vnd.openxmlformats-officedocument"
                                     ".wordprocessingml.document",
                                use_container_width=True,
                                key=f"gen_dl_{rfi_n}_{pid}",
                            )
                    else:
                        st.button("↓ Download", disabled=True,
                                  use_container_width=True, key=f"dl_inactive_{rfi_n}_{pid}")

            if _clicked:
                with st.spinner("Building Word document…"):

                    logo_path = ""
                    sig_path  = ""

                    for _asset, _attr in (("company_logo.png", "logo"), ("signature.png", "sig")):
                        _adata = get_asset_bytes(email, _asset)
                        if _adata:
                            _tmp_path = _tmp_dir / _asset
                            try:
                                _tmp_path.parent.mkdir(parents=True, exist_ok=True)
                                _tmp_path.write_bytes(_adata)
                                if _attr == "logo":
                                    logo_path = str(_tmp_path)
                                else:
                                    sig_path = str(_tmp_path)
                            except Exception:
                                pass
                        if not logo_path and _attr == "logo":
                            _local = _scripts / _asset
                            if _local.exists():
                                logo_path = str(_local)
                        if not sig_path and _attr == "sig":
                            _local = _scripts / _asset
                            if _local.exists():
                                sig_path = str(_local)

                    _pdf_resolved = resolve_pdf_path(pid, email)
                    _issue_copy = issue.copy()
                    _issue_copy["question"]              = st.session_state.get(f"t5_question_{rfi_n}_{pid}", issue.get("description", ""))
                    _issue_copy["reference_doc"]         = st.session_state.get(f"t5_ref_doc_{rfi_n}_{pid}", "")
                    _issue_copy["sheets"]                = st.session_state.get(f"t5_sheets_{rfi_n}_{pid}", issue.get("sheets", ""))
                    _issue_copy["response_required_by"]  = str(st.session_state.get(f"t5_rbd_{rfi_n}_{pid}", issue.get("response_required_by", "")))
                    _issue_copy["cost_impact"]           = st.session_state.get(f"t5_cost_{rfi_n}_{pid}", "TBD")
                    _issue_copy["schedule_impact"]       = st.session_state.get(f"t5_schedule_{rfi_n}_{pid}", "TBD")
                    _issue_copy["environmental_impact"]  = st.session_state.get(f"t5_env_{rfi_n}_{pid}", "TBD")
                    _issue_copy["public_affairs_impact"] = st.session_state.get(f"t5_pub_{rfi_n}_{pid}", "TBD")

                    config = {
                        "project": {
                            "name":           pcfg.get("name", ""),
                            "address":        pcfg.get("address", ""),
                            "project_number": pcfg.get("project_number", ""),
                            "pdf":            str(_pdf_resolved) if _pdf_resolved else "",
                        },
                        "company":    co,
                        "originator": orig,
                        "client": {
                            "company": _sel_client.get("company", ""),
                            "attn":    _sel_client.get("attn",    ""),
                            "email":   _sel_client.get("email",   ""),
                            "phone":   _sel_client.get("phone",   ""),
                            "role":    _sel_client.get("role",    ""),
                        },
                        "paths": {
                            "logo":      logo_path,
                            "signature": sig_path,
                            "snapshots": str(snaps_dir),
                            "output":    str(out_dir),
                        },
                        "settings":          cfg.get("settings", {"max_snapshots": 5}),
                        "approved_rfis":     [_issue_copy],
                        "instructions_text":    "",
                        "superintendent_text":  "",
                    }

                    result = generate_rfi_document(config)

                if result["success"]:
                    out_path = result["output_path"]
                    if out_path and os.path.exists(out_path):
                        with open(out_path, "rb") as _doc_fh:
                            _doc_bytes = _doc_fh.read()
                        if not upload_project_document(email, pid, os.path.basename(out_path), _doc_bytes):
                            st.warning("⚠ Cloud backup failed — document saved locally. Check your connection.")
                        st.session_state[f"t5_doc_path_{rfi_n}_{pid}"] = out_path
                    increment_usage(email)
                    upsert_project_register_rows(pid, [issue], pcfg.get("name", ""), email)
                    st.rerun()
                else:
                    st.error(result["message"])

    # ── Manual RFI entry form ─────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("## Create New RFI")
    st.markdown(
        '<div style="font-size:12px;color:#6b7280;margin-top:-8px;margin-bottom:16px;">'
        'Create an RFI from scratch without AI analysis</div>',
        unsafe_allow_html=True)

    st.session_state.setdefault(f"t5_new_reset_{pid}", 0)
    _reset_ctr = st.session_state.get(f"t5_new_reset_{pid}", 0)

    # RFI number auto-suggestion
    _reg_rows      = load_project_register(pid, email)
    _existing_nums = (
        [get_rfi_num(iss, 1) for iss in approved] +
        [int(r["rfi_number"]) for r in _reg_rows if r.get("rfi_number")]
    )
    _suggested_rfi_num = max(_existing_nums) + 1 if _existing_nums else 1

    # ── Card 1 — RFI Identification ──────────────────────────────────────────
    st.markdown('<div class="sec-lbl">RFI Identification</div>', unsafe_allow_html=True)
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

    # ── Card 2 — RFI Content ─────────────────────────────────────────────────
    st.markdown('<div class="sec-lbl" style="margin-top:16px;">RFI Content</div>',
                unsafe_allow_html=True)
    _subj_col, _subj_ai_col = st.columns([5, 1])
    with _subj_col:
        st.text_input("Subject *", key=f"t5_new_subject_{pid}")
    with _subj_ai_col:
        st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
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
        st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
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

    # Send to
    _gen_disabled = False
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
        _gen_disabled = True

    # ── Card 3 — Impact Assessment ───────────────────────────────────────────
    st.markdown('<div class="sec-lbl" style="margin-top:16px;">Impact Assessment</div>',
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

    # ── Card 4 — Attachments ─────────────────────────────────────────────────
    st.markdown('<div class="sec-lbl" style="margin-top:16px;">Attachments</div>',
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

    # ── Generate / Clear buttons ─────────────────────────────────────────────
    _nb1, _nb2 = st.columns([2, 1])
    with _nb1:
        _new_gen = st.button(
            "Generate RFI document",
            type="primary",
            disabled=_gen_disabled,
            key=f"t5_new_gen_{pid}",
            use_container_width=True,
        )
    with _nb2:
        _new_clr = st.button("Clear form", key=f"t5_new_clr_{pid}",
                             use_container_width=True)

    if _new_clr:
        _prev_reset = st.session_state.get(f"t5_new_reset_{pid}", 0)
        for _ck in list(st.session_state.keys()):
            if _ck.startswith("t5_new_") and _ck.endswith(f"_{pid}"):
                st.session_state.pop(_ck, None)
        st.session_state[f"t5_new_reset_{pid}"] = _prev_reset + 1
        st.rerun()

    if _new_gen:
        _subj = st.session_state.get(f"t5_new_subject_{pid}", "").strip()
        _qst  = st.session_state.get(f"t5_new_question_{pid}", "").strip()
        if not _subj or not _qst:
            st.error("Subject and Question are both required.")
        else:
            # Save uploaded attachments to snaps_dir
            _up_files = st.session_state.get(f"t5_new_uploads_{pid}_{_reset_ctr}") or []
            _num = int(st.session_state.get(f"t5_new_rfi_num_{pid}", _suggested_rfi_num))
            for _fi, _uf in enumerate(_up_files[:5], start=1):
                _fname = f"RFI_{_num:03d}_snap{_fi}.png"
                _fdata = _uf.read()
                _fpath = snaps_dir / _fname
                _fpath.parent.mkdir(parents=True, exist_ok=True)
                _fpath.write_bytes(_fdata)
                upload_project_snapshot(email, pid, _fname, _fdata)

            # Build issue dict
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

            # Resolve client with bounds check
            _ci = st.session_state.get(f"t5_new_client_idx_{pid}", 0)
            if not isinstance(_ci, int) or _ci < 0 or _ci >= len(clients):
                _ci = 0
            _new_sel_client = clients[_ci]

            # Load logo / signature assets
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
                "instructions_text":   "",
                "superintendent_text": "",
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
                increment_usage(email)
                upsert_project_register_rows(pid, [_new_issue], pcfg.get("name", ""), email)
                st.success("RFI document generated successfully.")
                st.rerun()
            else:
                st.error(result["message"])

    # ── Previous documents ───────────────────────────────────────────────────
    st.markdown("---")
    prev_docs = sorted(out_dir.glob("*.docx"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
    if prev_docs:
        with st.expander(f"📂  Previously generated documents ({len(prev_docs)})"):
            st.markdown(
                '<div style="display:grid;grid-template-columns:5fr 1fr;'
                'background:#fafafa;border-bottom:1px solid #f0f0f0;'
                'padding:4px 0;font-size:10.5px;color:#9ca3af;'
                'text-transform:uppercase;font-weight:600;">'
                '<span>Filename</span><span>Download</span></div>',
                unsafe_allow_html=True)
            for doc_path in prev_docs[:10]:
                dc1, dc2 = st.columns([5, 1])
                dc1.markdown(
                    f'<span style="color:#374151;font-size:13px;">{doc_path.name}</span>',
                    unsafe_allow_html=True)
                with dc2:
                    with open(doc_path, "rb") as fh:
                        st.download_button(
                            "↓ Download",
                            data=fh,
                            file_name=doc_path.name,
                            mime="application/vnd.openxmlformats-officedocument"
                                 ".wordprocessingml.document",
                            use_container_width=True,
                            key=f"dl_{doc_path.stem}",
                        )
