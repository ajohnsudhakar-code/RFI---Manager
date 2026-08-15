# RFI Manager — Running Backlog

Observations, concerns, and non-blocking issues found during testing.
Add to this file as they come up. Fix later in priority order.

**Last updated:** 13 August 2026 — Tab 5 list rebuilt (C1, C2); C3 discarded

---

## HOW TO USE THIS FILE

- Anything found during testing that is NOT an immediate blocker goes here
- Each item gets: what it is, why it matters, severity, and which file to fix
- Severity: 🔴 P0 (breaks for users) / 🟠 P1 (fix before charging money) / 🟡 P2 (polish)
- When an item is fixed, move it to the FIXED section at the bottom with the date

---

## IN FLIGHT

Clean tree at `8045c90`. Nineteen commits.

**Tab 5 list rebuild — where it got to.**
Three passes were planned. C1 and C2 are committed and working. **C3 was built,
tested, and deliberately discarded** — see the decision below, it matters.

- **C1 (`d894335`)** — dedupe. An approved AI issue is now hidden from the list
  once a register row exists for its number, not once a `.docx` filename matches.
  This also closed the "delete a document and the card resurrects" bug, since
  list membership no longer depends on what files happen to exist in Storage.
- **C2 (`8045c90`)** — the list itself. Folder filters with counts (All / To
  raise / Draft / Generated), a search box gated behind a form so it does not
  rerun per keystroke, and one compact row per RFI replacing the old card + Open
  button pairs. Rows are `st.button` with scoped CSS: left-aligned, hairline
  divider, CSS `text-overflow: ellipsis` rather than a fixed character cut, and
  `:gray[...]` markdown on the number and date so the subject carries the weight.

**C3 was discarded — do not rebuild it without reading this.**
C3 replaced the permanent `st.columns` split with list-or-detail: the list filled
the page, clicking a row replaced it with the RFI at full width, with a back link.
It was implemented, tested, and worked correctly.

It was discarded because it is the wrong model for this app. Gmail on **desktop**
keeps the list visible beside the message; only mobile replaces it. The original
argument for replacing was that a 600px panel left the detail only 360px — but
the tab now renders at full page width, so a split gives the list ~400px and the
detail ~1100px, which is ample for both. The reasoning was right for the width we
had and wrong for the width we now have.

**Immediate next step:** Tab 5 has no width constraint at all, which is why the
list rows sprawled to ~130 characters of subject at 1600px. Give the tab a
sensible max width the way Tabs 1 and 2 already do (`st.container(key=...)` plus
a scoped rule using `width` and `align-self: center !important` — `margin: auto`
does not work, the key class lands on a flex item). Then the split reads properly
at any screen size.

**Untested, already committed:**
- Tab 3 prompt change (`45148f5`) — never run against a real drawing set.
- Tab 4 captions (`e76c3a2`) — save but do **not** print on the document.
- Markdown escaping on row labels — `_md_escape` was added when the row label
  became markdown. Untested against a subject containing `*`, `[` or `#`.
- Two register smoke tests: renumbering an RFI with no document (the only path
  that deletes a register row), and regenerating on a **different calendar day**
  from first generation.

---

## DESIGN SYSTEM — the reason Tabs 1 and 2 still look wrong

### 🟠 P1 — There is no visual system; each screen was fixed in isolation
**Raised:** 12 Aug 2026, after John said he did not like the Tab 1 and Tab 2 results.

**What actually happened.** Tabs 1 and 2 got *cleanup*, not *design*: constrain
the width, wrap things in cards, make labels consistent, stop buttons
letter-stacking. That removes badness. It does not produce something designed.
The result is tidy and forgettable, which is exactly the reaction.

**Root cause.** The work was done from screenshots, one tab at a time, with no
visual system underneath — no type scale, no spacing rhythm, no colour
discipline, no component vocabulary. Each screen was fixed on its own terms, so
none of them share a language. Every individual change was defensible and the
whole still reads as arbitrary.

**Fix — a SKILL.md holding real decisions, not principles.**
Vague guidance ("use good hierarchy") reproduces the current problem. The file
must contain specific, checkable values:
- type scale — page title, section heading, body, caption, in px with weights
- spacing scale — a fixed set (e.g. 8 / 16 / 32), used everywhere
- one accent colour and its permitted uses
- border weight and radius, stated once
- when a card is used and when whitespace is used instead
- button hierarchy — primary, secondary, tertiary, and what each is for
- the 600px content width rule and the `st-key-*` scoping pattern already proven
  in `ui_company.py` and `ui_project.py`

**Prerequisite: reference apps.** The SKILL.md should be derived from two or
three real products John judges as professional, screenshotted, with what he
likes about each stated explicitly — not from Claude's taste, which has now been
seen and found wanting. Without references it is just a different arbitrary
system.

**Known ceiling.** Streamlit can reach clean, calm and consistent. It cannot
reach Linear. If the chosen references are all custom React products, the gap
between reference and achievable will frustrate. Worth accepting before starting.

**Files:** a new SKILL.md, then re-application across `ui_company.py`,
`ui_project.py`, `ui_analyse.py`, `ui_crop.py`, `ui_generate.py`, `ui_register.py`
**Blocker?** Not functionally. Yes for anything shown to a customer.

---

### 🟡 P2 — Three workarounds now fight `app.py`'s shared style block
**Found:** 10-11 Aug 2026, accumulated across the Tab 1 and Tab 2 passes.
**What:** `app.py`'s global CSS makes decisions individual tabs then have to
undo, each time with a local override:
1. `text-transform: uppercase !important` on every input label, worked around in
   `ui_company.py` with `label_visibility="collapsed"` plus custom labels
2. `.stButton > button` with no `[kind=...]` qualifier, so it repaints tertiary
   buttons — worked around with a scoped `.st-key-*` override
