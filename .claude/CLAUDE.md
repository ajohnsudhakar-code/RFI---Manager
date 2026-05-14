# RFI Manager — Project Intelligence File
# Location: C:\Users\Admin\Desktop\RFI_Manager_Public\.claude\CLAUDE.md
# Read this file completely before starting any task.
# This is the single source of truth for the entire project.

---

## WHO IS JOHN

John Sudhakar is a Civil Engineer with 12 years of experience
transitioning to self-employment through AI. He is building
RFI Manager as a commercial product for the construction industry.
John is not a developer — he reviews plans and approves changes
but does not write code himself.

Every decision must consider: will a non-technical engineer 
in New Zealand or the UK be able to use this without training?

---

## WHAT WE ARE BUILDING

RFI Manager is a cloud-based SaaS platform for construction 
engineers. It replaces the manual process of writing RFIs 
(Requests for Information) by:

1. Accepting uploaded PDF drawing sets
2. Using AI to scan drawings and identify design issues
3. Allowing engineers to crop and annotate relevant drawing areas
4. Generating professional Word document RFIs automatically
5. Maintaining a tracked register of all RFIs per project

TARGET USERS:
- Civil engineers, structural engineers, project managers
- Construction contractors, subcontractors
- Quantity surveyors, estimators

TARGET MARKET: New Zealand, Australia, UK initially

BUSINESS MODEL:
- Free tier: 5 RFIs lifetime
- Paid tier: unlimited RFIs
- Upgrade contact: ajohnsudhakar@gmail.com

---

## TECHNOLOGY STACK

| Component | Technology | Version | Notes |
|---|---|---|---|
| Frontend | Streamlit | 1.55.0 | NEVER change version |
| Deployment | Streamlit Cloud | — | https://rfi-manager.streamlit.app/ |
| Backend | Python | 3.14 | Windows local, Linux cloud |
| Database | Supabase PostgreSQL | latest | All data scoped by email |
| Storage | Supabase Storage | latest | Two private buckets |
| Auth | Supabase Auth | latest | Email + password only |
| AI | Claude API (Anthropic) | claude-opus-4-6 | Never say "Claude" in UI — say "AI" |
| Documents | python-docx | latest | Word document generation |
| PDF | PyMuPDF | latest | PDF rendering and cropping |

Run command: py -m streamlit run scripts/app.py

Theme config: .streamlit/config.toml (created UX session). Settings: base=light,
primaryColor=#1d4ed8, backgroundColor=#f5f6f8, secondaryBackgroundColor=#ffffff,
textColor=#111111

### Dependency Version Constraints

| Package | Pinned Version | Reason |
|---|---|---|
| streamlit | 1.55.0 | Never upgrade — UI layout and RerunException behaviour tied to this version |
| supabase | 2.10.0 | Never upgrade — newer versions crash on Python 3.14 (SyncPostgrestClient.__init__() error) |
| AI model | claude-opus-4-6 | Verified live May 2026 — do not change without testing |
| AI scan limits | FREE 3/day, PAID 20/day | Stored in rfi_usage.ai_scans_today + ai_scans_date |

---

## PRODUCT WORKFLOW

This is the exact sequence a user follows every session:

```
FIRST TIME SETUP (once only):
Tab 1 → Enter company name, address, website
      → Upload company logo (PNG/JPG)
      → Upload signature image (PNG/JPG)
      → Enter originator name, title, email, phone
      → Save

EACH NEW PROJECT:
Tab 2 → Enter project name, site address, project number
      → Upload drawing PDF (the architectural/structural drawings)
      → Add clients (architect, structural engineer, etc.)
      → Save

EACH RFI SESSION:
Tab 3 → AI scans the uploaded PDF
      → Identifies potential RFI items (missing info, clashes, gaps)
      → Engineer reviews each item — approves or rejects
      → Approved items proceed to Tab 4

Tab 4 → Engineer crops the relevant drawing area for each RFI
      → Optionally uploads a site photograph
      → Annotates the crop if needed

Tab 5 → For each approved RFI: select client, click Generate
      → Each click produces one Word document for that RFI
      → Download individual documents per RFI

Tab 6 → View all RFIs raised for this project
      → Track status (Open / Responded / Closed)
      → Export to Excel
```

---

## DATA ARCHITECTURE

Every piece of data is owned by a user (identified by email).
All database queries MUST include email as a filter.
All storage paths MUST use email_to_folder(email) as prefix.

```
User (email: ajohnsudhakar@gmail.com)
│
├── Company Profile [user_config table]
│   └── name, address, country, postcode, website,
│       originator name/title/email/phone
│
├── Assets [rfi-manager-files storage bucket]
│   ├── {email_folder}/company_logo.png
│   └── {email_folder}/signature.png
│
└── Projects [projects table — one row per project]
    ├── proj_001: "New Proposed Single House"
    │   ├── config: name, address, project_number, pdf_path
    │   ├── clients: [{company, attn, role, email, phone}]
    │   ├── approved_rfis: [list from Tab 3]
    │   ├── Drawing PDF [rfi-manager-files/{email_folder}/proj_001/drawings/]
    │   ├── Snapshots [snapshots/{email_folder}/proj_001/snapshots/]
    │   ├── Word docs [rfi-manager-files/{email_folder}/proj_001/output/]
    │   └── RFI rows [rfi_register table]
    │
    └── proj_002: "Proposed Dwelling for Luke"
        └── (same structure)
```

---

## SUPABASE CONFIGURATION

Project ID: kflkrzxaaoceemcudqvb
Region: ap-southeast-1
Streamlit Cloud URL: https://rfi-manager.streamlit.app/
Supabase Site URL: https://rfi-manager.streamlit.app/
Supabase Redirect URL: https://rfi-manager.streamlit.app/
RLS Status: All 8 tables have email-scoped RLS policies as of this session. Verified via pg_policies query.
Reset email template: uses token_hash query param (not hash fragment) — required for Streamlit compatibility.
Note: Add http://localhost:8501 to Supabase Redirect URLs for local development — password reset and email confirmation links need it.
Auth: Email + Password — PERMANENT. Never change this.
Email Confirmation: Currently OFF (for local testing).
MUST be turned ON in Supabase dashboard before deployment:
Authentication → Sign In / Providers → Confirm email → ON
Path: Authentication → Sign In / Providers → Confirm email
Session: Stored in user_sessions table, accessed via ?sid= URL param.

### Database Tables

| Table | Unique Key | What it stores |
|---|---|---|
| user_config | email | Company details and originator info |
| projects | (email, project_id) | All project data including clients and approved RFIs |
| rfi_register | (email, project_id, rfi_number) | Log of every generated RFI |
| rfi_usage | email | RFI count and paid status |
| approved_rfis | — | UNUSED — approved RFIs stored in projects.approved_rfis_data |
| contacts | — | UNUSED — clients stored in projects.clients_data |
| user_sessions | session_key | Login session tokens |
| usage_events | — | Analytics events |

