# RFI Manager — What to Incorporate: Industry vs. Your Tool

**For: John Sudhakar**
Benchmarked against: Procore RFI Tool, PlanGrid, CM Fusion, Autodesk Build
Based on: Your 9 source files + Procore course + industry research

---

## Your Biggest Strength — Own It

Your AI-powered drawing analysis (Claude Vision scanning PDF drawings and auto-generating RFIs) is a **genuine market differentiator**.[cite:34] Procore only launched its own "Draft RFI Agent" in open beta in September 2025 — and it only generates from text input, not from scanning drawings.[cite:31] You are doing something more powerful. Everything else in this guide is about building the workflow *around* that differentiator so the product feels complete.

---

## The Core Gap: You Generate. You Don't Yet Manage.

Procore's RFI tool is built around a 5-stage lifecycle: **Draft → Open → In Review → Responded → Closed**.[cite:28] Every feature in Procore — routing, BIC tracking, notifications, revisions, the register — exists to move an RFI through that lifecycle and never let it stall.[cite:11] Your tool handles Stage 1 (Generate) brilliantly. Stages 2–5 are missing entirely. That is the gap to close.

---

## Feature-by-Feature: Industry Standard vs. Your Tool

| Feature | Procore / Industry Standard | Your Tool Today | Incorporate? |
|---------|----------------------------|-----------------|:---:|
| AI-assisted RFI drafting | ✅ Draft RFI Agent (text input) | ✅ **Better** — PDF drawing scan | ✅ Already ahead |
| RFI Number (auto-increment) | ✅ | ✅ | ✅ |
| 5-stage lifecycle status | ✅ Draft→Open→In Review→Responded→Closed | ⚠️ Only "Open/Closed" | **🔴 Must add** |
| Ball-in-Court (BIC) always visible | ✅ Core feature — always shown | ❌ Missing entirely | **🔴 Must add** |
| Due date per RFI + overdue alerts | ✅ | ❌ Not enforced | **🔴 Must add** |
| Cost impact flag | ✅ AI-generated in Procore | ❌ Missing | **🔴 Must add** |
| Schedule impact flag | ✅ AI-generated in Procore | ❌ Missing | **🔴 Must add** |
| Suggested solution field | ✅ | ❌ Missing | **🔴 Must add** |
| Response capture (who, when, what) | ✅ | ❌ Missing | **🔴 Must add** |
| Close RFI workflow | ✅ Deliberate action | ❌ Missing | **🔴 Must add** |
| RFI Revisions (v1, v2, v3) | ✅ Added Sept 2025 | ❌ Missing | 🟡 Add in v2 |
| Automated email notifications | ✅ On every status change | ❌ Missing | 🟡 Add in v2 |
| Overdue escalation reminders | ✅ | ❌ Missing | 🟡 Add in v2 |
| Activity log / audit trail | ✅ Every comment + update logged | ❌ Missing | 🟡 Add in v2 |
| Drawing/spec reference linking | ✅ | ✅ (sheets field) | ✅ |
| Snapshot/photo attachments | ✅ | ✅ (crop viewer) | ✅ |
| Snapshot annotation/markup | ✅ PlanGrid-style markups | ❌ Missing | 🟡 Add in v2 |
| Word/PDF document generation | ✅ | ✅ **Better** — A4 landscape Word | ✅ Already ahead |
| Suggested solution in document | ✅ Standard RFI form field | ❌ Not in Word doc | **🔴 Must add** |
| Response section in document | ✅ Physical response block in doc | ❌ Not in Word doc | **🔴 Must add** |
| Distribution list / CC | ✅ | ⚠️ Single recipient only | 🟡 Add multi-CC |
| RFI Register / Log table | ✅ Centralized, filterable | ⚠️ Basic, no filters | **🔴 Needs upgrade** |
| Filter + search the register | ✅ | ❌ Missing | **🔴 Must add** |
| Overdue highlighting in register | ✅ | ❌ Missing | **🔴 Must add** |
| Days open / response time metric | ✅ | ❌ Missing | 🟡 Add |
| Export register to CSV/PDF | ✅ (enhanced Aug 2025) | ❌ Missing | 🟡 Add in v2 |
| Dashboard / analytics | ✅ Open count, BIC bottleneck, avg response | ❌ Missing | 🟡 Add in v2 |
| Mobile-friendly | ✅ | ⚠️ Streamlit desktop-first | 🟢 Optional |
| Role-based permissions | ✅ | ❌ | 🟢 Optional |
| Submittal linking | ✅ | ❌ | 🟢 Optional (v3) |
| Change order linking | ✅ | ❌ | 🟢 Optional (v3) |