3. `[class*="st-key-t2_rcpt_edit_"]` and similar substring selectors, which
   depend on Streamlit's generated class names

**Why it matters:** every new tab styled means repeating these workarounds, and
all three depend on Streamlit internals that a version bump could change at
once. The audit found ~35 label strings across five files that would need
rewriting to fix (1) at source — its own task, deliberately deferred.
**Fix:** fold into the SKILL.md work above — decide the global rules once, then
remove the overrides rather than adding a fourth.
**Files:** `app.py`, all tab files
**Blocker?** No.

---

## ARCHITECTURE

### 🟠 P1 — The RFI is not an object; it lives in three places
**Found:** 9 Aug 2026, during end-to-end testing
**What:** "An RFI" currently means three different things in three different places:
- the **left panel** in Tab 5 shows approved AI issues that have no document yet
  (generated RFIs disappear from it)
- the **"Previously generated documents"** list shows `.docx` files in Supabase Storage
- the **`rfi_register` table** holds rows, surfaced only in Tab 6

No single list shows the RFIs belonging to a project. Nothing in the codebase owns the
concept end to end — the RFI is assembled at generate time from session state, written
to a file and a register row, then discarded.

**Why it matters:** This is the root of every workflow complaint. You cannot find an RFI
after generating it, cannot reopen it, and cannot edit it. It is also why Tab 5 has two
different doors (AI issue vs "+ New Manual RFI") behaving differently.

**Fix — agreed design (9 Aug 2026):**

Industry practice confirmed against Procore, Newforma and Trimble documentation:
creating a revision creates a *new linked record*; the original is never edited and
becomes read-only once revised. Revisions are raised *after* an answer is received,
to clarify or restate the question. Numbers are never reused for unrelated RFIs.

