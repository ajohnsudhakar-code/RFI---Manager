# RFI Manager — Product Blueprint & Field Template

> A comprehensive guide synthesizing construction RFI best practices for building a fast, effective RFI Manager tool.

---

## What Is an RFI in Construction?

A **Request for Information (RFI)** is a formal document used during construction to clarify ambiguities, resolve conflicts, fill information gaps, and answer questions that arise from project drawings, specifications, or site conditions.

RFIs move between three primary parties:
- **Initiator** — Subcontractor, site manager, or field crew who raises the question
- **Reviewer** — General Contractor / Project Manager who routes and screens the RFI
- **Respondent (BIC — Ball in Court)** — Architect, Engineer, or Owner who answers

> **Key insight from the Procore course:** The RFI log must always show who the BIC is at any time. This is the heartbeat of your tool.

---

## The 5 RFI Lifecycle Stages

Your RFI Manager must support all five stages with distinct statuses:

| Stage | Status Label | Who Acts | What Happens |
|-------|-------------|----------|--------------|
| 1. Draft | `Draft` | Initiator | RFI is being written; not yet submitted |
| 2. Open | `Open` | GC / PM | RFI submitted; routed to respondent |
| 3. In Review | `In Review` | Architect / Engineer | Under active review; BIC is responding |
| 4. Responded | `Responded` | GC / PM | Answer received; initiator reviews |
| 5. Closed | `Closed` | GC / PM | Accepted; RFI officially resolved |

> **Special state: `Revised`** — When a response is insufficient, the RFI can be revised and resubmitted. Procore tracks this as a **Revision** (version 2, 3, etc.) rather than a new RFI.

---

## The Complete RFI Data Model

### Required Fields (Core)

| Field | Type | Purpose |
|-------|------|---------|
| `rfi_number` | Auto-increment string (e.g., `RFI-001`) | Unique identifier for tracking and log |
| `title` | Short text | One-line description of the issue |
| `status` | Enum (Draft / Open / In Review / Responded / Closed) | Current lifecycle stage |
| `ball_in_court` (BIC) | Linked contact | Who currently must act — visible at all times |
| `date_created` | Date | When the RFI was initiated |
| `date_submitted` | Date | When it was formally sent |
| `due_date` | Date | Response deadline (typically 5–14 business days) |
| `question` / `description` | Long text | Clear, specific description of the issue |
| `spec_section` | Text | Reference to spec section or drawing number |
| `location` | Text | Where on the project site this applies |
| `priority` | Enum (Low / Normal / High / Urgent) | Urgency level |

### Important Fields (Strongly Recommended)

| Field | Type | Purpose |
|-------|------|---------|
| `rfi_category` | Enum | Design Clarification / Change Request / Substitution / Site Condition / Constructability |
| `cost_impact` | Boolean + amount | Does this RFI have a cost implication? |
| `schedule_impact` | Boolean + days | Does this affect the project timeline? |
| `suggested_solution` | Long text | Initiator's proposed resolution (speeds up response) |
| `attachments` | File list | Drawings, photos, specs, sketches |
| `response` | Long text | The official answer from the respondent |
| `date_responded` | Date | When the official response was received |
| `drawing_reference` | Text | Specific drawing sheet/detail being questioned |

### Optional / Advanced Fields

| Field | Type | Purpose |
|-------|------|---------|
| `distribution_list` | Multi-select contacts | Who receives notifications |
| `linked_submittal` | Reference | If the RFI relates to a submittal |
| `linked_change_order` | Reference | If the RFI spawned a change order |
| `revision_number` | Integer | Tracks RFI revision iterations |
| `tags` | Multi-select | Custom tags for filtering |
| `source_company` | Linked company | Which subcontractor/trade initiated |
| `assigned_to` | Linked user | Internal reviewer |

---

## RFI Categories — What Your Tool Should Support

These 5 categories cover ~95% of all construction RFIs:

