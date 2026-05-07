# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Full project intelligence is in `.claude/CLAUDE.md`** — read it completely before any task. It contains the architecture, all known bugs and their fixes, Supabase configuration, and rules that must never be violated.

---

## Commands

**Install dependencies**
```
pip install -r requirements.txt
```

**Run the app**
```
py -m streamlit run scripts/app.py
```

**Syntax check a file after editing** (required after every change)
```
py -m py_compile scripts/<file>.py
```

---

## Secrets

Create `.streamlit/secrets.toml` (never commit this file):
```toml
SUPABASE_URL = "https://kflkrzxaaoceemcudqvb.supabase.co"
SUPABASE_KEY = "<anon key from Supabase dashboard>"
ANTHROPIC_API_KEY = "<key from Anthropic console>"
```

---

## Repository Structure

The git repository root is inside `scripts/` — not the workspace root. All Python source files live in `scripts/`.

```
RFI_Manager_Public/
├── scripts/              ← git repo root AND all Python source
│   ├── app.py            ← entry point: auth, sidebar, tab routing
│   ├── data_layer.py     ← ALL Supabase and storage access (single source of truth)
│   ├── ui_company.py     ← Tab 1: company setup
│   ├── ui_project.py     ← Tab 2: project setup + PDF upload
│   ├── ui_analyse.py     ← Tab 3: AI drawing analysis
│   ├── ui_crop.py        ← Tab 4: crop and annotate
│   ├── ui_generate.py    ← Tab 5: Word document generation
│   ├── ui_register.py    ← Tab 6: RFI register and Excel export
│   └── generate_rfi.py   ← Word doc builder (called via generate_rfi_document())
├── .streamlit/
│   └── secrets.toml      ← never commit
├── requirements.txt
└── .claude/
    └── CLAUDE.md         ← full project intelligence file
```

---

## Architecture in One Paragraph

`app.py` handles authentication (Supabase email/password → session stored in `user_sessions` table → `?sid=` URL param for persistence), renders the sidebar (project switcher, workflow progress), and routes to six tab modules. Every read and write to Supabase or local disk goes through `data_layer.py` — tab modules import from it and must never access Supabase directly. All data is scoped by user email; `email_to_folder(email)` converts email to a safe storage path prefix. PDFs are stored both locally (`projects/{email_folder}/{pid}/drawings/`) and in Supabase Storage; `resolve_pdf_path()` returns a local path, downloading from Supabase if the local copy is missing.

---

## Hard Constraints (never violate)

- `streamlit==1.55.0` — never upgrade (RerunException and layout tied to this version)
- `supabase==2.10.0` — never upgrade (crashes on Python 3.14 with newer versions)
- `st.rerun()` must never be inside a `try/except` block — it raises `RerunException` which inherits from `Exception` and will be silently caught
- `{"upsert": "true"}` — string, not boolean, for Supabase storage file options
- Never say "Claude" in any UI text — always say "AI"
- All storage paths must use `email_to_folder(email)` — never raw email strings
- Soft-delete only for projects — set `deleted_at`, never hard-delete rows
- All project queries must filter `.is_("deleted_at", "null")`
