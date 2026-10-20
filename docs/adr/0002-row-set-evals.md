# ADR 0002 — evals compare row sets, never SQL strings

## Decision

Golden cases pair a question with independent reference SQL. Passing =
the agent's returned rows equal the reference rows (order-free,
floats rounded to 2).

## Why

There are many correct spellings of the same query (different join
order, aliases, subquery shapes). String comparison would fail
correct SQL and — worse — tempt the generator to imitate the
reference instead of answering the question. Row sets test the thing
users care about: the numbers. The reference SQL is written from the
schema by hand, never generated from the agent's output, so the eval
can't ratify the agent's own mistakes.

## Cost

Reference SQL has to be maintained by hand for every golden question.
That's the honest price of an eval you can trust — the same rule the
other four projects use for their golden sets.
