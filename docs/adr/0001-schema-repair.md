# ADR 0001 — repair against the live schema, not a prompt

## Decision

The corrector reads the SQLite error and diffs it against the actual
schema: unknown columns/tables are swapped for the closest real name
(difflib) before any model rewrite is attempted. Only errors with no
deterministic fix go back to the brain with the error text attached.

## Why

"No such column" is the overwhelmingly common NL-to-SQL failure, and
it's mechanical — a prompt asking the model to "try again" burns a
network call and a fresh coin-flip on what a lookup answers exactly.
Deterministic repair is free, instant, and inspectable. The model
rewrite stays as the fallback for semantic errors (wrong join, wrong
filter), where a lookup genuinely can't help.

## Cost

Closest-name repair is syntactic: it can fix the spelling while
keeping the wrong column semantically (an invented `customer_name`
maps to `customer_id` just as happily as to `name`). Accepted, and
stated: repairs make SQL valid; the eval's row-set comparison is what
keeps answers right. Repairs are also bounded at 2 — past that, fail
loudly rather than guess forever.
