# RFI Manager — Fix History

## Purpose
This file archives all resolved bugs and security fixes for reference.
Claude Code does not need to read this file automatically.
Only read it when specifically asked for historical context.

## Archive Date
May 2026

---

## Authentication Fixes

**Bug #4 — Supabase unauthenticated client**
`_get_supabase()` returns an unauthenticated client. RLS blocks all queries,
returns None, causes AttributeError.
Fix: Always use `_get_storage_client()` for any RLS-protected operation.
File: data_layer.py

**BUG-14 — Email confirmation flow broken on registration** ✅ RESOLVED
After `sign_up()` succeeded, code immediately called `sign_in_with_password()`
which returned "Email not confirmed" as a red error. User had no idea the
account was created.
Fix: Intercept "not confirmed" / "confirm" error after `sign_in_with_password()`.
Set `_signup_confirm_pending` flag, show green confirmation banner with
"Go to Sign In" button.
File: app.py

**BUG-15 — "User already registered" raw error on signup** ✅ RESOLVED
Raw Supabase error shown directly. User stayed on signup screen with no guidance.
Fix: Intercept "already registered"/"already exists" in except block. Replace
with friendly message and auto-switch to signin screen.
File: app.py

**BUG-16 — Password reset link went to Supabase hosted page** ✅ RESOLVED
Forgot Password sent reset email but link went to Supabase's own page, not the app.
User had to find the app URL manually.
Fix: Added recovery token detection in `_render_login()`. Detects `type=recovery`
in query params, calls `set_session()`, shows Set New Password screen, calls
`update_user()` on submit.
Additional fixes applied in follow-up session:
- Supabase Site URL updated to https://rfi-manager.streamlit.app/
- Redirect URL updated to https://rfi-manager.streamlit.app/
- Supabase reset password email template updated to use `token_hash` as query
  parameter instead of hash fragment
- app.py recovery handler updated from `set_session(access_token)` to
  `verify_otp(token_hash)` — lines 574–583
- Malformed reset link now handled gracefully (Scenario 16b)
File: app.py

**BUG-17 — Sidebar hide/show feature caused permanent sidebar loss** ✅ RESOLVED
Custom Hide Panel / Show Panel buttons and native Streamlit collapse arrow
all removed. Sidebar is now permanently visible.
Removed: `sidebar_visible` session state, Hide Panel button, Show Panel block,
`stHeader` and `collapsedControl` CSS rules.
Additional CSS added to hide `stSidebarResizeHandle`, `stSidebarNav`, and
`stHeader` elements.
File: app.py

**BUG-18 — Signup duplicate email shows raw error with confirmation ON** ✅ RESOLVED
When email confirmation is ON, Supabase silently succeeds on `sign_up()` for
duplicate emails instead of raising an error. The friendly "email already exists"
detection never fires. User sees generic "Invalid login credentials" with no guidance.
Fix: `sign_up()` response inspected for empty identities list. If empty, friendly
error shown and user redirected to signin. `getattr` used safely to prevent
AttributeError. `st.rerun()` outside all try/except.
File: app.py

---

## st.rerun() Fixes

**Bug #1 — st.rerun() inside try/except (root principle)**
Streamlit 1.55.0: `RerunException` inherits from `Exception`. If `st.rerun()`
is inside `try/except` it gets caught silently — the rerun never happens, but
no error is shown.
Fix: Always put `st.rerun()` in the else clause or after the try/except block closes.
PERMANENT RULE — never put st.rerun() inside try/except.

**Bug #2 — Success messages wiped by rerun**
`st.success()` before `st.rerun()` disappears immediately because the rerun
clears the widget state before the user sees it.
Fix: Use session state flag — set flag before rerun, check flag at top of
function on next render, show message, pop flag.

**st.rerun() audit — ALL 7 violations fixed** ✅
Fixed across all files in a dedicated audit session:
- app.py line 527 — session restore on login
- ui_analyse.py line 273 — Format with AI manual entry
- ui_project.py line 235 — Save Project Details
- ui_company.py line 165 — logo upload
- ui_company.py line 202 — signature upload
- ui_company.py line 224 — Save Company Details
- ui_register.py line 209 — Update RFI Status
Pattern used: session state flag set inside try, `st.rerun()` called after
the try/except block closes.

