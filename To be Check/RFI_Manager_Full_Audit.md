# RFI Manager — Full Product Audit & Enhancement Roadmap

> **For: John Sudhakar**
> Deep analysis of all 9 source files against Procore RFI industry standards.
> This document tells you exactly what to build, fix, and add — tab by tab.

---

## Executive Summary

Your tool is genuinely impressive for a 60% build. The foundation is solid:
- Clean Supabase + local fallback architecture
- AI-powered drawing analysis (Claude) — a differentiator most tools don't have
- Word document generation with smart layout (portrait/landscape)
- Auth, session persistence, freemium gating — all production-grade

**What's missing is the RFI lifecycle itself.** Your tool brilliantly *generates* RFIs but doesn't yet *manage* them as living documents. The industry standard (Procore, Autodesk BIM 360, PlanGrid) is built around the post-generation workflow: routing, responding, closing, tracking. That's the gap to close.

---

## Current Tab Structure vs. What It Should Be

| Current Tab | What It Does Now | Industry Gap |
|-------------|-----------------|--------------|
| **Company** | Company + originator setup | ✅ Correct — foundation data |
| **Project** | Project details + PDF upload + recipients | Missing: BIC assignment per project, due-date defaults |
| **Analyse Drawings** | AI scans PDF → flags issues | Missing: issue editing, priority overrides, BIC per issue |
| **Crop Viewer** | Snapshot screenshots from drawings | Missing: annotation/markup on snapshots |
| **Generate RFI** | Builds Word doc from approved list | Missing: response section, cost/schedule impact fields |
| **Register** | Shows list of generated RFIs | Missing: BIC column, overdue alerts, respond/close workflow |

**Recommended new tab to add:** `📬 Respond & Close` — the RFI response management workflow.

---

## Tab-by-Tab Deep Analysis

---

### Tab 1 — Company Setup ✅ Good Foundation

**What's there:** Company name, address, website, originator name/title/phone/email, logo upload, signature upload.

**What's working well:** This correctly separates company identity from project identity. The logo/signature embedded in generated documents is professional.

**What to add:**

1. **Default Response Window** — Add a field: "Default response required by (days): [7]". This auto-populates `response_required_by` on every new RFI instead of leaving it blank.

2. **Default RFI Number Prefix** — Currently hardcoded as `RFI-001`. Let users set a custom prefix per company (e.g., `ABC-RFI-001`, `TMP-001`).

3. **Company Role** — What is this company's role on projects? (General Contractor / Subcontractor / Architect / Engineer / Owner). This determines which side of the RFI they're on — initiator or respondent.

---

### Tab 2 — Project Setup ⚠️ Missing Critical Fields

**What's there:** Project name, address, project number, PDF upload, recipients list (company/attn/email/phone/role).

**What's working well:** Multi-project support, Supabase sync, PDF upload to cloud storage.

**Critical gaps:**

1. **No BIC (Ball-in-Court) default per recipient** — The recipients list stores company/attn/email/phone/role. But there's no concept of "this person is the default BIC for this project." In Procore, every project has a designated respondent (usually the Architect). You need to add a `is_default_bic: bool` flag to each recipient, so when a new RFI is created, it auto-assigns the BIC.

2. **No project-level due-date default** — No `default_response_days` field. Every RFI is generated without a deadline unless manually set in Analyse tab.

3. **Recipients need roles expanded** — Currently a free-text `role` field. Should be a dropdown: `Architect / Structural Engineer / Civil Engineer / MEP Engineer / Owner / General Contractor / Subcontractor / Other`. This matters for routing logic.

4. **No project status** — Projects have no active/archived/completed status. A user with 20 projects can't tell which ones are live.

**SQL schema fix needed in `rfi_register`:**
```sql
-- Add missing columns to rfi_register
ALTER TABLE rfi_register ADD COLUMN IF NOT EXISTS ball_in_court text;
ALTER TABLE rfi_register ADD COLUMN IF NOT EXISTS cost_impact boolean DEFAULT false;
ALTER TABLE rfi_register ADD COLUMN IF NOT EXISTS cost_impact_amount numeric;
ALTER TABLE rfi_register ADD COLUMN IF NOT EXISTS schedule_impact boolean DEFAULT false;
ALTER TABLE rfi_register ADD COLUMN IF NOT EXISTS schedule_impact_days int;
ALTER TABLE rfi_register ADD COLUMN IF NOT EXISTS suggested_solution text;
ALTER TABLE rfi_register ADD COLUMN IF NOT EXISTS response text;
ALTER TABLE rfi_register ADD COLUMN IF NOT EXISTS date_responded date;
ALTER TABLE rfi_register ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();
ALTER TABLE rfi_register ADD COLUMN IF NOT EXISTS revision_number int DEFAULT 0;
ALTER TABLE rfi_register ADD COLUMN IF NOT EXISTS location text;
ALTER TABLE rfi_register ADD COLUMN IF NOT EXISTS due_date date;
```

