"""
ui_register.py — Tab 6: RFI Register (per-project, all projects combined)
"""
import io
import streamlit as st

from data_layer import (
    _list_project_ids,
    load_project_cfg,
    load_project_register,
    update_project_register_status,
)

_STATUS_OPTIONS = ["Open", "Responded", "Closed"]

_STATUS_COLORS = {
    "Open":      ("#dc2626", "#fff"),
    "Responded": ("#7c3aed", "#fff"),
    "Closed":    ("#059669", "#fff"),
}

_DISPLAY_COLS = {
    "rfi_number":           "RFI No.",
    "project_name":         "Project",
    "sheet_reference":      "Sheet",
    "category":             "Category",
    "priority":             "Priority",
    "description":          "Description",
    "status":               "Status",
    "date_raised":          "Date Raised",
    "response_required_by": "Response By",
}


def _load_all_rows(email: str = "") -> list:
    """Scan every project folder for the given user and return combined register rows."""
    rows = []
    for pid in _list_project_ids(email):
        proj_rows = load_project_register(pid, email)
        if not proj_rows:
            continue
        # Ensure project_name is set; fall back to loading from config
        pcfg = load_project_cfg(pid, email)
        proj_name = pcfg.get("name", "") or pid
        for row in proj_rows:
            enriched = dict(row)
            if not enriched.get("project_name"):
                enriched["project_name"] = proj_name
            enriched["_pid"] = pid          # internal key for status updates
            rows.append(enriched)
    return rows


