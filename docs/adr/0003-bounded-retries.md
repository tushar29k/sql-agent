# ADR 0003 — bounded retries, loud failures

## Decision

At most 2 repairs per question. After that the agent returns the last
error in the response (and the UI shows it), not a best-effort answer.

## Why

An NL-to-SQL agent that returns plausible-but-wrong numbers is worse
than one that admits failure — the user acts on the number. Bounded
retries also bound cost and latency with a real model in the loop.
The trace shows every attempt, so "it failed" is diagnosable instead
of mysterious.

## Cost

Some questions that a third or fourth attempt would fix stay failed.
Accepted: in production that's the escalation path (log it, fix the
brain), not the retry path.
