# UI_REDESIGN_PRD.md — Phase 8: Product UI redesign (PIN-inspired)

**Status:** Owner-approved, in progress on branch `ui-redesign`. This document is the **sequencing and scope authority for Phase 8**. `CLAUDE.md` remains the working contract (style rules, gate ritual, non-negotiables); `docs/MASTER_BRIEF.md` remains the spec authority for everything the redesign does not change. Phases 0–7 are complete and tagged (`gate-0`…`gate-7`); `main` is the submitted state and **must not receive any commit from this work until the Owner approves the merge**.

**One-line goal:** rebuild the frontend's look and feel to the standard of a commercial recruiting product (design reference: PIN, screenshots in `private/Pin_Screenshots/` — you may and should read all 12), add automatic client-side persistence of every search with a downloadable audit trace, and add a clearly-labeled non-functional outreach demo — **without changing one line of backend behavior**.

---

## 0. Read order for the implementing agent

1. `CLAUDE.md` (working contract — style gate, non-negotiables, gate procedure).
2. This document, fully.
3. The 12 screenshots in `private/Pin_Screenshots/` (design reference — this is an explicitly permitted `private/` read for this phase).
4. The current frontend: `public/index.html`, `public/app.js`, `public/styles.css` (78 / 268 / 125 lines — small; read all three completely).
5. `docs/MASTER_BRIEF.md` §2 (non-negotiables) and §4.5 (the frontend product bar — the behavioral floor you must preserve).

Do **not** re-read the rest of the brief, the implementation plan, or the phase-by-phase docs — they govern the completed backend, which you are not touching.

## 1. Hard constraints (violating any of these fails the phase)

1. **Zero backend changes.** No edits under `core/`, `api/`, `scripts/`, `tests/`, `data/`, `prompts/`. `git diff main --stat` at the end must show changes only in `public/`, `docs/`, `CLAUDE.md` (phase table row), `docs/DECISIONS.md`, `docs/TEST_RESULTS.md`, and `private/INTERVIEW_NOTES.md`.
2. **No frameworks, no build step, no new dependencies, no external requests.** Vanilla JS/CSS/HTML only. No CDN scripts, no icon fonts, no Google Fonts — system font stack and inline SVG icons only. The page must work served as plain static files.
3. **Every existing behavior keeps working** (the §4.5 product bar): access-code gate → role picker → guidance → Compile → echo-back (interpretation + ops + adjustments + rejections, policy-violation vs not-supported styled differently) → Confirm & Score → ranked table + separate insufficient-data strip → analyst cards streaming (first call alone, then pool of 4 — this caching pattern is D-26, do not change it) → reranker disagreement badges → checkbox approve → Approve & Export → markdown preview + `.md` download + `audit.json` download. Also preserve: 401 → re-prompt for access code, 429 → single retry after `retry_after`, per-card retry button on analyze failure, cache-hit badge, empty-guidance → default-rubric path.
4. **The echo-back confirmation and the human approval gate are non-negotiables** (brief §2.5, D-05). Restyle them; never bypass or auto-confirm them.
5. **No invented personal names, no photos, no PII** in any shipped file, including demo copy. Candidates are `candidate_id` + headline; avatars are generated (see §5). Outreach demo copy uses real data tokens, never invented names. No effort/time estimates anywhere. `python scripts/check_style.py` must stay green (it term-scans all git-visible files including new `public/*.js`).
6. **API key stays server-side; no LLM call is added, removed, or reconfigured.** The frontend still only renders JSON from the six existing endpoints.
7. **Do not deploy from this branch.** `vercel --prod` would overwrite the submitted production site. Local verification only (`python scripts/dev_server.py`, port **3000**) until the Owner merges.
8. `private/Pin_Screenshots/` stays in `private/`. Never copy screenshots or their contents into shipped files.

## 2. The API contract (verified against the code — render these, exactly these)