1. **Design Clarification** — Conflicts in drawings, incomplete plans, spec ambiguities
2. **Design Change Request** — Changes triggered by errors in construction, sequencing problems
3. **Substitution Request** — Value engineering, material substitution, availability issues
4. **Site Condition / Field Condition** — Unexpected conditions found during construction
5. **Constructability Issue** — The design cannot be built as shown without modification

---

## The RFI Form — Field-by-Field UX Guidance

### What to Show When Creating an RFI

**Section 1: Identity**
- `RFI Number` — Auto-generated, editable prefix (e.g., `RFI-001`)
- `Title` — Required, 5–80 characters, verb+noun format ("Clarify wall thickness at Grid B-3")
- `RFI Category` — Dropdown (see 5 categories above)
- `Priority` — Low / Normal / High / Urgent (default: Normal)

**Section 2: The Question**
- `Description / Question` — Rich text; what is unclear, missing, or conflicting?
- `Spec Section Reference` — Text field, e.g., `Section 03300 – Concrete`
- `Drawing Reference` — Sheet and detail reference
- `Location on Site` — Floor, room, grid reference, or GPS pin

**Section 3: Impact Assessment**
- `Cost Impact?` — Toggle + estimated amount
- `Schedule Impact?` — Toggle + estimated days
- `Suggested Solution` — Optional rich text; proposed fix from initiator

**Section 4: People & Dates**
- `Submitted By` — Auto-filled (current user)
- `Assigned To / BIC` — The person who must respond
- `Distribution List` — Who gets notified
- `Due Date` — Calculated (submit date + default response window, editable)

**Section 5: Attachments**
- Drag-and-drop file upload
- Link to drawing (from Drawings module if integrated)
- Image preview for photos

---

## What Should NOT Be in an RFI

Avoid these anti-patterns in your tool and in the RFIs users create:

- **Vague questions** — "Please clarify the wall" (no drawing ref, no location, no spec)
- **Multiple questions in one RFI** — One RFI = one question. Your tool should warn users if the question section contains what looks like multiple distinct items
- **RFIs used as change orders** — Your tool should flag if cost/schedule impact is selected and redirect to a change order workflow
- **No due date** — Every submitted RFI must have a deadline; make this required on submit
- **No drawing/spec reference** — Warn (not block) if these are missing at submission
- **Missing BIC** — Never allow an RFI to be submitted without a Ball-in-Court assigned

---

## RFI Log — Your Most Important View

The RFI log is the command center. Based on the Procore course and industry practice, your log table should include:

| Column | Why It Matters |
|--------|---------------|
| RFI # | Sort and jump to any RFI instantly |
| Title | Scannable description |
| Status | Color-coded pill (Draft=gray, Open=blue, In Review=amber, Responded=green, Closed=dark) |
| BIC (Ball in Court) | Who must act RIGHT NOW — the most critical column |
| Priority | Red badge for Urgent/High |
| Due Date | Highlight overdue items in red |
| Days Overdue / Days Left | Calculated field |
| Category | Filter by type |
| Cost Impact | Flag if yes |
| Schedule Impact | Flag if yes |

**Essential log features:**
- Filter by status, BIC, category, date range, overdue
- Sort by due date, RFI number, priority
- Bulk actions: reassign BIC, change status, export
- Search by keyword across title + description
- Export to PDF / Excel for distribution

---

## Notifications & Reminders — Critical for Adoption

The biggest pain point in RFI management is delayed responses. Your tool must automate:

- **On Submit** → Email/notification to BIC and distribution list
- **Day 3 Before Due** → Reminder to BIC
- **Day 1 Before Due** → Urgent reminder to BIC + Project Manager
- **Overdue** → Daily escalation until responded
- **On Response** → Notify initiator and PM immediately
- **On Close** → Notify entire distribution list

---

## Insights & Analytics for Your Dashboard

Add these metrics to give PMs instant project health visibility:

