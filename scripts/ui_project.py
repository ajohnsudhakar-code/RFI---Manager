"""
ui_project.py — Tab 2: Project Setup
"""
import streamlit as st
from pathlib import Path

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
    return {"company": "", "attn": "", "email": "", "phone": "", "role": ""}


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
    st.markdown("## Project Details")
    if st.session_state.pop("_project_saved_ok", False):
        st.success("Project details saved successfully.")
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

    col_left, col_right = st.columns(2, gap="large")

    with col_left:
        _pi_l, _pi_r = st.columns([4, 1])
        with _pi_l:
            st.markdown('<div class="sec-lbl">Project Information</div>', unsafe_allow_html=True)
        with _pi_r:
            if not _t2_edit:
                if st.button("✏ Edit Details", key=f"t2_projinfo_edit_{pid}", use_container_width=True):
                    st.session_state[f"t2_proj_name_{pid}"]    = pcfg.get("name", "")
                    st.session_state[f"t2_proj_address_{pid}"] = pcfg.get("address", "")
                    st.session_state[f"t2_proj_number_{pid}"]  = pcfg.get("project_number", "")
                    st.session_state[f"t2_edit_mode_{pid}"]    = True
                    st.rerun()
        if _t2_edit:
            proj_name   = st.text_input("Project Name",   key=f"t2_proj_name_{pid}")
            site_addr   = st.text_input("Site Address",   key=f"t2_proj_address_{pid}")
            proj_number = st.text_input("Project Number", key=f"t2_proj_number_{pid}")
        else:
            _nm  = pcfg.get("name", "")           or "—"
            _adr = pcfg.get("address", "")         or "—"
            _num = pcfg.get("project_number", "")
            _num_display = f"#{_num}" if _num else "—"
            st.markdown(
                f'<div style="margin:8px 0 4px 0;">'
                f'<div style="font-size:10.5px;font-weight:500;text-transform:uppercase;'
                f'letter-spacing:0.5px;color:#9ca3af;margin-bottom:4px;">Project Name</div>'
                f'<div style="font-size:13.5px;color:#111111;padding:6px 0;'
                f'border-bottom:1px solid #f0f0f0;margin-bottom:12px;">{_nm}</div>'
                f'<div style="font-size:10.5px;font-weight:500;text-transform:uppercase;'
                f'letter-spacing:0.5px;color:#9ca3af;margin-bottom:4px;">Site Address</div>'
                f'<div style="font-size:13.5px;color:#111111;padding:6px 0;'
                f'border-bottom:1px solid #f0f0f0;margin-bottom:12px;">{_adr}</div>'
                f'<div style="font-size:10.5px;font-weight:500;text-transform:uppercase;'
                f'letter-spacing:0.5px;color:#9ca3af;margin-bottom:4px;">Project Number</div>'
                f'<div style="font-size:13.5px;color:#111111;padding:6px 0;'
                f'border-bottom:1px solid #f0f0f0;margin-bottom:12px;">{_num_display}</div>'
                f'</div>',
                unsafe_allow_html=True)
            proj_name = site_addr = proj_number = ""

    with col_right:
        st.markdown('<div class="sec-lbl">Drawing PDF</div>', unsafe_allow_html=True)
        drawings = _drawings_dir(pid, email)

        _uploader_gen = st.session_state.get("t2_uploader_gen", 0)
        up_pdf = st.file_uploader("Upload Drawing PDF", type=["pdf"], key=f"t2_pdf_upload_{pid}_{_uploader_gen}")
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
                    st.success(f"✓ Uploaded **{up_pdf.name}** ({pc} pages) — click Save to confirm.")
                except Exception:
                    st.success(f"✓ Uploaded **{up_pdf.name}** — click Save to confirm.")

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
            sel_pdf  = st.selectbox("Active PDF", pdf_names, index=pdf_idx,
                                    key=f"t2_sel_pdf_{pid}")
            st.markdown(
                f'<div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;'
                f'padding:10px 14px;margin-top:8px;">'
                f'<div style="color:#15803d;font-weight:500;font-size:13px;">📄 {sel_pdf}</div>'
                f'<div style="color:#9ca3af;font-size:11px;margin-top:3px;">Active drawing set</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="info-box warn">No PDFs yet — upload one above.</div>',
                unsafe_allow_html=True,
            )
            sel_pdf = None

    st.markdown("---")
    if _t2_edit:
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
                    save_project_cfg(pid, pcfg, email)
                    st.session_state["current_project_id"] = pid
                    st.session_state["_project_saved_ok"]  = True
                    st.session_state["_project_do_rerun"]  = True
                    st.session_state[f"t2_edit_mode_{pid}"] = False
                    st.session_state.pop("_pid_is_new_unsaved", None)
                    st.session_state.pop(f"t2_uploaded_pdf_{pid}", None)
                    st.session_state.pop(f"t2_pdf_cloud_ok_{pid}", None)
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
        form_mode = st.session_state.get("t2_client_form_mode")  # None | ("new",) | ("edit", idx)
        _ch_l, _ch_r = st.columns([5, 1])
        with _ch_l:
            st.markdown("## Recipients")
        with _ch_r:
            if not form_mode or form_mode[0] == "edit":
                if st.button("＋ Add Recipient", key="t2_add_client_btn", type="primary"):
                    st.session_state["t2_client_form_mode"] = ("new",)
                    st.rerun()
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
            if clients:
                st.markdown(
                    '<div style="display:grid;grid-template-columns:2fr 1.5fr 1fr 2fr 1.2fr 0.8fr;'
                    'background:#fafafa;border-bottom:1px solid #f0f0f0;padding:8px 20px;">'
                    '<span style="font-size:10.5px;color:#9ca3af;font-weight:700;text-transform:uppercase;">Company</span>'
                    '<span style="font-size:10.5px;color:#9ca3af;font-weight:700;text-transform:uppercase;">Contact</span>'
                    '<span style="font-size:10.5px;color:#9ca3af;font-weight:700;text-transform:uppercase;">Role</span>'
                    '<span style="font-size:10.5px;color:#9ca3af;font-weight:700;text-transform:uppercase;">Email</span>'
                    '<span style="font-size:10.5px;color:#9ca3af;font-weight:700;text-transform:uppercase;">Phone</span>'
                    '<span style="font-size:10.5px;color:#9ca3af;font-weight:700;text-transform:uppercase;">Actions</span>'
                    '</div>',
                    unsafe_allow_html=True)
            for i, client in enumerate(clients):
                if form_mode and form_mode[0] == "edit" and form_mode[1] == i:
                    st.markdown(f"**Edit recipient: {client.get('company','')}**")
                    result = _client_form(prefix=f"edit_{i}", defaults=client)
                    if result == "cancel":
                        st.session_state.pop("t2_client_form_mode", None)
                        st.rerun()
                    elif result is not None:
                        clients[i] = result
                        try:
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
                    _role_html = (
                        f'<span style="background:#f0f4ff;color:#3b5bdb;font-size:11px;'
                        f'padding:2px 8px;border-radius:10px;">{_ro}</span>' if _ro else "—")
                    _em_html = f'<span style="color:#1d4ed8;">{_em}</span>' if _em else "—"
                    _rd, _re, _rdl = st.columns([10, 1, 1])
                    with _rd:
                        st.markdown(
                            f'<div style="display:grid;grid-template-columns:2fr 1.5fr 1fr 2fr 1.2fr;'
                            f'padding:10px 20px;border-bottom:1px solid #f7f7f7;align-items:center;">'
                            f'<span style="font-size:13px;color:#111;font-weight:500;">{_co}</span>'
                            f'<span style="font-size:13px;color:#374151;">{_at or "—"}</span>'
                            f'{_role_html}'
                            f'{_em_html}'
                            f'<span style="font-size:13px;color:#374151;">{_ph or "—"}</span>'
                            f'</div>',
                            unsafe_allow_html=True)
                    with _re:
                        if st.button("Edit", key=f"t2_edit_{i}_{pid}", use_container_width=True):
                            st.session_state["t2_client_form_mode"] = ("edit", i)
                            st.rerun()
                    with _rdl:
                        if st.button("Del", key=f"t2_del_{i}_{pid}", use_container_width=True):
                            st.session_state["t2_confirm_del_client"] = i
                            st.rerun()

        _pending_del_idx = st.session_state.get("t2_confirm_del_client")
        if _pending_del_idx is not None and 0 <= _pending_del_idx < len(clients):
            _del_company = clients[_pending_del_idx].get("company", "this recipient")
            st.warning(f"Delete **{_del_company}**? This cannot be undone.")
            _dcc1, _dcc2, _ = st.columns([1, 1, 4])
            with _dcc1:
                if st.button("✓ Yes, Delete", key="t2_del_client_confirm", type="primary",
                             use_container_width=True):
                    _clients_fresh = load_project_clients(pid, email)
                    _clients_fresh.pop(_pending_del_idx)
                    try:
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
                    save_project_clients(pid, clients, email)
                    st.session_state.pop("t2_client_form_mode", None)
                    st.session_state["_client_saved_ok"] = f"✓ Added **{result['company']}**."
                except Exception as _add_err:
                    st.error(f"❌ Could not save recipient: {_add_err}")
                    st.stop()
                st.rerun()

    # ── Danger Zone ──────────────────────────────────────────────────────────
    if pid in _list_project_ids(email):
        st.markdown("---")
        _confirm_del = st.session_state.get("t2_confirm_delete") == pid
        if not _confirm_del:
            _dz_l, _dz_r = st.columns([5, 1])
            with _dz_l:
                st.markdown(
                    '<div style="background:#fff5f5;border:1px solid #fee2e2;border-radius:10px;'
                    'padding:14px 20px;">'
                    '<div style="color:#dc2626;font-size:11px;font-weight:700;'
                    'text-transform:uppercase;letter-spacing:0.08em;">Danger zone</div>'
                    '<div style="color:#9ca3af;font-size:11px;margin-top:4px;">'
                    'Permanently deletes this project and all its data</div>'
                    '</div>',
                    unsafe_allow_html=True)
            with _dz_r:
                st.write("")
                if st.button("🗑 Delete Project", key="t2_del_proj_btn", use_container_width=True):
                    st.session_state["t2_confirm_delete"] = pid
                    st.rerun()
        else:
            st.warning("Delete this project? This cannot be undone.")
            _dc1, _dc2, _ = st.columns([1, 1, 4])
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
    if not _is_new_pid and not _t2_edit:
        st.markdown(
            '<div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;'
            'padding:14px 20px;display:flex;justify-content:space-between;'
            'align-items:center;margin-top:16px;">'
            '<span style="color:#1e3a8a;font-size:14px;font-weight:500;">'
            '✓ Project setup complete</span>'
            '<span style="color:#6b7280;font-size:12px;">'
            'Next: scan your drawings · ↑ Click Analyse Drawings above</span>'
            '</div>',
            unsafe_allow_html=True)