NOTE: projects table has a deleted_at column (timestamptz, default NULL).
Soft delete only — never hard delete projects. All project queries must
filter with .is_("deleted_at","null"). _list_project_ids() always returns
immediately after a successful Supabase query — never falls through to
local disk fallback when Supabase is connected and returns empty list.
projects table also has: scan_results_data (jsonb) for AI scan results,
captions_data (jsonb) for snapshot annotation labels added this session.
rfi_register table also has: priority (text) and response_required_by (date) columns
added this session. Duplicate UNIQUE constraint rfi_register_email_project_rfi_key
removed — only rfi_register_email_project_id_rfi_number_key remains.

### Storage Buckets

| Bucket | Purpose |
|---|---|
| rfi-manager-files | PDFs, Word docs, logo, signature |
| snapshots | Cropped drawing images from Tab 4 |

### Storage Path Formats

| Asset | Path in bucket |
|---|---|
| Company logo | {email_folder}/company_logo.png |
| Signature | {email_folder}/signature.png |
| Drawing PDF | {email_folder}/{pid}/drawings/{filename} |
| Snapshots | {email_folder}/{pid}/snapshots/{filename} |
| Word docs | {email_folder}/{pid}/output/{filename} |

### Critical Storage Rule
email_to_folder() converts email to safe folder name.
ajohnsudhakar@gmail.com → ajohnsudhakar_at_gmail_dot_com
ALWAYS use this function in storage paths. Never use raw email.

---

## AUTHENTICATION AND SESSIONS

How login works:
1. User enters email + password on login screen
2. sign_in_with_password() authenticates with Supabase
3. Session tokens saved to user_sessions table
4. URL updated with ?sid=UUID
5. User bookmarks this URL — never needs to log in again

How session restore works:
1. App reads ?sid= from URL on every load
2. Loads tokens from user_sessions table
3. Calls set_session() to restore authenticated state
4. Dashboard shows without password prompt

PERMANENT DECISIONS (never revisit these):
- Password login only — magic link failed (rate limits)
- OTP failed — rate limits
- localStorage failed — Streamlit sandboxes it
- Session via user_sessions table is the only working approach

---

## SECRETS AND CONFIGURATION

### How secrets are managed

Streamlit has a built-in secrets management system.
NEVER switch to .env files — secrets.toml is correct
for Streamlit and is already working.

Local development:
Secrets live in .streamlit/secrets.toml
This file must NEVER be committed to GitHub.
It must be in .gitignore.

Streamlit Cloud deployment:
Do NOT upload secrets.toml to GitHub.
Instead paste all secrets directly into the
Streamlit Cloud dashboard under:
App Settings → Secrets
Streamlit Cloud injects them automatically.

Access in code:
st.secrets["KEY"] or _secret("KEY")
Both already work in data_layer.py — do not change.

### What is in secrets.toml

SUPABASE_URL = "your supabase project URL"
SUPABASE_KEY = "your supabase anon key"
ANTHROPIC_API_KEY = "your anthropic API key"

### What .gitignore must always contain

.streamlit/secrets.toml
.claude/settings.local.json
__pycache__/
*.pyc
projects/
snapshots/
output/
drawings/
error_log.txt

---

## FILE RESPONSIBILITIES

Each file has ONE job. Never put logic in the wrong file.

| File | Single Responsibility |
|---|---|
| app.py | Auth flow, session management, sidebar, tab routing |
| data_layer.py | Every single read and write to Supabase and storage |
| ui_company.py | Tab 1 only — company setup UI |
| ui_project.py | Tab 2 only — project setup UI |
| ui_analyse.py | Tab 3 only — AI drawing analysis UI |
| ui_crop.py | Tab 4 only — crop and annotate UI |
| ui_generate.py | Tab 5 only — RFI generation UI |
| ui_register.py | Tab 6 only — RFI register UI |
| generate_rfi.py | Word document creation — called via generate_rfi_document() |

---

## PDF HANDLING FLOW

This is critical to understand before touching Tab 2, 3, or 4.

### Upload (Tab 2 — ui_project.py)
1. User picks a file via st.file_uploader
2. Bytes are read once into _pdf_bytes
3. Written to local disk: projects/{email_folder}/{pid}/drawings/{filename}
4. upload_project_pdf() uploads same bytes to Supabase Storage
5. Warning shown if Supabase upload fails (local save still succeeds)
6. Path stored in Supabase projects table as relative string "drawings/{filename}"
7. No st.rerun() after upload — user stays in the form to fill details and click Save

### Resolution (data_layer.resolve_pdf_path)
Called by Tab 3 and Tab 4 to get an absolute local Path to the PDF.
1. Loads stored path from Supabase config_data["pdf"]
2. If relative path → resolves against proj_dir → if local file exists, return it
3. If local file missing → downloads from Supabase Storage to local drawings dir → return it
4. Returns None only if both local and Supabase fail

### Read (Tab 3 — ui_analyse.py)
- resolve_pdf_path() called at line 42
- Used for: PDF viewer widget, page 1 preview, fitz.open() for AI text extraction

### Read (Tab 4 — ui_crop.py)
- resolve_pdf_path() called at line 89
- Used for: PDF viewer widget (right column), base64 iframe fallback

---

## KNOWN BUGS AND THEIR FIXES

These bugs have been fixed. Never reintroduce them.

### 1. st.rerun() inside try/except
Streamlit 1.55.0: RerunException inherits from Exception.
If st.rerun() is inside try/except it gets caught silently.
Fix: Always put st.rerun() in the else clause.

### 2. Success messages wiped by rerun
st.success() before st.rerun() disappears immediately.
Fix: Use session state flag — set flag before rerun,
check flag at top of function, show message, pop flag.

### 3. Widget value= with key= conflict
Using both value= and key= on same widget causes Streamlit warning
and unpredictable behaviour.
Fix: Use key= only. Seed initial values via session state.

### 4. Supabase unauthenticated client
_get_supabase() returns unauthenticated client.
RLS blocks all queries. Returns None. Causes AttributeError.
Fix: Always use _get_storage_client() for any RLS-protected operation.

### 5. Upsert file_options boolean
{"upsert": True} crashes httpx in supabase-py 2.10.0.
Fix: Always use {"upsert": "true"} as string.

### 6. Local fallback masking Supabase failures
When Supabase is connected but row not found, code was
falling through to local file. Stale local data appeared.
Fix: When Supabase is connected, return [] on not found.
Never fall through to local file when Supabase is reachable.

### 7. New project generating same pid
_new_project_id() called _list_project_ids() which could
return empty list causing proj_001 to be generated again.
Fix: Iterate from n=1 upward, skip any pid already in the
existing set. Always finds the first unused slot.

