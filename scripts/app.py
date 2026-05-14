"""
RFI Manager — Streamlit Dashboard  v4
Deploy: streamlit run scripts/app.py

──────────────────────────────────────────────────────────────────────────────
SUPABASE — Run these in your Supabase SQL Editor before first use:
──────────────────────────────────────────────────────────────────────────────

-- user_config: stores project + company config per user
CREATE TABLE IF NOT EXISTS user_config (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  email text UNIQUE NOT NULL,
  config_data jsonb,
  updated_at timestamptz DEFAULT now()
);

-- contacts: stores client contact list per user
CREATE TABLE IF NOT EXISTS contacts (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  email text UNIQUE NOT NULL,
  contacts_data jsonb
);

-- approved_rfis: stores approved RFI lists per user session
CREATE TABLE IF NOT EXISTS approved_rfis (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  email text NOT NULL,
  session_id text,
  rfis_data jsonb,
  created_at timestamptz DEFAULT now()
);

-- rfi_register: one row per generated RFI
CREATE TABLE IF NOT EXISTS rfi_register (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  email text NOT NULL,
  project_id text,
  project_name text,
  rfi_number int,
  sheet_reference text,
  category text,
  description text,
  status text DEFAULT 'Open',
  date_raised date DEFAULT current_date,
  UNIQUE (email, project_id, rfi_number)
);

-- rfi_usage: tracks free/paid usage per user
CREATE TABLE IF NOT EXISTS rfi_usage (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  email text UNIQUE NOT NULL,
  rfi_count int DEFAULT 0,
  is_paid boolean DEFAULT false
);

-- user_sessions: persistent login sessions keyed by UUID (?sid= in URL)
CREATE TABLE IF NOT EXISTS user_sessions (
  session_key text PRIMARY KEY,
  email text NOT NULL,
  access_token text NOT NULL,
  refresh_token text,
  expires_at bigint,
  created_at bigint DEFAULT extract(epoch from now())::bigint,
  last_used_at bigint DEFAULT extract(epoch from now())::bigint
);
CREATE INDEX IF NOT EXISTS user_sessions_email_idx ON user_sessions (email);

-- Storage bucket (create in Supabase Dashboard → Storage):
--   Bucket name: snapshots   (private)

──────────────────────────────────────────────────────────────────────────────
"""

# ── IMPORTS ───────────────────────────────────────────────────────────────────
try:
    import streamlit as st
except ImportError as _e:
    raise SystemExit(f"Streamlit not installed: {_e}")

import io, uuid
import streamlit.components.v1 as components