*Data model — add to `rfi_register`:*
- `status` — `draft` / `issued` / `answered` / `closed`
- `revision` — integer, default 0 (feeds the Word doc's "Rev 0Q")
- `supersedes` — RFI number this revises, null until revisions ship
- `issued_date`, `answered_date` — null until set

The register row becomes the full RFI record, not a summary. Everything the form
collects is persisted there.

*Screens:*
- Tab 5 becomes **"RFIs"** — one list per project, every RFI regardless of origin,
  showing number, subject, status, response-due date. This list *is* the register,
  so **Tab 6 is deleted**
- Click a row → detail view. Draft = editable, regenerating overwrites the document.
  Issued = read-only, offers "Mark answered". Answered = read-only, "Create revision"
  (greyed out in v1)
- Two actions on the list: **+ New RFI** and **Scan drawings for issues**
- Tab 3 remains the scan engine but writes draft rows straight into the RFI list;
  approve/reject becomes a property of the draft, not a separate panel
- Tab 4 (Crop) becomes reachable from inside an RFI detail view — a crop belongs to
  an RFI
- "Previously generated documents" disappears; the document becomes a field on the RFI

*Numbering:* sequential per project. A revision reuses the number and increments the
revision integer (RFI-012 Rev 1). Never reuse a number for an unrelated RFI.

*Build order — one prompt per step:*
1. Add status columns; backfill existing rows as `issued`
2. Make the register row the full RFI record
3. Build the list view
4. Build the detail view with the draft/issued split
5. Point Tab 3's output at the list
6. Move cropping into the detail view
7. Delete Tab 6

Steps 1-4 alone resolve the "I can't find or edit my RFIs" problem.

*Deferred:* revisions (needs answer capture first — answers arrive by email, outside
the app). Email sending stays out of scope; engineers download and send themselves.

**Open question for a real user:** will engineers actually mark an RFI as issued, or
leave everything in draft forever? If they forget, the frozen state never happens and
the model quietly fails.

**Files:** `ui_generate.py`, `ui_analyse.py`, `ui_crop.py`, `data_layer.py`, `app.py`
**Blocker?** Not for a beta. Yes for a coherent product.

---

## OPEN ITEMS

### 🔴 P0 — Save functions report success when the write failed
**Found:** 9 Aug 2026 (`save_cfg`). **Second instance found:** 10 Aug 2026
(`save_project_clients`). Both confirmed by code trace.
**What:** This is one design flaw in `data_layer.py`, not two bugs. Save
functions swallow their own failure and return normally, so the caller's success
message always fires.

- `save_cfg()` (~384-394) catches Supabase exceptions, logs, shows `st.warning`,
  and never re-raises — always returns `None`. The `try/except` around it in
  `ui_company.py` (~234-252) therefore cannot catch a real database failure. The
  user sees "Could not connect to database" immediately followed by "Company
  details saved successfully", and `tab_company_done` is set True regardless.
- `save_project_clients()` (~881-896) is worse: when Supabase is unreachable it
  hits `if not sb: _warn(...); return` and does nothing at all — no local write,
  no raise. `ui_project.py`'s `try/except` (~451-457) never fires, so the code
  proceeds to show "✓ Added {company}". The recipient exists in memory for that
  session and then evaporates.

**Why it matters:** Silent data loss reported as success. Worse than a crash,
because a crash tells the user something failed. Compounded by the known
Supabase free-tier pausing issue, which makes outages routine rather than rare.
**Fix:** Decide the contract for save functions in `data_layer.py` — return a
success boolean, or raise. Then make every caller honour it. **Audit all callers
before changing anything** — these functions are used across tabs.
**Files:** `data_layer.py`, `ui_company.py`, `ui_project.py`, plus any other caller
**Blocker?** Yes, before real users trust the app with data.

---

### 🟡 P2 — Recipients have no stable identity; list position is the only handle
**Raised as suspected P0 on 10 Aug 2026, downgraded the same day after investigation.**

**What:** `_blank_client()` returns five string fields and no id. Every handle to
a specific recipient — Edit and Del button keys (`t2_edit_{i}_{pid}`,
`t2_del_{i}_{pid}`), the delete-confirm flag, the edit-form match, and Tab 5's
`client_idx` — is a list position. The alphabetical `clients.sort()` on add
(`ui_project.py:450`) is the only reorder in the app, and it is enough to move
things under a stored index.

**Why it was downgraded — this is the important part, do not re-escalate without
re-reading it.** The initial fear was that a saved RFI could be silently
re-addressed to the wrong company months later. That does not happen:
- `client_idx` is **never persisted**. It lives only in
  `st.session_state[f"t5_new_record_{pid}"]` and is popped the moment generation
  succeeds (`ui_generate.py:1025`).
- The `rfi_register` table has **no client column at all** — confirmed against
  the live schema, not inferred. `approved_rfis_data` has no `client_idx` either.
- At generation the recipient's fields are **copied as static text** into the
  .docx. Nothing links a generated document back to the client list.

**What remains, and it is genuinely small:** within one open session, between
choosing "Send to" and clicking Generate, a reorder could shift the index. Same
shape for the Tab 2 delete-confirm race — click Del on a recipient, add another
in between, confirm, and the sort has moved things. Both require an add mid-flow
in a single session.

**Fix:** assign a stable `id` on client creation (`ui_project.py:449` is the only
creation site; `ui_project.py:379` must carry the existing id forward on edit),
key the row buttons and the delete confirmation by that id, and fall back to
position for legacy clients that have none. Two existing projects, both with
clients lacking an id — confirmed by query.
**Folded into:** Tab 2 part 2b, since those rows are being rewritten anyway.
**Files:** `ui_project.py`, possibly `ui_generate.py`
**Blocker?** No.

---

### 🟡 P2 — Recipient email, phone and role never reach the document
**Found:** 10 Aug 2026
**What:** `generate_rfi.py:314-316` assigns `CLIENT_EMAIL`, `CLIENT_PHONE` and
`CLIENT_ROLE` and never references them again. Only `CLIENT_ATTN` and
`CLIENT_COMPANY` are placed on the document, in the "To" block
(`generate_rfi.py:623-637`).
**Why it matters:** May be deliberate — many RFI templates address the person and
company only. But three fields are collected in Tab 2, stored, and silently
dropped. Check a real RFI against what a recipient expects to see.
**Files:** `generate_rfi.py`
**Blocker?** No.

---

### 🟡 P2 — Dead session keys in app.py
**Found:** 10 Aug 2026
**What:** `t5_sel_client` and `t5_sel_client_idx` (no `_{pid}` suffix, unlike
every current Tab 5 key) appear only in `_reset_project_state()` and the
`_TAB_CLEAR` list in `app.py` (~950, 1030-1031). Nothing in `scripts/` sets or
reads them. Leftovers from an earlier Tab 5.
**Fix:** delete both entries.
**Files:** `app.py`
**Blocker?** No.

---

### 🟡 P2 — A deleted document still resurrects its RFI card
**Found:** 12 Aug 2026. **Partly mitigated 13 Aug** by the Saved RFIs list.
**What:** The pending list in Tab 5 hides an approved AI issue by matching a
filename prefix against the `.docx` files in Storage. Delete the document and the
card reappears as pending, and can be generated again under the same number.
**Why it is now less severe:** the RFI also appears in the Saved RFIs section,
sourced from the register row, so it is no longer invisible — and the collision
guard (`66abc60`) blocks a save that would overwrite a different RFI. The
remaining problem is cosmetic duplication: the same RFI shows in both lists.
**Fix:** the pending list should filter on the register row's `document_path`
rather than on what files happen to exist in Storage.
**Files:** `ui_generate.py`
**Blocker?** No.

---

### 🟡 P2 — The register row is written before generation and never rolled back
**Found:** 12 Aug 2026
**What:** `upsert_project_register_rows` runs at Save, before Generate is even
clickable. If generation then fails, the row stays, claiming the RFI exists.
**Why it matters:** given the August blocker, some of the 21 existing rows may be
exactly this — saved, never generated. Pass A makes this visible rather than
worse: `document_path` NULL now means "not generated", which is a coherent state
and arguably the fix.
**Files:** `ui_generate.py`
**Blocker?** No.

---

### 🟠 P1 — Per-status actions on an open RFI
**Designed 13 Aug 2026, not yet built.** The action buttons should change with
the RFI's state:

| Status | Actions |
|---|---|
| Draft — `document_path` null | Edit · Generate · Delete |
| Generated — `document_path` set | **Download** · Edit · Regenerate |
| Issued — sent to the recipient | Download · Revise |

**The reasoning, which is the part that matters.** *Generated does not mean
sent.* This app produces a Word file; the engineer emails it themselves. So there
is a window where a document exists but nobody outside has seen it — and in that
window, editing and regenerating is completely safe. Same RFI, same number,
corrected document. No revision needed.

A revision is only required once the RFI has left the building. Someone holds
RFI-012 Rev 0 in their inbox; changing what Rev 0 means is dishonest, so you
raise Rev 1 linked to Rev 0, and Rev 0 goes read-only. This matches Procore's
documented model.

**Which implies a "Mark as sent" action** — only the user knows when they hit
send; the app cannot detect it. That is what creates the Issued state.

**Build now:** Draft and Generated. Both derive from `document_path`, which
already exists, so no schema change. Download matters most — today the only way
to get an RFI's document is the separate "Previously generated documents"
section, disconnected from the RFI itself.

**Build later:** Issued, Mark as sent, and revisions. Those need a `revision`
column, a `supersedes` link, and answer tracking — the seven-step architecture
work below.
**Files:** `ui_generate.py`
**Blocker?** No, but Download is the obvious gap in the manual workflow.

---

### 🟡 P2 — The AI prefill does not carry the issue's RFI number
**Found:** 13 Aug 2026, while testing the C1 dedupe
**What:** Clicking "→ Create RFI" on approved issue RFI-001 prefills subject,
question, category, recipient and date — but leaves the RFI number at the
auto-suggested next value. Saving produced RFI-018 for an issue numbered 1.
**Why it matters:** the approved issue and its RFI should share a number. Because
they do not, the C1 dedupe rarely fires in practice — the numbers never match, so
the pending card never disappears. The dedupe is correct; the prefill undercuts it.
**Files:** `ui_generate.py`
**Blocker?** No.

---

### 🟠 P1 — Snapshot captions save but never print on the document
**Found:** 12 Aug 2026
**What:** Tab 4 now captures a free-text caption per crop and stores it in
`captions_data` (`e76c3a2`). `generate_rfi.py` never reads that column — the
caption paragraph under each image still prints
`"Attachment N of M — Sheet ref. {sheets}"` from the RFI-level sheets field
(`generate_rfi.py:779-780`).
**Why it matters:** the user types a caption and it goes nowhere. A feature that
appears to work and does not is worse than one that is absent.
**Fix:** load `load_project_captions(pid, email)` at `ui_generate.py:976` where
`pid` and `email` are already in scope, pass it through config, and print the
user's caption under each image — keyed by `os.path.basename(_spath)`, matching
the pattern already used one line below for logging. Blank caption prints
nothing at all, per John's decision.
**Files:** `ui_generate.py`, `generate_rfi.py`
**Blocker?** No, but it is a half-wired feature sitting in `master`.

---

### 🟠 P1 — The scan may be losing its richest batches silently
**Found:** 12 Aug 2026, during the batch-failure investigation
**What:** `max_tokens=4096` is fixed regardless of how many issues a batch
produces. A batch that legitimately finds many problems generates a longer
response, gets truncated mid-array, and fails `json.loads` — so **the failure is
most likely on the busiest sheets**. Until `e3bdd12` this was silently
discarded; it is now counted, reported to the user, and logged to
`error_log.txt`.
**Why it matters:** if this is happening routinely, the scan is losing exactly
the findings it was working hardest to produce. That would make it more
important than the 2000-character truncation below.
**Fix:** run real scans, then read `error_log.txt`. If truncation is confirmed,
raise `max_tokens` or reduce `batch_size` — do not guess before the log says so.
**Files:** `ui_analyse.py`
**Blocker?** Unknown until measured. That is the point.

---

### 🟠 P1 — Only the first 2000 characters of each page reach the AI
**Found:** 12 Aug 2026
**What:** `ui_analyse.py:246` truncates each page's extracted text to
`text[:2000]` before batching. A dense drawing sheet — notes, schedules,
dimensions, callouts — carries far more than that. Anything past the cap is
never seen by the model.
**Why it matters:** this directly caps how good the scan can be, which is the
product's differentiator. Nobody measured 2000 against a real drawing set; it is
a hardcoded guess.
**Fix:** measure the actual extracted length of pages from a real set, then set
the cap against evidence — or remove it and manage size via `batch_size`
instead. Interacts with the `max_tokens` item above: more input means longer
responses means more truncation risk.
**Files:** `ui_analyse.py`
**Blocker?** No, but it is the ceiling on scan quality.

---

### 🟡 P2 — Re-scans repeat findings already reviewed
**Raised:** 12 Aug 2026
**What:** Scanning the same drawings twice produces the same issues again, with
no awareness that the user already approved or rejected them. Everything needed
to fix this is already stored — `scan_results_data` holds every prior finding
with its status.
**Fix (agreed approach):** include previously-found issues for the same sheets
in the prompt — "you already reported these on S101, do not report them again."
A few lines, no new technology. Makes a second scan useful instead of noise.
**Files:** `ui_analyse.py`
**Blocker?** No.

---

### 🟡 P2 — `add_label_to_image` is now dead code
**Found:** 12 Aug 2026
**What:** `data_layer.py:1332-1350` burned the old drawing-type value onto the
crop as an orange uppercase banner. `ui_crop.py` stopped calling it in `e76c3a2`
when captions became free text — a sentence stamped in caps across a drawing
looks bad, and the caption now belongs under the image on the document instead.
The function remains, uncalled.
**Fix:** delete it, or keep it deliberately and note why.
**Files:** `data_layer.py`
**Blocker?** No.

---

### 🟡 P2 — No way to cancel a new project
**Found:** 11 Aug 2026, during the tab-fix investigation
**What:** Once `_pid_is_new_unsaved` is True, saving is the only exit. The
sidebar project switcher is blocked for the duration (`app.py:1085`), and there
is no cancel action anywhere. Click "+ New Project" by mistake and you are
committed to creating one.
**Files:** `app.py`, `ui_project.py`
**Blocker?** No.

---

### 🟡 P2 — `max_snapshots` is read in four places and written in none
**Found:** 12 Aug 2026, confirmed by grep across `scripts/`
**What:** Defaults to 5 in `data_layer.py:343`, `ui_crop.py:84` and
`ui_generate.py:57`, but 6 in `generate_rfi.py:320` — and that variable is
assigned and never used. The document embedding uses a **hardcoded**
`snap_info[:5]` (`generate_rfi.py:764`) that ignores the setting entirely. No
widget or write path exposes it to a user anywhere.
**Why it matters:** harmless today because nothing can change it. The moment
anyone exposes the setting, the document will quietly ignore it.
**Fix:** make `generate_rfi.py:764` read the setting, and align the defaults.
**Files:** `generate_rfi.py`, `data_layer.py`
**Blocker?** No.

---

### 🟠 P1 — Response Required By can be earlier than the date raised
**Found:** 9 Aug 2026, in generated document RFI-012
**What:** RFI-012 was raised 09 Aug 2026 with a Response Due Date of 04 Aug 2026 — five
days in the past. The date came from Tab 3's AI prefill; the manual path correctly
defaults to today+14 (verified in RFI-013 and RFI-014). Nothing validates that the date
is in the future.
**Why it matters:** The date appears three times across the two pages of the document.
Sending a client an RFI whose response deadline has already passed looks careless and
undermines the tool's credibility.
**Fix:** Validate on Save that Response Required By is not earlier than today. Also fix
whatever Tab 3 writes as the prefilled date.
**Files:** `ui_generate.py`, `ui_analyse.py`
**Blocker?** Not technically. Embarrassing in front of a real client.

---

### 🟠 P1 — No City field; `country` holds a city
**Found:** 9 Aug 2026. **Confirmed at database level:** 10 Aug 2026.
**What:** Tab 1 has Address, Country and Postcode — no City. Verified directly
in Supabase (`user_config.config_data->'company'`): the stored keys are `name`,
`address`, `country`, `website`, `postcode`. There is no `city` key anywhere in
the config, and `country` currently holds `"Sydney"`.
**Why it matters:** This prints on every RFI document — the header renders as
"Lot 125, Sydney 2011". A user filling the form as labelled gets a country where
the city belongs. Target market is New Zealand; the test data is Australian.
**Fix:** Add a City field to Tab 1, add the key to the config write/read, and
update the document header in `generate_rfi.py` to print it. Backward
compatibility matters — existing configs have no `city` key, so the read must
tolerate its absence rather than erroring.
**Files:** `ui_company.py`, `generate_rfi.py`
**Blocker?** No, but it is on every document the tool produces.

---

### 🟠 P1 — Paywall has no checkout flow
**Found:** Carried over from code review
**What:** Free tier is 5 RFIs lifetime. To upgrade, the user must email
`ajohnsudhakar@gmail.com` manually. There is no Stripe integration, no payment page,
no automated upgrade.
**Why it matters:** You cannot charge money. Every upgrade requires manual intervention
from John — checking the email, manually flipping `is_paid` in Supabase, replying to
the customer. This does not scale past a handful of users.
**Fix:** Stripe Checkout integration. Webhook to flip `rfi_usage.is_paid` on successful payment.
**Files:** New payment module, `data_layer.py`, `app.py` sidebar
**Blocker?** For monetisation, yes. For a free beta with early users, no.
**Note:** Pricing model still undecided. Unit cost per AI drawing scan has never been
measured — that number should be established before any tier structure is designed.

---

### 🟠 P1 — Supabase free tier pauses after inactivity
**Found:** 4 Jun 2026 and again 4 Aug 2026
**What:** The Supabase project pauses automatically after roughly one week of no activity.
When paused, the app returns HTTP 521 and login fails completely.
**Why it matters:** A real user hitting a paused database sees a broken app with no
explanation. This has already happened twice during testing. Also makes the `save_cfg`
false-success bug above far more likely to fire in practice.
**Fix:** Upgrade to Supabase Pro tier. Pro projects never pause.
**Files:** None — this is a Supabase dashboard setting
**Blocker?** Yes, before any real user touches the app.

---

### 🟠 P1 — max_snaps slice cuts across PDFs
**Found:** 4 Aug 2026, reviewing the snapshot-naming plan
**What:** `_local_snaps` in `ui_generate.py` globs every snapshot for an RFI
regardless of which PDF it came from (`RFI_007_*_snap*.png`), then slices the
result to `max_snaps`. The cap is applied across all PDFs combined.
**Why it matters:** Once multiple PDFs per project ship, an engineer who crops
3 details from the structural drawing and 3 from the architectural drawing for
the same RFI will silently lose one when `max_snaps` is 5. No warning, no error —
the attachment just never appears in the Word document.
**Fix:** Decide whether the cap is per-RFI or per-RFI-per-PDF, then apply it
consistently in `_local_snaps`, the glob near the attachments block, and
`get_snapshots` in `generate_rfi.py`. If per-RFI is kept, warn the user in Tab 4
when the limit is reached rather than dropping silently.
**Files:** `ui_generate.py`, `generate_rfi.py`, possibly `ui_crop.py`
**Blocker?** Not for the naming change itself — the multi-PDF flow does not exist
yet. Must be resolved before the Tab 3 / Tab 4 PDF pickers ship.

---

### 🟡 P2 — Address autocomplete (decided against for now)
**Raised:** 10 Aug 2026
**What:** Type-ahead address suggestions on the Address fields in Tab 1 and Tab 2
— type "18" and get real addresses in a dropdown, as consumer apps do. Google
Places Autocomplete is the standard implementation.
**Decision: not building it.** Three reasons, recorded so this does not get
re-litigated:
- It is a paid Google API — billing account, API key management, per-request
  cost — added to an app with no checkout and no users.
- Streamlit has no native autocomplete widget. This needs a custom component,
  meaning a React build step inside a Streamlit app. Real work.
- Company address is filled **once, ever**. Project address is once per project.
  Days of work to save one person thirty seconds, one time.
**Revisit when:** a real engineer complains about typing an address, or the app
grows a screen where addresses are entered frequently.
**Files:** would be `ui_company.py`, `ui_project.py`, plus a new component
**Blocker?** No.

---

### 🟡 P2 — Subject field has no length or quality validation
**Found:** 9 Aug 2026, across generated documents RFI-012, RFI-013, RFI-014
**What:** Two failure shapes, same missing guard. RFI-012's subject ran to a six-line
paragraph (Tab 3's scan description dropped straight into the subject slot, bypassing
the AI subject formatter which does specify "concise one-line"). RFI-013 and RFI-014
accepted single-character keyboard mash.
**Why it matters:** The subject is what appears in the recipient's email subject line
and in the register. A paragraph breaks the Identification table layout; nonsense goes
to a client unchallenged.
**Fix:** Length constraint plus non-empty-meaningful check on Subject. Separately,
stop feeding Tab 3's full description into the subject field — it is a description,
not a subject.
**Files:** `ui_generate.py`, `ui_analyse.py`
**Blocker?** No.

---

### 🟡 P2 — "unknown" prints literally on the document
**Found:** 9 Aug 2026, in generated document RFI-012
**What:** When Drawing Reference is unknown, the document prints "Sheet ref. unknown"
under the attachment and in the reference table.
**Why it matters:** A professional document omits an unknown field rather than
announcing the gap.
**Fix:** Suppress the row/caption when the value is empty or "unknown".
**Files:** `generate_rfi.py`
**Blocker?** No.

---

### 🟡 P2 — Tab 1: two different save behaviours on one screen
**Found:** 9 Aug 2026
**What:** Logo and signature save instantly on upload, with their own success message.
The text fields require the "Save Company Details" button. Nothing on screen signals
the difference.
**Why it matters:** A user uploads a logo, sees "Logo saved successfully", and
reasonably concludes the whole screen is saved. Navigating away loses the text fields
with no warning. Dangerous in combination with the `save_cfg` P0 above.
**Fix:** Either make everything save on the button, or make it explicit which parts
save immediately.
**Files:** `ui_company.py`
**Blocker?** No.

---

### 🟡 P2 — Tab 1: three redundant "setup complete" messages
**Found:** 9 Aug 2026
**What:** Green banner at top, blue banner at bottom, and "↑ Click Project Setup above"
on the right of the bottom banner — all on a screen that fits without scrolling.
**Fix:** Keep one. The bottom banner is the useful one; it tells the user where to go
next. The top green banner is decoration — the tab is visibly filled in.
**Files:** `ui_company.py`
**Blocker?** No.

---

### 🟡 P2 — Tab 1: "Originator" wording, and website is not a link
**Found:** 9 Aug 2026
**What:** The heading "Originator — Person signing RFIs" uses a gloss to explain a label
that should stand alone. Check what the Word document calls this role and match it —
consistency between screen and output matters more than being technically correct in
one place. Separately, the Website field renders as plain text rather than a link.
**Files:** `ui_company.py`, `generate_rfi.py`
**Blocker?** No.

---

### 🟡 P2 — Tab 1: dead code
**Found:** 9 Aug 2026, Claude Code investigation
**What:** `_tab_done` (~line 28) is assigned and never read again — definitely dead.
`co.get("company_name", "")` (~lines 21, 85) is a permanently inert fallback; nothing
in `scripts/` ever writes a `company_name` key, only `name`.
**Fix:** Delete both.
**Files:** `ui_company.py`
**Blocker?** No.

---

### 🟡 P2 — `t5_new_saved_{pid}` stays True after generation
**Found:** 9 Aug 2026, in probe log runs #11 and #12
**What:** After a successful Generate, the record is cleared but the saved flag remains
True.
**Why it matters:** Harmless today — the record now gates the branch, and both entry
handlers reset the flag. But a stale flag that nothing depends on is the kind of thing
that bites after a later refactor.
**Fix:** Clear it in the same cleanup that pops the record.
**Files:** `ui_generate.py`
**Blocker?** No.

---

### 🟡 P2 — RFI template list has no management UI
**Found:** 4 Aug 2026, during Tab 1 verification
**What:** Templates for Instructions and Notes are saved to `user_config.config_data.rfi_templates`
as a dictionary. There is no limit on how many can be saved (practical limit is the Postgres
jsonb column size — effectively unlimited).
**Why it matters:** If an engineer saves 20-30 templates over time, the dropdown to select one
becomes unusable. There is no search, no delete, no rename, no organisation.
**Fix:** Add a delete button next to each saved template in the dropdown, or a small
"Manage templates" expander. Consider a soft cap with a warning at ~15 templates.
**Files:** `ui_generate.py` (template save/load UI), `data_layer.py` (`save_rfi_templates`)
**Blocker?** No. Only becomes a problem after months of real use.

---

### 🟡 P2 — st.text_input with empty label (accessibility warning)
**Found:** 25 May 2026, in error log during Tab 5 testing. Still present 9 Aug 2026.
**What:** `ui_generate.py` calls `st.text_input("")` with an empty label in the template-name
fields. Streamlit logs a warning: "label got an empty value. This is discouraged for
accessibility reasons and may be disallowed in the future by raising an exception."
**Note:** This entry previously cited lines 404 and 480. Line numbers have drifted —
the warning was observed at line 527 on 9 Aug 2026. **Locate by symbol, not line number.**
**Why it matters:** Currently only a warning. A future Streamlit version will turn this into
a hard exception and crash Tab 5.
**Fix:** Add a real label plus `label_visibility="collapsed"` to both text inputs.
The pattern is already used correctly elsewhere in `app.py` (e.g. the login form).
**Files:** `ui_generate.py`
**Blocker?** No — but it is a 5 minute fix and should be done before launch.

---

### 🟡 P2 — No OCR fallback for scanned/raster PDFs
**Found:** Carried over from CLAUDE.md known risks
**What:** If an engineer uploads a scanned PDF (image-only, no embedded text layer),
the AI scan finds nothing because there is no extractable text.
**Why it matters:** Older drawing sets in NZ construction are often scanned. The engineer
uploads, runs the scan, gets zero results, and has no idea why.
**Fix:** Short term — detect no extractable text and show a clear message explaining why.
Long term — add OCR (Tesseract or a cloud OCR API) as a fallback.
**Files:** `ui_analyse.py`
**Blocker?** No, but the error message fix is important — silent failure is worse than a
clear "this PDF has no readable text".

---

### 🟡 P2 — Drawing revision upload wipes prior AI scan work
**Found:** Carried over from CLAUDE.md known risks
**What:** If an engineer uploads Rev B of a drawing set over Rev A, all prior AI scan
results and approved RFIs for that project are lost. There is no revision management.
**Why it matters:** Drawing revisions are constant in construction. An engineer who has
done 10 RFIs on Rev A and uploads Rev B loses all that work.
**Fix:** Either warn clearly before overwriting, or add proper revision tracking so each
revision keeps its own scan results.
**Files:** `ui_project.py` (PDF upload), `data_layer.py`
**Blocker?** No, but this will bite a real user eventually.

---

### 🟡 P2 — No automated tests
**Found:** Carried over from code review
**What:** All testing is manual end-to-end clicking through the app.
**Why it matters:** Every change risks breaking something silently. There is no safety net.
The 9 Aug Generate bug survived from May to August partly because nothing exercised the
Save → View → Generate path automatically.
**Fix:** At minimum, a smoke test that logs in, creates a project, and generates an RFI.
**Files:** New test module
**Blocker?** No.

---

### 🟡 P2 — Orphaned test data in Supabase Storage
**Found:** 4 Aug 2026
**What:** Storage contains folders for projects that no longer exist in the database:
`proj_001/drawings/` (soft-deleted project) and `proj-c2c8/drawings/` (no matching DB row).
**Why it matters:** Cosmetic only for now. Wastes storage quota on the free tier.
**Fix:** Manual cleanup via the Supabase Storage dashboard.
**Files:** None — data cleanup task
**Blocker?** No.

---

## FIXED

### ✅ The register row is now the RFI — schema, write, guard, and loader
**Fixed:** 12-13 Aug 2026 across `ecca09c`, `c13077e`, `9c994e2`, `66abc60`, `612f297`

**The problem it solved.** An RFI's actual content — the question, the impact
flags, the reference doc, the recipient — was never persisted anywhere. It existed
only inside the generated Word file. `generate_rfi.py` built the document from an
in-memory list while the register row was written separately, so there were two
independent half-records of the same RFI with nothing reconciling them. An RFI
vanished from Tab 5 the moment its document was generated and could never be found,
opened or edited again.

**What was done, in order:**
1. **Schema** — eleven columns added to `rfi_register`: `question`,
   `reference_doc`, the four impact flags, `client_id`, `document_path`,
   `document_generated_at`, `instructions`, `note`. All nullable, no defaults, no
   backfill. 24 columns total, existing rows untouched, RLS unchanged.
2. **Write** — Tab 5 now saves the full RFI at Save time, and records
   `document_path` / `document_generated_at` after a successful upload. The
   mapping lives in one helper (`_register_content_fields`) called from both
   payload builds so the local mirror and Supabase cannot drift.
3. **Guard** — a save can no longer silently overwrite a different RFI's row or
   orphan the original. Collision detected before the upsert and named to the
   user; renumbering refused once a document exists.
4. **Loader** — a "Saved RFIs" section in Tab 5's left panel lists every register
   row with a Sent/Draft badge. Opening one rebuilds the record from the row and
   lands in View mode, reusing the existing Edit and Generate paths unchanged.

**Verified end to end:** RFI-017 was opened from the register after its document
had been generated, its response date changed from 27 Aug to 5 Sep, saved, and
regenerated. The database and the regenerated document both show 5 September.

**Decisions taken — do not revisit without a reason:**
- **Mapping, not renaming.** Three incompatible shapes for the same RFI exist
  (`_new_issue`, the register row, `_rec`) with different key names for nearly
  every field. Settling on one vocabulary is cleaner and was rejected as too risky
  in the file where the August blocker lived. The translation is contained in two
  helpers instead.
- **`client_id` cannot be a foreign key.** Clients live in a jsonb array on
  `projects`, only recently gained ids, and legacy ones still lack them — the
  column stores whatever id or `posN` fallback was in effect, with no constraint.
- **A deleted recipient blocks generation rather than substituting.** Clamping to
  the first client is harmless when the record was just built from the live list,
  but on a reopened row `client_id` is a stored fact about who the RFI was
  addressed to. Silently substituting would produce a client-facing document
  addressed to a company that was never the recipient.
- **Renumber is refused once `document_path` is set.** The number has already been
  communicated to the recipient; changing it breaks the paper trail between what
  was sent and what the register shows. Before a document exists, the row moves
  (write new, delete old — never the reverse, so a partial failure duplicates
  rather than loses).
- **Attachments need no column.** They are recoverable from Storage by filename
  convention, independent of session.

**Discovered along the way:** the output filename embeds the generation date, so
regenerating on a different day produces a second file rather than overwriting.
The loader deletes the superseded document after the new one is confirmed written.
Untested — needs a cross-day regeneration to exercise.

### ✅ Tab 3 manual issue entry removed
**Fixed:** 12 Aug 2026 (`7619905`)
Tab 3 had a second sub-tab duplicating Tab 5's manual RFI creation, including its
own Claude call to reformat free text into an issue. Removed — Tab 3 now does one
thing. 68 lines deleted. Messages pointing at manual entry now point to Tab 5.
The one historical manually-created issue in `scan_results_data` still renders,
approves, edits and generates normally.

### ✅ Failed scan batches were discarded silently and still charged the user
**Fixed:** 12 Aug 2026 (`e3bdd12`)
`except json.JSONDecodeError: pass` dropped five pages of findings with no
warning, no log entry, and no way to distinguish a broken scan from a clean one —
while `increment_scan_usage` had already been called before the loop, so the user
paid for it. Batch outcomes are now counted, parse failures logged to
`error_log.txt` with the batch number and response text, the result message
distinguishes three cases, and the usage counter only increments if at least one
batch parsed. The abuse guard still holds: forcing a failure costs the same API
spend as a real scan.

### ✅ New project creation lost Tab 2 on every rerun
**Fixed:** 11 Aug 2026 (`e850ceb`)
`_goto_tab2` fired a one-shot JS tab-click that never re-fired, so typing a
project name reran the script and dropped the user back on Tab 1. The project's
session state was always intact — only the visible tab reset. Now re-fires while
`_pid_is_new_unsaved` is True, gated on a snapshot of the pid-scoped `t2_` keys
so it only follows the user when a Tab 2 widget actually changed. Interacting
with another tab does not yank them back. Verified: "Outdoor SleepOut" saved
correctly with its slug and PDF.
**Known limitation:** the app still has no state tracking which tab is active and
forces selection by clicking a DOM element. This is a stopgap on an existing hack.

### ✅ Tab 4 captions are free text, editable, and no longer stamped on the image
**Fixed:** 12 Aug 2026 (`e76c3a2`)
The caption control was a five-option dropdown (Plan / Elevation / Section /
Detail / None) whose value was **also burned onto the crop** as an orange
uppercase banner via `add_label_to_image()` — which is why the options were short
words. Now a free-text field capped at 60 characters, derived from
`_estimate_snap_height`'s single-line assumption at the narrowest column width.
Editable after the crop is saved. Blank writes no key. Image stamping stopped.
**Still open:** the caption does not yet print on the document — see the P1 above.

### ✅ Tab 5 "Generate Word Document" did nothing (the August blocker)
**Fixed:** 9 Aug 2026
**Symptom:** Save worked and View Mode rendered with the Generate button live. Clicking
Generate returned a blank Edit form asking to Save again. No document written locally or
to Supabase Storage, no error on screen, nothing in `error_log.txt`. Edit failed the same
way. Regressed since May 2026.

**Root cause (measured, not inferred):** View Mode renders zero input widgets. Streamlit
garbage-collects a keyed widget's session-state value once a run completes without that
widget being instantiated. Every field — including `t5_new_subject_{pid}` — was read back
for View Mode, for Edit repopulation, and for the Generate handler's document config
straight from those transient widget keys. One View Mode render was enough to lose them.
On the next run `_has_content` evaluated False, the branch fell back to EDIT, and the
Generate handler — which lives entirely inside the View Mode branch — was never reached.
No exception, hence no error and no log entry.

**Regression source:** commit `bffa4ea` (20 May 2026) introduced the Save/View/Edit state
machine. Before it, the Generate button rendered in the same pass as the form widgets, so
they were never garbage-collected.

**Ruled out along the way:** the sidebar project-switch clear block in `app.py` was
suspected and exonerated — `WILL_FIRE=False` on every run of two live probe sessions. The
project-id list is deterministically ordered (`.order("project_id")` in
`_list_project_ids`, `sorted()` on the local fallback), so the misfire theory did not hold.

**Fix:** A single non-widget session key `t5_new_record_{pid}` holds the full saved RFI
(15 fields, including `client_idx`, `instructions` and `note` — three fields previously
captured nowhere durable). The branch condition, View Mode display, Edit repopulation and
the Generate handler's config all read from it. Both entry handlers ("+ New Manual RFI"
and "→ Create RFI") reset the flag and clear the record so a stale RFI cannot leak into a
new one. A `_default_kwarg` helper suppresses Streamlit's "default value but also set via
Session State API" warning on the 8 widgets that Edit repopulation writes ahead of
instantiation. The recipient bounds check was preserved.

