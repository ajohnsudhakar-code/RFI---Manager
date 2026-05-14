"""
data_layer.py — All data access, file I/O, Supabase, and utility helpers.
Imported by app.py and every ui_*.py tab module.
"""

import json, os, re, io, sys, uuid, shutil, traceback
from pathlib import Path
from datetime import date, datetime

# ── Optional: Supabase ────────────────────────────────────────────────────────
try:
    from supabase import create_client as _sb_create, Client as _SbClient, ClientOptions as _SbClientOptions
    _supabase_ok = True
except ImportError:
    _supabase_ok = False
    _SbClientOptions = None  # type: ignore

try:
    from storage3.utils import StorageException as _StorageException
    _storage3_ok = True
except ImportError:
    _StorageException = None  # type: ignore
    _storage3_ok = False

# ── Streamlit (needed for @st.cache_data and session_state snap cache) ────────
try:
    import streamlit as st
    _st_ok = True
except ImportError:
    _st_ok = False

# ══════════════════════════════════════════════════════════════════════════════
#  PATHS
# ══════════════════════════════════════════════════════════════════════════════
# _frozen is True only in a PyInstaller .exe build — always False in Streamlit web deployment
_frozen = getattr(sys, "frozen", False)
if _frozen:
    BASE           = Path(sys.executable).resolve().parent
    SCRIPTS_PY_DIR = Path(sys._MEIPASS) / "scripts"
else:
    BASE           = Path(__file__).resolve().parent.parent
    SCRIPTS_PY_DIR = Path(__file__).resolve().parent

CFG_PATH      = BASE / "scripts" / "config.json"
PROJECTS_DIR  = BASE / "projects"
LOG_PATH      = BASE / "error_log.txt"

FREE_LIMIT = 5

PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════════════════════════════════════
#  ERROR LOGGING
# ══════════════════════════════════════════════════════════════════════════════
def _log_error(fn_name: str, e: Exception):
    """Append a timestamped traceback entry to error_log.txt."""
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.now()}] {fn_name}: {traceback.format_exc()}\n")
    except Exception:
        pass  # Can't log the logger failure


