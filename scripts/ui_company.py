"""
ui_company.py — Tab 1: Company Setup
"""
import io
import base64
import streamlit as st

from data_layer import (
    load_cfg, save_cfg,
    get_asset_bytes, upload_asset,
)


def render_tab_company(email: str):
    st.markdown("## Company Setup")

    cfg    = load_cfg(email)
    co     = cfg.get("company", {})
    orig_c = cfg.get("originator", {})

    _company_name = co.get("company_name", "") or co.get("name", "")
    _orig_name    = orig_c.get("name", "")
    _co_filled    = _company_name.strip() != ""
    _orig_filled  = _orig_name.strip() != ""
    _all_filled   = _co_filled and _orig_filled

    # Determine edit mode default: view when tab done and data present, edit otherwise
    _tab_done = st.session_state.get("tab_company_done", False)
    st.session_state.setdefault("co_edit_mode", not (_tab_done and _all_filled))
    _edit_mode = st.session_state["co_edit_mode"]

    # ── Status banner ─────────────────────────────────────────────────────────
    if not _co_filled and not _orig_filled:
        st.markdown(
            '<div style="border-left:3px solid #1d4ed8;background:#eff6ff;'
            'border-radius:6px;padding:14px 18px;margin-bottom:18px;color:#1e3a8a;font-size:14px;">'
            'Welcome — fill in your company details to get started.</div>',
            unsafe_allow_html=True)
    elif _all_filled and not _edit_mode:
        st.markdown(
            f'<div style="border-left:3px solid #059669;background:#f0fdf4;'
            f'border-radius:6px;padding:14px 18px;margin-bottom:18px;color:#166534;font-size:14px;">'
            f'✓ &nbsp;Company setup complete — <strong>{_company_name}</strong></div>',
            unsafe_allow_html=True)
    else:
        st.markdown(
            '<div style="border-left:3px solid #d97706;background:#fffbeb;'
            'border-radius:6px;padding:14px 18px;margin-bottom:18px;color:#92400e;font-size:14px;">'
            'Almost done — complete your company details below.</div>',
            unsafe_allow_html=True)

    # View mode: always sync from freshly-loaded cfg; edit mode: preserve in-progress edits
    if not _edit_mode:
        st.session_state["co_name"]     = co.get("name", "") or orig_c.get("company", "")
        st.session_state["co_address"]  = co.get("address", "")
        st.session_state["co_country"]  = co.get("country", "")
        st.session_state["co_postcode"] = co.get("postcode", "")
        st.session_state["co_website"]  = co.get("website", "")
        st.session_state["orig_name"]   = orig_c.get("name", "")
        st.session_state["orig_title"]  = orig_c.get("title", "")
        st.session_state["orig_email"]  = orig_c.get("email", "")
        st.session_state["orig_phone"]  = orig_c.get("phone", "")
    else:
        st.session_state.setdefault("co_name",    co.get("name", "") or orig_c.get("company", ""))
        st.session_state.setdefault("co_address", co.get("address", ""))
        st.session_state.setdefault("co_country", co.get("country", ""))
        st.session_state.setdefault("co_postcode", co.get("postcode", ""))
        st.session_state.setdefault("co_website", co.get("website", ""))
        st.session_state.setdefault("orig_name",  orig_c.get("name", ""))
        st.session_state.setdefault("orig_title", orig_c.get("title", ""))
        st.session_state.setdefault("orig_email", orig_c.get("email", ""))
        st.session_state.setdefault("orig_phone", orig_c.get("phone", ""))

    col_form, col_assets = st.columns([3, 2], gap="large")

    with col_form:
        # Header row: section label left, Edit button right
        _hdr_l, _hdr_r = st.columns([4, 1])
        with _hdr_l:
            st.markdown('<div class="sec-lbl">Company Information</div>', unsafe_allow_html=True)
        with _hdr_r:
            if not _edit_mode:
                if st.button("✏ Edit Details", key="co_edit_btn", use_container_width=True):
                    st.session_state["co_edit_mode"] = True
                    st.session_state["co_name"]     = co.get("name", "") or co.get("company_name", "")
                    st.session_state["co_address"]  = co.get("address", "")
                    st.session_state["co_country"]  = co.get("country", "")
                    st.session_state["co_postcode"] = co.get("postcode", "")
                    st.session_state["co_website"]  = co.get("website", "")
                    st.session_state["orig_name"]   = orig_c.get("name", "")
                    st.session_state["orig_title"]  = orig_c.get("title", "")
                    st.session_state["orig_email"]  = orig_c.get("email", "")
                    st.session_state["orig_phone"]  = orig_c.get("phone", "")
                    st.rerun()

        if _edit_mode:
            co_name    = st.text_input("Company Name", key="co_name")
            co_address = st.text_input("Address",      key="co_address")
            f1, f2 = st.columns(2)
            with f1:
                co_country  = st.text_input("Country",  key="co_country")
            with f2:
                co_postcode = st.text_input("Postcode", key="co_postcode")
            co_website = st.text_input("Website",       key="co_website")
        else:
            def _ro(label, value):
                st.markdown(
                    f'<div style="margin-bottom:12px;">'
                    f'<div style="font-size:11px;color:#6b7280;margin-bottom:2px;">{label}</div>'
                    f'<div style="font-size:14px;color:#111111;">{value or "—"}</div>'
                    f'</div>',
                    unsafe_allow_html=True)
            _ro("Company Name", st.session_state.get("co_name", ""))
            _ro("Address",      st.session_state.get("co_address", ""))
            _vr1, _vr2 = st.columns(2)
            with _vr1:
                _ro("Country",  st.session_state.get("co_country", ""))
            with _vr2:
                _ro("Postcode", st.session_state.get("co_postcode", ""))
            _ro("Website",      st.session_state.get("co_website", ""))
            co_name = co_address = co_country = co_postcode = co_website = ""

        st.markdown('<div class="sec-lbl">Originator — Person signing RFIs</div>', unsafe_allow_html=True)
        if _edit_mode:
            g1, g2 = st.columns(2)
            with g1:
                orig_name  = st.text_input("Full Name", key="orig_name")
                orig_email = st.text_input("Email",     key="orig_email")
            with g2:
                orig_title = st.text_input("Job Title", key="orig_title")
                orig_phone = st.text_input("Phone",     key="orig_phone")
        else:
            _og1, _og2 = st.columns(2)
            with _og1:
                _ro("Full Name", st.session_state.get("orig_name", ""))
                _ro("Email",     st.session_state.get("orig_email", ""))
            with _og2:
                _ro("Job Title", st.session_state.get("orig_title", ""))
                _ro("Phone",     st.session_state.get("orig_phone", ""))
            orig_name = orig_email = orig_title = orig_phone = ""

    with col_assets:
        # ── COMPANY LOGO ──────────────────────────────────────────────────────
        st.markdown('<div class="sec-lbl">Company Logo</div>', unsafe_allow_html=True)

        if st.session_state.pop("_logo_saved_ok", False):
            st.success("Logo saved successfully")

        _logo_bytes = get_asset_bytes(email, "company_logo.png")
        if _logo_bytes:
            _logo_b64 = base64.b64encode(_logo_bytes).decode()
            st.markdown(
                f'<div style="height:120px;display:flex;align-items:center;padding:4px 0;">'
                f'<img src="data:image/png;base64,{_logo_b64}" '
                f'style="max-width:150px;max-height:120px;object-fit:contain;" /></div>',
                unsafe_allow_html=True)
        else:
            st.markdown(
                '<div style="height:120px;background:#f8f9fa;border:2px dashed #d1d5db;'
                'border-radius:10px;display:flex;align-items:center;justify-content:center;'
                'color:#6b7280;font-size:13px;">No logo uploaded — upload PNG or JPG</div>',
                unsafe_allow_html=True)

        if not _logo_bytes or _edit_mode:
            up_logo = st.file_uploader("Upload logo PNG/JPG", type=["png", "jpg", "jpeg"],
                                       key="up_logo", label_visibility="collapsed")
        else:
            up_logo = None
        if up_logo:
            try:
                from PIL import Image as _PIL
                buf = io.BytesIO()
                _PIL.open(up_logo).convert("RGBA").save(buf, format="PNG")
                upload_asset(email, "company_logo.png", buf.getvalue())
                st.session_state["_logo_saved_ok"] = True
                st.session_state["_logo_do_rerun"] = True
            except Exception as e:
                st.error(f"Could not save logo: {e}")
            if st.session_state.pop("_logo_do_rerun", False):
                st.rerun()

        # ── SIGNATURE IMAGE ───────────────────────────────────────────────────
        st.markdown(
            '<div class="sec-lbl" style="margin-top:24px;">Signature Image</div>',
            unsafe_allow_html=True)

        if st.session_state.pop("_sig_saved_ok", False):
            st.success("Signature saved successfully")

        _sig_bytes = get_asset_bytes(email, "signature.png")
        if _sig_bytes:
            _sig_b64 = base64.b64encode(_sig_bytes).decode()
            st.markdown(
                f'<div style="height:120px;display:flex;align-items:center;padding:4px 0;">'
                f'<img src="data:image/png;base64,{_sig_b64}" '
                f'style="max-width:250px;max-height:120px;object-fit:contain;" /></div>',
                unsafe_allow_html=True)
        else:
            st.markdown(
                '<div style="height:120px;background:#f8f9fa;border:2px dashed #d1d5db;'
                'border-radius:10px;display:flex;align-items:center;justify-content:center;'
                'color:#6b7280;font-size:13px;">No signature uploaded — upload PNG or JPG</div>',
                unsafe_allow_html=True)

        if not _sig_bytes or _edit_mode:
            up_sig = st.file_uploader("Upload signature PNG/JPG", type=["png", "jpg", "jpeg"],
                                      key="up_sig", label_visibility="collapsed")
        else:
            up_sig = None
        if up_sig:
            try:
                from PIL import Image as _PIL
                buf = io.BytesIO()
                _PIL.open(up_sig).convert("RGBA").save(buf, format="PNG")
                upload_asset(email, "signature.png", buf.getvalue())
                st.session_state["_sig_saved_ok"] = True
                st.session_state["_sig_do_rerun"] = True
            except Exception as e:
                st.error(f"Could not save signature: {e}")
            if st.session_state.pop("_sig_do_rerun", False):
                st.rerun()

    st.markdown("---")
    if _edit_mode:
        if st.button("💾  Save Company Details", type="primary", use_container_width=True):
            _missing = []
            if not co_name.strip():
                _missing.append("Company Name")
            if not orig_name.strip():
                _missing.append("Originator Full Name")
            if _missing:
                st.error(f"Required field(s) missing: {', '.join(_missing)}")
            else:
                try:
                    cfg["company"] = {
                        "name": co_name, "address": co_address,
                        "country": co_country, "postcode": co_postcode, "website": co_website,
                    }
                    cfg["originator"] = {
                        "name": orig_name, "title": orig_title,
                        "email": orig_email, "phone": orig_phone,
                        "company": co_name,
                    }
                    save_cfg(cfg, email)
                    st.session_state.tab_company_done = True
                    st.session_state["co_edit_mode"] = False
                    st.session_state["_company_saved_ok"] = True
                    st.session_state["_company_do_rerun"] = True
                except Exception as _save_err:
                    st.error(f"Save failed: {_save_err}")
                if st.session_state.pop("_company_do_rerun", False):
                    st.rerun()

    if st.session_state.pop("_company_saved_ok", False):
        st.success("Company details saved successfully.")

    # ── Next step banner ──────────────────────────────────────────────────────
    if st.session_state.get("tab_company_done") and not st.session_state.get("co_edit_mode"):
        st.markdown(
            '<div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;'
            'padding:16px 20px;display:flex;justify-content:space-between;align-items:center;">'
            '<span style="color:#1e3a8a;font-size:14px;">'
            'Company setup complete — next: Set up your project</span>'
            '<span style="color:#6b7280;font-size:13px;">↑ Click Project Setup above</span>'
            '</div>',
            unsafe_allow_html=True)
