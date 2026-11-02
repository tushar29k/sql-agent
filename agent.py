"""NL -> SQL agent with a self-correction loop.

MockBrain (deterministic patterns) or FreeBrain (real LLM) writes the
SQL; the CORRECTOR doesn't care which — it executes, reads the SQLite
error, and repairs against the live schema:

- "no such column: X"  -> swap in the closest real column (difflib)
- "no such table: X"   -> swap in the closest real table
- anything else        -> ask the brain to rewrite with the error fed
                          back (bounded: 2 repair attempts, then fail
                          loudly with the last error — never loop, never
                          silently return wrong numbers)

Every attempt (SQL, error, fix) lands in the trace the API returns —
self-correction you can't see is self-correction you can't trust.
"""
import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db as dbmod
from validate import validate_sql

_REV = ("(SELECT SUM(oi.quantity * p.price) FROM order_items oi "
        "JOIN products p ON p.id = oi.product_id "
        "JOIN orders o ON o.id = oi.order_id)")


def _schema_text(schema):
    return "; ".join(f"{t}({', '.join(cols)})" for t, cols in schema.items())


class MockBrain:
    name = "mock"

    def sql(self, question, schema, error_context=""):
        q = question.lower()
        m = re.search(r"top (\d+)", q)
        top = int(m.group(1)) if m else 5
        if "revenue" in q and "month" in q:
            return ("SELECT strftime('%Y-%m', o.order_date) AS month, "
                    "ROUND(SUM(oi.quantity * p.price), 2) AS revenue "
                    "FROM orders o JOIN order_items oi ON oi.order_id = o.id "
                    "JOIN products p ON p.id = oi.product_id "
                    "GROUP BY month ORDER BY month")
        if "revenue" in q and "categor" in q:
            return ("SELECT p.category, "
                    "ROUND(SUM(oi.quantity * p.price), 2) AS revenue "
                    "FROM order_items oi JOIN products p ON p.id = oi.product_id "
                    "GROUP BY p.category ORDER BY revenue DESC")
        if "top" in q and "product" in q:
            return ("SELECT p.name, "
                    "ROUND(SUM(oi.quantity * p.price), 2) AS revenue "
                    "FROM order_items oi JOIN products p ON p.id = oi.product_id "
                    f"GROUP BY p.name ORDER BY revenue DESC LIMIT {top}")
        if "top" in q and "customer" in q:
            return ("SELECT c.name, "
                    "ROUND(SUM(oi.quantity * p.price), 2) AS spent "
                    "FROM customers c JOIN orders o ON o.customer_id = c.id "
                    "JOIN order_items oi ON oi.order_id = o.id "
                    "JOIN products p ON p.id = oi.product_id "
                    f"GROUP BY c.name ORDER BY spent DESC LIMIT {top}")
        if "each customer" in q and "order" in q:
            # deliberate near-miss: singular table name — this is what
            # model-generated SQL looks like on a bad day, and the
            # corrector's job is to bring it home
            return ("SELECT c.name, COUNT(o.id) AS orders "
                    "FROM customer c JOIN orders o ON o.customer_id = c.id "
                    "GROUP BY c.name")
        if "how many orders" in q or "number of orders" in q or "count" in q:
            cm = re.search(r"from ([a-z]+)", q)
            if cm:
                city = cm.group(1).capitalize()
                return ("SELECT COUNT(*) AS orders FROM orders o "
                        "JOIN customers c ON c.id = o.customer_id "
                        f"WHERE c.city = '{city}'")
            return "SELECT COUNT(*) AS orders FROM orders"
        if "average order" in q:
            return ("SELECT ROUND(AVG(t.total), 2) AS avg_order_value FROM "
                    "(SELECT o.id, SUM(oi.quantity * p.price) AS total "
                    "FROM orders o JOIN order_items oi ON oi.order_id = o.id "
                    "JOIN products p ON p.id = oi.product_id GROUP BY o.id) t")
        if "categor" in q and "product" in q:
            cm = re.search(r"in (?:the )?([a-z]+) categor", q)
            cat = cm.group(1).capitalize() if cm else "Electronics"
            return (f"SELECT name, price FROM products "
                    f"WHERE category = '{cat}' ORDER BY price")
        if "customers" in q and "from" in q:
            cm = re.search(r"from ([a-z]+)", q)
            city = cm.group(1).capitalize() if cm else "Delhi"
            return f"SELECT name FROM customers WHERE city = '{city}'"
        if "orders" in q and re.search(r"over|above|more than", q):
            n = re.search(r"(\d+)", q)
            amt = n.group(1) if n else "2000"
            return ("SELECT o.id, ROUND(SUM(oi.quantity * p.price), 2) AS total "
                    "FROM orders o JOIN order_items oi ON oi.order_id = o.id "
                    "JOIN products p ON p.id = oi.product_id "
                    f"GROUP BY o.id HAVING total > {amt} ORDER BY total DESC")
        if "most popular" in q or ("product" in q and "most" in q):
            return ("SELECT p.name, SUM(oi.quantity) AS units "
                    "FROM order_items oi JOIN products p ON p.id = oi.product_id "
                    "GROUP BY p.name ORDER BY units DESC LIMIT 1")
        return ("SELECT COUNT(*) AS orders, "
                "ROUND(SUM(oi.quantity * p.price), 2) AS revenue "
                "FROM orders o JOIN order_items oi ON oi.order_id = o.id "
                "JOIN products p ON p.id = oi.product_id")


