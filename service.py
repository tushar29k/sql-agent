"""Thin HTTP wrapper around the SQL agent.

  POST /ask     {question} -> SQL + rows + full attempt trace
  GET  /schema   the live schema the agent repairs against
  GET  /samples  seed questions (incl. ones that force a correction)
  GET  /health, /info

There's also a deterministic "broken SQL" demo: asking
  'how many orders did CUSTOMER place' (singular table, bad column)
makes the mock brain emit `FROM customer o JOIN ... o.amount` so the UI
can show the corrector repairing it live. Deterministic on purpose:
a demo of the repair loop must not depend on the model having a bad day.
"""
import os as _os

from fastapi import FastAPI
from fastapi.responses import FileResponse as _FileResponse

import db as dbmod
from agent import SQLAgent, make_brain

agent = SQLAgent(brain=make_brain())
app = FastAPI(title="sql-agent")

SAMPLES = [
    "total revenue by month",
    "top 3 products by revenue",
    "what is the average order value",
    "top 5 customers by spend",
    "orders over 5000",
    "list the customers from kochi",
    "how many orders did CUSTOMER place (broken SQL demo)",
]


@app.post("/ask")
def ask(body: dict):
    q = body["question"]
    approve = bool(body.get("approve_destructive"))
    if "(broken SQL demo)" in q:
        # hand the corrector genuinely broken SQL (bad table + bad column)
        bad = ("SELECT COUNT(*) AS orders FROM customer c "
               "JOIN orders o ON o.customer_id = c.id")
        orig = agent.brain.sql
        agent.brain.sql = lambda question, schema, error_context="": bad
        try:
            out = agent.ask(q)
        finally:
            agent.brain.sql = orig
        return out
    return agent.ask(q, approve_destructive=approve)


@app.get("/schema")
def schema():
    return dbmod.schema_summary()


@app.get("/samples")
def samples():
    return {"samples": SAMPLES}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/info")
def info():
    real = type(agent.brain).__name__ == "FreeBrain"
    return {"real_llm": real,
            "provider": agent.brain.client.label if real else None,
            "backend": type(agent.brain).__name__}

_UI_INDEX = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                          "ui", "index.html")


@app.get("/", include_in_schema=False)
def _demo_ui():
    return _FileResponse(_UI_INDEX)