---

## Security Fixes

**S1 — Cross-tenant asset isolation** ✅
File: data_layer.py — `get_asset_bytes()`
Removed local file fallback (`BASE/scripts/company_logo.png` etc.).
On Streamlit Cloud all users share the container filesystem — the local fallback
returned the wrong user's logo/signature.
Fix: Return None when Supabase read fails. No asset is safer than the wrong
user's asset.

**S2 — Cross-tenant asset write** ✅
File: data_layer.py — `upload_asset()`
Removed stale-file cleanup and local write fallback.
Fix: Return on Supabase success; call `_warn()` on failure with a clear
user-facing message. Never write assets to shared local disk.

**S3 — Cross-tenant snapshot isolation** ✅
File: generate_rfi.py — `_abs()`
Removed `_HERE` and `_BASE_EARLY` directory fallbacks from image resolution.
Fix: Only `SNAPSHOTS_DIR` (per-user path) is searched. Return bare filename
if not found; never look in shared script directories.

**S4 — Cross-tenant logo/signature defaults** ✅
File: generate_rfi.py
Removed `_HERE`-based default paths for `LOGO_IMG` and `SIGNATURE_IMG`.
Fix: Set to empty string when Supabase path is missing or invalid. Word doc
renders without image rather than showing another user's logo.

**S5 — AI scan cost protections** ✅
File: ui_analyse.py — 3 protections added:
- Protection 1: Scan caching — existing results trigger "Use Existing /
  Re-scan Anyway" confirmation before any API call is made.
- Protection 2: Large PDF gate — PDFs > 30 pages show credit warning and
  batch count; user must confirm before scan runs.
- Protection 3: Daily scan counter — FREE tier: 3 scans/day, PAID: 20/day.
  Counter stored in `rfi_usage` table (`ai_scans_today` + `ai_scans_date` columns).
  Supabase offline → counter returns 0 → scans allowed (acceptable trade-off).

**S6 — Supabase schema — rfi_usage table** ✅
Added two columns (run in SQL Editor):
```
ALTER TABLE rfi_usage ADD COLUMN IF NOT EXISTS ai_scans_today integer DEFAULT 0;
ALTER TABLE rfi_usage ADD COLUMN IF NOT EXISTS ai_scans_date  text    DEFAULT '';
```
New data_layer functions: `load_scan_usage(email)` and `increment_scan_usage(email)`.
Both follow the existing `load_usage` / `increment_usage` pattern.

---

## Tab 1 Fixes (ui_company.py)

**Bug #3 — Widget value= with key= conflict**
Using both `value=` and `key=` on the same widget causes a Streamlit warning
and unpredictable behaviour.
Fix: Use `key=` only. Seed initial values via session state.

**Bug #31 — Edit mode showing empty fields** ✅ RESOLVED
When user clicked Edit Details, form fields showed empty even though data existed
in Supabase.
Root cause: `setdefault()` never overwrites existing session state keys. Keys
existed as empty strings from a prior run.
Fix: On Edit Details button click, explicitly overwrite all 9 form session state
keys with current values from `cfg` before `st.rerun()`.
File: ui_company.py

---

## Tab 2 Fixes (ui_project.py + app.py project management)