---

## What to Incorporate — Grouped by Priority

### 🔴 Priority 1 — Must Incorporate Now (Completes the Core Product)

These are the features that make RFI Manager a complete tool rather than just a generator. None of these exist in your current build but every industry-standard platform has them.[cite:11][cite:38]

#### 1. Ball-in-Court (BIC) — The Heartbeat Feature

The single most important concept in Procore's RFI module is BIC: at any given moment, one person "has the ball" and everyone can see who it is.[cite:11] Add this as a visible, persistent field everywhere — in the Analyse tab when approving issues, in the Register log as a dedicated column, and in the generated Word document's header block. Without BIC, nobody knows who is responsible for an RFI and it silently stalls.

**Where to add it:**
- Analyse tab: when approving an issue, pick the BIC from the project's recipient list
- Register tab: BIC column always visible — the first column after RFI #
- Generated document: show BIC in the addressee/info block

#### 2. Complete 5-Stage Status Workflow

Your register currently has a status field but only uses "Open" and "Closed". The industry uses 5 stages and each transition means something specific.[cite:28]

```
Draft → Open → In Review → Responded → Closed
```

- **Draft**: Being written, not yet sent
- **Open**: Sent to BIC — they must respond
- **In Review**: BIC acknowledged and is working on it
- **Responded**: Answer received, GC reviews it
- **Closed**: Accepted, work can proceed

Procore makes Closing a deliberate, confirmable action — not an accidental click.[cite:28] Each status should have a visible colour: Draft=grey, Open=blue, In Review=amber, Responded=green, Closed=dark/neutral.

#### 3. Due Date + Overdue Alerts in the Register

Every submitted RFI must have a deadline. Industry average response time is 7–10 business days.[cite:10] When the due date passes and status is still Open or In Review, the row should turn red and show "OVERDUE (3 days)". This is the single most-requested feature in any construction PM tool because it drives accountability.

**How to implement:**
- Add a default response window (in days) in Company/Project settings
- Auto-calculate `due_date = submit_date + default_days`
- Show overdue rows highlighted in the Register
- Add an "Overdue Only" filter toggle

#### 4. Cost & Schedule Impact Flags

Procore's new AI Draft RFI Agent specifically generates cost and schedule impact fields automatically — this was called out as a key feature in their September 2025 release.[cite:31][cite:34] These two fields change everything about how urgently an RFI is treated. An RFI with a 5-day schedule impact sitting unanswered for 10 days is a project crisis. One without impact can wait.

**Where to add:**
- Analyse tab: two toggles per issue when approving — "💰 Cost impact?" (with amount) and "📅 Schedule impact?" (with days)
- Register: show small flags/icons in the register row
- Generated document: add a highlighted warning block if either is flagged

#### 5. Response Capture in the Register

Right now there is nowhere in your tool to record what the response actually was. When an RFI is "Responded", you need to capture: what was the official answer, who gave it, and when.[cite:11] This is fundamental to audit trail and project close-out documentation. In Procore, you can even respond to an RFI directly by email and it records automatically.[cite:11]

**Fields to capture:**
- Official response text
- Responded by (name + company)
- Date responded
- This updates the status to "Responded" and stamps the date

