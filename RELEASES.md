# Release notes

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
