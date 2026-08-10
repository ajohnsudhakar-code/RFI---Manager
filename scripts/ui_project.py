"""
ui_project.py — Tab 2: Project Setup
"""
import streamlit as st
from pathlib import Path
from uuid import uuid4

from data_layer import (
    proj_dir,
    load_project_cfg,
    save_project_cfg,
    load_project_clients,
    save_project_clients,
    _new_project_id,
    _list_project_ids,
    upload_project_pdf,
    delete_project,
    _default_project_cfg,
)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _drawings_dir(pid: str, email: str = "") -> Path:
    d = proj_dir(pid, email) / "drawings"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _blank_client() -> dict:
    return {"id": uuid4().hex, "company": "", "attn": "", "email": "", "phone": "", "role": ""}


def _client_cid(client: dict, idx: int) -> str:
    return client.get("id") or f"pos{idx}"


def _client_initials(company: str) -> str:
    words = company.split()
    if len(words) >= 2:
        return (words[0][0] + words[1][0]).upper()
    if words:
        return words[0][:2].upper()
    return "—"


def _backfill_client_ids(clients: list) -> None:
    for c in clients:
        if not c.get("id"):
            c["id"] = uuid4().hex


def _client_form(prefix: str, defaults: dict | None = None) -> dict | None:
    """
    Renders a client input form and returns the filled dict on Save,
    or None if the form was cancelled / not yet submitted.
    """
    d = defaults or _blank_client()
    with st.form(key=f"{prefix}_client_form", clear_on_submit=True):
        company = st.text_input("Company Name *", value=d.get("company", ""))
        col1, col2 = st.columns(2)
        with col1:
            attn  = st.text_input("Contact Person", value=d.get("attn", ""))
            email = st.text_input("Email",          value=d.get("email", ""))
        with col2:
            role  = st.text_input("Role",  value=d.get("role", ""))
            phone = st.text_input("Phone", value=d.get("phone", ""))

        save_col, cancel_col, _ = st.columns([1, 1, 4])
        submitted = save_col.form_submit_button("💾 Save Recipient",  type="primary")
        cancelled = cancel_col.form_submit_button("✕ Cancel")

    if cancelled:
        return "cancel"
    if submitted:
        if not company.strip():
            st.error("Company Name is required.")
            return None
        return {
            "id":      d.get("id", ""),
            "company": company.strip(),
            "attn":    attn.strip(),
            "email":   email.strip(),
            "phone":   phone.strip(),
            "role":    role.strip(),
        }
    return None



# ─────────────────────────────────────────────────────────────────────────────
# Main render
# ─────────────────────────────────────────────────────────────────────────────