### 8. Silent save failures
save functions caught exceptions and called _warn() which
was wiped by subsequent st.rerun(). User saw false success.
Fix: Re-raise exceptions so the UI handler catches and
shows st.error() with st.stop() to prevent rerun wipe.

### 9. Email variable shadow in _render_client_card
ui_project.py: local variable `email = client.get("email", "")` silently
shadowed the `email` function parameter (the logged-in user's email).
All data layer calls inside the function used the client's contact email
as the user identity — deletes and saves operated on the wrong account.
Fix: Rename to `_c_email` and update the one reference to it.

### 10. Duplicate unique index on projects table
Supabase projects table had two unique constraints on (email, project_id).
The second upsert failed with a duplicate key violation on the second index.
Fix: Drop the duplicate index in Supabase SQL Editor, keep one constraint.

### 11. maybe_single() returning None instead of response object
supabase-py 2.10.0: .maybe_single() returns None (not a response object)
when no row matches. Calling .data on None raises AttributeError.
Affected: load_project_cfg, load_project_clients, load_project_approved.
Fix: Guard with `if res and res.data` before accessing res.data.

### 12. Sidebar project switcher overriding unsaved new project
When a new project was created but not yet saved, the pid guard block
at the top of the dashboard reset current_project_id back to the first
saved project on every rerun, making it impossible to save a new project.
Fix: Set `_pid_is_new_unsaved = True` on New Project button click, clear
it on Save success. Guard both the pid guard block and the project
switcher selectbox change handler with this flag.

### 13. Premature save_project_cfg call on PDF upload
ui_project.py: PDF upload section called save_project_cfg immediately
after writing the file to disk, before the user clicked Save. This
overwrote any unsaved changes in the name/address/number fields.
Fix: Remove the premature save call. The pdf path is written on the
main Save button only.

### 14. st.rerun() after PDF upload wiping form fields
ui_project.py: st.rerun() was called after the PDF upload success
message. This re-seeded the form fields from load_project_cfg()
which returns empty for a new unsaved project — wiping whatever
the user had typed in name, address, and project number.
Fix: Remove st.rerun() from the PDF upload handler entirely.
The selectbox updates on the next natural rerun (e.g. Save click).

### 15. PDF only saved locally — not available on cloud or other machines
resolve_pdf_path() checked local disk only. On Streamlit Cloud or any
other machine, the local file did not exist so Tab 3 and Tab 4 both
showed "Please upload a PDF" even though the PDF had been uploaded.
Fix: upload_project_pdf() now uploads to Supabase Storage at
{email_folder}/{pid}/drawings/{filename} on every upload.
resolve_pdf_path() now falls back to downloading from Supabase
Storage and writing to local disk as cache when local file is missing.

### 16. Redundant crop tool in Tab 4
ui_crop.py: When streamlit-cropper was installed, Tab 4 showed
a crop tool after screenshot upload — asking the user to crop
an image they had already precisely cropped with Windows Snipping
Tool before uploading.
Fix: Removed the if _cropper_ok / else branching entirely. Tab 4
now always shows a direct preview of the uploaded image without
any crop tool, regardless of whether streamlit-cropper is installed.

### 17. Build log showing in Tab 5 UI
ui_generate.py: After generating a Word document, a white log
box appeared showing internal build steps (Building RFI-001,
snap sizes, etc.). This is developer output not needed by users.
Fix: Removed the if result["logs"] block from the success handler.

### 18. tab_crop_done never cleared and prematurely set True
app.py: _TAB_CLEAR did not include tab_crop_done. When a user
re-analysed and approved different RFIs, the crop tab stayed
marked done. The generated Word doc silently had missing images.
ui_crop.py: tab_crop_done was also set True immediately after
any single snapshot save — a project with 8 RFIs showed Crop as
done after 1 snapshot.
Fix: Added tab_crop_done to _TAB_CLEAR in app.py. Removed the
premature True set from the save block in ui_crop.py. Also clear
it when save_project_approved is called in ui_analyse.py.

### 19. Soft-deleted projects reappearing after deletion
data_layer.py: _list_project_ids() used `if res.data:` to guard
the Supabase response. When all projects were soft-deleted,
Supabase returned [] (success but empty). The falsy check caused
fallthrough to the local filesystem which still had the old
project folders. Deleted projects reappeared immediately.
Fix: Changed to `return [r["project_id"] for r in res.data] if
res.data else []` so the function always returns immediately on
a successful Supabase query, even when the result is empty.
delete_project() sets deleted_at timestamp via soft-delete.
Never hard-delete rows from the projects table.

### 20. Sidebar overwriting current_project_id when no projects exist
app.py: The no-projects branch forced current_project_id = "" on
every rerun. After clicking ＋ New Project (which assigns a new
pid), the very next rerun wiped it back to empty, making it
impossible to save a first project after all projects were deleted.
Fix: Wrapped the forced clear in
`if not st.session_state.get("_pid_is_new_unsaved"):` so it only
runs when no new unsaved project is in progress.

### 21. pid-scoped form widget keys bleeding across projects
ui_project.py / app.py: The form widgets for project name, address,
and project number use pid-scoped keys (t2_proj_name_{pid}, etc.).
When switching or deleting projects, the old pid's keys were not
cleared. The new project's form showed the old project's values.
Fix: Clear all t2_proj_name_*, t2_proj_address_*, and
t2_proj_number_* keys from session state whenever switching
projects, creating a new project, or after a delete completes.
Clearing happens in: the _project_deleted flag handler, the
auto-create block, the Danger Zone delete handler, and the
sidebar ＋ New Project button handler.

### 22. save_project_cfg raises on Supabase failure — no fallback
data_layer.py: save_project_cfg raised RuntimeError if Supabase was None
and re-raised bare on any DB exception. No local file fallback existed.
A slow connection mid-save caused a full app crash.
Fix: Removed RuntimeError raise and bare re-raise. Added _warn() on
Supabase failure. Added atomic local write to proj_dir(pid, email) /
"config.json" using .tmp → .replace() — consistent with save_cfg and
what load_project_cfg already reads.

### 23. rfi_register missing project_id column and UNIQUE constraint
app.py: The SQL comment block for CREATE TABLE rfi_register was missing
`project_id text,` and the UNIQUE(email, project_id, rfi_number) constraint.
Code used on_conflict="email,project_id,rfi_number" so all upserts failed.
Fix: Updated SQL comment block in app.py. Ran the following in Supabase:
    ALTER TABLE rfi_register ADD COLUMN IF NOT EXISTS project_id text;
    ALTER TABLE rfi_register DROP CONSTRAINT IF EXISTS rfi_register_email_project_id_rfi_number_key;
    ALTER TABLE rfi_register ADD CONSTRAINT rfi_register_email_project_id_rfi_number_key
        UNIQUE (email, project_id, rfi_number);
Supabase already had the correct schema in place — only the comment needed updating.

### 24. Snapshots not loading from Supabase on cloud reruns
generate_rfi.py, ui_generate.py, ui_crop.py: _local_snaps() uses Path.exists()
on local disk only. On cloud, all snapshots live in Supabase Storage (bucket:
"snapshots"). Tab 4 showed 0 snaps after a page refresh. Generated Word docs
had no images.
Fix: Added sync_snapshots_from_supabase(pid, email, snaps_dir) to data_layer.py.
It calls sb.storage.from_("snapshots").list(folder) then downloads any missing
files to snaps_dir. Called in ui_crop.py and ui_generate.py immediately after
proj_snapshots_dir() so _local_snaps() always finds files locally.

### 25. Sheet map lost on every cloud rerun
data_layer.py: load_project_sheet_map() and save_project_sheet_map() read and
wrote a local sheet_map.json file only. On cloud the filesystem is wiped on
every rerun so the sheet map was rebuilt from scratch on every AI scan.
Fix: Rewrote both functions to use config_data in the projects Supabase table.
save_project_sheet_map() now calls load_project_cfg() → sets cfg["sheet_map"] →
calls save_project_cfg(). load_project_sheet_map() reads cfg.get("sheet_map", {})
with int-key conversion. Local sheet_map.json retained as read-only fallback.

### 26. Snapshot captions lost on every cloud rerun
ui_crop.py: _load_captions() and _save_captions() read and wrote snap_captions.json
in the local snapshots directory. On cloud this file was lost on every rerun.
Fix: Added load_project_captions() and save_project_captions() to data_layer.py.
Both follow the dual-layer pattern (Supabase first, local JSON fallback).
captions_data jsonb column added to projects table in Supabase.
Four call sites in ui_crop.py updated to use the new data_layer functions.

### 27. _PRIORITY_OPTS UnboundLocalError in ui_analyse.py
_PRIORITY_OPTS was defined inside the `if results:` block. The manual entry form
(tab_manual) renders before that block and referenced _PRIORITY_OPTS at module scope —
causing UnboundLocalError whenever the manual tab was shown before any scan results.
Fix: Moved _PRIORITY_OPTS to module level (line 21), removed the inner definition.

### 28. Empty string rejected by Postgres date column (error 22007)
upsert_project_register_rows() sent `iss.get("response_required_by", "")` which
returns "" for RFIs with no date set. Supabase rfi_register.response_required_by is
typed date — Postgres rejected "" with code 22007.
Fix: Changed to `iss.get("response_required_by") or None` in both the local row dict
and the Supabase upsert payload in data_layer.py. Empty string and None both map to NULL.

### 29. Two-click Generate bug in Tab 5
After clicking Generate, the Download button stayed grey until a second click. The
_btn_col rendered before the if _clicked: handler ran — t5_doc_path was set in session
state but the button was already rendered without it.
Fix: Added st.rerun() after upsert_project_register_rows() in ui_generate.py, inside
if result["success"]: and outside all try/except blocks.

### 30. approved_rfis_data not synced when editing RFIs in Tab 3
The edit form save handler called save_project_scan_results() only. Tab 5 reads from
load_project_approved() which reads approved_rfis_data — so priority and
response_required_by edits were never written to approved_rfis_data, leaving the Word
document with empty values for those fields.
Fix: Added save_project_approved() call in the edit form save handler in ui_analyse.py,
rebuilding the approved list from session state after each edit.

### 31. Tab 1 edit mode showing empty fields
When user clicked Edit Details, form fields showed empty even though data
existed in Supabase.
Root cause: setdefault() never overwrites existing session state keys. Keys
existed as empty strings from prior run.
Fix: On Edit Details button click, explicitly overwrite all 9 form session
state keys with current values from cfg before st.rerun().
File: ui_company.py

---

## WHAT IS WORKING TODAY

| Feature | Status |
|---|---|
| Login with email + password | ✅ Working |
| Session persistence via ?sid= | ✅ Working |
| Tab 1 — Company details save | ✅ Working |
| Tab 1 — Logo upload to Supabase | ✅ Working |
| Tab 1 — Signature upload to Supabase | ✅ Working |
| Tab 2 — Single project create and save | ✅ Working |
| Tab 2 — Client add/edit/delete | ✅ Working |
| Tab 2 — Multi-project creation | ✅ Working |
| Tab 2 — PDF upload to local disk | ✅ Working |
| Tab 2 — PDF upload to Supabase Storage | ✅ Working |
| Tab 2 — Delete project (soft delete) | ✅ Working |
| Sidebar — project switcher dropdown | ✅ Working |
| Sidebar — hide/show panel button | ✅ Working |
| Sidebar — ＋ New Project always visible | ✅ Working |
| PDF available on cloud (resolve_pdf_path fallback) | ✅ Working |
| Tab 3 — AI drawing analysis | ✅ Working |
| Tab 4 — Crop and annotate | ✅ Working |
| Tab 4 — Redundant crop tool removed | ✅ Working |
| Tab 4 — Snapshots saved to Supabase Storage | ✅ Working |
| Tab 4 — Snapshots synced from Supabase on tab load | ✅ Working |
| Tab 4 — Sheet map persistent in Supabase (config_data) | ✅ Working |
| Tab 4 — Snapshot captions persistent in Supabase (captions_data) | ✅ Working |
| Tab 5 — Generate RFI | ✅ Working |
| Tab 5 — Word doc saved to Supabase Storage | ✅ Working |
| Tab 5 — Build log removed from UI | ✅ Working |
| Tab 4 — Two-column [5,5] layout; inline snap count HTML badge | ✅ Working |
| Tab 4 — Gallery: fixed-height 2-col grid; base64 img at 180px | ✅ Working |
| Tab 5 — Per-RFI generation (one Generate button per RFI card) | ✅ Working |
| Tab 5 — Per-RFI client selector (key: t5_client_{rfi_n}_{pid}) | ✅ Working |
| Tab 5 — RFI number in filename: RFI_{num}_{Project}_{date}.docx | ✅ Working |
| Tab 6 — Summary metrics strip: Total / Open / Responded / Closed | ✅ Working |
| Tab 6 — Custom HTML table with coloured status badges | ✅ Working |
| Tab 6 — Status options reduced to 3: Open / Responded / Closed | ✅ Working |
| Tab 6 — Explicit Search button (no live keystroke filtering) | ✅ Working |
| Tab 6 — RFI register | ✅ Working |
| Tab 6 — Excel export working | ✅ Working |
| Tab 6 — Status update working | ✅ Working |
| Sign Up / registration screen | ❌ Not yet |
| Forgot Password screen | ❌ Not yet |
| Tab 3 — Priority field (Critical/High/Normal/Low) in edit form, manual entry, card display | ✅ Working |
| Tab 3 — Response Required By date field in edit form, manual entry, card display | ✅ Working |
| Tab 3 — Priority + Response Required By sync to Word doc via save_project_approved() on every edit save | ✅ Working |
| Full app light theme — dark theme replaced across all 6 tabs, login screen, and sidebar | ✅ Working |
| Tab 1 — View/edit mode (co_edit_mode session key) — form read-only after save, Edit Details button to re-enter edit mode | ✅ Working |
| Tab 1 — Next step banner after save pointing to Project Setup | ✅ Working |
| Tab 2 — View/edit mode (t2_edit_mode_{pid} session key) — project info read-only after save | ✅ Working |
| Tab 2 — Client table (replaces card layout) — Company, Contact, Role, Email, Phone, Actions | ✅ Working |
| Tab 2 — Client delete confirmation (t2_confirm_del_client session key) | ✅ Working |
| Tab 2 — Raw file path hidden — replaced with green PDF status card showing filename only | ✅ Working |
| Tab 2 — Next step banner after save pointing to Analyse Drawings | ✅ Working |
| Tab 3 — Progress bar replacing metric columns | ✅ Working |
| Tab 3 — Filter radio (t3_filter session key, defaults to Pending) — All/Approved/Rejected/Pending | ✅ Working |
| Tab 3 — Redesigned RFI cards — description as headline, colour-coded badges, priority colours | ✅ Working |
| Tab 3 — Save Approved RFIs button compact with context label | ✅ Working |
| Tab 4 — Page header with title, subtitle, and progress pill (X of Y RFIs have snapshots) | ✅ Working |
| Tab 4 — Navigation row redesigned — both arrows together left, dropdown centre, snap badge right | ✅ Working |
| Tab 4 — Numbered step circles (1/2/3) for upload workflow | ✅ Working |
| Tab 4 — Snapshot gallery header shows RFI context | ✅ Working |
| Tab 5 — RFI numbers visible in blue (#1d4ed8) | ✅ Working |
| Tab 5 — Previously generated documents — filenames readable, proper table layout | ✅ Working |
| Tab 5 — Page subtitle added | ✅ Working |
| Tab 6 — Page title and subtitle added | ✅ Working |
| Tab 6 — Update button styled as primary | ✅ Working |
| Tab 6 — Download Register button label and width fixed | ✅ Working |

---

## PENDING TASKS — BEFORE DEPLOYMENT

1. Word doc: add response_required_date field (date picker — NOT response_days)
2. Word doc: add RFI category A/B/C/D selection
   - A = Missing Information
   - B = Clarification Required
   - C = Additional Information
   - D = Uncoordinated Information
3. Word doc: add blank response section at bottom
4. Enforce 5 free RFI limit in Tab 5
5. Add Sign Up screen to login flow (email + password + confirm password)
6. Add Forgot Password screen to login flow (email → Supabase reset link)
7. Upgrade Supabase to Pro tier — free tier showing "EXCEEDING USAGE LIMITS"
8. Turn ON email confirmation in Supabase dashboard:
   Authentication → Sign In / Providers → Confirm email → ON
9. GitHub repo with proper .gitignore (never commit secrets.toml)
10. Deploy to Streamlit Community Cloud
11. Update Supabase Site URL to cloud URL
12. Test login and session persistence on cloud URL
13. Full end to end test with a real engineer in New Zealand

---

## HOW TO WORK WITH JOHN

John is the decision maker. Claude Code is the executor.

PROCESS FOR EVERY TASK:
1. Read this file completely first
2. Read all relevant source files completely
3. Present a plan — what will change, why, what stays the same
4. Wait — do not execute until John approves the plan
5. Execute exactly as approved
6. Run syntax check on every changed file: py -m py_compile scripts/<file>.py
7. Report pass/fail and exact lines changed

COMMUNICATION RULES:
- One task at a time — never bundle multiple fixes
- If something is unclear — ask before guessing
- Never modify files outside the current task scope
- If a fix requires changing multiple files — say so in the plan
- Report must show what changed, why it changed, and verification

THINGS THAT WILL NEVER CHANGE:
- Magic link is dead — password login is permanent
- OTP is dead — password login is permanent
- localStorage is dead — user_sessions table is permanent
- response_days field is dead — response_required_date is the future field
- subprocess is dead — import and call directly
- "Claude" in UI is dead — always say "AI"
- supabase-py 2.10.0 — never upgrade without John's explicit approval
- streamlit 1.55.0 — never upgrade without John's explicit approval

---

## DEVELOPMENT ROADMAP — SESSIONS IN ORDER

Follow this exact sequence. Do not skip ahead.

### SESSION 1 — Complete ✅
- [x] Confirm multi-project creation works
- [x] PDF upload to Supabase Storage
- [x] Verify PDF loads correctly in Tab 3 and Tab 4 after upload

### SESSION 2 — Complete ✅
- [x] Tab 3 — AI drawing analysis end to end test
- [x] Tab 3 — Approve/reject RFI items working
- [x] Tab 4 — Crop and annotate end to end test
- [x] Snapshots saving to Supabase Storage

### SESSION 3 — Complete ✅
- [x] Tab 5 — Client selection working
- [x] Tab 5 — Word document generation end to end
- [x] Word doc saved to Supabase Storage
- [x] Tab 6 — RFI register showing generated RFIs
- [x] Tab 6 — Status update working
- [x] Tab 6 — Excel export working

### SESSION 4 — Word Document Quality
NOTE: Pending Procore R&D — John is reviewing Procore RFI format
before finalising response_required_date and category fields.
- [ ] Add response_required_date field (date picker — NOT response_days)
- [ ] Add RFI category selection A/B/C/D
  - A = Missing Information
  - B = Clarification Required
  - C = Additional Information
  - D = Uncoordinated Information
- [ ] Add blank response section at bottom of Word doc
- [ ] Enforce 5 free RFI limit in Tab 5

### SESSION 5 — Multi-User Registration ✅ Complete
- [x] Add Sign Up screen to login flow
- [x] New user: email + password + confirm password
- [x] Supabase creates user account with email verification
- [x] After verification user lands on Tab 1 Company Setup
- [x] Add Forgot Password screen to login flow
- [x] Forgot Password: email input → Supabase sends reset link
- [x] Existing users: login as normal — no change
- [x] NOTE: RLS already isolates data by email — no DB changes needed
NOTE: Sign Up, Forgot Password, and password reset flow implemented in app.py (lines 638–742).
Email confirmation must be turned ON in Supabase dashboard at deployment time.

### PRE-DEPLOYMENT WARNINGS — Fix before SESSION 6

These Streamlit warnings must be resolved before going live.
They will not crash the app today but will in future Streamlit versions.

**WARNING 1 — Empty widget label (ui_analyse.py line ~239)**
`st.text_area("", ...)` has an empty string label.
Streamlit warns: empty labels will raise exceptions in future versions.
Fix: Add `label_visibility="collapsed"` parameter (confirmed valid in Streamlit 1.55.0).

**WARNING 2 — use_container_width deprecation (multiple files)**
Streamlit 1.55.0 warns: `use_container_width` parameter is deprecated.
Replace with `width` parameter:
- `use_container_width=True` → `width="stretch"`
- `use_container_width=False` → `width="content"`
Deadline: 2025-12-31 (will break after December 2025).
Files affected: ui_generate.py, ui_crop.py, ui_register.py, ui_analyse.py, app.py.
Fix all uses before SESSION 6 deployment.

---

### SESSION 6 — Deployment
- [ ] Upgrade Supabase to Pro tier — free tier showing "EXCEEDING USAGE LIMITS"
- [ ] Turn ON email confirmation in Supabase dashboard:
      Authentication → Sign In / Providers → Confirm email → ON
- [ ] GitHub repo with proper .gitignore (never commit secrets.toml)
- [ ] Streamlit Community Cloud deployment
- [ ] Update Supabase Site URL to cloud URL
- [ ] Test login and session persistence on cloud URL
- [ ] Full end to end test with real engineer in New Zealand
- [ ] Google Sign In (OAuth) — requires deployed URL registered
      in Google Cloud Console and callback URL set in Supabase
- [ ] Microsoft Sign In (OAuth) — requires deployed URL registered
      in Microsoft Azure and callback URL set in Supabase
- [ ] Magic Link login — requires Supabase email rate limit increase
      and deployed URL for redirect
- [ ] NOTE: OAuth providers cannot be tested on localhost —
      must be done after Streamlit Cloud deployment

### SESSION 7 — Real World Testing
- [ ] Share with 2-3 real engineers
- [ ] Collect feedback
- [ ] Fix issues found in real world testing
- [ ] Version 2 planning based on feedback

### UX/UI OVERHAUL SESSION — Complete ✅
- [x] Light theme — .streamlit/config.toml created
- [x] Global CSS block (app.py lines 112-418) converted from dark to light theme
- [x] Login screen dark card fixed
- [x] Sidebar logo area fixed
- [x] Tab 1 — view/edit mode, next step banner, edit mode empty fields bug fixed
- [x] Tab 2 — view/edit mode, client table, delete confirmation, project info
      view mode, raw file path hidden, next step banner
- [x] Tab 3 — progress bar, filter radio, card redesign, save button layout
- [x] Tab 4 — page header, nav fix, step circles, gallery context label
- [x] Tab 5 — RFI number colours, previously generated docs table, subtitle
- [x] Tab 6 — title, Update button primary, Download button fixed
- [x] Deployed to Streamlit Cloud

---

## VERSION 1 — Remaining Work (Must complete before launch)

### Bugs
**BUG-04** | data_layer.py — save_project_register() local only ✅ RESOLVED
Status changes (Tab 6) persist correctly: update_project_register_status() writes
local JSON via save_project_register() AND syncs to Supabase rfi_register separately.
save_project_register() is local-only but is not in the critical path for status updates.

### Workflow Gaps
- S3-01: No editing of AI descriptions before approving ✅ RESOLVED — edit button in ui_analyse.py (lines 322–363, 397–399) allows engineers to edit description, reason, category, and sheets for approved RFIs
- S3-05: No Response Required By date per RFI ✅ RESOLVED — date picker added in Tab 3 edit form, manual entry, and card display; flows through to Word document via save_project_approved() sync
- S3-07: Approved RFI list locked — no inline edit after approval ✅ RESOLVED — same edit form (S3-01) covers inline editing of approved RFIs

### Pre-Deployment Checklist
- [x] Turn on email confirmation in Supabase dashboard (Authentication → Sign In / Providers → Confirm email → ON)
- [x] Deploy to Streamlit Cloud
- [x] Test Sign Up flow with a real new user email
- [x] RLS policies verified on all 8 Supabase tables (pg_policies query)
- [x] Cross-tenant asset leak fixed — local file fallbacks removed from data_layer.py and generate_rfi.py
- [x] AI scan cost protections added — rescan confirmation, large PDF gate, daily scan counter
- [x] AI model claude-opus-4-6 verified live in production
- [ ] Add http://localhost:8501 to Supabase Redirect URLs for local development testing

---

## VERSION 2 BACKLOG (After launch, based on user feedback)

### Workflow
- S3-02: Subject/title field separate from description
- S3-03/04: Discipline and Priority fields per RFI — Priority ✅ RESOLVED (added this session: Critical/High/Normal/Low selectbox in Tab 3 edit form, manual entry, card, Word doc); Discipline deferred
- S3-06: Standalone New RFI creation without AI scan
- S4-01: Drawing markup tools (arrow, cloud, circle, text)
- S5-01: PDF export via LibreOffice headless
- S5-05: Email/send directly from app
- S6-01/02/03/04: Response tracking + overdue flag
- S6-07: Cost/time impact flag per RFI
- S7-xx: Closing loop (variation link, archive, notifications)
- S1-01: Multi-user team roles
- S2-01: Drawing revision management

### Dead Code Cleanup (low risk, defer)
- DC-04: load_company() redundant call in app.py sidebar
- DC-05: track_usage() function in data_layer.py
- DC-08: json import in ui_crop.py after BUG-08 fix

---

## VERSION 2 FEATURES (after launch only)

Do not build these until Version 1 is live and tested:
- Site photographs alongside drawing snapshots in RFI
- Cost impact field (Yes/No + dollar amount)
- Schedule impact field (Yes/No + number of days)
- Multi-model AI support
- Bulk RFI generation
- Client portal for responding to RFIs

---

## Tab 3 — Analyse Drawings (COMPLETED)

All phases complete as of Session 4:
- Two-column layout: PDF viewer right (ratio 2), controls left (ratio 3)
- Native st.tabs() switcher: "AI-Assisted Scan" and "Add Your Own Issue"
- System prompt + user template pattern (_SYSTEM_PROMPT, _USER_TEMPLATE, _build_user_prompt)
- scan_results_data jsonb column added to projects table
- load_project_scan_results() / save_project_scan_results() in data_layer.py
- Auto-saves on scan complete, approve, reject, manual entry
- New scan appends to existing — does not replace
- Edit button for approved issues only (t3_edit_idx session state key)
- Bulk Approve All Pending / Reject All Pending buttons
- Persistent across page refresh via Supabase

---

## Tab 4 — Crop and Annotate (COMPLETED)

All cloud-persistence issues resolved:
- sync_snapshots_from_supabase() added to data_layer.py — called on tab load
  in ui_crop.py (after proj_snapshots_dir()) and ui_generate.py (same position)
- Sheet map persists in projects.config_data via rewritten load/save_project_sheet_map()
- Snapshot captions persist in projects.captions_data via new load/save_project_captions()
- captions_data jsonb column added to projects table in Supabase
- Four call sites in ui_crop.py updated from local _load/_save_captions to data_layer functions
- _load_captions() and _save_captions() remain in ui_crop.py as dead code (DC cleanup pending)

UI improvements:
- Two-column layout redesigned — true [5,5] split created immediately after sync_snapshots
- Header "## Crop and Annotate" removed
- Snap count st.metric replaced with compact inline HTML badge
- Gallery changed to always-visible 2-column grid
- st.image() replaced with base64 <img> tag at fixed height:180px / object-fit:cover
  for equal cell heights regardless of image aspect ratio

---

## Tab 5 — Generate RFI (COMPLETED)

All phases complete:
- Per-RFI individual generation — each RFI card has its own Generate button
- One click = one Word document for that specific RFI only
- RFI number in filename: RFI_{num}_{Project}_{date}.docx (single-RFI only)
- Global client selector removed — per-RFI "Send to" dropdown inside each card
  Session state key: t5_client_{rfi_n}_{pid}
- Column split [4, 2, 1]: RFI info card | client dropdown | Generate + Download buttons
- Two stacked buttons per card:
  - ▶ Generate (blue, primary) — always visible
  - ↓ Download — greyed out until generated, active green after
- Generated file path stored in: t5_doc_path_{rfi_n}_{pid} session state
- open_file() removed from ui_generate.py imports and all call sites
- Usage counter increments per RFI generated (increment_usage called inside loop)
- Previously generated documents expander at bottom — unchanged

---

## Tab 6 — RFI Register (COMPLETED)

All phases complete:
- Header "## RFI Register" removed
- Summary metrics strip: Total RFIs / Open / Responded / Closed (st.columns(4))
- st.dataframe replaced with custom HTML table — Streamlit 1.55.0 cannot render
  HTML badges in dataframe cells; custom table is the only reliable approach
- Colour-coded status badges via _STATUS_COLORS module-level dict
- Column headers renamed for display via _DISPLAY_COLS module-level dict
- Status options reduced from 5 to 3: Open / Responded / Closed
  Removed: "In Progress", "Sent"
- Update RFI Status expander removed — always visible with sec-lbl heading
- Search input + Search button side by side (columns [5,1])
  Explicit button-triggered filtering — no live keystroke filtering
  Active search term stored in: st.session_state.reg_active_search
  Keys: reg_search_input, reg_search_btn
- Footer row st.columns([6, 2]): record count left, Download button right
- Excel export uses show.rename(columns=_DISPLAY_COLS) for human-readable headers
- Download button key: reg_download (no use_container_width)

---

## Known Bugs — Priority Order for Next Sessions

### CRITICAL — All bugs in this section resolved ✅

**BUG-12** | ui_analyse.py — _PRIORITY_OPTS UnboundLocalError on Python 3.14 ✅ RESOLVED
Tab 3 crashed immediately on load with:
UnboundLocalError: cannot access local variable '_PRIORITY_OPTS'
Root cause: Python 3.14 changed free variable resolution in nested
scopes — the module-level _PRIORITY_OPTS became ambiguous inside
render_tab_analyse() under certain execution paths.
Fix: Added _PRIORITY_OPTS = ["Critical", "High", "Normal", "Low"]
as first line inside render_tab_analyse() at line 70 of ui_analyse.py.

**BUG-13** | data_layer.py — Empty date string crashing Supabase register save ✅ RESOLVED
Every RFI generation failed to save to Supabase rfi_register with:
APIError code 22007: invalid input syntax for type date: ""
Root cause: response_required_by field sent as "" instead of NULL.
The "or None" guard failed for values like "None" string or whitespace.
Fix: Added sanitiser at lines 1117-1121 and 1152-1156 of data_layer.py.
Sanitiser rejects "", whitespace, and literal "None" — sends NULL to
Postgres. Valid date strings like "2026-06-01" pass through unchanged.

**BUG-14** | app.py — Email confirmation flow broken on registration ✅ RESOLVED
After sign_up() succeeded, code immediately called
sign_in_with_password() which returned "Email not confirmed"
shown as a red error. User had no idea account was created.
Fix: Intercept "not confirmed" / "confirm" error after
sign_in_with_password(). Set _signup_confirm_pending flag,
show green confirmation banner with "Go to Sign In" button.

**BUG-15** | app.py — "User already registered" raw error on signup ✅ RESOLVED
Raw Supabase error shown directly. User stayed on signup
screen with no guidance.
Fix: Intercept "already registered"/"already exists" in
except block. Replace with friendly message and auto-switch
to signin screen.

**BUG-16** | app.py — Password reset link went to Supabase hosted page ✅ RESOLVED
Forgot Password sent reset email but link went to Supabase's
own page, not the app. User had to find app URL manually.
Fix: Added recovery token detection in _render_login().
Detects type=recovery in query params, calls set_session(),
shows Set New Password screen, calls update_user() on submit.
Supabase dashboard: Site URL and Redirect URL both set to
https://rfi-manager.streamlit.app/
Additional fixes applied in follow-up session:
- Supabase Site URL updated to https://rfi-manager.streamlit.app/
- Redirect URL updated to https://rfi-manager.streamlit.app/
- Supabase reset password email template updated to use
  token_hash as query parameter instead of hash fragment
- app.py recovery handler updated from set_session(access_token)
  to verify_otp(token_hash) — lines 574-583
- Malformed reset link now handled gracefully (Scenario 16b)

**BUG-17** | app.py — Sidebar hide/show feature caused
permanent sidebar loss ✅ RESOLVED
Custom Hide Panel / Show Panel buttons and native Streamlit
collapse arrow all removed. Sidebar is now permanently visible.
Removed: sidebar_visible session state, Hide Panel button,
Show Panel block, stHeader and collapsedControl CSS rules.
Additional CSS added to hide stSidebarResizeHandle,
stSidebarNav, and stHeader elements.

**BUG-18** | app.py — Signup duplicate email shows raw error
with confirmation ON ✅ RESOLVED
When email confirmation is ON, Supabase silently succeeds on
sign_up() for duplicate emails instead of raising an error.
The friendly "email already exists" detection never fires.
User sees generic "Invalid login credentials" with no guidance.
Status: FIXED — sign_up() response inspected for empty 
identities list. If empty, friendly error shown and user 
redirected to signin. getattr used safely to prevent 
AttributeError. st.rerun() outside all try/except.

**BUG-19** | ui_analyse.py — empty label warning on Python 3.14 ✅ RESOLVED
st.text_area("", ...) at line 242 generates a warning in
Python 3.14 — may become an exception in future versions.
Fix: Change empty string label "" to a descriptive label
with label_visibility="collapsed".
Status: FIXED — st.text_area label changed from "" to 
"RFI Description" with label_visibility="collapsed". 
Warning eliminated on Python 3.14.

**BUG-20** | app.py — New Project button did not redirect
to Tab 2 (Project Setup) ✅ RESOLVED
After clicking "+ New Project", app stayed on current tab.
User had to manually click Project Setup tab.
Fix: Set _goto_tab2 flag before st.rerun() in the New 
Project handler. After rerun, inject JavaScript via 
st.components.v1.html to click the second tab button 
using [data-baseweb="tab"] selector with 200ms delay.
Flag is consumed with pop() so JS fires exactly once.

**BUG-21** | app.py — Old project data persisted on tabs
after project switch ✅ RESOLVED
After switching projects or clicking New Project, Tabs 3,
4, 5 still showed previous project scan results, snapshots,
and generated documents.
Fix: Added dynamic key clearing loop in both 
_reset_project_state() and the project switch handler.
Clears all keys starting with t5_doc_path_, t5_client_,
t4_, gen_, dl_, and any key containing the old project ID
that also starts with a known tab prefix (t2_, t3_, t5_,
gen_, dl_, ul_, lbl_, sv_, del_).
_old_pid captured before pop loop so pid is available
for matching.

---

## SECURITY FIXES — Completed

**S1** | Cross-tenant asset isolation — data_layer.py get_asset_bytes()
Removed local file fallback (BASE/scripts/company_logo.png etc.).
On Streamlit Cloud all users share the container filesystem — local
fallback returned wrong user's logo/signature.
Fix: Return None when Supabase read fails. No asset is safer than the
wrong user's asset.

**S2** | Cross-tenant asset write — data_layer.py upload_asset()
Removed stale-file cleanup and local write fallback.
Fix: Return on Supabase success; call _warn() on failure with a clear
user-facing message. Never write assets to shared local disk.

**S3** | Cross-tenant snapshot isolation — generate_rfi.py _abs()
Removed _HERE and _BASE_EARLY directory fallbacks from image resolution.
Fix: Only SNAPSHOTS_DIR (per-user path) is searched. Return bare filename
if not found; never look in shared script directories.

**S4** | Cross-tenant logo/signature defaults — generate_rfi.py
Removed _HERE-based default paths for LOGO_IMG and SIGNATURE_IMG.
Fix: Set to empty string when Supabase path is missing or invalid.
Word doc renders without image rather than showing another user's logo.

**S5** | AI scan cost protections — ui_analyse.py (3 protections)
Protection 1: Scan caching — existing results trigger "Use Existing /
Re-scan Anyway" confirmation before any API call is made.
Protection 2: Large PDF gate — PDFs > 30 pages show credit warning and
batch count; user must confirm before scan runs.
Protection 3: Daily scan counter — FREE tier: 3 scans/day, PAID: 20/day.
Counter stored in rfi_usage table (ai_scans_today + ai_scans_date columns).
Supabase offline → counter returns 0 → scans allowed (acceptable trade-off).

**S6** | Supabase schema — rfi_usage table
Added two columns (run in SQL Editor before deploying):
    ALTER TABLE rfi_usage ADD COLUMN IF NOT EXISTS ai_scans_today integer DEFAULT 0;
    ALTER TABLE rfi_usage ADD COLUMN IF NOT EXISTS ai_scans_date  text    DEFAULT '';
New data_layer functions: load_scan_usage(email) and increment_scan_usage(email).
Both follow the existing load_usage / increment_usage pattern.

---

**BUG-01** | data_layer.py — _migrate_legacy_to_projects() ✅ RESOLVED
References CONTACTS_JSON which was deleted. NameError on every new user login.
Fix: Replace `if CONTACTS_JSON.exists():` with local variable:
    _legacy_contacts = BASE / "scripts" / "contacts.json"
    if _legacy_contacts.exists():
Status: Already fixed — _legacy_contacts local variable confirmed
in place at line 1252 of data_layer.py.

**BUG-11** | app.py — analysis_results not cleared on project switch ✅ RESOLVED
Switching projects leaves previous project's scan results in session state.
User can approve Project A's issues while viewing Project B.
Fix: Add "analysis_results" and "t3_loaded_pid" to the TABCLEAR tuple in app.py.
Status: Already fixed — "analysis_results" and "t3_loaded_pid"
confirmed in _TAB_CLEAR list at lines 884 and 892 of app.py.

### HIGH PRIORITY — All bugs in this section resolved ✅
BUG-02/09/10, BUG-07, BUG-08 fixed this session. See KNOWN BUGS AND THEIR FIXES #24–26.

### st.rerun() inside try/except — ALL 7 VIOLATIONS FIXED ✅
Fixed in audit session:
- app.py line 527 — session restore on login
- ui_analyse.py line 273 — Format with AI manual entry
- ui_project.py line 235 — Save Project Details
- ui_company.py lines 165, 202, 224 — logo upload, signature upload, Save Company Details
- ui_register.py line 209 — Update RFI Status
All st.rerun() calls now outside try/except blocks across all files.
Pattern used: session state flag set inside try, st.rerun() called
after try/except closes.

### MEDIUM PRIORITY — Fix after Tab 4

**BUG-05** | app.py — _migrate_legacy_to_projects() runs every page load ✅ RESOLVED
Fix: Guard with st.session_state.get("_migration_done") flag.
Status: Already fixed — _migration_done guard confirmed at
lines 778-780 of app.py.

**BUG-03** | app.py — load_register misuse ✅ RESOLVED
Fixed as side effect of removing the workflow status bar — load_register and
tab_generate_done removed from app.py; load_register is no longer called in the sidebar.

### DEAD CODE — Remaining items

**DC-02/10** | data_layer.py — open_file() and subprocess import ✅ RESOLVED
open_file() function and subprocess import removed from data_layer.py this session.

**DC-03** | generate_rfi.py — if __name__ == "__main__": block ✅ RESOLVED
CLI block removed from generate_rfi.py this session.

---

## Workflow Gaps — Future Roadmap

### Stage 2 — Project Setup
- S2-01: No drawing revision management — Rev B wipes all prior work (CRITICAL)
- S2-04: ✅ RESOLVED — Per-RFI client selector added in Tab 5

### Stage 4 — Crop & Annotate
- S4-01: No drawing markup tools (arrow, cloud, circle, text)
- S4-02: Crop tab does not auto-navigate to sheet from Analyse results
- S4-04: No zoom control on PDF viewer

### Stage 5 — Generate RFI
- S5-01: Word only — no PDF export
- S5-02: ✅ RESOLVED — Per-RFI individual Generate buttons added
- S5-05: No email/send directly from app

### Stage 6 — Register
- S6-01/02/03/04: No response tracking, no date sent, no response required by, no overdue flag
- S6-05/06: No filtering, no CSV export

### Stage 7 — Closing Loop (entirely missing)
- No variation/change order link
- No project archiving
- No notifications for overdue RFIs
KNOWN UI ISSUE: Streamlit built-in sidebar collapse arrow 
cannot be fully hidden via CSS in v1.55.0. Deferred — 
investigate browser DevTools to find exact selector.