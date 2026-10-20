"""NL-to-SQL evals: execution accuracy on a golden question set.

Each case is a question plus INDEPENDENT reference SQL (written directly
against the schema — not produced by the agent). Execution accuracy =
agent's result rows match the reference rows, ignoring row order.
SQL strings are never compared — many spellings are correct.

Also counts how often the self-correction loop fired, and how often it
turned a failure into a correct answer.

Run: python3 evals/run_eval.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import db as dbmod  # noqa: E402
from agent import MockBrain, SQLAgent  # noqa: E402

GOLDEN = [
    ("how many orders are there in total",
     "SELECT COUNT(*) AS orders FROM orders"),
    ("total revenue by month",
     "SELECT strftime('%Y-%m', o.order_date) AS month, "
     "ROUND(SUM(oi.quantity * p.price), 2) AS revenue "
     "FROM orders o JOIN order_items oi ON oi.order_id = o.id "
     "JOIN products p ON p.id = oi.product_id "
     "GROUP BY month ORDER BY month"),
    ("top 3 products by revenue",
     "SELECT p.name, ROUND(SUM(oi.quantity * p.price), 2) AS revenue "
     "FROM order_items oi JOIN products p ON p.id = oi.product_id "
     "GROUP BY p.name ORDER BY revenue DESC LIMIT 3"),
    ("what is the average order value",
     "SELECT ROUND(AVG(t.total), 2) AS avg_order_value FROM "
     "(SELECT o.id, SUM(oi.quantity * p.price) AS total "
     "FROM orders o JOIN order_items oi ON oi.order_id = o.id "
     "JOIN products p ON p.id = oi.product_id GROUP BY o.id) t"),
    ("how many orders are from delhi customers",
     "SELECT COUNT(*) AS orders FROM orders o "
     "JOIN customers c ON c.id = o.customer_id WHERE c.city = 'Delhi'"),
    ("list the customers from kochi",
     "SELECT name FROM customers WHERE city = 'Kochi'"),
    ("show me products in the sports category",
     "SELECT name, price FROM products WHERE category = 'Sports' "
     "ORDER BY price"),
    ("revenue by category",
     "SELECT p.category, ROUND(SUM(oi.quantity * p.price), 2) AS revenue "
     "FROM order_items oi JOIN products p ON p.id = oi.product_id "
     "GROUP BY p.category ORDER BY revenue DESC"),
    ("top 5 customers by spend",
     "SELECT c.name, ROUND(SUM(oi.quantity * p.price), 2) AS spent "
     "FROM customers c JOIN orders o ON o.customer_id = c.id "
     "JOIN order_items oi ON oi.order_id = o.id "
     "JOIN products p ON p.id = oi.product_id "
     "GROUP BY c.name ORDER BY spent DESC LIMIT 5"),
    ("what is the most popular product",
     "SELECT p.name, SUM(oi.quantity) AS units "
     "FROM order_items oi JOIN products p ON p.id = oi.product_id "
     "GROUP BY p.name ORDER BY units DESC LIMIT 1"),
    ("orders over 5000",
     "SELECT o.id, ROUND(SUM(oi.quantity * p.price), 2) AS total "
     "FROM orders o JOIN order_items oi ON oi.order_id = o.id "
     "JOIN products p ON p.id = oi.product_id "
     "GROUP BY o.id HAVING total > 5000 ORDER BY total DESC"),
    ("top 2 products by revenue",
     "SELECT p.name, ROUND(SUM(oi.quantity * p.price), 2) AS revenue "
     "FROM order_items oi JOIN products p ON p.id = oi.product_id "
     "GROUP BY p.name ORDER BY revenue DESC LIMIT 2"),
    ("how many orders has each customer placed",
     "SELECT c.name, COUNT(o.id) AS orders "
     "FROM customers c JOIN orders o ON o.customer_id = c.id "
     "GROUP BY c.name"),
]


def _norm(rows):
    # row sets compared order-free; floats rounded to 2 (money)
    out = []
    for r in rows:
        out.append(tuple(round(v, 2) if isinstance(v, float) else v
                         for v in r.values()))
    return sorted(out)


def main():
    agent = SQLAgent(brain=MockBrain())
    con = dbmod.connect()
    correct, corrected = 0, 0
    for question, ref_sql in GOLDEN:
        expected = _norm([dict(r) for r in con.execute(ref_sql)])
        out = agent.ask(question)
        got = _norm(out["rows"]) if out["rows"] is not None else None
        ok = got == expected
        correct += ok
        corrected += ok and out["corrected"]
        status = "PASS" if ok else "FAIL"
        fix = " (self-corrected)" if out["corrected"] else ""
        print(f"{status}{fix}  {question[:44]}")
        if not ok:
            print(f"   want {expected[:3]}\n   got  {got[:3] if got else None}")
    con.close()
    print(f"execution accuracy: {correct}/{len(GOLDEN)}")
    print(f"wins from self-correction: {corrected}/{len(GOLDEN)}")
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "eval-history.jsonl"), "a") as f:
        f.write(json.dumps({"accuracy": correct, "total": len(GOLDEN),
                            "corrected": corrected}) + "\n")
    return 0 if correct == len(GOLDEN) else 1


if __name__ == "__main__":
    sys.exit(main())