All endpoints require header `X-Access-Code`. All POST with JSON bodies except health (GET works). Error shapes: 401 `{error:"unauthorized"}`, 429 `{error:"rate_limited", retry_after}`, 502 `{error:"llm_output", detail}`, 400 `{error:"invalid_rubric", detail:[…]}`.

- `GET /api/health` → `{ok, model, data_loaded, prompts_dir, roles:[{role_id, title}]}` (10 roles).
- `POST /api/compile_rubric` `{role_id, guidance}` → `{rubric, interpretation, ops_accepted:[…], rejected:[{text, reason, detail, closest_supported}], adjustments:[{dimension, requested, applied, reason}], meta}`. `rubric` = `{weights, hard_filters, skill_overrides, boosts, penalties, top_k, interpretation, hash}`. `rejected[].reason` ∈ `policy_violation | not_supported | injection_suspected`.
- `POST /api/score` `{role_id, rubric}` → `{ranked:[entry…], insufficient_data:[cid…], filtered_out, unevaluable, decomposition:{cid→entry}, flags:{cid→[…]}, pool_countries:{country→n}, meta}`. Each ranked `entry`:
  ```
  {candidate_id, score (int 0-100), score_float, band ("strong"|"viable-with-gaps"|"stretch"),
   subscores: {required_skills|nice_to_have|experience_fit|seniority|location|availability
               → {value (0-1), flags:[…], evidence}},
   boosts_fired, penalties_fired, flags:[…], auto_questions:[…],
   country, headline, skills:[…], experience_years, seniority_level,
   location:{city,country}, notice_days, requirements:{required:[…], nice_to_have:[…]},
   dup_group_id, dup_conflicts, dup_members:[cid…] (only on collapsed group entries)}
  ```
  For `required_skills`/`nice_to_have`, `evidence` is the list of match hits `{skill, tier ("exact"|"alias"|"semantic"), evidence_token, similarity}` — this powers the tier-annotated skill chips. Read `core/scorer.py` if any shape is unclear; **never invent fields**.
- `POST /api/analyze` `{role_id, candidate_id, rubric}` → `{analysis, critic, regenerated, meta}`. `analysis` = `{candidate_id, overlaps:[{requirement, evidence, source_field, tier}], gaps:[{requirement, severity, note}], fit_brief, clarifying_questions:[{text, kind}], data_flags:[…], confidence}`. `meta.usage.cache_read_input_tokens > 0` ⇒ show the cache-hit badge.
- `POST /api/rerank` `{role_id, top_ids:[…], rubric}` → `{disagreements:[{candidate_id, det_rank, llm_rank, delta, rationale}], llm_order, missing_ids, meta}`.
- `POST /api/export` `{role_id, rubric, approved_ids, analyses:{cid→analyze-response}, rerank, session_meta:{guidance, rejected, adjustments, decomposition, compiled_at, approved_at}}` → `{markdown, audit_json}`. **Move the existing payload-assembly code from `app.js`; do not rewrite it** — its shape is contract-tested on the backend.

## 3. Design reference — what to take from the PIN screenshots

Study all 12 screenshots. The elements to reproduce (adapted to our data):

