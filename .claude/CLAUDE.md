# RFI Manager — Project Intelligence File
# Read this file completely before starting any task.

---

## 1 — PROJECT OVERVIEW

- RFI Manager: cloud SaaS for construction engineers — replaces manual RFI writing using AI
- Workflow: upload PDF → AI identifies issues → crop drawing → generate Word doc → track in register
- Deployed: https://rfi-manager.streamlit.app/
- GitHub: https://github.com/ajohnsudhakar-code/RFI---Manager
- Supabase Project ID: kflkrzxaaoceemcudqvb
- Run locally: `py -m streamlit run scripts/app.py`
- Business: Free = 5 RFIs lifetime / Paid = unlimited / Upgrade contact: ajohnsudhakar@gmail.com

---

## 2 — TECH STACK AND HARD CONSTRAINTS

- `streamlit==1.55.0` — NEVER upgrade (RerunException + layout tied to this version)
- `supabase==2.10.0` — NEVER upgrade (crashes Python 3.14 with SyncPostgrestClient error)
- Python 3.11 (Windows local / Linux cloud) / AI: `claude-opus-4-6` — never change without testing
- `st.rerun()` NEVER inside `try/except` — RerunException inherits from Exception, silently caught
- Never say "Claude" in any UI text — always say "AI"
- All storage paths use `email_to_folder(email)` — never raw email strings
- Soft-delete only — set `deleted_at`, never hard-delete rows from projects table
- `{"upsert": "true"}` — string not boolean; `True` crashes httpx in supabase-py 2.10.0
- All project queries must filter `.is_("deleted_at", "null")`
- Password login only — magic link, OTP, localStorage all permanently dead
- Secrets in `.streamlit/secrets.toml` — NEVER commit to git, NEVER switch to .env

---

## 3 — THE DRILL

8-step workflow — never deviate from this:

1. John uploads files when investigation is needed
2. Investigate — read files, report findings, NO changes made
3. Write a prompt describing the problem and requirements (NOT code itself)
4. John pastes prompt into Claude Code in VS Code
5. Claude Code enters plan mode and produces a plan — John pastes it back here
6. Analyse the plan — approve or reject with reasons
7. John tells Claude Code "go ahead" ONLY after approval here
8. John pastes the compile result and output back here for review

Key rules:
- Plan mode only — never execute without John's explicit approval
- One logical change per prompt — never bundle multiple fixes
- Rate every prompt out of 10 — be honest, not always 9
- Run `py -m py_compile scripts/<file>.py` after every changed file and report pass/fail

---

## 4 — FILE STRUCTURE

All source files live in `scripts/`. Each file has ONE job — never put logic in the wrong file.

| File | Responsibility |
|---|---|
| app.py | Auth, session management, sidebar, tab routing |
| data_layer.py | ALL Supabase and storage access — tabs never touch Supabase directly |
| ui_company.py | Tab 1 — company setup |
| ui_project.py | Tab 2 — project setup and PDF upload |
| ui_analyse.py | Tab 3 — AI drawing analysis |
| ui_crop.py | Tab 4 — crop and annotate |
| ui_generate.py | Tab 5 — Word document generation |
| ui_register.py | Tab 6 — RFI register and Excel export |
| generate_rfi.py | Word doc builder — called via `generate_rfi_document()` |

---

## 5 — ARCHITECTURE

- Auth: email+password → `sign_in_with_password()` → tokens in `user_sessions` table → `?sid=` URL param
- Session restore: read `?sid=` → load tokens → `set_session()` → dashboard shown (no re-login)
- Data layer: ALL reads/writes go through `data_layer.py`. Every query filters by `email`.
- Storage paths: `email_to_folder(email)` prefix always — e.g. `ajohnsudhakar_at_gmail_dot_com/`
- PDF flow: upload → local disk + Supabase Storage → `resolve_pdf_path()` returns local or downloads on demand
- Snapshots: `sync_snapshots_from_supabase()` called on Tab 4 + Tab 5 load so `_local_snaps()` always works

---

## 6 — SUPABASE CONFIGURATION

- **Schema changes must update this section in the same session they are applied.** This has now
  drifted twice — Bug #23 was the first time.
- Project ID: `kflkrzxaaoceemcudqvb` / Region: `ap-southeast-1`
- Site URL + Redirect URL: `https://rfi-manager.streamlit.app/`
- Email Confirmation: ON (production) — must stay ON
- RLS: All 8 tables have email-scoped policies ✅ verified — usage_events INSERT policy added 25 May 2026
- Reset email template: uses `token_hash` as query param (not hash fragment)
- Tables: `user_config` / `projects` / `rfi_register` / `rfi_usage` / `user_sessions` / `usage_events` /
  `approved_rfis` (active — Tab 3 saves, Tab 5 reads) / `contacts` (UNUSED)