---

### Tab 3 — Analyse Drawings ✅ Your Biggest Differentiator — Needs Polish

**What's there:** Claude AI scans PDF pages in batches, returns JSON issues with: `issue_number`, `sheets`, `category`, `description`, `reason`. Users can approve/reject each issue and set priority.

**What's working brilliantly:** Using Claude Vision on construction drawings is genuinely cutting-edge. No mainstream tool does this natively. This is your product's #1 selling point — protect and polish it.

**What to add:**

1. **BIC Assignment per Issue** — When approving an issue, let the user assign WHO should respond to this specific RFI. Show the project's recipient list as a dropdown. This becomes the `ball_in_court` on the register.

   ```
   Issue #4: Missing rebar detail at column F-12
   Priority: [High ▼]    BIC: [Jane Doe — Structural Engineer ▼]    Due Date: [27 May 2026]
   [✓ Approve]  [✗ Reject]  [✏️ Edit]
   ```

2. **Suggested Solution Field** — After AI generates an issue, let the user add a "Suggested Solution" before approving. This is standard industry practice — it dramatically speeds up response time.

3. **Cost/Schedule Impact Flags** — For each approved issue, add two toggles:
   - `💰 Cost impact?` → if yes, show amount field
   - 📅 `Schedule impact?` → if yes, show days field
   These get stored on the register row and show in the document.

4. **Edit Description Before Approving** — Currently users can only approve/reject. They need to be able to edit the AI-generated description before approving. AI output always needs human review for accuracy.

5. **Issue Categories are Good — Add "Specification Conflict" Urgency** — Your current categories (Missing Information, Conflict Between Sheets, Coordination Issue, Ambiguous Detail, Specification Conflict, Structural Concern, Architectural Concern, Services Conflict) are excellent and align with industry standards. Add one: `"Code Compliance Issue"` — issues that may violate building codes need urgent flagging.

6. **Batch Re-scan** — Currently a re-scan replaces all results. Add an option to "scan only new pages" (pages not previously scanned) to preserve existing approvals.

---

### Tab 4 — Crop Viewer ⚠️ Needs Annotation Feature

**What's there:** Users navigate PDF pages and take cropped screenshots (snapshots) that get embedded in the generated Word document.

**What to add:**

1. **Markup/Annotation on Snapshots** — Industry standard: RFI snapshots should have annotations (arrows, circles, text callouts) highlighting the specific area of concern. Even a basic Streamlit drawing canvas (using `streamlit-drawable-canvas`) would be a major upgrade.
   ```
   [📷 Crop]  [✏️ Annotate]  [🗑️ Delete]
   ```

2. **Link Snapshot to Specific RFI** — Currently snapshots are named `RFI_001_snap1.png` based on RFI number. Make the linkage explicit in the UI so users know which snapshot belongs to which RFI.

3. **Caption Field** — You already have `save_project_captions` in `data_layer.py` — expose this in the UI. When a snapshot is taken, prompt: "Add a caption for this snapshot (optional)." This appears below the image in the Word doc.

---

### Tab 5 — Generate RFI ⚠️ Document is Good, Workflow is Incomplete

**What's there:** Takes the approved list, calls `generate_rfi_document()`, produces a beautifully formatted A4 Landscape Word document with: logo, header, addressee block, info table (subject/drawings/priority/response-by), main description + reason, snapshots, signature.

**What the document is missing (vs. industry standard):**

1. **No "Suggested Solution" section** — The Word doc currently shows: Description → Reason → Snapshots. Industry standard adds a third row: "Contractor's Proposed Solution" — this is how Procore, Autodesk, and most standard RFI forms work. When a contractor suggests a solution, response time drops by 40%.