class FreeBrain:
    name = "free-llm"

    def __init__(self, client):
        self.client = client

    def sql(self, question, schema, error_context=""):
        prompt = (f"SQLite schema: {_schema_text(schema)}\n"
                  "Write ONE SQLite SELECT query answering the question. "
                  "Reply with ONLY the SQL.\n"
                  + (f"Previous attempt failed with: {error_context}\n"
                     if error_context else "")
                  + f"Question: {question}")
        try:
            text = self.client.generate(prompt, max_tokens=220)
            sql = re.search(r"SELECT.*?;?$", text, re.S | re.I)
            if sql:
                return sql.group(0).rstrip(";")
        except Exception:  # noqa: BLE001 - fall back to the mock patterns
            pass
        return MockBrain().sql(question, schema, error_context)


def make_brain():
    try:
        from llm_client import FreeLLMClient
        client = FreeLLMClient.from_env()
        if client is not None:
            return FreeBrain(client)
    except Exception:  # noqa: BLE001 - no key -> mock
        pass
    return MockBrain()


class SQLAgent:
    def __init__(self, brain=None, db_path=dbmod.DB_PATH,
                 allow_destructive=False):
        self.brain = brain or make_brain()
        self.db_path = db_path
        self.allow_destructive = allow_destructive
        self.schema = dbmod.schema_summary(db_path)

    def _execute(self, sql):
        con = dbmod.connect(self.db_path)
        try:
            rows = [dict(r) for r in con.execute(sql)]
            return rows, None
        except Exception as e:  # noqa: BLE001 - errors are the input
            return None, f"{type(e).__name__}: {e}"
        finally:
            con.close()

    def _repair(self, sql, error):
        """Deterministic schema repair for the two classic error shapes."""
        m = re.search(r"no such column: (?:\w+\.)?(\w+)", error)
        if m:
            bad = m.group(1)
            all_cols = [c for cols in self.schema.values() for c in cols]
            close = difflib.get_close_matches(bad, all_cols, n=1)
            if close:
                fixed = re.sub(rf"\b{re.escape(bad)}\b", close[0], sql)
                return fixed, f"column '{bad}' -> '{close[0]}' (schema)"
        m = re.search(r"no such table: (\w+)", error)
        if m:
            bad = m.group(1)
            close = difflib.get_close_matches(bad, list(self.schema), n=1)
            if close:
                fixed = re.sub(rf"\b{re.escape(bad)}\b", close[0], sql)
                return fixed, f"table '{bad}' -> '{close[0]}' (schema)"
        return None, None

    def ask(self, question, approve_destructive=False):
        trace = []
        sql = self.brain.sql(question, self.schema)
        allow = self.allow_destructive or approve_destructive
        for attempt in range(3):  # 1 try + at most 2 repairs
            # gate runs before execute on every attempt — a brain
            # rewrite after an error could itself turn destructive
            status, reason = validate_sql(sql, allow_destructive=allow)
            if status != "ok":
                trace.append({"attempt": attempt + 1, "sql": sql,
                              "error": reason, "rows": None,
                              "blocked": status == "blocked",
                              "needs_approval": status == "needs_approval"})
                return {"question": question, "sql": sql, "rows": None,
                        "attempts": len(trace), "corrected": False,
                        "error": reason, "blocked": status == "blocked",
                        "needs_approval": status == "needs_approval",
                        "trace": trace, "brain": self.brain.name}
            rows, err = self._execute(sql)
            trace.append({"attempt": attempt + 1, "sql": sql,
                          "error": err,
                          "rows": len(rows) if rows is not None else None})
            if err is None:
                return {"question": question, "sql": sql, "rows": rows,
                        "attempts": attempt + 1, "corrected": attempt > 0,
                        "trace": trace, "brain": self.brain.name}
            fixed, note = self._repair(sql, err)
            if fixed is None:
                # no deterministic fix: ask the brain again with the error
                sql2 = self.brain.sql(question, self.schema,
                                      error_context=err)
                if sql2 == sql:
                    break  # brain can't improve it; fail loudly
                sql = sql2
                trace[-1]["repair"] = "brain rewrite with error context"
            else:
                sql = fixed
                trace[-1]["repair"] = note
        return {"question": question, "sql": sql, "rows": None,
                "attempts": len(trace), "corrected": False,
                "error": trace[-1]["error"], "trace": trace,
                "brain": self.brain.name}
