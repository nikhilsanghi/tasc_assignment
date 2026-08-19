# prompts/ — verbatim system-prompt text per stage

Every prompt below is rendered as a stable system-prompt prefix (see `core/llm.py`'s `prompt_hash()` and each stage's own `_build_*_prefix()` — there is no shared generic prefix builder, each stage owns its own). The hash is the first 12 hex characters of a sha256 of the prompt file's text, computed at call time and returned in every API response's `meta.prompt_hashes`, so any change to a prompt is visible in the audit trail.

| Prompt | File | Hash (current) | Called from | Used at runtime? |
|---|---|---|---|---|
| Rubric Compiler | `compiler.md` | `022fa4946272` | `core/rubric.py::compile_guidance`, via `/api/compile_rubric` | yes |
| Analyst | `analyst.md` | `615fe3fbff5c` | `core/analyst.py::analyze_candidate`, via `/api/analyze` | yes |
| Reranker | `reranker.md` | `7faf458fd583` | `core/reranker.py::rerank`, via `/api/rerank` | yes |
| Judge | `judge.md` | `3967985c7a17` | `scripts/eval_live.py::judge_candidate`, via `scripts/run_evals.py` §6 | evals only — never called in the product's ranking or scoring path |

Hashes change if a prompt file's text changes; if the numbers above ever drift from `python3 -c "from core import llm; print(llm.prompt_hash('compiler'))"` (etc.), trust the live command, not this table — this table is a snapshot taken at the end of Phase 7.

## What each prompt does

**`compiler.md`** — translates a recruiter's free-text guidance into a small set of whitelisted rubric operations (reweight, promote/demote a skill, hard-filter, boost/penalty, set top-k). It never scores or names individual candidates; it structurally cannot emit a score override, since the output schema has no field for one. Comparative guidance ("we value X over Y") is required to emit both a positive op for X and a reweight down for Y. Untrusted guidance text is wrapped in `<recruiter_guidance>` tags and treated as data; anything addressing the system, requesting a prompt reveal, or targeting a candidate ID is rejected with `injection_suspected` or `policy_violation`.

**`analyst.md`** — explains one candidate's fit for one role using the already-deterministic score decomposition, producing verbatim-cited overlaps, gaps, a fit brief, three clarifying questions, and data flags. Every `overlaps[].evidence` string must be a literal substring of the candidate's normalized profile text — the prompt gives a worked good/bad citation example, and the mechanical critic (`core/critic.py`, not an LLM) re-verifies every citation before it reaches the recruiter. Profile text is wrapped in `<candidate_profile>` tags; an embedded instruction aimed at an "AI screener" is explicitly called out as an attack pattern to flag, not obey.

**`reranker.md`** — an independent, holistic second opinion on shortlist ordering, run once per session (single pass, never iterative). It never changes the deterministic score or order; it only returns a full re-ordering plus one-sentence rationales, which the scorer compares against its own ranking to surface `|Δrank| ≥ 2` disagreements as flags for the recruiter. The prompt explicitly bars it from weighing any banned criterion (nationality, age, gender, religion, …).

**`judge.md`** — evaluation-only. Grades a candidate 0–3 against a role's requirements using the same rubric a human recruiter uses when labeling the golden set, so `scripts/run_evals.py` §6 can report Cohen's κ between the judge and the Owner's own labels. Never touches the product's ranking or scoring path.

## Examples

Every prompt has at least one real input/output pair captured from a live call, in `prompts/examples/`:

- `compiler_1.json`, `compiler_2.json`, `compiler_3.json`
- `analyst_1.json`, `analyst_2.json`
- `reranker_1.json`
- `judge_1.json`
