"""
ui_crop.py — Tab 4: Crop and Annotate
"""
import os, io, json, base64
import streamlit as st
from pathlib import Path

try:
    from streamlit_pdf_viewer import pdf_viewer as _pdf_viewer
    _pdf_viewer_ok = True
except ImportError:
    _pdf_viewer_ok = False

from data_layer import (
    load_cfg,
    load_project_cfg, load_project_approved,
    proj_snapshots_dir,
    get_rfi_num, add_label_to_image,
    resolve_pdf_path,
    upload_project_snapshot, delete_project_snapshot,
    sync_snapshots_from_supabase,
    load_project_captions, save_project_captions,
    load_project_sheet_map,
)

# ── Local snapshot helpers (per-project filesystem) ──────────────────────────

def _local_snaps(snaps_dir: Path, rfi_num: int, max_snaps: int) -> list[str]:
    """Return list of existing snap filenames for this RFI."""
    return [
        f"RFI_{rfi_num:03d}_snap{i}.png"
        for i in range(1, max_snaps + 1)
        if (snaps_dir / f"RFI_{rfi_num:03d}_snap{i}.png").exists()
    ]


def _local_snap_count(snaps_dir: Path, rfi_num: int, max_snaps: int) -> int:
    return len(_local_snaps(snaps_dir, rfi_num, max_snaps))


def _local_next_snap(snaps_dir: Path, rfi_num: int, max_snaps: int):
    """Return the next available snap slot number, or None if full."""
    for i in range(1, max_snaps + 1):
        if not (snaps_dir / f"RFI_{rfi_num:03d}_snap{i}.png").exists():
            return i
    return None


def _load_captions(snaps_dir: Path) -> dict:
    try:
        with open(snaps_dir / "snap_captions.json") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_captions(snaps_dir: Path, captions: dict):
    try:
        with open(snaps_dir / "snap_captions.json", "w") as f:
            json.dump(captions, f, indent=2)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────