def render_tab_project(email: str):
    if st.session_state.pop("_project_deleted", False):
        st.success("✓ Project deleted successfully.")
        st.session_state["current_project_id"] = ""
        st.session_state["t2_loaded_pid"] = None
        for _rk in list(st.session_state.keys()):
            if (_rk.startswith("t2_proj_name_") or
                    _rk.startswith("t2_proj_address_") or
                    _rk.startswith("t2_proj_number_")):
                st.session_state.pop(_rk, None)
        st.session_state["_pid_is_new_unsaved"] = True
        st.rerun()
    if st.session_state.get("_project_delete_err"):
        st.error(st.session_state.pop("_project_delete_err"))

    pid = st.session_state.get("current_project_id", "")
    if not pid:
        pid = _new_project_id(email)
        st.session_state["current_project_id"] = pid
        st.session_state["t2_loaded_pid"] = None
        for _rk in list(st.session_state.keys()):
            if (_rk.startswith("t2_proj_name_") or
                    _rk.startswith("t2_proj_address_") or
                    _rk.startswith("t2_proj_number_")):
                st.session_state.pop(_rk, None)
        st.session_state["_pid_is_new_unsaved"] = True
        st.rerun()

    # ── Section 1: Project Details ──────────────────────────────────────────
    _is_new_pid = st.session_state.get("_pid_is_new_unsaved", False)
    pcfg = _default_project_cfg() if _is_new_pid else load_project_cfg(pid, email)

    if st.session_state.get("t2_loaded_pid") != pid:
        _is_new = _is_new_pid
        st.session_state[f"t2_proj_name_{pid}"]    = "" if _is_new else pcfg.get("name",           "")
        st.session_state[f"t2_proj_address_{pid}"] = "" if _is_new else pcfg.get("address",        "")
        st.session_state[f"t2_proj_number_{pid}"]  = "" if _is_new else pcfg.get("project_number", "")
        st.session_state[f"t2_edit_mode_{pid}"]    = _is_new   # True for new, False for existing
        if _is_new:
            st.session_state.pop(f"t2_uploaded_pdf_{pid}", None)
            st.session_state.pop(f"t2_pdf_cloud_ok_{pid}", None)
            st.session_state["t2_uploader_gen"] = st.session_state.get("t2_uploader_gen", 0) + 1
        st.session_state["t2_loaded_pid"]   = pid

    _t2_edit = st.session_state.get(f"t2_edit_mode_{pid}", _is_new_pid)

    def _lbl(text):
        st.markdown(
            f'<div style="font-size:11px;color:#6b7280;margin-bottom:2px;">{text}</div>',
            unsafe_allow_html=True)

    # Scope width/centering to this tab only — .st-key-pr_scope matches nothing
    # outside this container, so other tabs are unaffected. The container itself
    # is a flex item (Streamlit nests every block in its parent's flex column),
    # so align-self (not margin:auto) is what actually centers it.
    st.markdown(
        '<style>'
        '.st-key-pr_scope { width:600px; max-width:100%; align-self:center !important; margin:0 auto; }'
        '.pr-hdr { color:#111111; font-size:14px; font-weight:500; margin:4px 0 12px; '
        'display:flex; align-items:center; gap:8px; }'
        '.pr-hdr::after { content:""; flex:1; height:1px; background:#d1d5db; }'
        '.st-key-t2_hdr_edit_btn button, .st-key-t2_del_proj_btn button { '
        'background:transparent !important; border:none !important; '
        'padding:2px 8px !important; font-size:12px !important; color:#6b7280 !important; '
        'box-shadow:none !important; white-space:nowrap !important; flex-shrink:0 !important; }'
        '.st-key-t2_hdr_edit_btn button:hover { color:#1d4ed8 !important; background:transparent !important; '
        'box-shadow:none !important; transform:none !important; }'
        '.st-key-t2_del_proj_btn button:hover { color:#dc2626 !important; background:transparent !important; '
        'box-shadow:none !important; transform:none !important; }'
        '.st-key-pr_scope [data-testid="stFileUploaderDropzoneInstructions"] { display:none !important; }'
        '.st-key-pr_scope [data-testid="stFileUploaderDropzone"] { '
        'padding:6px !important; min-height:0 !important; }'
        '.st-key-t2_add_client_btn button { '
        'padding:4px 10px !important; font-size:12px !important; }'
        '.st-key-pr_scope [data-testid="column"]:has(.st-key-t2_add_client_btn) { '
        'display:flex !important; justify-content:flex-end !important; align-items:center !important; }'
        '[class*="st-key-t2_rcpt_edit_"] button, [class*="st-key-t2_rcpt_del_"] button { '
        'padding:4px 10px !important; }'
        '</style>',
        unsafe_allow_html=True)

    with st.container(key="pr_scope"):
        if st.session_state.pop("_project_saved_ok", False):
            st.success("Project details saved successfully.")

        # ── Project header ───────────────────────────────────────────────────
        _hdr_l, _hdr_r = st.columns([4, 1])
        with _hdr_l:
            st.markdown(f"### {pcfg.get('name', '') or '—'}")
        with _hdr_r:
            if not _t2_edit:
                if st.button("Edit", key="t2_hdr_edit_btn", type="tertiary"):
                    st.session_state[f"t2_proj_name_{pid}"]    = pcfg.get("name", "")
                    st.session_state[f"t2_proj_address_{pid}"] = pcfg.get("address", "")
                    st.session_state[f"t2_proj_number_{pid}"]  = pcfg.get("project_number", "")
                    st.session_state[f"t2_edit_mode_{pid}"]    = True
                    st.rerun()

        if _t2_edit:
            _lbl("Project name")
            proj_name   = st.text_input("Project Name",   key=f"t2_proj_name_{pid}", label_visibility="collapsed")
            _lbl("Site address")
            site_addr   = st.text_input("Site Address",   key=f"t2_proj_address_{pid}", label_visibility="collapsed")
            _lbl("Job number")
            proj_number = st.text_input("Job Number",     key=f"t2_proj_number_{pid}", label_visibility="collapsed")
        else:
            _adr = pcfg.get("address", "")
            _num = pcfg.get("project_number", "")
            _meta_html = ""
            if _adr:
                _meta_html += f'<div style="color:#6b7280;font-size:13px;margin-top:2px;">{_adr}</div>'
            if _num:
                _meta_html += f'<div style="color:#6b7280;font-size:13px;margin-top:2px;">Job no. {_num}</div>'
            if _meta_html:
                st.markdown(_meta_html, unsafe_allow_html=True)
            proj_name = site_addr = proj_number = ""

        # ── Drawings ──────────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown('<div class="pr-hdr">Drawings</div>', unsafe_allow_html=True)
        st.markdown(
            '<div style="color:#6b7280;font-size:12px;margin-top:-6px;margin-bottom:10px;">'
            'Analyse and Crop both read from the active set.</div>',
            unsafe_allow_html=True)

        drawings = _drawings_dir(pid, email)
        _active_ph = st.empty()

        _row_sel, _row_up = st.columns([3, 1])

        _uploader_gen = st.session_state.get("t2_uploader_gen", 0)
        with _row_up:
            up_pdf = st.file_uploader("Upload Drawing PDF", type=["pdf"],
                                       key=f"t2_pdf_upload_{pid}_{_uploader_gen}",
                                       label_visibility="collapsed")
        if up_pdf:
            size_mb = up_pdf.size / (1024 * 1024)
            with st.spinner(f"Saving PDF ({size_mb:.1f} MB)…"):
                _pdf_bytes = up_pdf.read()
                dest = drawings / up_pdf.name
                dest.write_bytes(_pdf_bytes)
                st.session_state[f"t2_uploaded_pdf_{pid}"] = up_pdf.name
                _cloud_ok = upload_project_pdf(email, pid, up_pdf.name, _pdf_bytes)
                st.session_state[f"t2_pdf_cloud_ok_{pid}"] = _cloud_ok
            if not _cloud_ok:
                st.error(
                    "⚠ PDF not saved to cloud storage. On Streamlit Cloud the file will be "
                    "lost after the next restart. Please re-upload the PDF before saving."
                )
            else:
                try:
                    import fitz as _fitz
                    doc = _fitz.open(str(dest))
                    pc  = len(doc)
                    doc.close()
                    st.success(f"✓ {pc} page{'s' if pc != 1 else ''} uploaded — click Save to confirm.")
                except Exception:
                    st.success("✓ Uploaded — click Save to confirm.")

        pdf_files = sorted(drawings.glob("*.pdf"))
        _is_new_proj = st.session_state.get("_pid_is_new_unsaved", False)
        _cur_upload = (up_pdf.name if up_pdf else None) or st.session_state.get(f"t2_uploaded_pdf_{pid}", "")
        if _is_new_proj:
            pdf_names = [_cur_upload] if _cur_upload and (drawings / _cur_upload).exists() else []
        else:
            _saved = Path(pcfg.get("pdf", "")).name
            pdf_names = [p.name for p in pdf_files if p.name in {_saved, _cur_upload} and p.name]
        if pdf_names:
            cur_name = Path(pcfg.get("pdf", "")).name
            pdf_idx  = pdf_names.index(cur_name) if cur_name in pdf_names else 0
            with _row_sel:
                sel_pdf  = st.selectbox("Active PDF", pdf_names, index=pdf_idx,
                                        key=f"t2_sel_pdf_{pid}", label_visibility="collapsed")
            _active_ph.markdown(
                f'<div style="background:#f8fafc;border:1px solid #e5e7eb;border-radius:8px;'
                f'padding:12px 16px;margin-bottom:10px;">'
                f'<div style="color:#111111;font-weight:600;font-size:14px;">📄 {sel_pdf}</div>'
                f'<div style="color:#15803d;font-size:11px;margin-top:3px;font-weight:500;">● Active set</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            _active_ph.empty()
            with _row_sel:
                st.markdown(
                    '<div class="info-box warn">No PDFs yet — upload one above.</div>',
                    unsafe_allow_html=True,
                )
            sel_pdf = None

        if _t2_edit:
            st.markdown("---")
            if st.button("💾  Save Project Details", type="primary", use_container_width=True, key="t2_save_proj"):
                _pdf_cloud_failed = st.session_state.get(f"t2_pdf_cloud_ok_{pid}") is False
                if not proj_name.strip():
                    st.error("❌ Project Name is required.")
                elif _pdf_cloud_failed:
                    st.error("❌ The PDF was not saved to cloud storage. Please re-upload the PDF before saving.")
                else:
                    try:
                        pcfg["name"]           = proj_name.strip()
                        pcfg["address"]        = site_addr.strip()
                        pcfg["project_number"] = proj_number.strip()
                        if sel_pdf:
                            pcfg["pdf"] = str(Path("drawings") / sel_pdf)
                        else:
                            pcfg["pdf"] = ""
                        if _is_new_pid:
                            slug_pid = _new_project_id(email, proj_name.strip())
                            _t2_keys_to_migrate = [
                                f"t2_proj_name_{pid}",
                                f"t2_proj_address_{pid}",
                                f"t2_proj_number_{pid}",
                                f"t2_edit_mode_{pid}",
                                f"t2_uploaded_pdf_{pid}",
                                f"t2_pdf_cloud_ok_{pid}",
                                f"t2_sel_pdf_{pid}",
                            ]
                            for _sk in _t2_keys_to_migrate:
                                if _sk in st.session_state:
                                    _new_sk = _sk.replace(pid, slug_pid)
                                    st.session_state[_new_sk] = st.session_state.pop(_sk)
                            _up_fname = st.session_state.get(f"t2_uploaded_pdf_{slug_pid}")
                            if _up_fname:
                                _pdf_local = _drawings_dir(pid, email) / _up_fname
                                if _pdf_local.exists():
                                    _pdf_bytes = _pdf_local.read_bytes()
                                    _reup_ok = upload_project_pdf(email, slug_pid, _up_fname, _pdf_bytes)
                                    if _reup_ok:
                                        st.session_state[f"t2_pdf_cloud_ok_{slug_pid}"] = True
                                    else:
                                        st.error("❌ PDF could not be re-uploaded under the new project ID. Please re-upload and try again.")
                                        st.stop()
                            st.session_state["current_project_id"] = slug_pid
                            st.session_state["t2_loaded_pid"] = None
                            pid = slug_pid
                        save_project_cfg(pid, pcfg, email)
                        st.session_state["current_project_id"] = pid
                        st.session_state["_project_saved_ok"]  = True
                        st.session_state["_project_do_rerun"]  = True
                        st.session_state[f"t2_edit_mode_{pid}"] = False
                        st.session_state.pop("_pid_is_new_unsaved", None)
                        st.session_state.pop(f"t2_uploaded_pdf_{pid}", None)
                        st.session_state.pop(f"t2_pdf_cloud_ok_{pid}", None)
                        st.session_state.pop("_sb_labels", None)
                        st.session_state.pop("_sb_label_pids", None)
                    except Exception as _save_err:
                        st.error(f"❌ Save failed: {type(_save_err).__name__}: {_save_err}")
                        st.stop()
                    if st.session_state.pop("_project_do_rerun", False):
                        st.rerun()

        # ── Section 2: Recipients ────────────────────────────────────────────────
        st.markdown("---")
        if _is_new_pid:
            st.markdown(
                '<div class="info-box warn">Save your project details above before adding recipients.</div>',
                unsafe_allow_html=True,
            )
        else:
            clients = load_project_clients(pid, email)
            form_mode = st.session_state.get("t2_client_form_mode")  # None | ("new",) | ("edit", cid)
            _ch_l, _ch_r = st.columns([4, 1])
            with _ch_l:
                st.markdown('<div class="pr-hdr">Recipients</div>', unsafe_allow_html=True)
            with _ch_r:
                if not form_mode or form_mode[0] == "edit":
                    if st.button("+ Add", key="t2_add_client_btn", type="secondary"):
                        st.session_state["t2_client_form_mode"] = ("new",)
                        st.rerun()
            st.markdown(
                '<div style="color:#6b7280;font-size:12px;margin-top:-6px;margin-bottom:10px;">'
                'Who your RFIs are addressed to.</div>',
                unsafe_allow_html=True)
            if st.session_state.get("_client_saved_ok"):
                st.success(st.session_state.pop("_client_saved_ok"))
            if st.session_state.get("_client_deleted_ok"):
                st.success(st.session_state.pop("_client_deleted_ok"))
            if st.session_state.get("_client_delete_err"):
                st.error(st.session_state.pop("_client_delete_err"))

            # ── Recipient table ───────────────────────────────────────────────────
            if not clients and not form_mode:
                st.markdown(
                    '<div class="info-box warn" style="text-align:center;padding:20px;">'
                    '👥 &nbsp;No recipients yet — add your first recipient below.'
                    '</div>',
                    unsafe_allow_html=True,
                )
            else:
                for i, client in enumerate(clients):
                    cid = _client_cid(client, i)
                    if form_mode and form_mode[0] == "edit" and form_mode[1] == cid:
                        st.markdown(f"**Edit recipient: {client.get('company','')}**")
                        result = _client_form(prefix=f"edit_{cid}", defaults=client)
                        if result == "cancel":
                            st.session_state.pop("t2_client_form_mode", None)
                            st.rerun()
                        elif result is not None:
                            clients[i] = result
                            try:
                                _backfill_client_ids(clients)
                                save_project_clients(pid, clients, email)
                                st.session_state.pop("t2_client_form_mode", None)
                                st.session_state["_client_saved_ok"] = f"✓ Updated **{result['company']}**."
                            except Exception as _upd_err:
                                st.error(f"❌ Could not update recipient: {_upd_err}")
                                st.stop()
                            st.rerun()
                    else:
                        _co = client.get("company", "—")
                        _at = client.get("attn", "")
                        _ro = client.get("role", "")
                        _em = client.get("email", "")
                        _ph = client.get("phone", "")
                        _initials = _client_initials(_co)
                        _line1 = _co
                        if _ro:
                            _line1 += f' <span style="color:#9ca3af;font-weight:400;">— {_ro}</span>'
                        _line2_parts = [p for p in (_at, _em, _ph) if p]
                        _line2 = " · ".join(_line2_parts) or "—"
                        _rav, _rd, _re, _rdl = st.columns([1, 8, 1.2, 1.2])
                        with _rav:
                            st.markdown(
                                f'<div style="width:32px;height:32px;border-radius:50%;'
                                f'background:#eef2ff;color:#3b5bdb;font-size:12px;font-weight:700;'
                                f'display:flex;align-items:center;justify-content:center;">'
                                f'{_initials}</div>',
                                unsafe_allow_html=True)
                        with _rd:
                            st.markdown(
                                f'<div style="min-width:0;padding:2px 0;">'
                                f'<div style="font-size:13px;color:#111;font-weight:500;'
                                f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{_line1}</div>'
                                f'<div style="font-size:12px;color:#6b7280;margin-top:1px;'
                                f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{_line2}</div>'
                                f'</div>',
                                unsafe_allow_html=True)
                        with _re:
                            if st.button("✎", key=f"t2_rcpt_edit_{cid}_{pid}"):
                                st.session_state["t2_client_form_mode"] = ("edit", cid)
                                st.rerun()
                        with _rdl:
                            if st.button("✗", key=f"t2_rcpt_del_{cid}_{pid}"):
                                st.session_state["t2_confirm_del_client"] = cid
                                st.rerun()
                        st.markdown(
                            '<div style="border-bottom:1px solid #f7f7f7;margin:4px 0 8px;"></div>',
                            unsafe_allow_html=True)

            _pending_del_cid = st.session_state.get("t2_confirm_del_client")
            if _pending_del_cid is not None:
                _pending_del_idx = next(
                    (i for i, c in enumerate(clients) if _client_cid(c, i) == _pending_del_cid), None)
                if _pending_del_idx is not None:
                    _del_company = clients[_pending_del_idx].get("company", "this recipient")
                    st.warning(f"Delete **{_del_company}**? This cannot be undone.")
                    _dcc1, _dcc2, _ = st.columns([1, 1, 4])
                    with _dcc1:
                        if st.button("✓ Yes, Delete", key="t2_del_client_confirm", type="primary",
                                     use_container_width=True):
                            _clients_fresh = load_project_clients(pid, email)
                            _fresh_idx = next(
                                (i for i, c in enumerate(_clients_fresh)
                                 if _client_cid(c, i) == _pending_del_cid), None)
                            if _fresh_idx is not None:
                                _clients_fresh.pop(_fresh_idx)
                            try:
                                _backfill_client_ids(_clients_fresh)
                                save_project_clients(pid, _clients_fresh, email)
                                st.session_state.pop("t2_client_form_mode", None)
                                st.session_state["_client_deleted_ok"] = f"Deleted **{_del_company}**."
                            except Exception as _del_err:
                                st.session_state["_client_delete_err"] = f"❌ Could not delete recipient: {_del_err}"
                            st.session_state.pop("t2_confirm_del_client", None)
                            st.rerun()
                    with _dcc2:
                        if st.button("✕ Cancel", key="t2_del_client_cancel", use_container_width=True):
                            st.session_state.pop("t2_confirm_del_client", None)
                            st.rerun()

            if form_mode and form_mode[0] == "new":
                st.markdown("**New Recipient**")
                result = _client_form(prefix="new")
                if result == "cancel":
                    st.session_state.pop("t2_client_form_mode", None)
                    st.rerun()
                elif result is not None:
                    clients.append(result)
                    clients.sort(key=lambda c: c.get("company", "").lower())
                    try:
                        _backfill_client_ids(clients)
                        save_project_clients(pid, clients, email)
                        st.session_state.pop("t2_client_form_mode", None)
                        st.session_state["_client_saved_ok"] = f"✓ Added **{result['company']}**."
                    except Exception as _add_err:
                        st.error(f"❌ Could not save recipient: {_add_err}")
                        st.stop()
                    st.rerun()

        # ── Next-step banner ─────────────────────────────────────────────────
        if not _is_new_pid and not _t2_edit:
            _pdf_ready = bool(pcfg.get("pdf"))
            _status_line = "Project details saved" + (
                " · Drawing PDF active" if _pdf_ready else " · No drawing PDF uploaded yet")
            st.markdown(
                f'<div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;'
                f'padding:14px 20px;margin-top:16px;">'
                f'<div style="color:#1e3a8a;font-size:14px;font-weight:600;">Ready to scan</div>'
                f'<div style="color:#6b7280;font-size:12px;margin-top:2px;">{_status_line}</div>'
                f'</div>',
                unsafe_allow_html=True)

        # ── Danger Zone ──────────────────────────────────────────────────────────
        if pid in _list_project_ids(email):
            st.markdown("---")
            _confirm_del = st.session_state.get("t2_confirm_delete") == pid
            if not _confirm_del:
                _dz_l, _dz_r = st.columns([3, 2])
                with _dz_l:
                    st.markdown(
                        '<div style="margin-top:6px;color:#9ca3af;font-size:11px;">'
                        'Deleting this project permanently removes it and all its data.</div>',
                        unsafe_allow_html=True)
                with _dz_r:
                    if st.button("Delete project", key="t2_del_proj_btn", type="tertiary",
                                 use_container_width=True):
                        st.session_state["t2_confirm_delete"] = pid
                        st.rerun()
            else:
                st.warning("Delete this project? This cannot be undone.")
                _dc1, _dc2, _ = st.columns([2, 1, 3])
                with _dc1:
                    if st.button("✓ Yes, Delete", key="t2_del_proj_confirm", type="primary",
                                 use_container_width=True):
                        _del_ok = delete_project(email, pid)
                        st.session_state.pop("t2_confirm_delete", None)
                        if _del_ok:
                            _remaining = _list_project_ids(email)
                            st.session_state["current_project_id"] = _remaining[0] if _remaining else ""
                            st.session_state["t2_loaded_pid"] = None
                            for _k in ["analysis_results", "t2_client_form_mode",
                                       "_pid_is_new_unsaved"]:
                                st.session_state.pop(_k, None)
                            for _rk in list(st.session_state.keys()):
                                if (_rk.startswith("t2_proj_name_") or
                                        _rk.startswith("t2_proj_address_") or
                                        _rk.startswith("t2_proj_number_")):
                                    st.session_state.pop(_rk, None)
                            st.session_state.pop("_sb_labels", None)
                            st.session_state.pop("_sb_label_pids", None)
                            st.session_state["_project_deleted"] = True
                        else:
                            st.session_state["_project_delete_err"] = "❌ Could not delete project. Please try again."
                        st.rerun()
                with _dc2:
                    if st.button("✕ Cancel", key="t2_del_proj_cancel", use_container_width=True):
                        st.session_state.pop("t2_confirm_delete", None)
                        st.rerun()