def render_tab_register(email: str):
    all_rows = _load_all_rows(email)

    if not all_rows:
        st.markdown(
            '<div class="info-box warn">No RFIs in your register yet. '
            'Generate your first RFI document to populate this.</div>',
            unsafe_allow_html=True)
        return

    try:
        import pandas as pd

        df = pd.DataFrame(all_rows)

        # ── Summary metrics ───────────────────────────────────────────────────
        _total  = len(df)
        _open   = int((df["status"] == "Open").sum())      if "status" in df.columns else 0
        _resp   = int((df["status"] == "Responded").sum()) if "status" in df.columns else 0
        _closed = int((df["status"] == "Closed").sum())    if "status" in df.columns else 0
        sm1, sm2, sm3, sm4 = st.columns(4)
        sm1.metric("Total RFIs", _total)
        sm2.metric("Open",       _open)
        sm3.metric("Responded",  _resp)
        sm4.metric("Closed",     _closed)

        # ── Filters ──────────────────────────────────────────────────────────
        rf1, rf2, rf3 = st.columns([2, 2, 4])
        with rf1:
            if "project_name" in df.columns:
                projs    = ["All"] + sorted(df["project_name"].dropna().astype(str).unique().tolist())
                sel_proj = st.selectbox("Filter by Project", projs, key="reg_filter_proj")
            else:
                sel_proj = "All"
        with rf2:
            stats    = ["All"] + _STATUS_OPTIONS
            sel_stat = st.selectbox("Filter by Status", stats, key="reg_filter_status")
        with rf3:
            src1, src2 = st.columns([5, 1])
            with src1:
                search_input = st.text_input(
                    "Search", placeholder="Search any field…",
                    key="reg_search_input",
                )
            with src2:
                st.markdown("<div style='margin-top:24px;'></div>", unsafe_allow_html=True)
                if st.button("Search", key="reg_search_btn", use_container_width=True):
                    st.session_state.reg_active_search = search_input

        # ── Apply filters ─────────────────────────────────────────────────────
        display_cols = ["rfi_number", "project_name", "sheet_reference",
                        "category", "priority", "description", "status",
                        "date_raised", "response_required_by"]
        filt = df.copy()
        if sel_proj != "All" and "project_name" in filt.columns:
            filt = filt[filt["project_name"].astype(str) == sel_proj]
        if sel_stat != "All" and "status" in filt.columns:
            filt = filt[filt["status"].astype(str) == sel_stat]
        _active_search = st.session_state.get("reg_active_search", "")
        if _active_search:
            mask = filt.apply(
                lambda row: row.astype(str).str.contains(
                    _active_search, case=False, na=False).any(), axis=1)
            filt = filt[mask]

        # Drop internal _pid column before display
        show = filt[[c for c in display_cols if c in filt.columns]]

        # ── RFI table ─────────────────────────────────────────────────────────
        _vis_cols = [c for c in _DISPLAY_COLS if c in show.columns]
        _thead_cells = "".join(
            f'<th style="background:#f8f9fa;color:#6b7280;padding:8px 12px;'
            f'text-align:left;font-weight:600;font-size:12px;white-space:nowrap;">'
            f'{_DISPLAY_COLS[c]}</th>'
            for c in _vis_cols
        )
        _rows_html = ""
        for _, _row in show.iterrows():
            _cells = ""
            for _col in _vis_cols:
                _val = str(_row.get(_col, ""))
                if _col == "status":
                    _bg, _fg = _STATUS_COLORS.get(_val, ("#374151", "#fff"))
                    _cells += (
                        f'<td style="padding:8px 12px;border-bottom:1px solid #e8eaed;">'
                        f'<span style="background:{_bg};color:{_fg};padding:2px 8px;'
                        f'border-radius:4px;font-size:11px;">{_val}</span></td>'
                    )
                elif _col == "description":
                    _short = _val[:120] + "…" if len(_val) > 120 else _val
                    _cells += (
                        f'<td style="padding:8px 12px;border-bottom:1px solid #e8eaed;'
                        f'color:#6b7280;font-size:12px;">{_short}</td>'
                    )
                else:
                    _cells += (
                        f'<td style="padding:8px 12px;border-bottom:1px solid #e8eaed;'
                        f'color:#111111;font-size:13px;">{_val}</td>'
                    )
            _rows_html += f'<tr>{_cells}</tr>'
        st.markdown(
            f'<div style="overflow-x:auto;margin:12px 0;">'
            f'<table style="width:100%;border-collapse:collapse;">'
            f'<thead><tr>{_thead_cells}</tr></thead>'
            f'<tbody>{_rows_html}</tbody>'
            f'</table></div>',
            unsafe_allow_html=True,
        )

        # ── Status update ─────────────────────────────────────────────────────
        st.markdown('<div class="sec-lbl" style="margin-top:16px;">Update RFI Status</div>',
                    unsafe_allow_html=True)
        # Build (pid, rfi_number) options from filtered df if a project is selected,
        # else from all rows.
        source = filt if sel_proj != "All" else df
        if "rfi_number" in source.columns and "_pid" in source.columns:
            pairs = (
                source[["_pid", "rfi_number", "project_name"]]
                .dropna(subset=["rfi_number"])
                .drop_duplicates(subset=["_pid", "rfi_number"])
                .sort_values(["project_name", "rfi_number"])
                .values.tolist()
            )
        else:
            pairs = []

        if pairs:
            upd1, upd2, upd3 = st.columns([3, 2, 1])
            with upd1:
                pair_labels = [
                    f"RFI-{int(rn):03d}  ({pname})" for _pid, rn, pname in pairs
                ]
                sel_pair_idx = st.selectbox(
                    "RFI", range(len(pair_labels)),
                    format_func=lambda i: pair_labels[i],
                    key="reg_sel_rfi",
                )
            with upd2:
                sel_status = st.selectbox("New Status", _STATUS_OPTIONS,
                                          key="reg_sel_status")
            with upd3:
                st.write("")
                if st.button("Update", key="reg_update", use_container_width=True):
                    _upd_pid, _upd_rn, _upd_pname = pairs[sel_pair_idx]
                    update_project_register_status(_upd_pid, int(_upd_rn), sel_status, email)
                    st.success(f"✓ RFI-{int(_upd_rn):03d} → {sel_status}")
                    st.rerun()
        else:
            st.info("No RFIs available to update.")

        # ── Footer ────────────────────────────────────────────────────────────
        st.markdown("---")
        foot1, foot2 = st.columns([6, 2])
        with foot1:
            st.markdown(
                f'<div style="color:#374151;font-size:12px;padding-top:8px;">'
                f'Showing <strong style="color:#111111;">{len(show)}</strong> '
                f'of {len(df)} records</div>',
                unsafe_allow_html=True)
        with foot2:
            _xlsx_buf = io.BytesIO()
            show.rename(columns=_DISPLAY_COLS).to_excel(_xlsx_buf, index=False, engine="openpyxl")
            _xlsx_buf.seek(0)
            st.download_button(
                "⬇️  Download Register (.xlsx)",
                data=_xlsx_buf,
                file_name="RFI_Register.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="reg_download",
            )

    except ImportError:
        st.error("pandas not installed. Run: `pip install pandas openpyxl`")
    except Exception as e:
        st.error(f"Could not load register: {e}")
