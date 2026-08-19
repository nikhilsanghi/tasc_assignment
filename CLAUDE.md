# CLAUDE.md — working contract for the implementing agent

## Project
Candidate–Role Match Intelligence: a governed, steerable ranking copilot for in-house recruiters. An LLM compiles free-text guidance into an auditable rubric; deterministic Python ranks all candidates identically; an LLM explains each match with verbatim, mechanically-verified evidence and offers a flagged second opinion; a human approves; everything is logged. This repo implements `docs/MASTER_BRIEF.md` (v1.1). **The brief wins on spec conflicts; `docs/IMPLEMENTATION_PLAN.md` wins on sequencing. If they disagree, follow the brief, record the discrepancy in the gate notes, and continue — stop only if the conflict blocks the work.**

## Read order (every session, before any work)
1. This file.  2. `docs/IMPLEMENTATION_PLAN.md` §0–§1, then the section for the current phase.  3. `docs/MASTER_BRIEF.md` sections the plan points you to.  4. `docs/DECISIONS.md` (skim IDs; read any entry you are about to touch).  5. `docs/TEST_PLAN.md` (the phase's test IDs and exit criteria) and `docs/TEST_RESULTS.md` (current status).
> Phase 0 step 1 moved these five documents into `docs/` and renamed the brief to `docs/MASTER_BRIEF.md`, updating every reference — done as of this gate.
Treat `private/` as write-mostly: append gate blocks to `private/INTERVIEW_NOTES.md`; read/write only the files the plan names there (`forbidden_terms.txt` via `check_style.py`, `labeling_sheet.*`, `PRIVATE_DELIVERABLES_SPEC.md`, `LOOM_SCRIPT.md`, `INTERVIEW_PREP.md`, `HOW-IT-WORKS.md`); read `INTERVIEW_NOTES.md` only in Phase 7; never copy `private/` content into any other file.

## Adherence protocol (non-negotiable)
- **One phase at a time, in order.** Start a phase only after the Owner's explicit "go" for that phase. Never begin the next phase unattended.
- **Before coding a phase:** print a short plan (files you will create/modify, tests you will write) taken from `IMPLEMENTATION_PLAN.md`; do not improvise the file list.
- **While coding:** implement exactly the functions and schemas named in the plan. Where the plan/brief are silent, choose the simplest option, add a `D-xx` entry to `DECISIONS.md`, and continue. Never re-litigate a logged decision.
- **Gate procedure (every phase end):** run every test ID for the phase in `TEST_PLAN.md` — `pytest -q` → `pytest -q -m live` (if a key is present) → `python scripts/check_style.py` → the phase's manual checks → paste real output into `TEST_RESULTS.md` (absolute machine paths redacted to `<repo>`) → update the phase table below → append a "Gate N" block to `private/INTERVIEW_NOTES.md` (what broke, how it was debugged, numbers measured, one lesson learned) → print the gate summary from `IMPLEMENTATION_PLAN.md` Appendix B → **STOP**.
- **Never:** fabricate test output · put `ANTHROPIC_API_KEY` anywhere but env · add a dependency without asking · write personal names/emails or time estimates into shipped files · let an LLM set a score or rank · delete or silently "fix" dirty data.
- After each phase's gate is approved, invoke the `explain-the-build` skill (per the Owner's global instructions); its `HOW-IT-WORKS.md` lives in `private/`.