#### 6. Suggested Solution in Analyse Tab AND in the Document

A contractor's "Suggested Solution" is an industry-standard field in every RFI form. When the contractor proposes a solution alongside the question, response time drops significantly because the architect can simply confirm or deny rather than starting from scratch.[cite:15] This field needs to appear in your Analyse tab (when approving an issue) and carry through into the Word document as a dedicated row in the info table.

---

### 🟡 Priority 2 — Incorporate in Version 2 (Makes the Product Stand Out)

#### 7. RFI Revisions

Procore added formal RFI Revisions in September 2025 after feedback from over 600 users.[cite:37] When a response is unsatisfactory, the GC creates a revision (v2, v3...) which is linked to the original and inherits its history. In your tool this means: keep the same RFI number, increment a revision counter, reopen it, re-assign BIC. The revision chain should be visible in the register (RFI-003 Rev.2).

#### 8. Automated Email Notifications

Procore sends automated notifications on every status change and automated reminders when an RFI is approaching or past its due date.[cite:11][cite:39] This is what separates a tool from a tracker — the tool chases people for you. With Supabase, you can trigger emails using Edge Functions or an external email service (Resend, SendGrid). Priority sequence: submit → notify BIC; 2 days before due → reminder; overdue → daily escalation.

#### 9. Activity Log / Audit Trail

Every comment, reply, and update should be logged with a timestamp and user name.[cite:11] This is critical for construction claims and dispute resolution — you need to prove when something was sent, responded to, and closed. Even a simple append-only `activity_log` JSON column in the register table achieves this.

#### 10. Filter, Search & Export the Register

Procore enhanced its export functionality in August 2025 to preserve user-applied filters.[cite:31] Your register will become unusable without search and filter as projects grow. At minimum: filter by status, filter by BIC, filter overdue-only, keyword search on title/description. Export to CSV is the simplest first step for data portability.

#### 11. Multi-Recipient Distribution in the Document

Currently your Word document is addressed to a single client (To/Attn). Industry standard sends the primary RFI to one party (Architect or Engineer) with a CC list showing all other parties who received copies.[cite:7] Add a "CC:" block to the document showing all other recipients from the project's distribution list.

---

### 🟢 Priority 3 — Consider for Version 3 (Power Features)

#### 12. Snapshot Annotation/Markup

PlanGrid's biggest strength is its drawing markup capability.[cite:38] When you crop a snapshot from a drawing, users should be able to draw arrows, circles, and text callouts directly on the image to pinpoint exactly where the issue is. This is a significant development effort but makes the snapshots far more useful as communication documents.

#### 13. Dashboard / Analytics Panel