**Bug #9 — Email variable shadow in _render_client_card** ✅ RESOLVED
ui_project.py: local variable `email = client.get("email", "")` silently shadowed
the `email` function parameter (the logged-in user's email). All data layer calls
inside the function used the client's contact email as the user identity — deletes
and saves operated on the wrong account.
Fix: Rename to `_c_email` and update the one reference to it.
File: ui_project.py

**Bug #12 — Sidebar project switcher overriding unsaved new project** ✅ RESOLVED
When a new project was created but not yet saved, the pid guard block at the top
of the dashboard reset `current_project_id` back to the first saved project on every
rerun, making it impossible to save a new project.
Fix: Set `_pid_is_new_unsaved = True` on New Project button click, clear it on Save
success. Guard both the pid guard block and the project switcher selectbox change
handler with this flag.
File: app.py

**Bug #13 — Premature save_project_cfg call on PDF upload** ✅ RESOLVED
ui_project.py: PDF upload section called `save_project_cfg` immediately after writing
the file to disk, before the user clicked Save. This overwrote any unsaved changes
in the name/address/number fields.
Fix: Remove the premature save call. The pdf path is written on the main Save button only.
File: ui_project.py

**Bug #14 — st.rerun() after PDF upload wiping form fields** ✅ RESOLVED
ui_project.py: `st.rerun()` was called after the PDF upload success message. This
re-seeded the form fields from `load_project_cfg()` which returns empty for a new
unsaved project — wiping whatever the user had typed in name, address, and project number.
Fix: Remove `st.rerun()` from the PDF upload handler entirely. The selectbox updates
on the next natural rerun (e.g. Save click).
File: ui_project.py

**Bug #15 — PDF only saved locally — not available on cloud or other machines** ✅ RESOLVED
`resolve_pdf_path()` checked local disk only. On Streamlit Cloud or any other machine,
the local file did not exist so Tab 3 and Tab 4 both showed "Please upload a PDF"
even though the PDF had been uploaded.
Fix: `upload_project_pdf()` now uploads to Supabase Storage at
`{email_folder}/{pid}/drawings/{filename}` on every upload. `resolve_pdf_path()`
now falls back to downloading from Supabase Storage and writing to local disk as
cache when local file is missing.
Files: data_layer.py, ui_project.py

**Bug #19 — Soft-deleted projects reappearing after deletion** ✅ RESOLVED
data_layer.py: `_list_project_ids()` used `if res.data:` to guard the Supabase
response. When all projects were soft-deleted, Supabase returned `[]` (success but
empty). The falsy check caused fallthrough to the local filesystem which still had
the old project folders. Deleted projects reappeared immediately.
Fix: Changed to `return [r["project_id"] for r in res.data] if res.data else []`
so the function always returns immediately on a successful Supabase query, even when
the result is empty. `delete_project()` sets `deleted_at` timestamp via soft-delete.
File: data_layer.py

**Bug #20 — Sidebar overwriting current_project_id when no projects exist** ✅ RESOLVED
app.py: The no-projects branch forced `current_project_id = ""` on every rerun. After
clicking ＋ New Project (which assigns a new pid), the very next rerun wiped it back to
empty, making it impossible to save a first project after all projects were deleted.
Fix: Wrapped the forced clear in
`if not st.session_state.get("_pid_is_new_unsaved"):` so it only runs when no new
unsaved project is in progress.
File: app.py

**Bug #21 — pid-scoped form widget keys bleeding across projects** ✅ RESOLVED
ui_project.py / app.py: The form widgets for project name, address, and project number
use pid-scoped keys (`t2_proj_name_{pid}`, etc.). When switching or deleting projects,
the old pid's keys were not cleared. The new project's form showed the old project's values.
Fix: Clear all `t2_proj_name_*`, `t2_proj_address_*`, and `t2_proj_number_*` keys from
session state whenever switching projects, creating a new project, or after a delete
completes. Clearing happens in: the `_project_deleted` flag handler, the auto-create
block, the Danger Zone delete handler, and the sidebar ＋ New Project button handler.
Files: ui_project.py, app.py

**Bug #22 — save_project_cfg raises on Supabase failure — no fallback** ✅ RESOLVED
data_layer.py: `save_project_cfg` raised RuntimeError if Supabase was None and
re-raised bare on any DB exception. No local file fallback existed. A slow connection
mid-save caused a full app crash.
Fix: Removed RuntimeError raise and bare re-raise. Added `_warn()` on Supabase failure.
Added atomic local write to `proj_dir(pid, email) / "config.json"` using
`.tmp → .replace()` — consistent with `save_cfg` and what `load_project_cfg` already reads.
File: data_layer.py

**BUG-20 — New Project button did not redirect to Tab 2 (Project Setup)** ✅ RESOLVED
After clicking "+ New Project", app stayed on current tab. User had to manually click
the Project Setup tab.
Fix: Set `_goto_tab2` flag before `st.rerun()` in the New Project handler. After rerun,
inject JavaScript via `st.components.v1.html` to click the second tab button using
`[data-baseweb="tab"]` selector with 200ms delay. Flag is consumed with `pop()` so
JS fires exactly once.
File: app.py

**BUG-21 — Old project data persisted on tabs after project switch** ✅ RESOLVED
After switching projects or clicking New Project, Tabs 3, 4, 5 still showed previous
project scan results, snapshots, and generated documents.
Fix: Added dynamic key clearing loop in both `_reset_project_state()` and the project
switch handler. Clears all keys starting with `t5_doc_path_`, `t5_client_`, `t4_`,
`gen_`, `dl_`, and any key containing the old project ID that also starts with a known
tab prefix (`t2_`, `t3_`, `t5_`, `gen_`, `dl_`, `ul_`, `lbl_`, `sv_`, `del_`).
`_old_pid` captured before pop loop so pid is available for matching.
File: app.py

---

## Tab 3 Fixes (ui_analyse.py)

**Bug #27 — _PRIORITY_OPTS UnboundLocalError** ✅ RESOLVED
`_PRIORITY_OPTS` was defined inside the `if results:` block. The manual entry form
(`tab_manual`) renders before that block and referenced `_PRIORITY_OPTS` at module
scope — causing `UnboundLocalError` whenever the manual tab was shown before any
scan results.
Fix: Moved `_PRIORITY_OPTS` to module level (line 21), removed the inner definition.
File: ui_analyse.py

**Bug #28 — Empty string rejected by Postgres date column (error 22007)** ✅ RESOLVED
`upsert_project_register_rows()` sent `iss.get("response_required_by", "")` which
returns `""` for RFIs with no date set. Supabase `rfi_register.response_required_by`
is typed `date` — Postgres rejected `""` with code 22007.
Fix: Changed to `iss.get("response_required_by") or None` in both the local row dict
and the Supabase upsert payload. Empty string and None both map to NULL.
File: data_layer.py

**Bug #30 — approved_rfis_data not synced when editing RFIs in Tab 3** ✅ RESOLVED
The edit form save handler called `save_project_scan_results()` only. Tab 5 reads from
`load_project_approved()` which reads `approved_rfis_data` — so priority and
`response_required_by` edits were never written to `approved_rfis_data`, leaving the
Word document with empty values for those fields.
Fix: Added `save_project_approved()` call in the edit form save handler in ui_analyse.py,
rebuilding the approved list from session state after each edit.
File: ui_analyse.py

**BUG-12 — _PRIORITY_OPTS UnboundLocalError on Python 3.14** ✅ RESOLVED
Tab 3 crashed immediately on load with:
`UnboundLocalError: cannot access local variable '_PRIORITY_OPTS'`
Root cause: Python 3.14 changed free variable resolution in nested scopes — the
module-level `_PRIORITY_OPTS` became ambiguous inside `render_tab_analyse()` under
certain execution paths.
Fix: Added `_PRIORITY_OPTS = ["Critical", "High", "Normal", "Low"]` as first line
inside `render_tab_analyse()` at line 70 of ui_analyse.py.
File: ui_analyse.py

**BUG-13 — Empty date string crashing Supabase register save** ✅ RESOLVED
Every RFI generation failed to save to Supabase `rfi_register` with:
`APIError code 22007: invalid input syntax for type date: ""`
Root cause: `response_required_by` field sent as `""` instead of NULL.
The "or None" guard failed for values like `"None"` string or whitespace.
Fix: Added sanitiser at lines 1117–1121 and 1152–1156 of data_layer.py.
Sanitiser rejects `""`, whitespace, and literal `"None"` — sends NULL to Postgres.
Valid date strings like `"2026-06-01"` pass through unchanged.
File: data_layer.py

**BUG-19 — Empty label warning on Python 3.14** ✅ RESOLVED
`st.text_area("", ...)` at line 242 generates a warning in Python 3.14 — may
become an exception in future versions.
Fix: Changed label from `""` to `"RFI Description"` with
`label_visibility="collapsed"`. Warning eliminated on Python 3.14.
File: ui_analyse.py

---

## Tab 4 Fixes (ui_crop.py)

**Bug #16 — Redundant crop tool in Tab 4** ✅ RESOLVED
ui_crop.py: When streamlit-cropper was installed, Tab 4 showed a crop tool after
screenshot upload — asking the user to crop an image they had already precisely
cropped with Windows Snipping Tool before uploading.
Fix: Removed the `if _cropper_ok / else` branching entirely. Tab 4 now always shows
a direct preview of the uploaded image without any crop tool, regardless of whether
streamlit-cropper is installed.
File: ui_crop.py

**Bug #18 — tab_crop_done never cleared and prematurely set True** ✅ RESOLVED
app.py: `_TAB_CLEAR` did not include `tab_crop_done`. When a user re-analysed and
approved different RFIs, the crop tab stayed marked done. The generated Word doc
silently had missing images.
ui_crop.py: `tab_crop_done` was also set True immediately after any single snapshot
save — a project with 8 RFIs showed Crop as done after 1 snapshot.
Fix: Added `tab_crop_done` to `_TAB_CLEAR` in app.py. Removed the premature True set
from the save block in ui_crop.py. Also clear it when `save_project_approved` is
called in ui_analyse.py.
Files: app.py, ui_crop.py, ui_analyse.py

**Bug #24 — Snapshots not loading from Supabase on cloud reruns** ✅ RESOLVED
generate_rfi.py, ui_generate.py, ui_crop.py: `_local_snaps()` uses `Path.exists()`
on local disk only. On cloud, all snapshots live in Supabase Storage (bucket: "snapshots").
Tab 4 showed 0 snaps after a page refresh. Generated Word docs had no images.
Fix: Added `sync_snapshots_from_supabase(pid, email, snaps_dir)` to data_layer.py.
It calls `sb.storage.from_("snapshots").list(folder)` then downloads any missing files
to `snaps_dir`. Called in ui_crop.py and ui_generate.py immediately after
`proj_snapshots_dir()` so `_local_snaps()` always finds files locally.
Files: data_layer.py, ui_crop.py, ui_generate.py

**Bug #25 — Sheet map lost on every cloud rerun** ✅ RESOLVED
data_layer.py: `load_project_sheet_map()` and `save_project_sheet_map()` read and
wrote a local `sheet_map.json` file only. On cloud the filesystem is wiped on every
rerun so the sheet map was rebuilt from scratch on every AI scan.
Fix: Rewrote both functions to use `config_data` in the projects Supabase table.
`save_project_sheet_map()` now calls `load_project_cfg()` → sets `cfg["sheet_map"]`
→ calls `save_project_cfg()`. `load_project_sheet_map()` reads
`cfg.get("sheet_map", {})` with int-key conversion.
Local `sheet_map.json` retained as read-only fallback.
File: data_layer.py

**Bug #26 — Snapshot captions lost on every cloud rerun** ✅ RESOLVED
ui_crop.py: `_load_captions()` and `_save_captions()` read and wrote
`snap_captions.json` in the local snapshots directory. On cloud this file was
lost on every rerun.
Fix: Added `load_project_captions()` and `save_project_captions()` to data_layer.py.
Both follow the dual-layer pattern (Supabase first, local JSON fallback).
`captions_data` jsonb column added to projects table in Supabase.
Four call sites in ui_crop.py updated to use the new data_layer functions.
Files: data_layer.py, ui_crop.py

---

## Data Layer & Infrastructure Fixes

**Bug #5 — Upsert file_options boolean**
`{"upsert": True}` crashes httpx in supabase-py 2.10.0.
Fix: Always use `{"upsert": "true"}` as a string, never a boolean.
File: data_layer.py

**Bug #6 — Local fallback masking Supabase failures**
When Supabase is connected but a row is not found, code was falling through to the
local file. Stale local data appeared.
Fix: When Supabase is connected, return `[]` on not found. Never fall through to
local file when Supabase is reachable.
File: data_layer.py

**Bug #7 — New project generating same pid**
`_new_project_id()` called `_list_project_ids()` which could return an empty list,
causing `proj_001` to be generated again.
Fix: Iterate from n=1 upward, skip any pid already in the existing set. Always finds
the first unused slot.
File: data_layer.py

**Bug #8 — Silent save failures**
Save functions caught exceptions and called `_warn()` which was wiped by subsequent
`st.rerun()`. User saw false success.
Fix: Re-raise exceptions so the UI handler catches and shows `st.error()` with
`st.stop()` to prevent rerun wipe.
File: data_layer.py

**Bug #10 — Duplicate unique index on projects table**
Supabase projects table had two unique constraints on `(email, project_id)`.
The second upsert failed with a duplicate key violation on the second index.
Fix: Drop the duplicate index in Supabase SQL Editor, keep one constraint.

**Bug #11 — maybe_single() returning None instead of response object**
supabase-py 2.10.0: `.maybe_single()` returns None (not a response object) when no
row matches. Calling `.data` on None raises AttributeError.
Affected: `load_project_cfg`, `load_project_clients`, `load_project_approved`.
Fix: Guard with `if res and res.data` before accessing `res.data`.
File: data_layer.py

**Bug #23 — rfi_register missing project_id column and UNIQUE constraint** ✅ RESOLVED
app.py: The SQL comment block for CREATE TABLE rfi_register was missing
`project_id text,` and the `UNIQUE(email, project_id, rfi_number)` constraint.
Code used `on_conflict="email,project_id,rfi_number"` so all upserts failed.
Fix: Updated SQL comment block in app.py. Ran the following in Supabase:
```
ALTER TABLE rfi_register ADD COLUMN IF NOT EXISTS project_id text;
ALTER TABLE rfi_register DROP CONSTRAINT IF EXISTS rfi_register_email_project_id_rfi_number_key;
ALTER TABLE rfi_register ADD CONSTRAINT rfi_register_email_project_id_rfi_number_key
    UNIQUE (email, project_id, rfi_number);
```
Supabase already had the correct schema — only the comment needed updating.
File: app.py

**BUG-01 — _migrate_legacy_to_projects() NameError** ✅ RESOLVED
References `CONTACTS_JSON` which was deleted. `NameError` on every new user login.
Fix: Replace `if CONTACTS_JSON.exists():` with local variable:
```
_legacy_contacts = BASE / "scripts" / "contacts.json"
if _legacy_contacts.exists():
```
File: data_layer.py

**BUG-03 — load_register misuse** ✅ RESOLVED
Fixed as a side effect of removing the workflow status bar — `load_register` and
`tab_generate_done` removed from app.py; `load_register` is no longer called in
the sidebar.
File: app.py

**BUG-05 — _migrate_legacy_to_projects() runs every page load** ✅ RESOLVED
Fix: Guard with `st.session_state.get("_migration_done")` flag.
`_migration_done` guard confirmed at lines 778–780 of app.py.
File: app.py

**BUG-11 — analysis_results not cleared on project switch** ✅ RESOLVED
Switching projects left the previous project's scan results in session state.
User could approve Project A's issues while viewing Project B.
Fix: Added `"analysis_results"` and `"t3_loaded_pid"` to the `_TAB_CLEAR` tuple.
Confirmed in `_TAB_CLEAR` list at lines 884 and 892 of app.py.
File: app.py

---

## Tab 5 Fixes (ui_generate.py)

**Bug #17 — Build log showing in Tab 5 UI** ✅ RESOLVED
ui_generate.py: After generating a Word document, a white log box appeared showing
internal build steps (Building RFI-001, snap sizes, etc.). Developer output not
needed by users.
Fix: Removed the `if result["logs"]` block from the success handler.
File: ui_generate.py

**Bug #29 — Two-click Generate bug in Tab 5** ✅ RESOLVED
After clicking Generate, the Download button stayed grey until a second click.
The `_btn_col` rendered before the `if _clicked:` handler ran — `t5_doc_path`
was set in session state but the button was already rendered without it.
Fix: Added `st.rerun()` after `upsert_project_register_rows()` in ui_generate.py,
inside `if result["success"]:` and outside all try/except blocks.
File: ui_generate.py

---

## Dead Code Cleanup

**DC-02/10 — open_file() and subprocess import removed** ✅ RESOLVED
`open_file()` function and `subprocess` import removed from data_layer.py.
File: data_layer.py

**DC-03 — if __name__ == "__main__": block removed** ✅ RESOLVED
CLI block removed from generate_rfi.py.
File: generate_rfi.py