def render_tab_crop(email: str):
    pid = st.session_state.get("current_project_id", "")
    if not pid:
        st.info("No project selected. Create or select a project from the sidebar first.")
        return

    approved  = load_project_approved(pid, email)
    cfg       = load_cfg(email)
    pcfg      = load_project_cfg(pid, email)

    if not approved:
        st.markdown(
            '<div class="info-box warn">Please analyse drawings first and approve at least one RFI.</div>',
            unsafe_allow_html=True)
        return

    max_snaps  = int(cfg["settings"].get("max_snapshots", 5))
    pdf_path   = resolve_pdf_path(pid, email)
    snaps_dir  = proj_snapshots_dir(pid, email)
    if not st.session_state.get(f"t4_synced_{pid}"):
        sync_snapshots_from_supabase(pid, email, snaps_dir)
        st.session_state[f"t4_synced_{pid}"] = True

    # ── Pre-compute RFI state (needed by both columns) ────────────────────────
    rfi_labels = [
        f"RFI-{get_rfi_num(r):03d}  ·  Sheet {r.get('sheets','?')}  "
        f"[{_local_snap_count(snaps_dir, get_rfi_num(r), max_snaps)}/{max_snaps} snaps]"
        for r in approved
    ]
    idx         = min(st.session_state.get("crop_rfi_idx", 0), len(approved) - 1)
    issue       = approved[idx]
    rfi_num     = get_rfi_num(issue, idx + 1)

    _sheet_map   = load_project_sheet_map(pid, email)
    _inv_map     = {v: k for k, v in _sheet_map.items()}
    _raw_sheet   = issue.get("sheets", "").strip()
    _first_sheet = _raw_sheet.split(",")[0].strip() if _raw_sheet else ""
    _target_page = _inv_map.get(_first_sheet)
    if _target_page is None and _first_sheet:
        _fl = _first_sheet.lower()
        for _sn, _sp in _inv_map.items():
            if _sn.lower() == _fl:
                _target_page = _sp
                break

    saved_snaps = _local_snaps(snaps_dir, rfi_num, max_snaps)
    snap_slot   = _local_next_snap(snaps_dir, rfi_num, max_snaps)
    snap_name   = f"RFI_{rfi_num:03d}_snap{snap_slot}.png" if snap_slot else None

    # ── Two-column layout from the top ────────────────────────────────────────
    left_col, right_col = st.columns([5, 5])

    # ── RIGHT: PDF viewer ─────────────────────────────────────────────────────
    with right_col:
        st.markdown(
            '<div class="sec-lbl">Drawing viewer — scroll to find your area</div>',
            unsafe_allow_html=True)
        if not pdf_path:
            st.warning("PDF not found. Please re-upload in Project Setup.")
        else:
            if _pdf_viewer_ok:
                _pdf_viewer(
                    str(pdf_path),
                    height=800,
                    key=f"pdf_viewer_t4_{rfi_num}",
                    scroll_to_page=_target_page,
                )
            else:
                # Base64 iframe fallback — native PDF quality, no package needed
                try:
                    with open(pdf_path, "rb") as _pf:
                        _b64 = base64.b64encode(_pf.read()).decode()
                    st.markdown(
                        f'<iframe src="data:application/pdf;base64,{_b64}" '
                        f'width="100%" height="800px" '
                        f'style="border:1px solid #e8eaed;border-radius:8px;">'
                        f'</iframe>',
                        unsafe_allow_html=True,
                    )
                except Exception as _pe:
                    st.warning(f"Could not load PDF: {_pe}")

    # ── LEFT: controls ────────────────────────────────────────────────────────
    with left_col:

        # ── Page header ───────────────────────────────────────────────────────
        total_snaps_done = sum(
            1 for r in approved
            if _local_snap_count(snaps_dir, get_rfi_num(r), max_snaps) > 0
        )
        _hdr_l, _hdr_r = st.columns([3, 1])
        with _hdr_l:
            st.markdown(
                '<div style="font-size:18px;font-weight:500;color:#111111;">Crop &amp; Annotate</div>'
                '<div style="font-size:12px;color:#6b7280;margin-top:3px;">'
                'Upload a drawing screenshot for each approved RFI</div>',
                unsafe_allow_html=True)
        with _hdr_r:
            st.markdown(
                f'<div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:20px;'
                f'padding:4px 12px;font-size:12px;color:#1d4ed8;font-weight:500;'
                f'text-align:center;margin-top:4px;">'
                f'{total_snaps_done} of {len(approved)} RFIs have snapshots</div>',
                unsafe_allow_html=True)

        # ── Navigation row: ← → | selectbox | metric ─────────────────────────
        nav1, nav2, sel_col, badge_col = st.columns([1, 1, 6, 2])
        with nav1:
            if st.button("←", disabled=(idx == 0), key="cp_prev", use_container_width=True):
                st.session_state.crop_rfi_idx = idx - 1
                st.rerun()
        with nav2:
            if st.button("→", disabled=(idx == len(approved) - 1), key="cp_next", use_container_width=True):
                st.session_state.crop_rfi_idx = idx + 1
                st.rerun()
        with sel_col:
            new_idx = st.selectbox("Select RFI", range(len(rfi_labels)),
                                   format_func=lambda i: rfi_labels[i], index=idx,
                                   label_visibility="collapsed")
            if new_idx != idx:
                st.session_state.crop_rfi_idx = new_idx
                st.rerun()
            _desc_preview = issue.get("description", "")
            st.markdown(
                f'<div style="font-size:11px;color:#6b7280;margin-top:2px;">'
                f'{_desc_preview[:60] + "…" if len(_desc_preview) > 60 else _desc_preview}'
                f'</div>',
                unsafe_allow_html=True)
        with badge_col:
            st.markdown(
                f'<div style="text-align:center;padding:6px 4px;background:#f0f4ff;'
                f'border-radius:6px;border:1px solid #bfdbfe;margin-top:4px;">'
                f'<span style="color:#6b7280;font-size:10px;text-transform:uppercase;">Snaps</span><br>'
                f'<span style="color:#1d4ed8;font-weight:700;font-size:16px;">'
                f'{len(saved_snaps)}/{max_snaps}</span></div>',
                unsafe_allow_html=True,
            )

        # ── RFI description card ──────────────────────────────────────────────
        st.markdown(
            f'<div style="background:#ffffff;border:1px solid #e8eaed;'
            f'border-left:3px solid #1d4ed8;border-radius:10px;padding:12px 16px;margin-bottom:8px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:4px;">'
            f'<span style="color:#1d4ed8;font-size:13px;font-weight:600;">RFI-{rfi_num:03d}</span>'
            f'<span style="background:#f0f4ff;color:#3b5bdb;font-size:10px;'
            f'padding:2px 8px;border-radius:10px;">{issue.get("category","")}</span>'
            f'</div>'
            f'<div style="font-size:12px;color:#374151;line-height:1.6;margin-top:6px;">'
            f'{issue.get("description","")}'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True)

        # ── Upload section ────────────────────────────────────────────────────
        if snap_name:
            st.markdown(
                '<div style="background:#ffffff;border:1px solid #e8eaed;'
                'border-radius:10px;padding:16px 18px;margin-top:0;">',
                unsafe_allow_html=True)
            st.markdown(
                '<div style="display:flex;align-items:center;margin-bottom:6px;">'
                '<span style="width:20px;height:20px;border-radius:50%;background:#1d4ed8;'
                'color:#fff;font-size:10px;font-weight:600;display:inline-flex;'
                'align-items:center;justify-content:center;flex-shrink:0;margin-right:8px;">1</span>'
                '<div class="sec-lbl" style="margin:0;">Upload a screenshot of the area</div>'
                '</div>',
                unsafe_allow_html=True)
            st.caption("Take a screenshot of the relevant drawing area, then upload it here.")
            uploaded_shot = st.file_uploader(
                "Upload screenshot (PNG / JPG)",
                type=["png", "jpg", "jpeg"],
                key=f"ul_shot_{rfi_num}_{snap_slot}_{pid}",
            )

            if uploaded_shot:
                from PIL import Image as _PIL
                shot_img = _PIL.open(uploaded_shot).convert("RGB")

                st.markdown(
                    '<div style="display:flex;align-items:center;margin:12px 0 6px;">'
                    '<span style="width:20px;height:20px;border-radius:50%;background:#1d4ed8;'
                    'color:#fff;font-size:10px;font-weight:600;display:inline-flex;'
                    'align-items:center;justify-content:center;flex-shrink:0;margin-right:8px;">2</span>'
                    '<div class="sec-lbl" style="margin:0;">Preview</div>'
                    '</div>',
                    unsafe_allow_html=True)
                st.image(shot_img, caption="Screenshot", use_column_width=True)

                st.markdown(
                    '<div style="display:flex;align-items:center;margin:12px 0 6px;">'
                    '<span style="width:20px;height:20px;border-radius:50%;background:#1d4ed8;'
                    'color:#fff;font-size:10px;font-weight:600;display:inline-flex;'
                    'align-items:center;justify-content:center;flex-shrink:0;margin-right:8px;">3</span>'
                    '<div class="sec-lbl" style="margin:0;">Caption</div>'
                    '</div>',
                    unsafe_allow_html=True)
                lbl_col, save_col = st.columns([2, 1])
                with lbl_col:
                    label = st.selectbox(
                        "Drawing type",
                        ["Plan", "Elevation", "Section", "Detail", "None"],
                        key=f"lbl_{rfi_num}_{pid}",
                    )
                with save_col:
                    st.markdown("<div style='margin-top:24px;'></div>", unsafe_allow_html=True)
                    _do_save = st.button("💾  Save Snapshot", type="primary",
                                         use_container_width=True, key=f"sv_snap_{rfi_num}_{pid}")
                _save_ok = False
                if _do_save:
                    try:
                        annotated = add_label_to_image(
                            shot_img.copy(), label if label != "None" else ""
                        )
                        buf = io.BytesIO()
                        annotated.convert("RGB").save(buf, format="PNG")
                        dest = snaps_dir / snap_name
                        dest.write_bytes(buf.getvalue())
                        if not upload_project_snapshot(email, pid, snap_name, buf.getvalue()):
                            st.warning("⚠ Cloud backup failed — snapshot saved locally. Check your connection.")
                        caps = load_project_captions(pid, email)
                        if label and label != "None":
                            caps[snap_name] = label
                        save_project_captions(pid, caps, email)
                        st.success(f"✓ {snap_name} saved.")
                        _save_ok = True
                    except Exception as e:
                        st.error(f"Save failed: {e}")
                if _save_ok:
                    st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)
            st.caption(f"Saves as: {snap_name}")
        else:
            st.success(f"✓ All {max_snaps} snapshots saved for RFI-{rfi_num:03d}.")

        # ── Saved snapshot gallery ────────────────────────────────────────────
        if st.session_state.get("t4_delete_err"):
            st.error(st.session_state.pop("t4_delete_err"))
        if saved_snaps:
            st.markdown(
                f'<div style="display:flex;align-items:center;'
                f'justify-content:space-between;margin-bottom:8px;">'
                f'<span style="font-size:13px;font-weight:500;color:#374151;">'
                f'📷 Saved snapshots ({len(saved_snaps)})</span>'
                f'<span style="font-size:11px;color:#9ca3af;">RFI-{rfi_num:03d}</span>'
                f'</div>',
                unsafe_allow_html=True)
            _pending_delete = st.session_state.get("t4_confirm_delete", "")

            _grid_snaps = list(saved_snaps)
            if len(_grid_snaps) % 2 != 0:
                _grid_snaps.append(None)

            for row_start in range(0, len(_grid_snaps), 2):
                gcol_a, gcol_b = st.columns([1, 1])
                for gi, snap_fn in enumerate(_grid_snaps[row_start:row_start + 2]):
                    gcol = gcol_a if gi == 0 else gcol_b
                    with gcol:
                        if snap_fn is None:
                            continue
                        snap_path = snaps_dir / snap_fn
                        if not snap_path.exists():
                            continue
                        try:
                            with open(snap_path, "rb") as _sf:
                                _b64 = base64.b64encode(_sf.read()).decode()
                            st.markdown(
                                f'<img src="data:image/png;base64,{_b64}" '
                                f'style="width:100%;height:180px;object-fit:cover;'
                                f'border-radius:4px;margin-bottom:4px;" />',
                                unsafe_allow_html=True,
                            )
                            st.caption(snap_fn)
                        except Exception:
                            st.caption(snap_fn)

                        si = row_start + gi
                        if _pending_delete == str(snap_path):
                            st.warning(
                                "⚠ Are you sure you want to delete this snapshot? "
                                "This cannot be undone."
                            )
                            if st.button("✓ Yes Delete", key=f"del_yes_{si}_{pid}",
                                         type="primary", use_container_width=True):
                                _del_ok = delete_project_snapshot(email, pid, snap_fn)
                                if _del_ok:
                                    _caps = load_project_captions(pid, email)
                                    _caps.pop(snap_fn, None)
                                    save_project_captions(pid, _caps, email)
                                    if snap_path.exists():
                                        try:
                                            snap_path.unlink()
                                        except Exception:
                                            pass
                                else:
                                    st.session_state["t4_delete_err"] = (
                                        "⚠ Could not delete snapshot from cloud — no changes made. "
                                        "Check your connection and try again."
                                    )
                                st.session_state.pop("t4_confirm_delete", None)
                                st.rerun()
                            if st.button("✕ Cancel", key=f"del_cancel_{si}_{pid}",
                                         use_container_width=True):
                                st.session_state.pop("t4_confirm_delete", None)
                                st.rerun()
                        else:
                            if str(_pending_delete) == "":
                                if st.button("🗑 Delete", key=f"del_{si}_{pid}",
                                             use_container_width=True):
                                    st.session_state.t4_confirm_delete = str(snap_path)
                                    st.rerun()

        # ── Overall progress ──────────────────────────────────────────────────
        total_with_snaps = sum(
            1 for r in approved
            if _local_snap_count(snaps_dir, get_rfi_num(r), max_snaps) > 0
        )
        if total_with_snaps >= len(approved):
            st.markdown("---")
            st.markdown(
                '<div class="info-box success">✓ All RFIs have snapshots. '
                'Proceed to <strong>Generate RFI</strong>.</div>',
                unsafe_allow_html=True)