# ── PAGE CONFIG (must be the very first st.* call) ────────────────────────────
st.set_page_config(
    page_title="RFI Manager",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── DATA LAYER ────────────────────────────────────────────────────────────────
from data_layer import (
    load_cfg, load_company, load_usage,
    get_asset_bytes, track_usage, log_error,
    _migrate_legacy_to_projects, _list_project_ids, _new_project_id,
    load_project_cfg,
    load_project_approved, proj_output_dir,
    FREE_LIMIT,
    get_supabase_client, sign_in_with_password, sign_out_user,
    save_user_session, load_user_session, delete_user_session,
    _secret,
)

# ── TAB MODULES ───────────────────────────────────────────────────────────────
from ui_company  import render_tab_company
from ui_project  import render_tab_project
from ui_analyse  import render_tab_analyse
from ui_crop     import render_tab_crop
from ui_generate import render_tab_generate
from ui_register import render_tab_register

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Google Font ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Hide Streamlit chrome ── */
#MainMenu                    { display: none !important; }
footer                       { display: none !important; }
[data-testid="stToolbar"]    { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
[data-testid="stSidebarResizeHandle"] { display: none !important; }
[data-testid="stSidebarNav"]          { display: none !important; }
[data-testid="stHeader"]              { display: none !important; }

/* ── Base ── */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
[data-testid="stAppViewContainer"] { background: #f5f6f8; }
.block-container {
    padding-top: 1.25rem !important;
    padding-bottom: 2rem !important;
    max-width: 100% !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1px solid #e8eaed !important;
}
[data-testid="stSidebar"] > div:first-child { padding-top: 0 !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: #ffffff;
    border-bottom: 1px solid #e8eaed;
    gap: 0;
    padding: 0 4px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #374151;
    border: none !important;
    border-bottom: 3px solid transparent !important;
    border-radius: 0 !important;
    padding: 14px 24px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    letter-spacing: 0.02em;
    transition: color 0.2s ease;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #94a3b8 !important;
    background: rgba(0,0,0,0.02) !important;
}
.stTabs [aria-selected="true"] {
    color: #1d4ed8 !important;
    border-bottom-color: #1d4ed8 !important;
    background: rgba(29,78,216,0.04) !important;
}
.stTabs [data-baseweb="tab-panel"] {
    background: #f5f6f8;
    padding: 1.5rem 0.5rem 2rem !important;
}

/* ── Typography ── */
h1, h2, h3, h4, h5, h6 { color: #111111 !important; font-weight: 600 !important; letter-spacing: -0.02em !important; }
p, label { color: #6b7280; }

/* ── Form inputs ── */
.stTextInput > label,
.stSelectbox > label,
.stTextArea > label,
.stNumberInput > label,
.stFileUploader > label {
    color: #374151 !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    margin-bottom: 4px !important;
}
.stTextInput > div > div > input,
.stTextArea textarea,
.stNumberInput input {
    background: #ffffff !important;
    color: #111111 !important;
    border: 1px solid #e8eaed !important;
    border-radius: 8px !important;
    font-size: 14px !important;
    padding: 9px 12px !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
    font-family: 'Inter', sans-serif !important;
}
.stTextInput > div > div > input:focus,
.stTextArea textarea:focus {
    border-color: #2563b0 !important;
    box-shadow: 0 0 0 3px rgba(29,78,216,0.15) !important;
    outline: none !important;
}
.stSelectbox > div > div {
    background: #ffffff !important;
    border: 1px solid #e8eaed !important;
    border-radius: 8px !important;
    color: #111111 !important;
}
.stSelectbox > div > div:focus-within {
    border-color: #2563b0 !important;
    box-shadow: 0 0 0 3px rgba(29,78,216,0.15) !important;
}
[data-testid="stFileUploaderDropzone"] {
    background: #ffffff !important;
    border: 2px dashed #e8eaed !important;
    border-radius: 10px !important;
    transition: border-color 0.2s ease !important;
}
[data-testid="stFileUploaderDropzone"]:hover { border-color: #2563b0 !important; }

/* ── Buttons ── */
.stButton > button {
    background: #ffffff;
    color: #111111;
    border: 1px solid #e8eaed;
    border-radius: 8px;
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    font-weight: 500;
    padding: 10px 18px;
    letter-spacing: 0.01em;
    transition: all 0.2s ease;
    cursor: pointer;
}
.stButton > button:hover {
    background: #f0f4ff;
    border-color: #2563b0;
    color: #111111;
    box-shadow: 0 2px 8px rgba(29,78,216,0.15);
    transform: translateY(-1px);
}
.stButton > button:active { transform: translateY(0); }
.stButton > button[kind="primary"] {
    background: #1d4ed8;
    border: 1px solid #1d4ed8;
    color: #ffffff;
    font-weight: 700;
    font-size: 14px;
    padding: 12px 24px;
    box-shadow: 0 2px 8px rgba(29,78,216,0.2);
}
.stButton > button[kind="primary"]:hover {
    background: #2563eb;
    box-shadow: 0 4px 16px rgba(29,78,216,0.25);
    border-color: #1d4ed8;
    transform: translateY(-2px);
}
.stDownloadButton > button {
    background: linear-gradient(135deg, #064e3b 0%, #065f46 100%);
    color: #6ee7b7;
    border: 1px solid #065f46;
    border-radius: 8px;
    font-family: 'Inter', sans-serif;
    font-size: 13px;
    font-weight: 600;
    padding: 10px 18px;
    transition: all 0.2s ease;
}
.stDownloadButton > button:hover {
    background: linear-gradient(135deg, #065f46 0%, #047857 100%);
    box-shadow: 0 4px 12px rgba(5,150,105,0.3);
    color: #a7f3d0;
    transform: translateY(-1px);
}

/* ── Metrics ── */
[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #e8eaed;
    border-radius: 10px;
    padding: 18px 20px;
}
[data-testid="stMetricLabel"] {
    color: #374151 !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
}
[data-testid="stMetricValue"] { color: #111111 !important; font-size: 22px !important; font-weight: 700 !important; }
[data-testid="stMetricDelta"] { font-size: 12px !important; }

/* ── Cards ── */
.rfi-card {
    background: #ffffff;
    border: 1px solid #e8eaed;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 10px;
    transition: border-color 0.2s ease;
    line-height: 1.6;
}
.rfi-card:hover { border-color: #d1d5db; }
.section-card {
    background: #ffffff;
    border: 1px solid #e8eaed;
    border-radius: 12px;
    padding: 22px 24px;
    margin-bottom: 16px;
}
.info-box {
    background: #ffffff;
    border: 1px solid #e8eaed;
    border-left: 3px solid #2563b0;
    border-radius: 0 8px 8px 0;
    padding: 12px 16px;
    font-size: 13px;
    color: #6b7280;
    margin: 10px 0 14px;
    line-height: 1.65;
}
.info-box.warn { border-left-color: #d97706; }
.info-box.success { border-left-color: #059669; }
.snap-row {
    background: #ffffff;
    border: 1px solid #d97706;
    border-radius: 8px;
    padding: 12px 18px;
    margin: 8px 0 14px;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
}

/* ── Section labels ── */
.sec-lbl {
    color: #374151;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin: 18px 0 8px;
    display: flex;
    align-items: center;
    gap: 8px;
    white-space: nowrap;
}
.sec-lbl::after {
    content: '';
    flex: 1;
    height: 1px;
    background: #e8eaed;
    min-width: 20px;
}
hr { border: none !important; border-top: 1px solid #e8eaed !important; margin: 20px 0 !important; }

/* ── Sidebar step items ── */
.sb-header {
    background: #ffffff;
    border-bottom: 1px solid #e8eaed;
    padding: 18px 16px 14px;
    margin: -1rem -1rem 0;
}
.sb-brand { color: #1d4ed8; font-size: 16px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; }
.sb-company { color: #374151; font-size: 11px; margin-top: 2px; letter-spacing: 0.04em; }
.sb-project-label { color: #374151; font-size: 10px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; margin: 16px 0 4px; }
.sb-project-name { color: #111111; font-size: 13px; font-weight: 600; line-height: 1.4; }
.sb-project-pdf { color: #374151; font-size: 11px; margin-top: 2px; word-break: break-all; font-family: 'Courier New', monospace; }
.sb-progress-label { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.sb-progress-label span:first-child { color: #374151; font-size: 10px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; }
.sb-progress-label span:last-child { color: #1d4ed8; font-size: 12px; font-weight: 700; }
.sb-progress-track { background: #e8eaed; border-radius: 20px; height: 5px; overflow: hidden; margin-bottom: 12px; }
.sb-progress-fill { height: 100%; border-radius: 20px; background: linear-gradient(90deg, #1d4ed8, #3b82f6); transition: width 0.5s ease; }
.sb-step { padding: 8px 10px; border-radius: 8px; font-size: 12.5px; display: flex; align-items: center; gap: 10px; margin: 2px 0; cursor: default; }
.sb-step.done   { background: rgba(5,150,105,0.07); }
.sb-step.active { background: rgba(29,78,216,0.06); }
.sb-step.todo   { background: transparent; }
.sb-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.sb-step.done   .sb-dot { background: #059669; }
.sb-step.active .sb-dot { background: #1d4ed8; box-shadow: 0 0 6px rgba(29,78,216,0.5); }
.sb-step.todo   .sb-dot { background: #e8eaed; border: 1.5px solid #d1d5db; }
.sb-step.done   span { color: #374151; text-decoration: line-through; text-decoration-color: #d1d5db; }
.sb-step.active span { color: #1d4ed8; font-weight: 600; }
.sb-step.todo   span { color: #d1d5db; }

/* ── Alerts / Expander / Progress / Spinner / Dataframe ── */
[data-testid="stAlert"] { border-radius: 8px !important; font-size: 13px !important; }
[data-testid="stExpander"] { background: #ffffff !important; border: 1px solid #e8eaed !important; border-radius: 8px !important; }
details > summary { font-size: 13px !important; color: #6b7280 !important; font-weight: 500 !important; }
.stProgress > div > div > div { background: linear-gradient(90deg, #1d4ed8, #3b82f6) !important; border-radius: 4px !important; }
.stProgress > div > div { background: #e8eaed !important; border-radius: 4px !important; }
[data-testid="stSpinner"] { color: #1d4ed8 !important; }
[data-testid="stDataFrame"] { border: 1px solid #e8eaed !important; border-radius: 8px !important; }

</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
#  SECRETS VALIDATION
# ══════════════════════════════════════════════════════════════════════════════
_REQUIRED_SECRETS = ["SUPABASE_URL", "SUPABASE_KEY", "ANTHROPIC_API_KEY"]
_missing_secrets  = [k for k in _REQUIRED_SECRETS if not _secret(k)]
_supabase_configured = not any(k in _missing_secrets for k in ("SUPABASE_URL", "SUPABASE_KEY"))

if _missing_secrets:
    st.warning(
        "**Setup incomplete — missing secrets:** " +
        ", ".join(f"`{k}`" for k in _missing_secrets) +
        "\n\nAdd them to `.streamlit/secrets.toml`."
    )

# ══════════════════════════════════════════════════════════════════════════════
#  LOGIN SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
for _login_key, _login_default in {
    "_sb_session":  None,   # full session token stored after login
    "_sid":         "",     # UUID key stored in ?sid= query param
    "_login_error": "",     # error message shown on login form
    "_login_mode":  "signin",
}.items():
    st.session_state.setdefault(_login_key, _login_default)

# ══════════════════════════════════════════════════════════════════════════════
#  SESSION PERSISTENCE — restore user_email from Supabase user_sessions table
#
#  Flow:
#   1. Read ?sid= from query params (set at login; survives browser refresh)
#   2. Look up the row in user_sessions — returns None if not found / deleted
#   3. Check expires_at; if expired, delete the row and fall through to login
#   4. Call sb.auth.set_session(access_token, refresh_token) → restore Python auth
#   5. Set user_email → rerun → dashboard
#
#  Pure Python — no JavaScript, no localStorage, no iframes.
#  Works across app restarts, server reboots, and new browser tabs.
# ══════════════════════════════════════════════════════════════════════════════
st.session_state.setdefault("user_email", "")


def _restore_session_from_db():
    """Try to restore a logged-in session from the Supabase user_sessions table.

    Reads ?sid= from query params. If a valid, unexpired row is found, restores
    the Supabase Python client session and sets user_email in session_state.
    Calls st.rerun() on success so the dashboard renders immediately.
    Silently falls through to the login form on any failure.
    """
    if st.session_state.get("user_email", "").strip():
        return  # Already logged in
    if not _supabase_configured:
        return

    _sid = st.query_params.get("sid", "")
    if not _sid:
        return  # No sid in URL — fresh visit, show login form

    # Store sid in session_state so sign_out_user() can delete it
    st.session_state["_sid"] = _sid

    row = load_user_session(_sid)
    if not row:
        # Session not found (deleted, expired row, etc.) — clear param + show login
        try:
            st.query_params.clear()
        except Exception:
            pass
        return

    import time as _t
    _exp = float(row.get("expires_at") or 0)
    if _exp and _t.time() > _exp:
        # Token expired — clean up and show login form
        delete_user_session(_sid)
        try:
            st.query_params.clear()
        except Exception:
            pass
        return

    _at = row.get("access_token", "")
    _rt = row.get("refresh_token", "")
    _stored_email = row.get("email", "")
    if not _at or not _stored_email:
        return

    # Restore the Supabase Python client session
    sb = get_supabase_client()
    if not sb:
        return
    try:
        response = sb.auth.set_session(_at, _rt or "")
        _user = getattr(response, "user", None)
        _sess = getattr(response, "session", None)
        if _user is None and _sess is not None:
            _user = getattr(_sess, "user", None)
        _email_r = getattr(_user, "email", None) if _user else _stored_email
        if not _email_r:
            return
        # Refresh stored tokens (Supabase may have issued new ones)
        _new_at  = getattr(_sess, "access_token", _at) if _sess else _at
        _new_rt  = getattr(_sess, "refresh_token", _rt) if _sess else _rt
        _new_exp = getattr(_sess, "expires_at", _exp)  if _sess else _exp
        # Persist refreshed tokens back to DB
        save_user_session(_sid, _email_r, _new_at, _new_rt, int(_new_exp))
        st.session_state["user_email"] = _email_r
        st.session_state["_restore_do_rerun"] = True
    except Exception as _re:
        log_error(_re, "_restore_session_from_db/set_session")
        # Tokens invalid — delete the stale row and show login form
        delete_user_session(_sid)
        try:
            st.query_params.clear()
        except Exception:
            pass
    if st.session_state.pop("_restore_do_rerun", False):
        st.rerun()


_restore_session_from_db()


def _on_success(user_obj, sess_obj):
    """Handle successful login: store session, persist to DB, set ?sid=, rerun."""
    _email = getattr(user_obj, "email", None)
    if not _email:
        raise ValueError(f"No email in user object: {user_obj!r}")
    st.session_state.user_email = _email
    _exp = getattr(sess_obj, "expires_at", 0) if sess_obj else 0
    _at  = getattr(sess_obj, "access_token", "")
    _rt  = getattr(sess_obj, "refresh_token", "")
    _new_sid = str(uuid.uuid4())
    st.session_state["_sid"] = _new_sid
    save_user_session(_new_sid, _email, _at, _rt, int(_exp))
    st.query_params["sid"] = _new_sid
    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  LOGIN SCREEN
# ══════════════════════════════════════════════════════════════════════════════
def _render_login():
    """Render the login / sign-up / forgot-password form."""
    _, col_m, _ = st.columns([1, 2, 1])
    with col_m:
        st.markdown("""
        <div style="background:#ffffff;border:1px solid #e8eaed;border-radius:12px;
                    padding:48px 40px;margin-top:60px;">
          <div style="text-align:center;margin-bottom:32px;">
            <div style="color:#1d4ed8;font-size:30px;font-weight:700;letter-spacing:0.1em;margin-bottom:6px;">
              RFI MANAGER
            </div>
            <div style="color:#374151;font-size:14px;">
              Construction RFI workflow platform
            </div>
          </div>
        """, unsafe_allow_html=True)

        if _supabase_configured:
            # ── Recovery token detection (Supabase password reset link) ───────
            if not st.session_state.get("_password_reset_mode"):
                _rec_type = st.query_params.get("type", "")
                if _rec_type == "recovery":
                    _rec_th  = st.query_params.get("token_hash", "")
                    _rec_err = ""
                    if _rec_th:
                        try:
                            _sb_r = get_supabase_client()
                            _sb_r.auth.verify_otp({
                                "token_hash": _rec_th,
                                "type": "recovery"
                            })
                            st.session_state["_password_reset_mode"] = True
                        except Exception as _rec_exc:
                            _rec_err = str(_rec_exc)
                    else:
                        _rec_err = "malformed"
                    try:
                        st.query_params.clear()
                    except Exception:
                        pass
                    if _rec_err:
                        st.session_state["_login_error"] = (
                            "Password reset link is invalid or expired. "
                            "Please request a new one."
                        )
                        st.session_state["_login_mode"] = "forgot"
                        st.rerun()

            _mode      = st.session_state.get("_login_mode", "signin")
            _login_err = st.session_state.get("_login_error", "")
            if _login_err:
                st.error(_login_err)
            if st.session_state.pop("_password_reset_ok", False):
                st.success(
                    "Password updated — please sign in with your new password.")

            # ── STATE 0: Set New Password (recovery link) ─────────────────────
            if st.session_state.get("_password_reset_mode"):
                st.markdown(
                    '<div style="color:#111111;font-size:20px;'
                    'font-weight:700;margin-bottom:20px;">Set New Password</div>',
                    unsafe_allow_html=True)
                _np_pw = st.text_input(
                    "New Password",
                    placeholder="New password (min 8 characters)",
                    type="password",
                    label_visibility="collapsed",
                    key="reset_new_pw_input",
                )
                _np_confirm = st.text_input(
                    "Confirm New Password",
                    placeholder="Confirm new password",
                    type="password",
                    label_visibility="collapsed",
                    key="reset_confirm_pw_input",
                )
                if st.button("Update Password", type="primary",
                             use_container_width=True, key="reset_submit_btn"):
                    _np  = _np_pw.strip()
                    _nc  = _np_confirm.strip()
                    if len(_np) < 8:
                        st.session_state["_login_error"] = (
                            "Password must be at least 8 characters.")
                        st.rerun()
                    elif _np != _nc:
                        st.session_state["_login_error"] = (
                            "Passwords do not match.")
                        st.rerun()
                    else:
                        _upd_err = ""
                        try:
                            _sb_u = get_supabase_client()
                            _sb_u.auth.update_user({"password": _np})
                        except Exception as _upd_exc:
                            _upd_err = str(_upd_exc)
                        if _upd_err:
                            st.session_state["_login_error"] = (
                                f"Could not update password: {_upd_err}")
                            st.rerun()
                        else:
                            st.session_state["_password_reset_mode"] = False
                            st.session_state["_login_mode"]  = "signin"
                            st.session_state["_login_error"] = ""
                            st.session_state["_password_reset_ok"] = True
                            st.rerun()

            # ── STATE 1: Sign In ──────────────────────────────────────────────
            elif _mode == "signin":
                st.markdown(
                    '<div style="color:#111111;font-size:20px;'
                    'font-weight:700;margin-bottom:20px;">Sign In</div>',
                    unsafe_allow_html=True)
                _em_input = st.text_input(
                    "Email address",
                    placeholder="you@company.com",
                    label_visibility="collapsed",
                    key="login_email_input",
                )
                _pw_input = st.text_input(
                    "Password",
                    placeholder="Password",
                    type="password",
                    label_visibility="collapsed",
                    key="login_password_input",
                )
                if st.button("Sign In", type="primary", use_container_width=True,
                             key="login_submit_btn"):
                    _clean = _em_input.strip().lower()
                    _pw    = _pw_input.strip()
                    if not _clean or "@" not in _clean or "." not in _clean.split("@")[-1]:
                        st.session_state["_login_error"] = "Please enter a valid email address."
                        st.rerun()
                    elif not _pw:
                        st.session_state["_login_error"] = "Please enter your password."
                        st.rerun()
                    else:
                        with st.spinner("Signing in…"):
                            _result = sign_in_with_password(_clean, _pw)
                        _first, _second = _result
                        if _first is False:
                            st.session_state["_login_error"] = _second
                            st.rerun()
                        else:
                            st.session_state.pop("_login_error", None)
                            _on_success(_first, _second)

                _lnk1, _lnk2 = st.columns(2)
                with _lnk1:
                    if st.button("Don't have an account? Register",
                                 key="go_signup_btn", use_container_width=True):
                        st.session_state["_login_mode"]  = "signup"
                        st.session_state["_login_error"] = ""
                        st.rerun()
                with _lnk2:
                    if st.button("Forgot Password?",
                                 key="go_forgot_btn", use_container_width=True):
                        st.session_state["_login_mode"]  = "forgot"
                        st.session_state["_login_error"] = ""
                        st.rerun()

            # ── STATE 2: Sign Up ──────────────────────────────────────────────
            elif _mode == "signup":
                st.markdown(
                    '<div style="color:#111111;font-size:20px;'
                    'font-weight:700;margin-bottom:20px;">Create Account</div>',
                    unsafe_allow_html=True)
                if st.session_state.get("_signup_confirm_pending"):
                    _pending_email = st.session_state.get(
                        "_signup_pending_email", "your email")
                    st.markdown(
                        f'<div style="border-left:3px solid #059669;'
                        f'background:#f0fdf4;border-radius:6px;'
                        f'padding:14px 18px;margin-bottom:18px;'
                        f'color:#166534;font-size:14px;">'
                        f'✓ Account created for <strong>{_pending_email}'
                        f'</strong>.<br>Check your email and click the '
                        f'confirmation link, then come back to sign in.'
                        f'</div>',
                        unsafe_allow_html=True)
                    if st.button("Go to Sign In", type="primary",
                                 use_container_width=True,
                                 key="goto_signin_after_confirm"):
                        st.session_state["_signup_confirm_pending"] = False
                        st.session_state["_signup_pending_email"] = ""
                        st.session_state["_login_mode"] = "signin"
                        st.session_state["_login_error"] = ""
                        st.rerun()
                    st.stop()
                _su_email = st.text_input(
                    "Email address",
                    placeholder="you@company.com",
                    label_visibility="collapsed",
                    key="signup_email_input",
                )
                _su_pw = st.text_input(
                    "Password",
                    placeholder="Choose a password",
                    type="password",
                    label_visibility="collapsed",
                    key="signup_password_input",
                )
                _su_confirm = st.text_input(
                    "Confirm Password",
                    placeholder="Confirm password",
                    type="password",
                    label_visibility="collapsed",
                    key="signup_confirm_input",
                )
                if st.button("Create Account", type="primary", use_container_width=True,
                             key="signup_submit_btn"):
                    _clean = _su_email.strip().lower()
                    _pw    = _su_pw.strip()
                    _cpw   = _su_confirm.strip()
                    if not _clean or "@" not in _clean or "." not in _clean.split("@")[-1]:
                        st.session_state["_login_error"] = "Please enter a valid email address."
                        st.rerun()
                    elif len(_pw) < 8:
                        st.session_state["_login_error"] = "Password must be at least 8 characters."
                        st.rerun()
                    elif _pw != _cpw:
                        st.session_state["_login_error"] = "Passwords do not match."
                        st.rerun()
                    else:
                        _su_err_msg = ""
                        _su_resp = None
                        try:
                            _sb = get_supabase_client()
                            _su_resp = _sb.auth.sign_up({"email": _clean, "password": _pw})
                        except Exception as _su_exc:
                            _su_err_msg = str(_su_exc)
                        if _su_err_msg:
                            if "already registered" in _su_err_msg.lower() or \
                               "already exists" in _su_err_msg.lower():
                                _su_err_msg = (
                                    "An account with this email already exists. "
                                    "Please sign in instead."
                                )
                                st.session_state["_login_mode"] = "signin"
                            st.session_state["_login_error"] = _su_err_msg
                            st.rerun()
                        else:
                            _su_user = getattr(_su_resp, "user", None)
                            _su_ids  = getattr(_su_user, "identities", None)
                            if _su_user is not None and _su_ids is not None and len(_su_ids) == 0:
                                st.session_state["_login_error"] = (
                                    "An account with this email already exists. "
                                    "Please sign in instead."
                                )
                                st.session_state["_login_mode"] = "signin"
                                st.rerun()
                            with st.spinner("Creating account…"):
                                _result = sign_in_with_password(_clean, _pw)
                            _first, _second = _result
                            if _first is False:
                                _err_lower = _second.lower() if isinstance(_second, str) else ""
                                if "not confirmed" in _err_lower or "confirm" in _err_lower:
                                    st.session_state["_signup_confirm_pending"] = True
                                    st.session_state["_signup_pending_email"] = _clean
                                    st.session_state.pop("_login_error", None)
                                else:
                                    st.session_state["_login_error"] = _second
                                st.rerun()
                            else:
                                st.session_state.pop("_login_error", None)
                                _on_success(_first, _second)

                if st.button("Already have an account? Sign In",
                             key="go_signin_from_signup_btn", use_container_width=True):
                    st.session_state["_login_mode"]  = "signin"
                    st.session_state["_login_error"] = ""
                    st.rerun()

            # ── STATE 3: Forgot Password ──────────────────────────────────────
            elif _mode == "forgot":
                st.markdown(
                    '<div style="color:#111111;font-size:20px;'
                    'font-weight:700;margin-bottom:20px;">Reset Password</div>',
                    unsafe_allow_html=True)
                _fg_email = st.text_input(
                    "Email address",
                    placeholder="you@company.com",
                    label_visibility="collapsed",
                    key="forgot_email_input",
                )
                if st.button("Send Reset Link", type="primary", use_container_width=True,
                             key="forgot_submit_btn"):
                    _clean = _fg_email.strip().lower()
                    if not _clean or "@" not in _clean or "." not in _clean.split("@")[-1]:
                        st.session_state["_login_error"] = "Please enter a valid email address."
                        st.rerun()
                    else:
                        _fg_ok      = False
                        _fg_err_msg = ""
                        try:
                            _sb = get_supabase_client()
                            _sb.auth.reset_password_for_email(_clean)
                            _fg_ok = True
                        except Exception as _fg_exc:
                            _fg_err_msg = str(_fg_exc)
                        if _fg_err_msg:
                            st.session_state["_login_error"] = _fg_err_msg
                            st.rerun()
                        elif _fg_ok:
                            st.session_state["_login_error"] = ""
                            st.success("Password reset link sent. Check your email.")

                if st.button("Back to Sign In",
                             key="go_signin_from_forgot_btn", use_container_width=True):
                    st.session_state["_login_mode"]  = "signin"
                    st.session_state["_login_error"] = ""
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

        else:
            # ── LOCAL DEV BYPASS ────────────────────────────────────────────
            st.warning("Supabase not configured. Running in local mode.")
            st.markdown("#### Enter your email to continue")
            _em_input = st.text_input(
                "Email address",
                placeholder="you@company.com",
                label_visibility="collapsed",
                key="login_email_input",
            )
            if st.button("Continue →", type="primary", use_container_width=True):
                _clean_dev = _em_input.strip().lower()
                if (
                    _clean_dev
                    and "@" in _clean_dev
                    and "." in _clean_dev.split("@")[-1]
                ):
                    st.session_state.user_email = _clean_dev
                    st.rerun()
                else:
                    st.error(
                        "Please enter a valid email address "
                        "(e.g. you@company.com)."
                    )

if not st.session_state.get("user_email", "").strip():
    _render_login()
    st.stop()

_email = st.session_state.user_email

# ── MIGRATION + PROJECT INIT ──────────────────────────────────────────────────
if not st.session_state.get("_migration_done"):
    _migrate_legacy_to_projects(_email)
    st.session_state["_migration_done"] = True
_all_pids = _list_project_ids(_email)

# Restore or initialise current_project_id
if "current_project_id" not in st.session_state:
    # First load (or after sign-out): pick first available project
    st.session_state.current_project_id = _all_pids[0] if _all_pids else ""

# Guard: if stored pid no longer exists (deleted / session expired) re-anchor
_pid = st.session_state.current_project_id
if _pid and _pid not in _all_pids and not st.session_state.get("_pid_is_new_unsaved"):
    _pid = _all_pids[0] if _all_pids else ""
    st.session_state.current_project_id = _pid

# ── SESSION STATE ─────────────────────────────────────────────────────────────
_pcfg_init = load_project_cfg(_pid, _email) if _pid else {}
_papproved = load_project_approved(_pid, _email) if _pid else []
_pout_dir  = proj_output_dir(_pid, _email) if _pid else None

_defaults = {
    "tab_company_done":   bool(load_company(_email).get("name")),
    "analysis_results":   [],
    "crop_rfi_idx":       0,
    "show_manual_form":   False,
    "generate_output":    "",
    "current_project_id": _pid,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

if not st.session_state.get("_usage_tracked"):
    track_usage("app_load", {"email": _email})
    st.session_state["_usage_tracked"] = True

# ── SIDEBAR ───────────────────────────────────────────────────────────────────
def _reset_project_state():
    """Pop all project-scoped session state keys so a new project starts clean."""
    _old_pid = st.session_state.get("current_project_id", "")
    for _k in [
        "current_project_id", "_pid_is_new_unsaved", "t2_loaded_pid",
        "_sb_labels", "_sb_label_pids",
        "analysis_results", "crop_rfi_idx", "show_manual_form", "generate_output",
        "t5_sel_client", "t5_sel_client_idx",
        "t2_client_form_mode", "t2_confirm_delete", "t2_confirm_del_client",
    ]:
        st.session_state.pop(_k, None)
    for _rk in list(st.session_state.keys()):
        if (_rk.startswith("t2_proj_name_") or
                _rk.startswith("t2_proj_address_") or
                _rk.startswith("t2_proj_number_")):
            st.session_state.pop(_rk, None)
    for _rk in list(st.session_state.keys()):
        if (
            _rk.startswith("t5_doc_path_") or
            _rk.startswith("t5_client_") or
            _rk.startswith("t4_") or
            _rk.startswith("gen_") or
            _rk.startswith("dl_") or
            (_old_pid and _old_pid in _rk and (
                _rk.startswith("t2_") or _rk.startswith("t3_") or
                _rk.startswith("t5_") or _rk.startswith("gen_") or
                _rk.startswith("dl_") or _rk.startswith("ul_") or
                _rk.startswith("lbl_") or _rk.startswith("sv_") or
                _rk.startswith("del_")
            ))
        ):
            st.session_state.pop(_rk, None)


with st.sidebar:
    cfg_sb = load_cfg(_email)
    co_sb  = load_company(_email)
    usage  = load_usage(_email)
    co_nm  = co_sb.get("name", "") or cfg_sb.get("originator", {}).get("company", "RFI Manager")

    # Logo or brand header
    _logo_ok = False
    _logo_bytes = get_asset_bytes(_email, "company_logo.png")
    if _logo_bytes:
        try:
            from PIL import Image as _PIL
            _logo_img = _PIL.open(io.BytesIO(_logo_bytes))
            st.image(_logo_img, width=120)
            st.markdown(f'<div style="color:#6b7280;font-size:11px;margin-top:4px;">{co_nm}</div>', unsafe_allow_html=True)
            _logo_ok = True
        except Exception:
            pass
    if not _logo_ok:
        st.markdown(
            f'<div style="padding:12px 0 12px 0;border-bottom:1px solid #e8eaed;margin-bottom:8px;">'
            f'<div style="color:#1d4ed8;font-size:14px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;">RFI Manager</div>'
            f'<div style="color:#6b7280;font-size:11px;margin-top:2px;">{co_nm}</div>'
            f'</div>',
            unsafe_allow_html=True)

    st.markdown("---")

    # User + usage
    _rfi_count = usage.get("rfi_count", 0)
    _is_paid   = usage.get("is_paid", False)
    st.markdown(
        f'<div style="font-size:11px;color:#374151;margin-bottom:4px;'
        f'text-transform:uppercase;letter-spacing:0.08em;">Logged in as</div>'
        f'<div style="font-size:12px;color:#8892a4;word-break:break-all;">{_email}</div>'
        f'<div style="font-size:11px;color:#{"F0A500" if not _is_paid and _rfi_count >= FREE_LIMIT else "4a5568"};'
        f'margin-top:6px;">'
        f'RFIs used: {_rfi_count} / {"∞" if _is_paid else str(FREE_LIMIT)}'
        f'{"  🔒 Upgrade to unlock" if not _is_paid and _rfi_count >= FREE_LIMIT else ""}'
        f'</div>',
        unsafe_allow_html=True)
    if st.button("Sign Out", key="sb_signout"):
        sign_out_user()  # deletes DB session row, signs out Supabase, clears state
        st.rerun()

    st.markdown("---")

    # ── Project switcher ──────────────────────────────────────────────────────
    # Keys cleared whenever the active project changes
    _TAB_CLEAR = [
        "analysis_results", "crop_rfi_idx",
        "show_manual_form", "generate_output",
        "t5_sel_client",        # full client dict in Generate tab
        "t5_sel_client_idx",    # selectbox integer index in Generate tab
        "t2_client_form_mode",  # client edit/add form in Project Setup
        "t2_loaded_pid",
        "t2_confirm_delete",    # delete-project confirmation state
        "t2_confirm_del_client",  # delete-client confirmation state
        "t3_loaded_pid",
    ]

    _sb_all_pids = _list_project_ids(_email)
    _sb_pid      = st.session_state.get("current_project_id", "")

    if not st.session_state.get("tab_company_done"):
        st.markdown(
            '<div class="info-box warn" style="font-size:12px;margin:4px 0 10px;">'
            'Complete Company Setup first'
            '</div>',
            unsafe_allow_html=True)
    else:
        st.markdown('<div class="sb-project-label">Project</div>', unsafe_allow_html=True)

        if not _sb_all_pids:
            # No projects at all — guide user to create one
            if not st.session_state.get("_pid_is_new_unsaved"):
                st.session_state.current_project_id = ""
            st.markdown(
                '<div class="info-box warn" style="font-size:12px;margin:4px 0 10px;">'
                'No projects yet — click below to create your first project.'
                '</div>',
                unsafe_allow_html=True)
            _sb_sel_pid = ""
        else:
            # Build display labels: project name with pid as fallback
            if st.session_state.get("_sb_label_pids") != _sb_all_pids:
                st.session_state["_sb_labels"] = [
                    (load_project_cfg(p, _email).get("name") or p)
                    for p in _sb_all_pids
                ]
                st.session_state["_sb_label_pids"] = list(_sb_all_pids)
            _sb_labels = st.session_state["_sb_labels"]
            _sb_cur_idx = _sb_all_pids.index(_sb_pid) if _sb_pid in _sb_all_pids else 0

            _sb_sel_idx = st.selectbox(
                "project_selector",
                range(len(_sb_all_pids)),
                format_func=lambda i: _sb_labels[i],
                index=_sb_cur_idx,
                key="sb_proj_select",
                label_visibility="collapsed",
            )
            _sb_sel_pid = _sb_all_pids[_sb_sel_idx]

            # Switch project if selection changed
            if _sb_sel_pid != _sb_pid and not st.session_state.get("_pid_is_new_unsaved"):
                st.session_state.current_project_id = _sb_sel_pid
                for _rk in _TAB_CLEAR:
                    st.session_state.pop(_rk, None)
                for _rk in list(st.session_state.keys()):
                    if (_rk.startswith("t2_proj_name_") or
                            _rk.startswith("t2_proj_address_") or
                            _rk.startswith("t2_proj_number_")):
                        st.session_state.pop(_rk, None)
                for _rk in list(st.session_state.keys()):
                    if (
                        _rk.startswith("t5_doc_path_") or
                        _rk.startswith("t5_client_") or
                        _rk.startswith("t4_") or
                        _rk.startswith("gen_") or
                        _rk.startswith("dl_") or
                        (_sb_pid and _sb_pid in _rk and (
                            _rk.startswith("t2_") or _rk.startswith("t3_") or
                            _rk.startswith("t5_") or _rk.startswith("gen_") or
                            _rk.startswith("dl_") or _rk.startswith("ul_") or
                            _rk.startswith("lbl_") or _rk.startswith("sv_") or
                            _rk.startswith("del_")
                        ))
                    ):
                        st.session_state.pop(_rk, None)
                st.session_state.pop("_sb_labels", None)
                st.session_state.pop("_sb_label_pids", None)
                st.rerun()

        if st.button("＋ New Project", key="sb_new_proj_btn", use_container_width=True):
            _next_pid = _new_project_id(_email)
            _reset_project_state()
            st.session_state["current_project_id"] = _next_pid
            st.session_state["_pid_is_new_unsaved"] = True
            st.session_state["_goto_tab2"] = True
            st.rerun()


    st.markdown("---")
    st.markdown(
        '<div style="text-align:center;color:#374151;font-size:11px;padding:4px 0 6px;">'
        'RFI Manager &nbsp;v1.0.0-beta</div>',
        unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  TABS
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.pop("_goto_tab2", False):
    components.html(
        """<script>
(function(){
    function _clickTab2(){
        var tabs=window.parent.document.querySelectorAll(
            '[data-baseweb="tab"]');
        if(tabs.length>=2){tabs[1].click();}
        else{setTimeout(_clickTab2,200);}
    }
    setTimeout(_clickTab2,200);
})();
</script>""",
        height=0,
    )

try:
    t1, t2, t3, t4, t5, t6 = st.tabs([
        "🏢  Company Setup",
        "📋  Project Setup",
        "🔍  Analyse Drawings",
        "✂️  Crop and Annotate",
        "📄  Generate RFI",
        "📊  Register",
    ])
    st.info("Beta Version — We are actively improving this tool. Share your feedback at ajohnsudhakar@gmail.com")

    def _tab_guard():
        if not st.session_state.get("user_email", "").strip():
            st.info("Please log in to continue.")
            return False
        return True

    with t1:
        if _tab_guard(): render_tab_company(_email)
    with t2:
        if _tab_guard(): render_tab_project(_email)
    with t3:
        if _tab_guard(): render_tab_analyse(_email)
    with t4:
        if _tab_guard(): render_tab_crop(_email)
    with t5:
        if _tab_guard(): render_tab_generate(_email)
    with t6:
        if _tab_guard(): render_tab_register(_email)

except Exception as _app_err:
    log_error(_app_err, "main tab render")
    st.error(
        "**Something went wrong.** The error has been logged.\n\n"
        f"Error: {type(_app_err).__name__}: {_app_err}"
    )