- **App shell:** fixed left sidebar (~260px, white, 1px right border): product mark on top, then a **role switcher** (replaces PIN's job-position switcher; lists the 10 roles from `/api/health`, current one checked), then nav items with count badges and status chips (PIN shows "PAUSED" next to Outreach — ours shows "DEMO"). Main content area on `#f9fafb`.
- **Criteria bar** (screenshot 04.43.02): a rounded, bordered, full-width bar with a sparkle icon, the guidance text, and a "+N criteria" link showing the count of accepted ops; a pencil icon to edit. Below it, when compiled, the echo-back panel.
- **Candidate card:** avatar + `candidate_id — headline` title + location line; right side: score badge ("84 FIT SCORE" style — green tint for `strong`, amber for `viable-with-gaps`, gray for `stretch`) and an action row (Analyze · Shortlist · Details). Body sections with small-caps labels: CRITERIA (subscore rows: name, mini progress bar, value, flag icons — analog of PIN's "3 out of 3 Criteria Met" green checks), MATCHED SKILLS (chips annotated with tier: `SQL · exact`, `Python · alias`, `REST API design · semantic ~0.80`), PROFILE (experience years, seniority, notice days, country — analog of PIN's Tenure/Current lines).
- **Detail drawer** (04.43.41): right slide-over (~560px) with ↑/↓ candidate navigation, close ×, full subscore decomposition, all analyst output (overlaps with the verbatim evidence highlighted, gaps, fit brief, 3 questions, data flags, confidence), dup-group members + conflicting fields table, reranker verdict, boosts/penalties fired.
- **Shortlist flow** (04.43.54, 04.44.00): Shortlist button on the card → toast "Added to shortlist · Undo" (bottom center, auto-dismiss ~5s) → count badge in the sidebar → Shortlist view listing selected candidates → Approve & Export. Include a note echoing PIN's honesty line: "Nothing is exported without your explicit approval."
- **Outreach sequence editor** (04.44.21 → 04.44.31): three-pane layout — step list (New Email · Day 1 / Reply · Day 4 / Reply · Day 8, plus "After candidate replies" branches), step cards with From/Subject/Type rows and body, "Wait N days" connectors, add-step menu listing Email Reply / New Thread / LinkedIn Message / Connection Request / Text / Call / Custom Task. Ours is a **static demo** — see §7.
- **Empty states everywhere** (04.43.25): centered icon + bold title + one-line body + CTA button.
- **Overview dashboard** (04.43.11): stat panels + "Recent updates" list — ours is powered by localStorage history (§6).

## 4. Design system (implement as CSS custom properties in `styles.css`)

```
--bg:#f9fafb  --surface:#fff  --border:#e5e7eb  --border-2:#d1d5db
--text:#111827  --text-2:#6b7280  --text-3:#9ca3af
--accent:#2563eb  --accent-bg:#eff6ff
--green:#16a34a  --green-bg:#f0fdf4   (band strong, criteria met, success)
--amber:#d97706  --amber-bg:#fffbeb   (band viable, adjustments, shortlist accents)
--red:#dc2626    --red-bg:#fef2f2     (band stretch is gray, red = rejections/decline)
--violet:#7c3aed --violet-bg:#f5f3ff  (AI/LLM-related accents: compile sparkle, reranker)
--radius-s:8px --radius-m:12px --radius-l:16px
--shadow-s:0 1px 2px rgba(0,0,0,.05)  --shadow-m:0 4px 12px rgba(0,0,0,.08)
font: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, sans-serif
base 14px; small-caps section labels 11px/600/letter-spacing .05em/uppercase/--text-2
```

Components to build once and reuse: buttons (primary/secondary/ghost/danger), pill chips (per accent), score badge, card, sidebar item (+count badge), drawer + overlay, modal, toast, skeleton shimmer block, empty state, subscore progress bar, section label. Avatars: 40px rounded square, deterministic 2-color CSS gradient hashed from `candidate_id`, showing the numeric part (e.g. "C101" → "101") in white 11px.

## 5. Information architecture & routing

Hash-based routing, no server config: `#/sourcing` (default) · `#/shortlist` · `#/searches` · `#/outreach` · `#/reports` · `#/overview`. A tiny router shows/hides one `<section>` per view and sets the active sidebar item. The access-code overlay sits above everything until a valid code is stored (existing `sessionStorage` behavior — keep it).

Sidebar nav (top→bottom): **Overview · Sourcing · Shortlist [n] · Searches [n] · Outreach ["DEMO" chip] · Reports**. Role switcher above the nav; switching roles mid-session prompts "Start a new search for {role}?" (confirm → fresh session, current one is already auto-saved).

## 6. Auto-save every search (localStorage) — the persistence spec

**Decision to log (D-6x):** client-side persistence via `localStorage`, because the brief mandates zero server-side state at this scale and names append-only Postgres as the production path (already stated in the README). Auto-saving the recruiter's own session trace does not touch the export gate: the hiring-manager export still requires explicit approval.

- Key `mi_sessions_v1` → `{"sessions": {id → session}, "order": [newest-first ids]}`. Cap at 20 sessions; evict oldest. Wrap every write in try/catch (quota) — on failure, show a one-time toast "History full — oldest search dropped", evict, retry once.
- `session` = `{id (timestamp-based), created_at, updated_at, role_id, role_title, guidance, status: "compiled"|"scored"|"analyzed"|"reranked"|"approved"|"exported", rubric, compile: {interpretation, ops_accepted, rejected, adjustments}, score: {ranked, insufficient_data, filtered_out, pool_countries}, analyses: {cid → analyze-response}, rerank, approved_ids, export: {markdown, audit_json} | null}`. Omit `decomposition`/`flags` maps from the stored score (they duplicate `ranked`).
- Write points: after compile-confirm, after score, after **each** analyze completes, after rerank, after approval toggles, after export. Update in place by session id.
- **Searches view:** list sessions (role, guidance snippet, status chip, timestamp, candidate count). Click → read-only re-render of the full session from stored data (no API calls), with a "Re-run this search" button that prefills the guidance in a fresh Sourcing session. Delete button per row.
- **Reports view:** same sessions, audit-centric: "Download session trace (JSON)" for any session (pretty-printed session object — this is the automatic audit report), and for exported sessions also "Download audit.json" / "Download shortlist.md" (the real approved artifacts). One line at top: "Session traces are drafts; only approved exports are hiring-manager artifacts."

## 7. Outreach demo spec (static, honest)

Banner at top, styled like PIN's paused banner but explicit: **"Outreach is a design demo — nothing is sent and no email accounts are connected."** Layout mirrors the screenshots: left step list (Day 1 New Email, Day 4 Reply, Day 8 Reply; "After candidate replies" branches as static rows), right step cards. Step cards: From row shows "No accounts connected" (amber, like PIN), Subject `"{role_title} opportunity"`, a Written-by-AI/Manual toggle rendered but inert, and a body built by **deterministic template fill** from the currently shortlisted candidate (picker at top, like PIN's candidate preview): tokens `{{candidate_id}}`, `{{role_title}}`, `{{top_overlap}}` (first overlap requirement from that candidate's stored analysis, else first matched skill) rendered as violet highlight chips. Add-step menu rendered with all PIN options (LinkedIn Message, Connection Request, Text, Call, Custom Task) **grayed out** with tooltip "Not in scope — integration point". No LLM call, no network call, no personal names in the copy ("Hi {{candidate_id}}," is correct and honest for synthetic data).

## 8. Overview spec (light)

Stat cards from localStorage + last session meta: searches run, candidates analyzed (sum), exports made, cache-read tokens on last analyze (from stored `meta.usage`). "Recent updates" = last 5 sessions with status. Empty states when history is empty ("Run your first search → Go to Sourcing").

## 9. File organization

- `public/index.html` — shell, all view sections, drawer/modal/toast containers. Semantic, commented by view.
- `public/styles.css` — tokens + components + views (single file is fine; CSS is not length-checked).
- `public/app.js` — namespace `MI = {}`, `api()`, `pool()`, state, router, boot, auto-save/localStorage module. Keep the existing `api()`/`pool()`/retry/429 logic — move, don't rewrite.
- `public/views.js` — Sourcing view: criteria bar, echo-back, candidate cards, insufficient strip, skeletons.
- `public/drawer.js` — drawer, shortlist flow, toasts, modal, Shortlist view, export rendering.
- `public/extras.js` — Searches, Reports, Outreach demo, Overview.

Classic scripts with `defer`, loaded in that order; everything hangs off the single `MI` global. JS files are term-scanned by `check_style.py` automatically (it walks `git ls-files`) but not length-checked; still keep each file ≲400 lines for reviewability. `vercel.json` needs no change (`public/` is already the static root); `scripts/dev_server.py` already serves any file in `public/`.

## 10. Build sequence — commit after each step, verify before moving on

Each step ends with: `python scripts/dev_server.py` → full manual click-through of everything built so far (the D-57 lesson: mocked tests cannot catch browser-only bugs — the previous phase's only frontend bug was caught exactly this way), plus `pytest -q` (must stay 136 passed — proves backend untouched) and `python scripts/check_style.py` (green).

1. **Shell.** Design system CSS, sidebar, router, role switcher, access overlay restyle. Wire the **existing, unmodified flow** into the new Sourcing section — ugly is fine, working is mandatory. Commit: `phase8: app shell + design system`.
2. **Sourcing view.** Criteria bar + inline echo-back + candidate cards (subscore bars, tier chips, flags, dup badge) + insufficient strip + analyze streaming with skeletons + rerank badges. Commit: `phase8: sourcing view`.
3. **Drawer + shortlist.** Drawer with ↑/↓/Esc keys, full detail rendering; shortlist toggle + toast + sidebar count + Shortlist view + Approve & Export (existing payload assembly moved verbatim). Commit: `phase8: drawer + shortlist`.
4. **Persistence.** localStorage module + auto-save at all write points + Searches + Reports views. Log the decision entry. Commit: `phase8: auto-saved searches + reports`.
5. **Outreach demo + Overview.** Commit: `phase8: outreach demo + overview`.
6. **Polish + gate.** Empty states, focus states, `aria-label`s on icon buttons, error surfaces (429/502 messages inline). Full end-to-end twice: once with guidance `prioritize immediate availability; A/B testing matters a lot` on R004, once with empty guidance (default rubric). `pytest -q`, `pytest -q -m live` once (needs key; verifies nothing regressed in real calls), `check_style.py`. Then the gate paperwork (§11). Commit: `phase8: polish`, then STOP.

If any step reveals a backend bug or missing field: **stop and report to the Owner** — do not "fix" the backend under this PRD's authority.

## 11. Acceptance criteria & gate

**Functional floor (all must pass in a real browser):** every item in constraint §1.3, in the new UI. **New capabilities:** session auto-saved at every step and reopenable read-only from Searches; session trace downloadable from Reports; exported artifacts additionally downloadable there; outreach demo renders with real-data tokens and sends nothing; overview stats correct against history.

**Gate paperwork (per `CLAUDE.md` ritual, adapted):** add a "Phase 8 — product UI" section to `docs/TEST_RESULTS.md` (manual checklist as evidence — paste what you actually clicked and saw); append `D-60+` entries to `docs/DECISIONS.md` (file split, localStorage choice, outreach-demo design, plus anything you decided); add a Phase 8 row (`in review`) to the `CLAUDE.md` phase table; append a Gate 8 block to `private/INTERVIEW_NOTES.md` (what was built / what broke / numbers / lesson); update `README.md` with one short "Product UI" paragraph (no screenshots, no tool names needed). Then **STOP and wait for the Owner** — the Owner reviews the branch, and only the Owner merges to `main` and deploys.

## 12. Explicit do-not list (recap)

Do not: touch `core/ api/ scripts/ tests/ data/ prompts/` · add dependencies or CDNs · bypass echo-back or approval · auto-confirm anything · invent candidate names or photos · put time estimates or personal info in any file · deploy from the branch · commit anything from `private/` · change the analyze fan-out pattern (first alone, then pool of 4) · rewrite the export payload assembly · exceed rubric/LLM scope (no new LLM calls).