2. **No Cost/Schedule Impact section** — If `cost_impact` or `schedule_impact` is flagged, the document should include a highlighted warning box stating: "⚠️ This RFI has a potential cost/schedule impact. A response is required by [date] to avoid delay."

3. **Only one recipient** — Currently the document addresses a single `client` (To/Attn/Email). Industry practice sends to multiple parties (Architect + Engineer + Owner). Add a CC list section showing all distribution recipients.

4. **No Response Section in the Document** — Procore's RFI document has a physical "Response" section at the bottom with fields: Response / Responded By / Date. When you later implement the Respond workflow, this section should be populated and the document regenerated.

5. **No RFI Revision tracking** — If an RFI gets a Revision (the response was unsatisfactory), the document should show "REVISION 2" prominently in the header.

**Generate flow fix — current issue:**
`ui_generate-6.py` triggers generation but doesn't automatically update the register status to "Open" after a document is generated. Add this:
```python
# After successful generation, update register status
for issue in approved:
    update_project_register_status(pid, get_rfi_num(issue), "Open", email)
```

---

### Tab 6 — Register ⛔ This Is the Biggest Gap

**What's there:** A basic table showing: RFI #, project name, sheet reference, category, priority, response_required_by, description, status (with editable dropdown), date raised.

**What the industry requires and you're missing:**

1. **No BIC Column** — The most critical column in any RFI log. Every PM's first question: "Who has the ball right now?" This must be visible in the table at all times.

2. **No Overdue Highlighting** — If `due_date` (response_required_by) has passed and status is still Open/In Review, the row should be highlighted red. This is table-stakes for any RFI management tool.

3. **No Response Capture Workflow** — Currently you can change status to "Responded" but there's nowhere to record: what was the actual response? Who responded? When? This is the core missing feature.

4. **No "Days Open" Calculated Column** — `today - date_raised` = days this RFI has been open. Industry benchmark: anything over 14 days needs escalation.

5. **No Filter/Search** — With 50+ RFIs, the log becomes unusable without filtering by: status, BIC, overdue, category, priority.

6. **No Cost/Schedule Impact flags** — No visual indicator of which RFIs have financial or timeline risk.

**What the Register tab should look like:**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  RFI Register — [Project Name]                     [+ New RFI]  [Export]   │
├──────┬────────────────────────────┬───────────────┬──────────┬──────────────┤
│ RFI# │ Subject                    │ BIC           │ Due Date │ Status       │
├──────┼────────────────────────────┼───────────────┼──────────┼──────────────┤
│ 001  │ Rebar detail at col F-12   │ Jane Doe      │ 📅 OVERDUE (3d) │ 🔴 Open  │
│ 002  │ Wall thickness Grid B-3    │ John Smith    │ May 30   │ 🟡 In Review │
│ 003  │ MEP coordination Level 2   │ –             │ Jun 02   │ 🟢 Responded │
└──────┴────────────────────────────┴───────────────┴──────────┴──────────────┘
Filter: [All Statuses ▼]  [All BICs ▼]  [Overdue Only ☐]  Search: [______]
```

---

### Tab 7 — NEW: Respond & Close (Must Add)

This entire workflow is missing from your tool. It is the core of Procore's RFI module.

**What this tab does:**

When a PM clicks on an Open RFI in the register, they should be able to:

1. **View the full RFI** — description, reason, snapshots, drawing ref, priority, BIC, due date
2. **Record a response** — text field: "Official Response from [Architect/Engineer]"
3. **Set respondent info** — Who responded? (Name, company, date)
4. **Mark as Responded** — Changes status; stamps `date_responded`; triggers notification
5. **Close or Revise** — If response is acceptable → Close. If not → Create Revision (increment `revision_number`, reopen)
6. **Regenerate document with response** — Re-run `generate_rfi_document()` with the response section populated

**Minimal UI for the respond flow:**

```
RFI-003 — Clarify wall thickness at Grid B-3
Status: In Review    BIC: Jane Doe (Structural Engineer)    Due: May 30, 2026

[DESCRIPTION]
Drawing S-201 Detail 3 shows 200mm wall. S-101 Schedule shows 250mm...

[RESPONSE — Official Answer]
┌─────────────────────────────────────────────────────┐
│ Confirm 250mm as per structural schedule S-101.     │
│ Detail 3 on S-201 is superseded.                    │
└─────────────────────────────────────────────────────┘
Responded by: [Jane Doe ▼]   Date: [17 May 2026]   Company: [ABC Structural]