**Verified:** probe log run #10 — `subject key exists=False | record_exists=True |
has_content=True | BRANCH=VIEW`. RFI-012, RFI-013 and RFI-014 generated successfully.
RFI-014 contained none of RFI-013's data, confirming no stale-record leak.
**File:** `ui_generate.py`

### ✅ Uncommitted `st.stop()` diagnostic block left in ui_generate.py
**Fixed:** 9 Aug 2026
An earlier debugging pass had left an uncommitted block containing `st.warning`, several
`st.write` calls and `st.stop()` immediately after the `generate_rfi_document()` call,
plus two smaller `DIAG` blocks elsewhere in the file. All were removed. Its silence during
testing was itself the clue that broke the case — if the Generate handler had been running,
that warning would have been on screen.
**Lesson:** never leave diagnostics in the tree uncommitted.

### ✅ AI-scanned RFI does not prefill the Tab 5 form
**Fixed:** 5 Aug 2026 (commit `8534edb`)
Clicking "→ Create RFI" on an approved AI issue now seeds the form fields.
Confirmed working 9 Aug 2026 — probe run #3 shows the subject key populated on selection.

### ✅ Sidebar could not be reopened after collapsing
**Fixed:** 4 Aug 2026
CSS was hiding `stHeader` and `stToolbar`, which contain Streamlit's
`stExpandSidebarButton`. Replaced the blanket `display:none` rules with
`visibility:hidden` on the toolbar plus `visibility:visible` on the expand
button — the only CSS mechanism that allows selectively un-hiding a child.
Also made `stHeader` transparent with `pointer-events:none` so it stops
covering the tab row. File: `app.py`.

### ✅ Sidebar showed stale project name after rename
**Fixed:** 4 Aug 2026
`app.py` cached sidebar labels and only rebuilt them when the list of project
IDs changed. Renaming a project leaves the pid unchanged, so the cache never
refreshed. Save handler in `ui_project.py` now clears `_sb_labels` and
`_sb_label_pids` after a successful save.

### ✅ usage_events RLS blocking inserts (code 42501)
**Fixed:** 25 May 2026
Added an INSERT policy for authenticated users on the `usage_events` table
via Supabase. Analytics now record correctly.

---