Procore and all major platforms show a project health dashboard at the top of the RFI register.[cite:39] Key metrics: total open RFIs, overdue count, average response time (benchmark: 7–10 days), RFIs by BIC (who's the bottleneck), RFIs by category, total cost exposure from unresolved RFIs. A Streamlit `st.metric()` row at the top of the Register tab achieves this with minimal effort.

#### 14. Change Order & Submittal Linking

When an RFI results in a design change, it should link to a Change Order. When it relates to a material submittal, it should link to that submittal. This is a larger workflow integration that makes sense only after the core RFI lifecycle is solid.[cite:32]

---

## Workflow Redesign — What It Should Look Like

### Current Workflow (Your Tool)
```
Upload PDF → AI Scans Drawings → Approve Issues → Crop Snapshots → Generate Word Doc → Register
```

### Industry-Standard Workflow (What to Build Toward)
```
Setup Project + Recipients
      ↓
Upload PDF → AI Scans Drawings
      ↓
Review Issues → [Edit Description] → [Add Suggested Solution] → [Set BIC] → [Flag Cost/Schedule Impact] → [Set Due Date] → Approve
      ↓
Crop Snapshots (linked to specific RFI)
      ↓
Generate Word Doc (includes Suggested Solution, Cost/Schedule Impact block)
      ↓
Send to BIC (via email notification) → Status: Open
      ↓
BIC Responds → Record Response in Register → Status: Responded
      ↓
GC Reviews Response → Acceptable? → Status: Closed
                     → Unacceptable? → Create Revision → back to Open
      ↓
Register (always shows BIC, due date, status, overdue flag, days open)
```

---

## What the Generated Word Document Is Missing

The document you generate today is already professional and better-formatted than most tools produce. These additions bring it to full industry-standard:

| Missing Section | Where to Add | Why It Matters |
|----------------|-------------|----------------|
| **Suggested Solution row** | Info table (after "Response Required By") | Contractor's proposed fix — standard on all RFI forms |
| **Cost Impact row** | Info table | Flags financial risk; required for claims documentation |
| **Schedule Impact row** | Info table | Flags timeline risk; required for claims documentation |
| **CC list** | Addressee block | Shows all parties who received this RFI |
| **Official Response block** | Footer of document | For closed/responded RFIs — populated when response is recorded |
| **Revision marker** | Header (RFI-003 Rev.2) | Shows document version when a revision is issued |

---

## UX — What to Change

### Navigation Should Guide the User

A first-time user opening 6 tabs with no guidance will be lost. The tabs need to signal a sequence. Procore does this with a linear workflow where each step becomes available only after the previous is complete. Your sidebar should show a workflow progress indicator:[cite:11]

```
Step 1 ✅  My Company
Step 2 ✅  My Project
Step 3 ⬜  Analyse Drawings   ← Start Here
Step 4 ⬜  Crop Snapshots
Step 5 ⬜  Generate RFI
Step 6 ⬜  RFI Register
```

### Tab Names — Make Them Action-Oriented

| Current | Better |
|---------|--------|
| Company | 🏢 My Company |
| Project | 📁 My Project |
| Analyse Drawings | 🔍 Analyse Drawings |
| Crop Viewer | 📷 Crop & Annotate |
| Generate RFI | ⚡ Generate RFI |
| Register | 📋 RFI Register |

### The Register Needs to Be the Control Centre

Right now the Register feels like an afterthought — a simple table at the end. In Procore and every serious RFI tool, the Register IS the product — the place PMs live every day.[cite:11][cite:38] It should open showing: overdue count (red badge), open count, BIC bottleneck, and the full log with colour-coded statuses, overdue highlighting, and one-click access to respond/close any RFI.

---

## What You're Already Doing Better Than Procore

| Area | Why Yours Is Better |
|------|-------------------|
| AI-powered drawing analysis | Procore's Draft RFI Agent only works from text input. Yours scans actual PDF drawings — far more powerful.[cite:34] |
| Document quality | Your A4 landscape Word document with smart portrait/landscape switching and embedded snapshots is more refined than Procore's standard RFI PDF export. |
| Offline resilience | Procore is cloud-only. Your dual Supabase + local fallback works offline. Valuable on construction sites with poor connectivity. |
| Cost | Procore's pricing is enterprise-level and opaque. A focused, affordable RFI Manager is a clear market opportunity.[cite:38] |

---

## Build Sequence Recommendation

**This Month — Complete the Core Lifecycle:**
1. Add BIC field (Analyse tab when approving + Register column)
2. Upgrade to 5-stage status with colour coding
3. Add due date + overdue red highlighting in Register
4. Add Suggested Solution field in Analyse tab + carry into Word doc
5. Add Cost/Schedule impact toggles in Analyse tab + carry into Word doc
6. Add response capture to Register (who responded, what, when)

**Next Month — Make It Stand Out:**
7. Add RFI Revisions (linked version history)
8. Add automated email notifications (submit + overdue)
9. Add activity log per RFI
10. Add filter/search + CSV export to Register
11. Add dashboard metrics to Register header

**Later — Power Features:**
12. Snapshot annotation/markup
13. Change order + submittal linking
14. Multi-project analytics dashboard