[✓ Mark as Responded]   [✗ Response Unsatisfactory — Create Revision]   [✅ Close RFI]
```

---

## Critical Data Layer Fixes (data_layer.py)

These are bugs/gaps that will cause silent data loss:

### Fix 1 — `save_project_register` Must Write to Supabase
```python
# CURRENT (broken — only writes locally):
def save_project_register(pid, rows, email=""):
    with open(d / "register.json", "w") as f:
        json.dump(rows, f, indent=2)

# FIXED:
def save_project_register(pid, rows, email=""):
    # Write to Supabase
    sb = _get_storage_client()
    if sb and email and pid:
        try:
            for row in rows:
                sb.table("rfi_register").upsert({
                    "email": email,
                    "project_id": pid,
                    **row
                }, on_conflict="email,project_id,rfi_number").execute()
        except Exception as e:
            _log_error("save_project_register[supabase]", e)
    # Also write locally as fallback
    d = proj_dir(pid, email)
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "register.json", "w") as f:
        json.dump(rows, f, indent=2)
```

### Fix 2 — Add `updated_at` to Status Updates
```python
def update_project_register_status(pid, rfi_num, status, email=""):
    from datetime import datetime, timezone
    updated = datetime.now(timezone.utc).isoformat()
    # ... existing code ...
    row["status"] = status
    row["updated_at"] = updated  # ADD THIS
```

### Fix 3 — Remove Duplicate `load_register`
The `load_register(email, pid)` function (line ~180 in data_layer.py) is a duplicate of `load_project_register(pid, email)`. Keep `load_project_register`, delete `load_register`, update all callers.

### Fix 4 — New function needed: `save_rfi_response()`
```python
def save_rfi_response(pid: str, rfi_num: int, response: str,
                      responded_by: str, email: str = ""):
    from datetime import date, timezone, datetime
    sb = _get_storage_client()
    today = date.today().isoformat()
    updated = datetime.now(timezone.utc).isoformat()
    if sb and email and pid:
        try:
            sb.table("rfi_register").update({
                "response": response,
                "date_responded": today,
                "status": "Responded",
                "ball_in_court": responded_by,
                "updated_at": updated,
            }).eq("email", email).eq("project_id", pid
            ).eq("rfi_number", rfi_num).execute()
        except Exception as e:
            _log_error("save_rfi_response", e)
    # Local fallback
    rows = load_project_register(pid, email)
    for row in rows:
        if row.get("rfi_number") == rfi_num:
            row["response"] = response
            row["date_responded"] = today
            row["status"] = "Responded"
            row["updated_at"] = updated
    save_project_register(pid, rows, email)
```

---

## Word Document Enhancements (generate_rfi-2.py)

### Add Suggested Solution Row to Info Table
```python
# In the INFO TABLE section (after "Response Required By" row):
info_data = [
    ("Project / Address", f"{PROJECT_NAME} | {PROJECT_ADDRESS}"),
    ("Subject", issue['description']),
    ("Drawing Reference", sheets_str),
    ("Priority", priority),
    ("Response Required By", response_by),
    ("Suggested Solution", issue.get('suggested_solution', '')),  # ADD
    ("Cost Impact", "Yes" if issue.get('cost_impact') else "No"),  # ADD
    ("Schedule Impact", f"{issue.get('schedule_impact_days', 0)} days"
                        if issue.get('schedule_impact') else "No"),  # ADD
]
```

### Add Response Section at End of Document
```python
# After signature table, add response section:
if issue.get('response'):
    spacer(doc, 8)
    resp_tbl = doc.add_table(rows=2, cols=2)
    resp_tbl.style = 'Table Grid'
    set_table_width(resp_tbl, cw)
    # Header row
    set_cell_bg(resp_tbl.cell(0, 0), "D5E8D4")  # green background
    para(resp_tbl.cell(0, 0), "OFFICIAL RESPONSE", bold=True, size=10)
    para(resp_tbl.cell(0, 1), f"Date: {issue.get('date_responded','')}", size=9)
    # Response content
    merged = resp_tbl.cell(1, 0).merge(resp_tbl.cell(1, 1))
    para(merged, issue.get('response', ''), size=10)