- **Open RFIs by BIC** — Who is the bottleneck right now?
- **Average Response Time** — Benchmark: industry average is 7–10 business days
- **Overdue RFI Count** — Red alert badge
- **RFIs by Category** — Are most issues design clarifications? That's a design problem upstream
- **RFIs by Subcontractor** — Which trade is generating the most questions?
- **Cost Impact Exposure** — Total unresolved RFI cost impact ($)
- **Schedule Impact Exposure** — Total unresolved schedule days at risk

---

## Procore RFI Tool — Key Lessons to Incorporate

From the Procore Learn course (RFIs Tool — 8 lessons):

1. **Centralized Log** — All RFIs in one place; the log is the source of truth
2. **BIC is always visible** — The current Ball-in-Court must be shown everywhere
3. **Create → View → Respond → Close** is the core flow — keep it linear and obvious
4. **Revisions are first-class** — When a response is unsatisfactory, create a revision (not a new RFI). Track revision history (v1, v2, v3)
5. **Closing is a deliberate action** — Closing an RFI means work can proceed. Make it a clear, confirmable action, not an accidental click
6. **Resources/References attached** — Drawings and specs should be linkable to RFIs directly

---

## Recommended Tool Features — Priority Order

### Phase 1 (MVP)
- [ ] Create / Edit RFI with all required fields
- [ ] Status workflow: Draft → Open → In Review → Responded → Closed
- [ ] RFI Log with BIC column always visible
- [ ] File attachments
- [ ] Email notifications on key status changes
- [ ] Due date tracking + overdue highlighting
- [ ] PDF export of individual RFIs

### Phase 2 (Growth)
- [ ] RFI Revisions / version history
- [ ] Drawing/spec reference linking
- [ ] Bulk actions in log
- [ ] Dashboard with key metrics (open count, overdue, avg response time)
- [ ] Custom RFI number prefixes per project
- [ ] Role-based permissions (who can create, respond, close)

### Phase 3 (Scale)
- [ ] Change order linkage (if RFI has cost/schedule impact)
- [ ] Submittal linkage
- [ ] Analytics: category trends, BIC bottleneck analysis, response time benchmarks
- [ ] API for integrations (Procore, Autodesk, email)
- [ ] Mobile-first field creation (photo + voice-to-text RFI)

---

## Sample RFI — What a Good One Looks Like

```
RFI Number:     RFI-0047
Title:          Clarify Rebar Spacing at Column Footing F-12
Category:       Design Clarification
Priority:       High
Status:         Open
Ball in Court:  Jane Doe (Structural Engineer, ABC Design)
Due Date:       May 27, 2026

Description:
Drawing S-201, Detail 3 shows #5 rebar at 12" o/c in footing F-12.
However, the structural schedule on S-101 lists F-12 as requiring 
#6 rebar at 8" o/c. The discrepancy must be resolved before concrete 
pour scheduled for May 29.

Drawing Reference:  S-201 Detail 3, S-101 Footing Schedule
Spec Reference:     Section 03200 – Concrete Reinforcement
Location:           Grid B-4, Basement Level

Suggested Solution:
Recommend #6 at 8" o/c per structural schedule as it is more conservative.

Cost Impact:        No
Schedule Impact:    Yes — 2 days if not resolved before May 27
Attachments:        [S-201_Detail3.pdf] [S-101_Schedule.pdf] [site-photo-f12.jpg]
```

---

## Questions for Clarification Before Building

1. **Is this a standalone web app, or does it integrate with an existing platform** (e.g., Procore API, Autodesk)?
2. **Who are the primary users** — General Contractors, Subcontractors, Architects, or all three?
3. **Do you need multi-project support** in the MVP, or is single-project enough to start?
4. **What tech stack are you using** (React, Next.js, Node, etc.)?
5. **Is AI-assisted RFI drafting** (e.g., auto-suggest description based on drawing reference) part of the vision?

