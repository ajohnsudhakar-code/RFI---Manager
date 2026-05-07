"""
ui_generate.py — Tab 5: Generate RFI Document
"""
import os
import streamlit as st
from pathlib import Path

from data_layer import (
    load_cfg, load_usage, get_asset_bytes,
    get_rfi_num, increment_usage,
    FREE_LIMIT,
    load_project_cfg, load_project_approved, load_project_clients,
    proj_snapshots_dir, proj_output_dir, proj_dir,
    upsert_project_register_rows, resolve_pdf_path,
    upload_project_document, sync_snapshots_from_supabase,
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

    st.markdown("## Generate RFI Document")

    if not approved:
        st.markdown(
            '<div class="info-box warn">Nothing to generate. '
            'Please complete the Analyse Drawings step first.</div>',
            unsafe_allow_html=True)
        return

    orig      = cfg.get("originator", {})
    co        = cfg.get("company", {})
    max_snaps = int(cfg["settings"].get("max_snapshots", 5))
    snaps_dir = proj_snapshots_dir(pid, email)
    sync_snapshots_from_supabase(pid, email, snaps_dir)
    out_dir   = proj_output_dir(pid, email)

    # ── Summary strip ────────────────────────────────────────────────────────
    gm1, gm2, gm3 = st.columns(3)
    gm1.metric("RFIs",    len(approved))
    gm2.metric("Project", pcfg.get("name", "—"))
    gm3.metric("Clients", len(clients))

    if not clients:
        st.markdown(
            '<div class="info-box warn">Please add clients in '
            '<strong>Project Setup</strong> first.</div>',
            unsafe_allow_html=True)
        return

    # ── Usage limit check ────────────────────────────────────────────────────
    _usage   = load_usage(email)
    _rfi_cnt = _usage.get("rfi_count", 0)
    _is_paid = _usage.get("is_paid", False)

    if _rfi_cnt >= FREE_LIMIT and not _is_paid:
        st.error(
            f"**You have used your {FREE_LIMIT} free RFIs.** "
            "Contact us at **ajohnsudhakar@gmail.com** to upgrade."
        )
        return

    if not _is_paid:
        st.markdown(
            f'<p style="color:#4a5568;font-size:12px;margin:12px 0 0;">'
            f'Free RFIs remaining: <strong style="color:#F0A500;">'
            f'{FREE_LIMIT - _rfi_cnt}</strong> of {FREE_LIMIT}</p>',
            unsafe_allow_html=True)

    # ── RFI checklist with per-RFI generate buttons ──────────────────────────
    st.markdown('<div class="sec-lbl" style="margin-top:24px;">RFI Contents</div>',
                unsafe_allow_html=True)

    _scripts = SCRIPTS_PY_DIR
    _tmp_dir = proj_dir(pid, email)

    for issue in approved:
        rfi_n  = get_rfi_num(issue, 1)
        snaps  = _local_snaps(snaps_dir, rfi_n, max_snaps)
        has_s  = len(snaps) > 0
        border = "#059669" if has_s else "#dc2626"
        badge  = (f'<span style="color:#6ee7b7;font-size:12px;">🖼 {len(snaps)} snapshot(s)</span>'
                  if has_s else
                  '<span style="color:#fca5a5;font-size:12px;">⚠ No snapshots</span>')
        _card_col, _client_col, _btn_col = st.columns([4, 2, 1])
        with _card_col:
            st.markdown(f"""
<div class="rfi-card" style="border-left:3px solid {border};">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">
    <strong style="color:#e8edf5;">RFI-{rfi_n:03d}</strong>
    <div style="display:flex;gap:12px;align-items:center;">
      <span style="color:#374151;font-size:12px;">Sheet: {issue.get('sheets','?')}</span>
      {badge}
    </div>
  </div>
  <p style="color:#8892a4;font-size:13px;margin:8px 0 0;">{issue.get('description','')[:200]}</p>
</div>""", unsafe_allow_html=True)
        with _client_col:
            st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
            _sel_client_idx = st.selectbox(
                "Send to",
                range(len(clients)),
                format_func=lambda i: clients[i].get("company", "?"),
                index=0,
                key=f"t5_client_{rfi_n}_{pid}",
                label_visibility="collapsed",
            )
            _sel_client = clients[_sel_client_idx]
        with _btn_col:
            st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
            _clicked = st.button("▶ Generate", type="primary",
                                 use_container_width=True, key=f"gen_{rfi_n}_{pid}")
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
                    "settings":     cfg.get("settings", {"max_snapshots": 5}),
                    "approved_rfis": [issue],
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

    # ── Previous documents ───────────────────────────────────────────────────
    st.markdown("---")
    prev_docs = sorted(out_dir.glob("*.docx"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
    if prev_docs:
        with st.expander(f"📂  Previously generated documents ({len(prev_docs)})"):
            for doc_path in prev_docs[:10]:
                dc1, dc2 = st.columns([5, 1])
                dc1.markdown(
                    f'<span style="color:#e8edf5;font-size:13px;">{doc_path.name}</span>',
                    unsafe_allow_html=True)
                with dc2:
                    with open(doc_path, "rb") as fh:
                        st.download_button(
                            "⬇️",
                            data=fh,
                            file_name=doc_path.name,
                            mime="application/vnd.openxmlformats-officedocument"
                                 ".wordprocessingml.document",
                            key=f"dl_{doc_path.stem}",
                        )