- Full CREATE TABLE statements (kept in sync with live schema) live in the comment block at the
  top of `scripts/app.py` — treat that as the source of truth for column-level detail.
- Extra columns beyond the obvious: `projects.clients_data` / `approved_rfis_data` / `deleted_at` /
  `scan_results_data` (jsonb) / `captions_data` (jsonb); `rfi_register.created_at`,
  `priority` (text, default `'Normal'`), `response_required_by` (date), and nine RFI-detail columns —
  `question`, `reference_doc`, `cost_impact`, `schedule_impact`, `environmental_impact`,
  `public_affairs_impact`, `client_id`, `document_path` (all text), `document_generated_at`
  (timestamptz) — added and live as of 2026-08-13; `rfi_register.instructions`,
  `rfi_register.note` (both text, nullable, no default) — added and live as of 2026-08-13,
  columns exist but nothing writes them yet; `rfi_usage.created_at`, `ai_scans_today`,
  `ai_scans_date`; `approved_rfis.project_id`
- `user_sessions` primary key is `id` (uuid) — `session_key` is UNIQUE, not the PK. Don't assume
  otherwise from memory.
- Buckets: `rfi-manager-files` (PDFs, Word docs, logo, sig) / `snapshots` (Tab 4 crops)
- AI scan limits: FREE 3/day, PAID 20/day — stored in `rfi_usage.ai_scans_today` + `ai_scans_date`

---

## 7 — CURRENT APP STATE

| Component | Status |
|---|---|
| Tab 1 — Company Setup | ✅ Fully audited and complete |
| Tab 2 — Project Setup | ✅ Fully audited and complete |
| Tab 3 — Analyse Drawings | ✅ Fully audited and complete |
| Tab 4 — Crop and Annotate | ✅ Fully audited and complete |
| Tab 5 — Generate RFI | ✅ Fully audited and complete |
| Tab 6 — RFI Register | ✅ Fully audited and complete |
| generate_rfi.py | ✅ Fully rebuilt — two-page professional layout with all sections |
| Auth / login / signup / password reset | ✅ Complete and deployed |
| Deployed to Streamlit Cloud | ✅ Live |

---

## 8 — ACTIVE TASKS — PENDING

**Remaining pre-deployment:**
- Add http://localhost:8501 to Supabase Redirect URLs for local dev
- Upgrade Supabase to Pro tier (free tier hitting usage limits)
- Full end-to-end test with a real NZ engineer

---

## 9 — KNOWN ACTIVE RISKS

- Scanned/raster PDFs → no extractable text → AI scan returns no results; no OCR fallback exists
- Paywall has no checkout flow — upgrade is manual email to `ajohnsudhakar@gmail.com`
- No automated tests — all testing is manual end-to-end
- Drawing revision (Rev B upload) wipes all prior AI scan work — no revision management yet
- Free Supabase tier at usage limits — may cause intermittent failures under load
- Project IDs are now human-readable slugs e.g. mary-durnal-projects-a3f2 — old proj_001 style IDs exist only for soft-deleted test projects
- Previously generated documents reads from Supabase Storage (`list_project_documents`) — survives container restarts. The left panel's pending-issue exclusion does NOT — since C1 (d894335), it checks `rfi_register` (`reg_rows`) instead of matching Storage filenames. Moving that exclusion off filename matching is what closed the bug where deleting a document made its issue card reappear in the pending list.
- Local disk used only as session cache for PDFs and snapshots — all structured data writes go to Supabase only
- Empty-label accessibility warning fires live on the two template-name `st.text_input` calls in the Instructions and Note template panels (`ui_generate.py`) — both pass `label=""` with `label_visibility="collapsed"`. Confirmed `label_visibility="collapsed"` does NOT suppress this warning by itself — Streamlit still requires a non-empty label string underneath it; the visibility setting only controls whether that label is shown. Will become an error in future Streamlit versions — fix: give both a real label (e.g. `"Template name"`) and keep `label_visibility="collapsed"` to hide it visually.

---

## 10 — REFERENCE

- Full fix history (31 bugs + security fixes S1–S6): `.claude/HISTORY.md`
- Working style, drill detail, communication rules: `.claude/WORKING_STYLE.md`
- Read WORKING_STYLE.md at every session start. Read HISTORY.md only when specifically asked.
