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
    st.session_state.setdefault("co_edit_mode", not _all_filled)
    _edit_mode = st.session_state["co_edit_mode"]

    # View mode: always sync from freshly-loaded cfg; edit mode: preserve in-progress edits
    if not _edit_mode:
        st.session_state["co_name"]     = co.get("name", "") or orig_c.get("company", "")
        st.session_state["co_address"]  = co.get("address", "")
        st.session_state["co_city"]     = co.get("city", "")
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
        st.session_state.setdefault("co_city",    co.get("city", ""))
        st.session_state.setdefault("co_country", co.get("country", ""))
        st.session_state.setdefault("co_postcode", co.get("postcode", ""))
        st.session_state.setdefault("co_website", co.get("website", ""))
        st.session_state.setdefault("orig_name",  orig_c.get("name", ""))
        st.session_state.setdefault("orig_title", orig_c.get("title", ""))
        st.session_state.setdefault("orig_email", orig_c.get("email", ""))
        st.session_state.setdefault("orig_phone", orig_c.get("phone", ""))

    def _ro(label, value):
        st.markdown(
            f'<div style="margin-bottom:12px;">'
            f'<div style="font-size:11px;color:#6b7280;margin-bottom:2px;">{label}</div>'
            f'<div style="font-size:14px;color:#111111;">{value or "—"}</div>'
            f'</div>',
            unsafe_allow_html=True)

    def _sub(text):
        st.markdown(
            f'<div style="color:#6b7280;font-size:12px;margin-top:-6px;margin-bottom:10px;">'
            f'{text}</div>',
            unsafe_allow_html=True)

    def _lbl(text):
        st.markdown(
            f'<div style="font-size:11px;color:#6b7280;margin-bottom:2px;">{text}</div>',
            unsafe_allow_html=True)

    # Scope width/centering to this tab only — .st-key-co_scope matches nothing
    # outside this container, so other tabs are unaffected. The container itself
    # is a flex item (Streamlit nests every block in its parent's flex column),
    # so align-self (not margin:auto) is what actually centers it.
    st.markdown(
        '<style>'
        '.st-key-co_scope { width:600px; max-width:100%; align-self:center !important; margin:0 auto; }'
        '.co-hdr { color:#111111; font-size:13px; font-weight:700; margin:4px 0 12px; '
        'display:flex; align-items:center; gap:8px; }'
        '.co-hdr::after { content:""; flex:1; height:1px; background:#d1d5db; }'
        '.co-hdr.no-rule::after { display:none; }'
        '.st-key-co_edit_btn button { background:transparent !important; border:none !important; '
        'padding:2px 8px !important; font-size:12px !important; color:#6b7280 !important; '
        'box-shadow:none !important; }'
        '.st-key-co_edit_btn button:hover { color:#1d4ed8 !important; background:transparent !important; '
        'box-shadow:none !important; transform:none !important; }'
        '</style>',
        unsafe_allow_html=True)

    with st.container(key="co_scope"):
        # ── Page header ──────────────────────────────────────────────────────
        _title_col, _chip_col = st.columns([3, 1])
        with _title_col:
            st.markdown("### Company setup")
            st.markdown(
                '<div style="color:#6b7280;font-size:13px;margin-top:-6px;margin-bottom:8px;">'
                'These details appear on every RFI document you generate.</div>',
                unsafe_allow_html=True)
        with _chip_col:
            if _all_filled:
                st.markdown(
                    '<div style="text-align:right;margin-top:8px;">'
                    '<span style="background:#f0fdf4;color:#166534;border:1px solid #bbf7d0;'
                    'border-radius:20px;padding:4px 12px;font-size:12px;font-weight:600;">'
                    'Complete</span></div>',
                    unsafe_allow_html=True)
            else:
                st.markdown(
                    '<div style="text-align:right;margin-top:8px;">'
                    '<span style="background:#fffbeb;color:#92400e;border:1px solid #fde68a;'
                    'border-radius:20px;padding:4px 12px;font-size:12px;font-weight:600;">'
                    'Incomplete</span></div>',
                    unsafe_allow_html=True)

        # ── Card: Company ────────────────────────────────────────────────────
        with st.container(border=True):
            _hdr_l, _hdr_r = st.columns([4, 1])
            with _hdr_l:
                st.markdown('<div class="co-hdr no-rule">Company</div>', unsafe_allow_html=True)
            with _hdr_r:
                if not _edit_mode:
                    if st.button("Edit", key="co_edit_btn", type="tertiary"):
                        st.session_state["co_edit_mode"] = True
                        st.session_state["co_name"]     = co.get("name", "") or co.get("company_name", "")
                        st.session_state["co_address"]  = co.get("address", "")
                        st.session_state["co_city"]     = co.get("city", "")
                        st.session_state["co_country"]  = co.get("country", "")
                        st.session_state["co_postcode"] = co.get("postcode", "")
                        st.session_state["co_website"]  = co.get("website", "")
                        st.session_state["orig_name"]   = orig_c.get("name", "")
                        st.session_state["orig_title"]  = orig_c.get("title", "")
                        st.session_state["orig_email"]  = orig_c.get("email", "")
                        st.session_state["orig_phone"]  = orig_c.get("phone", "")
                        st.rerun()

            if _edit_mode:
                _lbl("Company name")
                co_name    = st.text_input("Company name", key="co_name", label_visibility="collapsed")
                _lbl("Address")
                co_address = st.text_input("Address",      key="co_address", label_visibility="collapsed")
                _c1, _c2 = st.columns([1, 1])
                with _c1:
                    _lbl("City")
                    co_city     = st.text_input("City",     key="co_city", label_visibility="collapsed")
                with _c2:
                    _lbl("Postcode")
                    co_postcode = st.text_input("Postcode", key="co_postcode", label_visibility="collapsed")
                _lbl("Country")
                co_country = st.text_input("Country",       key="co_country", label_visibility="collapsed")
                _lbl("Website")
                co_website = st.text_input("Website",       key="co_website", label_visibility="collapsed")
            else:
                _ro("Company name", st.session_state.get("co_name", ""))
                _ro("Address",      st.session_state.get("co_address", ""))
                _c1, _c2 = st.columns([1, 1])
                with _c1:
                    _ro("City",     st.session_state.get("co_city", ""))
                with _c2:
                    _ro("Postcode", st.session_state.get("co_postcode", ""))
                _ro("Country",      st.session_state.get("co_country", ""))
                _ro("Website",      st.session_state.get("co_website", ""))
                co_name = co_address = co_city = co_country = co_postcode = co_website = ""

        # ── Card: Person signing RFIs ───────────────────────────────────────
        with st.container(border=True):
            st.markdown('<div class="co-hdr">Person signing RFIs</div>', unsafe_allow_html=True)
            _sub("Printed in the approval block on page 2.")

            if _edit_mode:
                _g1, _g2 = st.columns([1, 1])
                with _g1:
                    _lbl("Full name")
                    orig_name  = st.text_input("Full name", key="orig_name", label_visibility="collapsed")
                with _g2:
                    _lbl("Job title")
                    orig_title = st.text_input("Job title", key="orig_title", label_visibility="collapsed")
                _g3, _g4 = st.columns([1, 1])
                with _g3:
                    _lbl("Email")
                    orig_email = st.text_input("Email", key="orig_email", label_visibility="collapsed")
                with _g4:
                    _lbl("Phone")
                    orig_phone = st.text_input("Phone", key="orig_phone", label_visibility="collapsed")
            else:
                _og1, _og2 = st.columns([1, 1])
                with _og1:
                    _ro("Full name", st.session_state.get("orig_name", ""))
                with _og2:
                    _ro("Job title", st.session_state.get("orig_title", ""))
                _og3, _og4 = st.columns([1, 1])
                with _og3:
                    _ro("Email", st.session_state.get("orig_email", ""))
                with _og4:
                    _ro("Phone", st.session_state.get("orig_phone", ""))
                orig_name = orig_email = orig_title = orig_phone = ""

        # ── Card: Logo and signature ────────────────────────────────────────
        with st.container(border=True):
            st.markdown('<div class="co-hdr">Logo and signature</div>', unsafe_allow_html=True)
            _sub("Images save as soon as you upload them.")

            _img_col, _sig_col = st.columns([1, 1])

            with _img_col:
                st.markdown(
                    '<div style="font-size:11px;color:#6b7280;margin-bottom:6px;">Company logo</div>',
                    unsafe_allow_html=True)

                if st.session_state.pop("_logo_saved_ok", False):
                    st.success("Logo saved successfully")

                _logo_bytes = get_asset_bytes(email, "company_logo.png")
                if _logo_bytes:
                    _logo_b64 = base64.b64encode(_logo_bytes).decode()
                    st.markdown(
                        f'<div style="height:120px;width:100%;display:flex;align-items:center;'
                        f'justify-content:center;background:#f8f9fa;border:1px solid #d1d5db;'
                        f'border-radius:10px;overflow:hidden;">'
                        f'<img src="data:image/png;base64,{_logo_b64}" '
                        f'style="max-width:100%;max-height:100%;object-fit:contain;" /></div>',
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
                        if upload_asset(email, "company_logo.png", buf.getvalue()):
                            st.session_state["_logo_saved_ok"] = True
                            st.session_state["_logo_do_rerun"] = True
                    except Exception as e:
                        st.error(f"Could not save logo: {e}")
                    if st.session_state.pop("_logo_do_rerun", False):
                        st.rerun()

            with _sig_col:
                st.markdown(
                    '<div style="font-size:11px;color:#6b7280;margin-bottom:6px;">Signature image</div>',
                    unsafe_allow_html=True)

                if st.session_state.pop("_sig_saved_ok", False):
                    st.success("Signature saved successfully")

                _sig_bytes = get_asset_bytes(email, "signature.png")
                if _sig_bytes:
                    _sig_b64 = base64.b64encode(_sig_bytes).decode()
                    st.markdown(
                        f'<div style="height:120px;width:100%;display:flex;align-items:center;'
                        f'justify-content:center;background:#f8f9fa;border:1px solid #d1d5db;'
                        f'border-radius:10px;overflow:hidden;">'
                        f'<img src="data:image/png;base64,{_sig_b64}" '
                        f'style="max-width:100%;max-height:100%;object-fit:contain;" /></div>',
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
                        if upload_asset(email, "signature.png", buf.getvalue()):
                            st.session_state["_sig_saved_ok"] = True
                            st.session_state["_sig_do_rerun"] = True
                    except Exception as e:
                        st.error(f"Could not save signature: {e}")
                    if st.session_state.pop("_sig_do_rerun", False):
                        st.rerun()

        st.markdown("---")
        if _edit_mode:
            if st.button("Save company details", type="primary", use_container_width=True):
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
                            "name": co_name, "address": co_address, "city": co_city,
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

        # ── Next step banner ─────────────────────────────────────────────────
        if st.session_state.get("tab_company_done") and not st.session_state.get("co_edit_mode"):
            st.markdown(
                '<div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;'
                'padding:16px 20px;display:flex;justify-content:space-between;align-items:center;">'
                '<span style="color:#1e3a8a;font-size:14px;">'
                'Company setup complete — next: Set up your project</span>'
                '</div>',
                unsafe_allow_html=True)
