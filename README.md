# sql-agent

## Release notes — v1.1 (2026-11-02)

Measured numbers, offline, mock brain — full build-up in `RELEASES.md`.

- **Guardrail evals: 11/11** — DROP, DELETE, UPDATE, INSERT, stacked
  queries, destructive CTEs and a prompt-injection DROP are all refused
  with the database unchanged; an approved write on a throwaway DB
  actually lands. Run them with `python3 evals/run_guardrails.py`.
- **Validation gate** — SELECT runs by default; destructive statements
  need explicit approval (`POST /ask` accepts `approve_destructive`),
  and smuggled statements are blocked outright (see
  `docs/adr/0004-validation-gate.md`).
- **Execution accuracy still 13/13**, and CI now gates every push on
  byte-compile + both eval suites.

## Release notes — v1.0 (2026-10-20)

Measured numbers, offline, mock brain — every figure below comes from
`python3 evals/run_eval.py`, re-run today, against the seeded SQLite
dataset (12 customers, 12 products, 124 orders over 120 days).

- **Execution accuracy: 13/13** — golden questions are graded by row
  sets against independent, hand-written reference SQL. SQL strings
  are never compared: many spellings are correct (see `docs/adr/0002`).
- **Self-correction produced 1 of the 13 wins** — the golden set
  includes a question the brain answers with a singular table name
  (`customer`), the way model-generated SQL actually goes wrong; the
  corrector repaired it against the live schema and returned the right
  rows. Repairs are bounded at 2 and every attempt is traced.
- **Zero silent wrong answers** — a question the pipeline cannot fix
  returns its last error, in the API and in the UI, instead of a
  plausible guess (see `docs/adr/0003`).

Ask the shop's database questions in plain English — and watch it fix
its own SQL. No key, no cost.

## Live demo

**[https://tushar29k-sql-agent.onrender.com](https://tushar29k-sql-agent.onrender.com)** — Ask about revenue, top products, customer spend; then hit the "broken SQL demo" chip to watch the self-correction trace repair bad SQL live.
> Hosted on Render's free tier — the first visit after a while can take ~30s while the instance wakes up.

## The idea

Text-to-SQL demos stop at the happy path. Production text-to-SQL is
mostly the unhappy path: the model writes `customer` instead of
`customers`, invents a column, misjoins — and something has to catch
it before a wrong number reaches a dashboard. This project is the
catching part, built properly:

1. **Write** — a brain (deterministic mock patterns here; a real LLM
   behind the same seam when `LLM_API_KEY` is set) writes SQL against
   the schema it was shown.
2. **Execute** — for real, against a seeded SQLite shop DB (`db.py`).
3. **Repair** — errors are diffed against the live schema: bad table
   and column names are swapped to their closest real match
   (deterministic, instant, inspectable — `docs/adr/0001`). Errors
   with no mechanical fix go back to the brain with the error text.
4. **Bounded** — two repairs max, then the query fails loudly with
   the last error. Every attempt lands in the returned trace.

## Architecture

```
question
   │
   ▼
┌──────────┐  brain.sql(question, schema)
│  brain    │  MockBrain patterns / FreeBrain (real LLM, same seam)
└────┬─────┘
     │ SQL
     ▼
┌──────────┐  sqlite3 execute
│ executor  │
└────┬─────┘
     │ error?                    rows
     ▼                              │
┌──────────┐  repair against       │
│ corrector │  live schema          │
└────┬─────┘  (difflib closest     │
     │        name swap),          │
     │        ≤ 2 attempts ────────┘
     ▼ still failing
 fail loudly with last error + full trace
```

## API

```
POST /ask      {"question": "..."} -> {sql, rows, attempts, corrected, trace[]}
               {"question": "...", "approve_destructive": true} runs a
               destructive statement the gate paused — default is refused
GET  /schema   the live schema
GET  /samples  seeded questions (incl. the broken-SQL demo)
GET  /info     backend honesty badge
```

## Evals

```
python3 evals/run_eval.py
```

13 golden questions; expected answers are independent SQL written from
the schema. The suite also reports how many wins came from the
correction loop. History in `evals/eval-history.jsonl`; decisions in
`docs/adr/`.
