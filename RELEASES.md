# Release notes

## v1.2 — guardrail variant benchmark (2026-11-03)

- **Variant benchmark (`evals/run_guardrail_variants.py`) — report-only.**
  The 10 hand-written guardrail seeds are multiplied by deterministic
  mutations (`evals/sql_mutations.py`, generator in
  `evals/generate_guardrail_variants.py`) into **84 attack variants**
  across 7 families — case, whitespace, comment splitting, stacked
  statements, structural synonyms, question encodings, paraphrases —
  plus **13 benign near-miss controls** (destructive keywords in
  identifiers, literals, comments, quoted aliases).
- **Results** (`evals/guardrail-variants-results.md`): attacks 78/84
  exact-match, **83/84 stopped at the gate, none executed** (DB
  unchanged in all 97 cases); controls 11/13, false-block rate 15.4%.
- **Findings logged, gate deliberately unfixed**: a comment-glued
  `DELETE/**/FROM` inside a WITH wrapper evades the keyword scan
  (not executable on this SQLite build — DML-in-CTE is a syntax
  error — but the classification is wrong); comment-glued standalone
  writes are over-blocked and lose the approval path; backtick- and
  bracket-quoted aliases are false-blocked. The seed suite stays the
  gate: 11/11, accuracy 13/13.

## v1.1 — validation gate + guardrail evals + CI (2026-11-02)

- **Validation gate (`validate.py`)** — every brain-written statement is
  checked before it touches the database. SELECT runs; a destructive
  first keyword pauses with `needs_approval` and only runs when the
  caller explicitly approves (`POST /ask` accepts
  `approve_destructive`); stacked statements and destructive keywords
  smuggled inside a read query are blocked outright.
- **Guardrail evals (`evals/run_guardrails.py`) — 11/11** — DROP, DELETE,
  UPDATE, INSERT, stacked SELECT+DROP, destructive CTE,
  comment-prefixed DROP and a prompt-injection DROP are all refused
  with the seeded DB byte-identical afterwards; two controls (a legit
  SELECT, a keyword inside a string literal) still pass, and an
  approved DELETE on a throwaway DB actually lands.
- **Bug the guardrails caught** — `_execute` closed the connection
  without committing, so an approved write silently rolled back. Fixed
  with an explicit commit; SELECTs are unaffected.
- **CI (`.github/workflows/ci.yml`)** — push/PR to main gates on
  byte-compile, accuracy evals (13/13) and guardrail evals (11/11),
  Python 3.12, offline, no keys.

## v1.0 — NL to SQL with bounded self-correction (2026-10-20)

- Execution accuracy 13/13 on golden questions graded by row sets
  against independent reference SQL; 1 of the 13 wins came from the
  correction loop.
- Bounded repairs (at most 2), every attempt traced, failures loud
  instead of plausible-but-wrong.
