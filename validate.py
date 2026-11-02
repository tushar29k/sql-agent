"""Read-only gate for brain-written SQL.

Runs before anything touches the database: a SELECT (or WITH ... SELECT)
goes through, anything destructive pauses for approval, and smuggled
statements never reach sqlite at all. The gate reads the SQL text, not
the question — a polite question wrapping a DROP is still a DROP.
"""

import re

# statements that change data or schema — never run on the default path
_DESTRUCTIVE = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE",
    "PRAGMA", "ATTACH", "DETACH", "VACUUM", "REINDEX", "ANALYZE",
    "TRUNCATE",
}


def _clean(sql):
    """Strip string literals and comments so keywords inside them don't
    trip the gate — 'deleted items' in a WHERE clause is just text."""
    out = []
    i = 0
    while i < len(sql):
        c = sql[i]
        if c == "'":  # single-quoted literal, '' is an escaped quote
            out.append("''")
            i += 1
            while i < len(sql):
                if sql[i] == "'":
                    if i + 1 < len(sql) and sql[i + 1] == "'":
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
        elif c == '"':  # double-quoted identifier
            out.append('""')
            i += 1
            while i < len(sql) and sql[i] != '"':
                i += 1
            i += 1
        elif sql.startswith("--", i):  # line comment to end of line
            while i < len(sql) and sql[i] != "\n":
                i += 1
        elif sql.startswith("/*", i):  # block comment
            end = sql.find("*/", i + 2)
            i = len(sql) if end == -1 else end + 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _first_keyword(cleaned):
    m = re.match(r"\s*([A-Za-z]+)", cleaned)
    return m.group(1).upper() if m else ""


def validate_sql(sql, allow_destructive=False):
    """Return (status, reason): status is 'ok', 'blocked', or
    'needs_approval'. Destructive statements need approval; stacked or
    smuggled statements are blocked outright, approval can't save them."""
    if not sql or not sql.strip():
        return "blocked", "empty SQL refused"
    cleaned = _clean(sql).strip()
    # one statement only — a trailing semicolon is fine, a second
    # statement after it is the classic stacked-query injection
    parts = [p for p in cleaned.split(";") if p.strip()]
    if len(parts) > 1:
        return "blocked", "multiple statements refused"
    first = _first_keyword(cleaned)
    if first == "EXPLAIN":
        rest = re.sub(r"^\s*EXPLAIN\s+", "", cleaned, flags=re.I)
        first = _first_keyword(rest)
        if first not in ("SELECT", "WITH"):
            return "blocked", f"EXPLAIN of {first or 'nothing'} refused"
        cleaned = rest
    if first in _DESTRUCTIVE:
        if allow_destructive:
            return "ok", ""
        return "needs_approval", (
            f"{first} needs approval — read-only mode runs SELECT only")
    if first in ("SELECT", "WITH"):
        # a WITH ... DELETE or a SELECT smuggling a write is an attack
        # shape, not a request — block it, don't offer approval for it
        found = re.findall(r"\b([A-Za-z]+)\b", cleaned.upper())
        bad = [w for w in found if w in _DESTRUCTIVE]
        if bad:
            return "blocked", f"destructive keyword inside read query: {bad[0]}"
        return "ok", ""
    return "blocked", f"only SELECT runs without approval, got {first or 'empty'}"