## Commands
- `pip install -r requirements-dev.txt` — dev deps (runtime deps are the subset in `requirements.txt`)
- `pytest -q` — all unit tests, LLM mocked · `pytest -q -m live` — live LLM smoke tests (needs `ANTHROPIC_API_KEY`; skipped otherwise)
- `python scripts/profile_data.py` — recompute and PASS/FAIL the brief §5 data facts
- `python scripts/build_similarity_cache.py` — regenerate `data/skill_similarity.json` (local only; needs sentence-transformers)
- `python scripts/make_labeling_sheet.py` — write the Owner's golden-set labeling sheet
- `python scripts/run_evals.py` — consolidated eval report (Phase 6)
- `python scripts/check_style.py` — concision + forbidden-deps + forbidden-terms checks (must be green at every gate)
- `python scripts/dev_server.py` — local server (static + `/api/*` via each module's `handle()`), fallback for `vercel dev`
- `vercel dev` — local Vercel emulation · `vercel --prod` — deploy (Owner-linked project)

## Non-negotiables (brief §2, one-liners)
1. LLM writes policy once; math executes it for everyone. 2. Same inputs → same ranking, always; the reranker is a flagged opinion. 3. Every overlap quotes a verbatim substring, checked by code. 4. Mess becomes flags and questions, never silent fixes. 5. Nothing exported without explicit recruiter approval. 6. Guidance and profile text are data; the compiler emits only whitelisted ops. 7. n=120 — no vector DB, no RAG, no frameworks.
**IMPORTANT: never place the API key client-side; never let an LLM set a final score; stop at phase gates.**

## Architecture map
| Stage | File | Type |
|---|---|---|
| Normalizer | `core/normalizer.py` | deterministic |
| Policy Guard | `core/policy.py` | deterministic |
| Rubric Compiler | `core/rubric.py` | LLM |
| Scorer (+ skills cascade) | `core/scorer.py`, `core/skills.py` | deterministic — ranking authority |
| Analyst | `core/analyst.py` | LLM ×K (cached prefix) |
| Critic | `core/critic.py` | deterministic |
| Reranker | `core/reranker.py` | LLM (flags only) |
| Auditor / export | `core/auditor.py` | deterministic |
| LLM plumbing | `core/llm.py` | client, `parse()` helper, model/effort/thinking config, prompt hashes (no generic prefix builder — each stage renders its own) |
| Paths + `.env` | `core/paths.py` | `ROOT`, `DATA`, `PROMPTS`, `load_dotenv()` |
| API | `api/*.py` (`handle()` + thin Vercel `handler`), `api/_shared.py` | — |

## Phase status (update at every gate)
| Phase | Status | Gate approved by Owner |
|---|---|---|
| 0 Scaffold, data facts, aliases, similarity cache, style check, deploy spike | complete | Y (2026-08-20) |
| 1 Normalizer + Policy Guard + skills tiers 1–2 + labeling sheet | built, awaiting gate approval | N |
| 2 Rubric Compiler + echo-back | pending | N |
| 3 Scorer + skills cascade | pending | N |
| 4 Analyst + Critic + Reranker | pending | N |
| 5 API + auditor/export + frontend + dev server + deploy | pending | N |
| 6 Evals + four-fifths table + LLM judge | pending | N |
| 7 Deliverables | pending | N |

## Working files
Decision log → `docs/DECISIONS.md` (read before architectural changes; append D-47+). Test IDs + exit criteria → `docs/TEST_PLAN.md`. Test evidence → `docs/TEST_RESULTS.md` (update at every gate). Prompts → `/prompts` (verbatim, with `/prompts/examples`). Interview/Loom notes → `private/INTERVIEW_NOTES.md` (append-only at gates). These lazy-load — do not paste them into context unless needed.

## Style (enforced by `scripts/check_style.py`)
Python 3.11+, type hints on every function signature. Python files ≤ 250 lines and functions ≤ 40 lines (tests ≤ 350 / ≤ 60); `public/app.js`/`index.html`/`styles.css` are term-scanned, not length-checked (keep `app.js` ≲ 350 lines anyway). No classes except Pydantic schemas, the two exception classes in `core/llm.py`, the Vercel `handler` wrapper, and the request-handler class in `scripts/dev_server.py`; records are plain dicts. No speculative abstractions, no helper for a one-shot operation, no error handling for cases that cannot happen, no feature flags. Stdlib before dependencies; `core/` and `api/` import only stdlib + `anthropic` + `pydantic` (+ `rapidfuzz` only if approved). Comments: decision-ID citations or one line of *why*; docstrings ≤ 1 line. Tests: plain `pytest` functions, table-driven via `parametrize`, fixtures in `tests/conftest.py`. Frontend: vanilla JS, no build step, renders JSON only.