def log_error(exc: Exception, context: str = ""):
    """Public alias — keeps compatibility with callers outside data_layer."""
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as _lf:
            _lf.write(f"\n{'='*60}\n")
            _lf.write(f"Time   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            if context:
                _lf.write(f"Where  : {context}\n")
            _lf.write(traceback.format_exc())
    except Exception:
        pass


def _warn(msg: str):
    """Show st.warning only when Streamlit is running."""
    if _st_ok:
        st.warning(msg)


def _is_not_found_error(e: Exception) -> bool:
    """Return True if e is a Supabase Storage 'object not found' error (expected)."""
    if _storage3_ok and _StorageException is not None and isinstance(e, _StorageException):
        msg = str(e).lower()
        return "not_found" in msg or "object not found" in msg
    # Fallback: check string representation for any exception type
    msg = str(e).lower()
    return "not_found" in msg or "object not found" in msg


# ══════════════════════════════════════════════════════════════════════════════
#  SECRETS + SUPABASE CLIENT
# ══════════════════════════════════════════════════════════════════════════════
def _secret(key: str, default: str = "") -> str:
    try:
        val = st.secrets.get(key, default)
        if val and not str(val).startswith("paste-your-"):
            return str(val)
    except Exception as e:
        _log_error("_secret", e)
    return default


_sb_client = None

def _get_supabase():
    """Return the best available Supabase client.

    Priority:
      1. Session-state client (_sb_auth_client) — created by get_supabase_client()
         and holds the authenticated session after login.  Using it here means
         RLS policies see the logged-in user and all database reads succeed.
      2. Module-level singleton (_sb_client) — unauthenticated fallback for
         CLI / import use and any code path where session_state is unavailable.
    """
    global _sb_client
    # ── 1. Prefer the authenticated session-state client ─────────────────────
    if _st_ok:
        _auth = st.session_state.get("_sb_auth_client")
        if _auth is not None:
            return _auth
    # ── 2. Fall back to module-level unauthenticated singleton ────────────────
    if _sb_client is not None:
        return _sb_client
    if not _supabase_ok:
        return None
    try:
        url = _secret("SUPABASE_URL")
        key = _secret("SUPABASE_KEY")
        if not url or not key:
            return None
        if not url.startswith("http"):
            url = f"https://{url}.supabase.co"
        _opts = _SbClientOptions(flow_type="implicit") if _SbClientOptions else None
        _sb_client = _sb_create(url, key, options=_opts) if _opts else _sb_create(url, key)
    except Exception as e:
        _log_error("_get_supabase", e)
    return _sb_client


def get_supabase_client():
    """Session-state-cached Supabase client for auth operations.
    Returns None if Supabase is not configured or unavailable.
    Fixes cached-None bug: if session_state holds None, evicts and retries."""
    if not _st_ok or not _supabase_ok:
        return None
    # Evict cached None so we always retry creation after a transient failure
    cached = st.session_state.get("_sb_auth_client")
    if cached is not None:
        return cached
    if "_sb_auth_client" in st.session_state:
        del st.session_state["_sb_auth_client"]
    try:
        url = _secret("SUPABASE_URL")
        key = _secret("SUPABASE_KEY")
        if not url or not key:
            _log_error("get_supabase_client",
                       Exception(f"Missing secrets — URL={'(empty)' if not url else 'ok'} "
                                 f"KEY={'(empty)' if not key else 'ok'}"))
            return None
        if not url.startswith("http"):
            url = f"https://{url}.supabase.co"
        # Disable PKCE (see _get_supabase comment)
        _opts = _SbClientOptions(flow_type="implicit") if _SbClientOptions else None
        client = _sb_create(url, key, options=_opts) if _opts else _sb_create(url, key)
        st.session_state["_sb_auth_client"] = client
        return client
    except Exception as e:
        _log_error("get_supabase_client", e)
        return None


def _get_storage_client():
    """Return authenticated Supabase client for storage operations.
    Prefers session-cached auth client so RLS policies pass.
    Falls back to module-level client for non-Streamlit contexts."""
    if _st_ok:
        _auth = st.session_state.get("_sb_auth_client")
        if _auth is not None:
            return _auth
    return _get_supabase()


def sign_in_with_password(email: str, password: str):
    """Sign in with email and password.

    Returns (user_obj, session_obj) on success.
    Returns (False, error_message_str) on failure.
    """
    sb = get_supabase_client()
    if not sb:
        _msg = (
            "Could not connect to Supabase. "
            "Check SUPABASE_URL and SUPABASE_KEY in secrets.toml."
        )
        _log_error("sign_in_with_password", Exception(_msg))
        return (False, _msg)
    try:
        response = sb.auth.sign_in_with_password({"email": email, "password": password})
        _user = getattr(response, "user", None)
        _sess = getattr(response, "session", None)
        if _user is None and _sess is not None:
            _user = getattr(_sess, "user", None)
        if _user is None:
            return (False, "Invalid email or password.")
        return (_user, _sess)
    except Exception as e:
        _raw_msg = (
            getattr(e, "message", None)
            or getattr(e, "msg", None)
            or str(e)
            or ""
        )
        _user_msg = str(_raw_msg).strip()
        if not _user_msg or _user_msg.lower() in ("none", ""):
            _user_msg = "Invalid email or password."
        _log_error("sign_in_with_password", e)
        return (False, _user_msg)



def save_user_session(session_key: str, email: str, access_token: str,
                      refresh_token: str, expires_at: int):
    """Upsert a session row into user_sessions keyed by session_key (UUID)."""
    sb = _get_supabase()
    if not sb:
        return
    try:
        sb.table("user_sessions").upsert({
            "session_key":   session_key,
            "email":         email,
            "access_token":  access_token,
            "refresh_token": refresh_token,
            "expires_at":    int(expires_at) if expires_at else 0,
        }, on_conflict="session_key").execute()
    except Exception as e:
        _log_error("save_user_session", e)


def load_user_session(session_key: str) -> dict:
    """Return the session row for session_key, or None if not found / expired."""
    sb = _get_supabase()
    if not sb:
        return None
    try:
        import time as _t
        res = (
            sb.table("user_sessions")
            .select("*")
            .eq("session_key", session_key)
            .execute()
        )
        rows = res.data or []
        if not rows:
            return None
        row = rows[0]
        # Touch last_used_at
        try:
            sb.table("user_sessions").update({"last_used_at": int(_t.time())}).eq(
                "session_key", session_key
            ).execute()
        except Exception:
            pass
        return row
    except Exception as e:
        _log_error("load_user_session", e)
        return None


def delete_user_session(session_key: str):
    """Delete the session row for session_key."""
    if not session_key:
        return
    sb = _get_supabase()
    if not sb:
        return
    try:
        sb.table("user_sessions").delete().eq("session_key", session_key).execute()
    except Exception as e:
        _log_error("delete_user_session", e)


def sign_out_user():
    """Sign out from Supabase, delete the DB session row, and clear all state."""
    # Delete the persisted session from the DB before clearing session_state
    if _st_ok:
        _sid = st.session_state.get("_sid", "")
        if _sid:
            delete_user_session(_sid)
    sb = get_supabase_client()
    if sb:
        try:
            sb.auth.sign_out()
        except Exception as e:
            _log_error("sign_out_user", e)
    if _st_ok:
        st.session_state.clear()
        try:
            st.query_params.clear()
        except Exception:
            pass


def track_usage(event: str, meta: dict = None):
    try:
        sb = _get_storage_client()
        if sb:
            sb.table("usage_events").insert({
                "event":      event,
                "meta":       json.dumps(meta or {}),
                "created_at": datetime.utcnow().isoformat(),
            }).execute()
    except Exception as e:
        _log_error("track_usage", e)


# ── Per-user config path (available early so load_cfg/save_cfg can use it) ────
def _user_cfg_path(email: str) -> Path:
    """Return the per-user company.json path inside the projects/<email_folder>/ dir.

    Falls back to the legacy scripts/config.json when email is empty so
    non-auth code paths still work.
    """
    if not email:
        return CFG_PATH
    folder = re.sub(r"\.", "_dot_", email.strip().lower().replace("@", "_at_"))
    d = PROJECTS_DIR / folder
    d.mkdir(parents=True, exist_ok=True)
    return d / "company.json"


# ══════════════════════════════════════════════════════════════════════════════
#  USER CONFIG (global — company, originator, api_key, settings)
# ══════════════════════════════════════════════════════════════════════════════
def _default_cfg() -> dict:
    return {
        "project":    {"name": "", "address": "", "project_number": ""},
        "client":     {"company": "", "attn": "", "email": "", "phone": "", "role": ""},
        "originator": {"name": "", "company": "", "email": "", "phone": "", "title": ""},
        "paths":      {"pdf": ""},
        "settings":   {"max_snapshots": 5},
        "api_key":    "",
        "version":    "1.0.0-beta",
        "company":    {"name": "", "address": "", "country": "", "postcode": "", "website": ""},
        "sheet_map":  {},
    }


def _deep_merge(base: dict, overlay: dict) -> dict:
    result = base.copy()
    for k, v in overlay.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_cfg(email: str = None) -> dict:
    default = _default_cfg()
    sb = _get_supabase()
    if sb and email:
        try:
            res = sb.table("user_config").select("config_data").eq("email", email).execute()
            if res.data and res.data[0].get("config_data"):
                return _deep_merge(default, res.data[0]["config_data"])
        except Exception as e:
            _log_error("load_cfg[supabase]", e)
            _warn("Could not connect to database. Working in offline mode.")
    # File fallback — reads from per-user company.json (never another user's data)
    cfg_file = _user_cfg_path(email)
    try:
        with open(cfg_file) as f:
            return _deep_merge(default, json.load(f))
    except FileNotFoundError:
        return default
    except Exception as e:
        _log_error("load_cfg[file]", e)
        return default


def save_cfg(cfg: dict, email: str = None):
    sb = _get_supabase()
    if sb and email:
        try:
            sb.table("user_config").upsert(
                {"email": email, "config_data": cfg},
                on_conflict="email",
            ).execute()
        except Exception as e:
            _log_error("save_cfg[supabase]", e)
            _warn("Could not connect to database. Working in offline mode.")
    # File write — atomic: write temp then rename so a crash mid-write never corrupts the file
    cfg_file = _user_cfg_path(email)
    try:
        cfg_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = cfg_file.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(cfg, f, indent=2)
        tmp.replace(cfg_file)   # atomic on same filesystem
    except Exception as e:
        _log_error("save_cfg[file]", e)
        _warn("Could not save data. Check error_log.txt for details.")


def load_company(email: str = None) -> dict:
    default = {"name": "", "address": "", "country": "", "postcode": "", "website": ""}
    return load_cfg(email).get("company", default)




# ── USAGE ─────────────────────────────────────────────────────────────────────
def load_usage(email: str) -> dict:
    default = {"rfi_count": 0, "is_paid": False}
    sb = _get_storage_client()
    if not sb:
        return default
    try:
        res = sb.table("rfi_usage").select("rfi_count,is_paid").eq("email", email).execute()
        if res.data:
            return {
                "rfi_count": res.data[0].get("rfi_count", 0),
                "is_paid":   res.data[0].get("is_paid", False),
            }
        sb.table("rfi_usage").insert({"email": email, "rfi_count": 0, "is_paid": False}).execute()
    except Exception as e:
        _log_error("load_usage", e)
        _warn("Could not connect to database. Working in offline mode.")
    return default


def increment_usage(email: str):
    sb = _get_storage_client()
    if not sb:
        return
    try:
        usage = load_usage(email)
        sb.table("rfi_usage").upsert(
            {"email": email, "rfi_count": usage["rfi_count"] + 1, "is_paid": usage["is_paid"]},
            on_conflict="email",
        ).execute()
    except Exception as e:
        _log_error("increment_usage", e)
        _warn("Could not connect to database. Working in offline mode.")


# ── ASSETS ────────────────────────────────────────────────────────────────────
def get_asset_bytes(email: str, asset_name: str):
    sb = _get_storage_client()
    if sb:
        try:
            return sb.storage.from_("rfi-manager-files").download(f"{email_to_folder(email)}/{asset_name}")
        except Exception as e:
            if not _is_not_found_error(e):
                _log_error("get_asset_bytes", e)
    local = BASE / "scripts" / asset_name
    if local.exists():
        return local.read_bytes()
    return None


def upload_asset(email: str, asset_name: str, data: bytes):
    sb = _get_storage_client()
    if sb:
        try:
            sb.storage.from_("rfi-manager-files").upload(
                f"{email_to_folder(email)}/{asset_name}", data, {"content-type": "image/png", "upsert": "true"}
            )
            # Supabase succeeded — delete any stale local copy so fallback
            # cannot return outdated data
            try:
                _stale = BASE / "scripts" / asset_name
                if _stale.exists():
                    _stale.unlink()
            except Exception:
                pass
            return  # skip local write
        except Exception as e:
            _log_error("upload_asset[supabase]", e)
            # Fall through to local write
    local = BASE / "scripts" / asset_name
    try:
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(data)
    except Exception as e:
        _log_error("upload_asset[local]", e)
        _warn("Could not save data. Check error_log.txt for details.")


def upload_project_pdf(email: str, pid: str, filename: str, data: bytes) -> bool:
    """Upload a PDF to Supabase Storage rfi-manager-files bucket.
    Returns True on success, False on failure.
    Storage path: {email_folder}/{pid}/drawings/{filename}
    """
    sb = _get_storage_client()
    if not sb:
        return False
    try:
        storage_path = f"{email_to_folder(email)}/{pid}/drawings/{filename}"
        sb.storage.from_("rfi-manager-files").upload(
            storage_path, data, {"content-type": "application/pdf", "upsert": "true"}
        )
        return True
    except Exception as e:
        _log_error("upload_project_pdf", e)
        return False


def upload_project_snapshot(email: str, pid: str, filename: str, data: bytes) -> bool:
    """Upload a snapshot PNG to Supabase Storage snapshots bucket.
    Returns True on success, False on failure.
    Storage path: {email_folder}/{pid}/snapshots/{filename}
    """
    sb = _get_storage_client()
    if not sb:
        return False
    try:
        storage_path = f"{email_to_folder(email)}/{pid}/snapshots/{filename}"
        sb.storage.from_("snapshots").upload(
            storage_path, data, {"content-type": "image/png", "upsert": "true"}
        )
        return True
    except Exception as e:
        _log_error("upload_project_snapshot", e)
        return False


def sync_snapshots_from_supabase(pid: str, email: str, snaps_dir) -> int:
    """Download any snapshots missing from local snaps_dir from Supabase Storage.

    Storage path: {email_folder}/{pid}/snapshots/
    Bucket: snapshots

    Returns the number of files newly downloaded (0 if all already local or
    Supabase is unavailable). Never raises — all errors are logged and swallowed.
    """
    sb = _get_storage_client()
    if not sb:
        return 0
    folder = f"{email_to_folder(email)}/{pid}/snapshots"
    try:
        items = sb.storage.from_("snapshots").list(folder)
    except Exception as e:
        _log_error("sync_snapshots_from_supabase/list", e)
        return 0
    if not items:
        return 0
    downloaded = 0
    for item in items:
        name = item.get("name", "") if isinstance(item, dict) else str(item)
        if not name or name == ".emptyFolderPlaceholder":
            continue
        local_path = Path(snaps_dir) / name
        if local_path.exists():
            continue
        try:
            data = sb.storage.from_("snapshots").download(f"{folder}/{name}")
            if data:
                local_path.write_bytes(data)
                downloaded += 1
        except Exception as e:
            _log_error(f"sync_snapshots_from_supabase/download/{name}", e)
    return downloaded


def delete_project_snapshot(email: str, pid: str, filename: str) -> bool:
    """Delete a snapshot PNG from Supabase Storage snapshots bucket.
    Returns True if deleted or file did not exist, False on unexpected error.
    Storage path: {email_folder}/{pid}/snapshots/{filename}
    """
    sb = _get_storage_client()
    if not sb:
        return False
    try:
        storage_path = f"{email_to_folder(email)}/{pid}/snapshots/{filename}"
        sb.storage.from_("snapshots").remove([storage_path])
        return True
    except Exception as e:
        if _is_not_found_error(e):
            return True
        _log_error("delete_project_snapshot", e)
        return False


def upload_project_document(email: str, pid: str, filename: str, data: bytes) -> bool:
    """Upload a generated Word document to Supabase Storage rfi-manager-files bucket.
    Returns True on success, False on failure.
    Storage path: {email_folder}/{pid}/output/{filename}
    """
    sb = _get_storage_client()
    if not sb:
        return False
    try:
        storage_path = f"{email_to_folder(email)}/{pid}/output/{filename}"
        sb.storage.from_("rfi-manager-files").upload(
            storage_path, data,
            {"content-type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
             "upsert": "true"}
        )
        return True
    except Exception as e:
        _log_error("upload_project_document", e)
        return False

def delete_project(email: str, pid: str) -> bool:
    """Soft-delete a project in Supabase and remove local folder.
    Sets deleted_at to now; local filesystem folder is removed.
    Supabase Storage files are intentionally left untouched.
    """
    sb = _get_storage_client()
    if not sb:
        return False
    try:
        from datetime import timezone
        sb.table("projects").update({
            "deleted_at": datetime.now(timezone.utc).isoformat()
        }).eq("email", email).eq("project_id", pid).execute()
    except Exception as e:
        _log_error("delete_project", e)
        return False
    local_dir = _user_projects_dir(email) / pid
    if local_dir.exists():
        try:
            shutil.rmtree(str(local_dir))
        except Exception as _rm_err:
            _log_error("delete_project[rmtree]", _rm_err)
    return True


# ── REGISTER ──────────────────────────────────────────────────────────────────
def load_register(email: str, pid: str = "") -> list:
    sb = _get_storage_client()
    if sb:
        try:
            q = (sb.table("rfi_register")
                   .select("*")
                   .eq("email", email)
                   .order("rfi_number"))
            if pid:
                q = q.eq("project_id", pid)
            res = q.execute()
            return res.data or []
        except Exception as e:
            _log_error("load_register", e)
            _warn("Could not connect to database. Working in offline mode.")
    return []



# ══════════════════════════════════════════════════════════════════════════════
#  PROJECT DATA LAYER
# ══════════════════════════════════════════════════════════════════════════════

def email_to_folder(email: str) -> str:
    """Sanitise an email address for use as a filesystem folder name.

    Examples:
        john@gmail.com      →  john_at_gmail_dot_com
        a.b@co.example.com  →  a_dot_b_at_co_dot_example_dot_com
    """
    return re.sub(r"\.", "_dot_", email.strip().lower().replace("@", "_at_"))


def _user_projects_dir(email: str) -> Path:
    """Return (and lazily create) the per-user projects subdirectory.

    If email is empty, falls back to the shared PROJECTS_DIR so that
    non-auth code paths (scripts, tests) still work.
    """
    if not email:
        return PROJECTS_DIR
    d = PROJECTS_DIR / email_to_folder(email)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _list_project_ids(email: str = "") -> list:
    """List project IDs for the given user (sorted). Supabase primary, local fallback."""
    if not email:
        return []
    sb = _get_storage_client()
    if sb:
        try:
            res = (sb.table("projects")
                     .select("project_id")
                     .eq("email", email)
                     .is_("deleted_at", "null")
                     .order("project_id")
                     .execute())
            return [r["project_id"] for r in res.data] if res.data else []
        except Exception as e:
            _log_error("_list_project_ids[supabase]", e)
    # Local fallback — only reached when Supabase is unavailable
    d = _user_projects_dir(email)
    if not d.exists():
        return []
    return sorted([p.name for p in d.iterdir() if p.is_dir()])


def _new_project_id(email: str = "") -> str:
    existing = set(_list_project_ids(email))
    n = 1
    while True:
        pid = f"proj_{n:03d}"
        if pid not in existing:
            return pid
        n += 1


def proj_dir(pid: str, email: str = "") -> Path:
    return _user_projects_dir(email) / pid


def _default_project_cfg() -> dict:
    return {"name": "", "address": "", "project_number": "", "pdf": "", "sheet_map": {}}


def load_project_cfg(pid: str, email: str = "") -> dict:
    default = _default_project_cfg()
    sb = _get_storage_client()
    if sb and email and pid:
        try:
            res = (sb.table("projects")
                     .select("config_data")
                     .eq("email", email)
                     .eq("project_id", pid)
                     .maybe_single()
                     .execute())
            if res and res.data and res.data.get("config_data"):
                return _deep_merge(default, res.data["config_data"])
        except Exception as e:
            _log_error("load_project_cfg[supabase]", e)
    # Local fallback
    try:
        with open(proj_dir(pid, email) / "config.json") as f:
            return _deep_merge(default, json.load(f))
    except FileNotFoundError:
        return default
    except Exception as e:
        _log_error("load_project_cfg", e)
        return default


def save_project_cfg(pid: str, cfg: dict, email: str = ""):
    sb = _get_storage_client()
    if sb and email and pid:
        try:
            sb.table("projects").upsert({
                "email":       email,
                "project_id":  pid,
                "config_data": cfg,
                "deleted_at":  None,
            }, on_conflict="email,project_id").execute()
        except Exception as e:
            _log_error("save_project_cfg[supabase]", e)
            _warn("Could not connect to database. Working in offline mode.")
    # Local fallback — atomic write so a crash mid-write never corrupts the file
    cfg_file = proj_dir(pid, email) / "config.json"
    try:
        cfg_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = cfg_file.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(cfg, f, indent=2)
        tmp.replace(cfg_file)
    except Exception as e:
        _log_error("save_project_cfg[file]", e)
        _warn("Could not save data. Check error_log.txt for details.")


def load_project_clients(pid: str, email: str = "") -> list:
    sb = _get_storage_client()
    if sb and email and pid:
        try:
            res = (sb.table("projects")
                     .select("clients_data")
                     .eq("email", email)
                     .eq("project_id", pid)
                     .maybe_single()
                     .execute())
            if res and res.data and res.data.get("clients_data") is not None:
                data = res.data["clients_data"]
                return data if isinstance(data, list) else []
            return []  # Supabase connected but project not found — don't use stale local file
        except Exception as e:
            _log_error("load_project_clients[supabase]", e)
    # Local fallback — only reached when Supabase client is unavailable
    try:
        with open(proj_dir(pid, email) / "clients.json") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except FileNotFoundError:
        return []
    except Exception as e:
        _log_error("load_project_clients", e)
        return []


def save_project_clients(pid: str, clients: list, email: str = ""):
    sb = _get_storage_client()
    if not sb:
        _warn("Not connected to database — client list could not be saved.")
        return
    if sb and email and pid:
        try:
            sb.table("projects").upsert({
                "email":        email,
                "project_id":   pid,
                "clients_data": clients,
                "deleted_at":   None,
            }, on_conflict="email,project_id").execute()
        except Exception as e:
            _log_error("save_project_clients[supabase]", e)
            raise


def load_project_approved(pid: str, email: str = "") -> list:
    sb = _get_storage_client()
    if sb and email and pid:
        try:
            res = (sb.table("projects")
                     .select("approved_rfis_data")
                     .eq("email", email)
                     .eq("project_id", pid)
                     .maybe_single()
                     .execute())
            if res and res.data and res.data.get("approved_rfis_data") is not None:
                data = res.data["approved_rfis_data"]
                return data if isinstance(data, list) else []
            return []  # Supabase connected, project not found — no stale fallback
        except Exception as e:
            _log_error("load_project_approved[supabase]", e)
    # Local fallback
    try:
        with open(proj_dir(pid, email) / "approved_rfis.json") as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except Exception as e:
        _log_error("load_project_approved", e)
        return []


def save_project_approved(pid: str, rfis: list, email: str = ""):
    # Write to Supabase
    sb = _get_storage_client()
    if sb and email and pid:
        try:
            sb.table("projects").upsert({
                "email":             email,
                "project_id":        pid,
                "approved_rfis_data": rfis,
                "deleted_at":        None,
            }, on_conflict="email,project_id").execute()
        except Exception as e:
            _log_error("save_project_approved[supabase]", e)
    # Also write locally
    d = proj_dir(pid, email)
    d.mkdir(parents=True, exist_ok=True)
    try:
        with open(d / "approved_rfis.json", "w") as f:
            json.dump(rfis, f, indent=2)
    except Exception as e:
        _log_error("save_project_approved[local]", e)
        _warn("Could not save data. Check error_log.txt for details.")


def load_project_scan_results(pid: str, email: str = "") -> list:
    sb = _get_storage_client()
    if sb and email and pid:
        try:
            res = (sb.table("projects")
                     .select("scan_results_data")
                     .eq("email", email)
                     .eq("project_id", pid)
                     .maybe_single()
                     .execute())
            if res and res.data and res.data.get("scan_results_data") is not None:
                data = res.data["scan_results_data"]
                return data if isinstance(data, list) else []
            return []  # Supabase connected, project not found — no stale fallback
        except Exception as e:
            _log_error("load_project_scan_results[supabase]", e)
    # Local fallback
    try:
        with open(proj_dir(pid, email) / "scan_results.json") as f:
            return json.load(f)
    except FileNotFoundError:
        return []
    except Exception as e:
        _log_error("load_project_scan_results", e)
        return []


def save_project_scan_results(pid: str, results: list, email: str = ""):
    sb = _get_storage_client()
    if sb and email and pid:
        try:
            sb.table("projects").upsert({
                "email":             email,
                "project_id":        pid,
                "scan_results_data": results,
                "deleted_at":        None,
            }, on_conflict="email,project_id").execute()
        except Exception as e:
            _log_error("save_project_scan_results[supabase]", e)
    d = proj_dir(pid, email)
    d.mkdir(parents=True, exist_ok=True)
    try:
        with open(d / "scan_results.json", "w") as f:
            json.dump(results, f, indent=2)
    except Exception as e:
        _log_error("save_project_scan_results[local]", e)
        _warn("Could not save data. Check error_log.txt for details.")


def load_project_captions(pid: str, email: str = "") -> dict:
    sb = _get_storage_client()
    if sb and email and pid:
        try:
            res = (sb.table("projects")
                     .select("captions_data")
                     .eq("email", email)
                     .eq("project_id", pid)
                     .maybe_single()
                     .execute())
            if res and res.data and res.data.get("captions_data") is not None:
                data = res.data["captions_data"]
                return data if isinstance(data, dict) else {}
            return {}  # Supabase connected, project not found — no stale fallback
        except Exception as e:
            _log_error("load_project_captions[supabase]", e)
    # Local fallback
    try:
        with open(proj_snapshots_dir(pid, email) / "snap_captions.json") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        _log_error("load_project_captions", e)
        return {}


def save_project_captions(pid: str, captions: dict, email: str = ""):
    sb = _get_storage_client()
    if sb and email and pid:
        try:
            sb.table("projects").upsert({
                "email":         email,
                "project_id":    pid,
                "captions_data": captions,
                "deleted_at":    None,
            }, on_conflict="email,project_id").execute()
        except Exception as e:
            _log_error("save_project_captions[supabase]", e)
    snaps = proj_snapshots_dir(pid, email)
    try:
        with open(snaps / "snap_captions.json", "w") as f:
            json.dump(captions, f, indent=2)
    except Exception as e:
        _log_error("save_project_captions[local]", e)
        _warn("Could not save data. Check error_log.txt for details.")


def proj_snapshots_dir(pid: str, email: str = "") -> Path:
    d = proj_dir(pid, email) / "snapshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def proj_output_dir(pid: str, email: str = "") -> Path:
    d = proj_dir(pid, email) / "output"
    d.mkdir(parents=True, exist_ok=True)
    return d


def resolve_pdf_path(pid: str, email: str = ""):
    """Return the absolute Path to this project's PDF, or None if not found.

    Handles three cases:
    1. Stored path is already relative (e.g. 'drawings/foo.pdf') — resolve against proj_dir.
    2. Stored path is absolute and exists — copy to drawings/, update config to relative.
    3. Stored path is absolute but missing — check if drawings/<filename> exists (already
       migrated by another machine) and update config to relative; else return None.
    """
    pcfg = load_project_cfg(pid, email)
    stored = pcfg.get("pdf", "")
    if not stored:
        return None

    p = Path(stored)

    # Case 1: relative path
    if not p.is_absolute():
        resolved = proj_dir(pid, email) / p
        if resolved.exists():
            return resolved
        # Local file missing — try Supabase Storage download
        if email:
            sb = _get_storage_client()
            if sb:
                try:
                    storage_path = f"{email_to_folder(email)}/{pid}/drawings/{p.name}"
                    pdf_bytes = sb.storage.from_("rfi-manager-files").download(storage_path)
                    if pdf_bytes:
                        resolved.parent.mkdir(parents=True, exist_ok=True)
                        resolved.write_bytes(pdf_bytes)
                        return resolved
                except Exception as e:
                    if not _is_not_found_error(e):
                        _log_error("resolve_pdf_path[supabase download]", e)
        return None

    # Cases 2 & 3: absolute path
    drawings_dir = proj_dir(pid, email) / "drawings"
    drawings_dir.mkdir(parents=True, exist_ok=True)
    rel = Path("drawings") / p.name

    if p.exists():
        # Case 2: absolute exists — copy to drawings/ if not already there
        dest = proj_dir(pid, email) / rel
        if not dest.exists():
            shutil.copy2(str(p), str(dest))
        # Update config to relative
        pcfg["pdf"] = str(rel)
        if email:
            save_project_cfg(pid, pcfg, email)
        return dest

    # Case 3: absolute missing — check drawings/
    dest = proj_dir(pid, email) / rel
    if dest.exists():
        pcfg["pdf"] = str(rel)
        if email:
            save_project_cfg(pid, pcfg, email)
        return dest

    return None


# ── PER-PROJECT SHEET MAP ─────────────────────────────────────────────────────
def load_project_sheet_map(pid: str, email: str = "") -> dict:
    try:
        cfg = load_project_cfg(pid, email)
        raw = cfg.get("sheet_map", {})
        if raw:
            return {int(k): v for k, v in raw.items()}
    except Exception as e:
        _log_error("load_project_sheet_map[cfg]", e)
    # Local fallback for offline use
    try:
        with open(proj_dir(pid, email) / "sheet_map.json") as f:
            return {int(k): v for k, v in json.load(f).items()}
    except FileNotFoundError:
        return {}
    except Exception as e:
        _log_error("load_project_sheet_map", e)
        return {}


def save_project_sheet_map(pid: str, sheet_map: dict, email: str = ""):
    try:
        cfg = load_project_cfg(pid, email)
        cfg["sheet_map"] = {str(k): v for k, v in sheet_map.items()}
        save_project_cfg(pid, cfg, email)
    except Exception as e:
        _log_error("save_project_sheet_map", e)
        _warn("Could not save data. Check error_log.txt for details.")


# ── PER-PROJECT REGISTER ──────────────────────────────────────────────────────
def load_project_register(pid: str, email: str = "") -> list:
    if email and pid:
        sb = _get_storage_client()
        if sb:
            try:
                res = (sb.table("rfi_register")
                         .select("*")
                         .eq("email", email)
                         .eq("project_id", pid)
                         .order("rfi_number")
                         .execute())
                return res.data or []
            except Exception as e:
                _log_error("load_project_register[supabase]", e)
                _warn("Could not connect to database. Working in offline mode.")
    try:
        with open(proj_dir(pid, email) / "register.json") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except FileNotFoundError:
        return []
    except Exception as e:
        _log_error("load_project_register", e)
        return []


def save_project_register(pid: str, rows: list, email: str = ""):
    d = proj_dir(pid, email)
    d.mkdir(parents=True, exist_ok=True)
    try:
        with open(d / "register.json", "w") as f:
            json.dump(rows, f, indent=2)
    except Exception as e:
        _log_error("save_project_register", e)
        _warn("Could not save data. Check error_log.txt for details.")


def upsert_project_register_rows(pid: str, approved: list, proj_name: str, email: str = ""):
    """Add/update register rows from an approved list; preserve existing statuses."""
    rows   = load_project_register(pid, email)
    by_rfi = {r["rfi_number"]: i for i, r in enumerate(rows)}
    today  = date.today().isoformat()
    for iss in approved:
        rn  = get_rfi_num(iss, 1)
        _rbd_local_raw = iss.get("response_required_by", "")
        _rbd_local = _rbd_local_raw.strip() if (
            isinstance(_rbd_local_raw, str)
            and _rbd_local_raw.strip()
            and _rbd_local_raw.strip().lower() != "none"
        ) else None
        row = {
            "rfi_number":           rn,
            "project_name":         proj_name,
            "sheet_reference":      iss.get("sheets", ""),
            "category":             iss.get("category", ""),
            "priority":             iss.get("priority", ""),
            "response_required_by": _rbd_local,
            "description":          iss.get("description", "")[:500],
            "status":               "Open",
            "date_raised":          today,
        }
        if rn in by_rfi:
            row["status"] = rows[by_rfi[rn]].get("status", "Open")
            rows[by_rfi[rn]] = row
        else:
            rows.append(row)
    save_project_register(pid, rows, email)
    # Also upsert into Supabase rfi_register table
    sb = _get_storage_client()
    if sb and email and pid:
        try:
            for iss in approved:
                rn = get_rfi_num(iss, 1)
                # Find current status from local rows to preserve it
                _status = "Open"
                for r in rows:
                    if r.get("rfi_number") == rn:
                        _status = r.get("status", "Open")
                        break
                _rbd_raw = iss.get("response_required_by", "")
                _rbd_val = _rbd_raw.strip() if (
                    isinstance(_rbd_raw, str)
                    and _rbd_raw.strip()
                    and _rbd_raw.strip().lower() != "none"
                ) else None
                sb.table("rfi_register").upsert({
                    "email":                email,
                    "project_id":           pid,
                    "project_name":         proj_name,
                    "rfi_number":           rn,
                    "sheet_reference":      iss.get("sheets", ""),
                    "category":             iss.get("category", ""),
                    "priority":             iss.get("priority", ""),
                    "response_required_by": _rbd_val,
                    "description":          iss.get("description", "")[:500],
                    "status":               _status,
                    "date_raised":          today,
                }, on_conflict="email,project_id,rfi_number").execute()
        except Exception as e:
            _log_error("upsert_project_register_rows[supabase]", e)
            _warn("Could not sync register to database. Working in offline mode.")


def update_project_register_status(pid: str, rfi_num: int, status: str, email: str = ""):
    rows = load_project_register(pid, email)
    for row in rows:
        if row.get("rfi_number") == rfi_num:
            row["status"] = status
    save_project_register(pid, rows, email)
    sb = _get_storage_client()
    if sb and email and pid:
        try:
            (sb.table("rfi_register")
               .update({"status": status})
               .eq("email", email)
               .eq("project_id", pid)
               .eq("rfi_number", rfi_num)
               .execute())
        except Exception as e:
            _log_error("update_project_register_status[supabase]", e)
            _warn("Could not sync status to database. Working in offline mode.")


def _migrate_legacy_to_projects(email: str = ""):
    """Idempotent migration: move project data into the per-user folder.

    Three cases handled (in order of priority):
    0. Supabase already has project rows for this user → nothing to do.
    1. User-scoped dir already has projects → nothing to do.
    2. Semi-legacy: projects/proj_001/ exists (flat, not yet scoped) → move into user folder.
    3. Fully-legacy: only scripts/config.json exists → recreate in user folder.
    """
    if not email:
        return

    # Case 0: Supabase already has data for this user — no migration needed
    sb = _get_supabase()
    if sb:
        try:
            res = (sb.table("projects")
                     .select("project_id", count="exact")
                     .eq("email", email)
                     .limit(1)
                     .execute())
            if res.data:
                return
        except Exception as e:
            _log_error("_migrate_legacy_to_projects[supabase check]", e)

    user_dir = _user_projects_dir(email)

    # Case 1: already migrated
    if user_dir.exists() and any(user_dir.iterdir()):
        return

    # Case 2: semi-legacy flat layout — projects/proj_001/ exists at top level
    _semi_legacy_pids = [
        p.name for p in PROJECTS_DIR.iterdir()
        if p.is_dir() and p.name.startswith("proj_") and p != user_dir
    ] if PROJECTS_DIR.exists() else []

    if _semi_legacy_pids:
        for _spid in _semi_legacy_pids:
            _src = PROJECTS_DIR / _spid
            _dst = user_dir / _spid
            if not _dst.exists():
                try:
                    shutil.copytree(str(_src), str(_dst))
                except Exception as e:
                    _log_error("_migrate_legacy_to_projects[semi-legacy move]", e)
        return

    # Case 3: fully-legacy — recreate from scripts/config.json
    pid = "proj_001"
    proj_dir(pid, email).mkdir(parents=True, exist_ok=True)
    try:
        old = {}
        if CFG_PATH.exists():
            with open(CFG_PATH) as f:
                old = json.load(f)
        save_project_cfg(pid, {
            "name":           old.get("project", {}).get("name",           ""),
            "address":        old.get("project", {}).get("address",        ""),
            "project_number": old.get("project", {}).get("project_number", ""),
            "pdf":            old.get("paths",   {}).get("pdf",            ""),
            "sheet_map":      old.get("sheet_map", {}),
        }, email)
    except Exception as e:
        _log_error("_migrate_legacy_to_projects[cfg]", e)
    try:
        _legacy_contacts = BASE / "scripts" / "contacts.json"
        if _legacy_contacts.exists():
            with open(_legacy_contacts) as f:
                contacts = json.load(f)
            if isinstance(contacts, list):
                save_project_clients(pid, contacts, email)
    except Exception as e:
        _log_error("_migrate_legacy_to_projects[contacts]", e)
    try:
        _legacy_approved = BASE / "scripts" / "approved_rfis.json"
        if _legacy_approved.exists():
            with open(_legacy_approved) as f:
                approved = json.load(f)
            if isinstance(approved, list) and approved:
                save_project_approved(pid, approved, email)
    except Exception as e:
        _log_error("_migrate_legacy_to_projects[approved]", e)


# ── MISC HELPERS ──────────────────────────────────────────────────────────────
def get_rfi_num(issue: dict, fallback: int = 1) -> int:
    val = issue.get("rfi_number", fallback)
    if isinstance(val, str):
        m = re.search(r"\d+", val)
        return int(m.group()) if m else fallback
    return int(val)



def add_label_to_image(img, label: str):
    """Stamp an annotation label banner onto a PIL image."""
    if not label or label == "None":
        return img
    try:
        from PIL import ImageDraw, ImageFont
        img = img.copy()
        draw = ImageDraw.Draw(img)
        w, h = img.size
        bh = max(28, h // 18)
        draw.rectangle([(0, 0), (w, bh)], fill=(240, 165, 0))
        try:
            font = ImageFont.truetype("arial.ttf", bh - 6)
        except Exception:
            font = ImageFont.load_default()
        draw.text((8, 4), label.upper(), fill=(8, 12, 20), font=font)
    except Exception as e:
        _log_error("add_label_to_image", e)
    return img





@st.cache_data
def pdf_page_to_pil(pdf_path: str, page_num: int, zoom: float = 1.5):
    """Render a PDF page to a PIL Image. Cached to avoid re-render on every rerun."""
    import fitz
    from PIL import Image
    doc  = fitz.open(str(pdf_path))
    page = doc[page_num - 1]
    pix  = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    img  = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    doc.close()
    return img
