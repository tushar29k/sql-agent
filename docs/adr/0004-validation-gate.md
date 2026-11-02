# ADR 0004 — validation gate before execution

## Decision

Every brain-written statement passes `validate_sql()` before it touches
the database. SELECT (and WITH ... SELECT, EXPLAIN SELECT) runs.
A destructive first keyword (DROP, DELETE, UPDATE, ...) pauses with
`needs_approval` and only runs when the caller explicitly approves.
Stacked statements and destructive keywords smuggled inside a read
query are `blocked` outright — approval can't rescue those shapes,
because no legitimate request looks like them.

## Why

The brain is untrusted text in, SQL out. The repair loop in ADR 0001
already trusts the brain's output enough to execute it; without a gate,
a jailbroken or merely sloppy model could wipe the shop DB through the
same demo endpoint that shows off self-correction. Checking the SQL
text (not the question) keeps the gate honest: a polite question
wrapping a DROP is still a DROP.

## Cost

Keyword scanning is syntactic, not semantic — a SELECT that joins
tables the user shouldn't see still runs. Row-level access control is
a separate layer, not this gate. String literals and comments are
stripped before scanning so a product literally named after a keyword
doesn't false-positive.