```

---

## generate_rfi-2.py — Issue: `approved_rfis` Data Model is Thin

The `issue` dict currently has: `rfi_number`, `sheets`, `description`, `reason`, `priority`, `response_required_by`.

**Needs to add:**
- `ball_in_court` — who to address the RFI to
- `suggested_solution` — contractor's proposed fix
- `cost_impact` / `cost_impact_amount`
- `schedule_impact` / `schedule_impact_days`
- `location` — where on site
- `response` / `date_responded` / `responded_by` — for closed RFIs
- `revision_number` — show "REVISION 2" in header if > 0
- `category` — already present ✅

---

## Dashboard / Analytics (Missing Entirely)

Add a **Dashboard tab** or a sidebar widget with:

| Metric | How to Calculate |
|--------|-----------------|
| Open RFIs | `COUNT WHERE status = 'Open'` |
| Overdue RFIs | `COUNT WHERE due_date < today AND status IN ('Open','In Review')` |
| Avg Response Time | `AVG(date_responded - date_raised) WHERE status IN ('Responded','Closed')` |
| RFIs by BIC | `GROUP BY ball_in_court` — shows who's the bottleneck |
| RFIs by Category | `GROUP BY category` |
| Cost Exposure | `SUM(cost_impact_amount) WHERE status NOT IN ('Closed')` |

This can be rendered with `st.metric()` widgets at the top of the Register tab — no new tab needed.

---

## UX Improvements (Streamlit-Specific)

### 1. The Workflow Is Not Obvious
A first-time user looking at 6 tabs has no idea where to start. Add a **progress bar / checklist** in the sidebar:

```
📋 RFI Manager
─────────────────
✅ 1. Company Setup
✅ 2. Project Setup
✅ 3. Analyse Drawings
⬜ 4. Crop Snapshots
⬜ 5. Generate RFI
⬜ 6. Register
```

### 2. Tab Names Should Be Action-Oriented
Current tab names are nouns. Change to verbs + context:

| Current | Recommended |
|---------|-------------|
| Company | 🏢 My Company |
| Project | 📁 Projects |
| Analyse Drawings | 🔍 Analyse Drawings |
| Crop Viewer | 📷 Crop & Annotate |
| Generate RFI | ⚡ Generate RFI |
| Register | 📋 RFI Register |
| *(missing)* | 📬 Respond & Close |

### 3. Status Colors Are Not Standardized
Throughout the app, status is shown as plain text. Add color coding consistently:

```python
STATUS_COLORS = {
    "Draft":       "⚫",
    "Open":        "🔵",
    "In Review":   "🟡",
    "Responded":   "🟢",
    "Closed":      "⚪",
    "Overdue":     "🔴",
}
```

### 4. Empty States Need Work
When a user has no projects, no analyses, no RFIs — the app shows bare `st.info()` messages. These should be warmer, with a clear call-to-action button:

```
📁 No projects yet
Create your first project to get started analysing drawings and generating RFIs.
[+ Create Project]
```

---

## Priority Build Order

### 🔴 Do First (Critical — breaks core workflow)
1. Fix `save_project_register` to write to Supabase
2. Add BIC field to register rows + `upsert_project_register_rows`
3. Add BIC dropdown in Analyse tab when approving issues
4. Add `due_date` field (from `response_required_by` or calculated)
5. Add `updated_at` to all register updates

### 🟡 Do Next (High value for users)
6. Add overdue highlighting in Register tab (red row if past due date)
7. Add "Suggested Solution" field in Analyse tab + carry into document
8. Add cost/schedule impact toggles in Analyse tab
9. Add response capture to Register tab (the Respond & Close flow)
10. Update document template to include Suggested Solution section

### 🟢 Do After (Polishes the product)
11. Add annotation/markup on snapshots (Crop tab)
12. Add dashboard metrics to Register tab header
13. Add workflow progress guide in sidebar
14. Add filter/search to Register tab
15. Add multi-recipient CC list in generated document

---

## Questions for John Before Building

Before starting on the fixes, I need clarity on 3 things:

1. **The "Analyse → Approve → Generate" flow** — currently, do users ever come back and *edit* an approved RFI before generating it? Or is it always a one-way flow (approve → generate → done)?

2. **Who uses this tool?** — Is it always the GC/PM initiating RFIs and sending to Architects? Or do you envision Architects also using it to respond? This determines how deep the "Respond" tab needs to be in v1.

3. **The `response_required_by` field** — In your Analyse tab, can users currently set this per issue before approving? Or is it always blank and set later? This affects where to add the due-date UX.

