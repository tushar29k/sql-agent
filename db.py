"""Seeded e-commerce SQLite dataset: customers, products, orders.

Deterministic seed: the same rows every run, so the eval golden set
has stable expected answers. Created fresh on import if missing.
"""
import os
import random
import sqlite3
from datetime import date, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "shop.db")

CUSTOMERS = [
    ("Aarav Mehta", "Bengaluru"), ("Diya Nair", "Kochi"),
    ("Rohan Iyer", "Chennai"), ("Priya Sharma", "Delhi"),
    ("Kabir Singh", "Mumbai"), ("Anaya Rao", "Hyderabad"),
    ("Vikram Patel", "Ahmedabad"), ("Isha Verma", "Pune"),
    ("Arjun Menon", "Kochi"), ("Sara Khan", "Delhi"),
    ("Nikhil Bose", "Kolkata"), ("Tara Reddy", "Hyderabad"),
]

PRODUCTS = [
    ("Wireless mouse", "Electronics", 899.0),
    ("Mechanical keyboard", "Electronics", 3499.0),
    ("USB-C hub", "Electronics", 1299.0),
    ("Notebook set", "Stationery", 299.0),
    ("Fountain pen", "Stationery", 1499.0),
    ("Desk lamp", "Home", 1099.0),
    ("Coffee mug", "Home", 349.0),
    ("Running shoes", "Sports", 2499.0),
    ("Yoga mat", "Sports", 799.0),
    ("Water bottle", "Sports", 499.0),
    ("Bluetooth speaker", "Electronics", 1999.0),
    ("Backpack", "Travel", 1799.0),
]


def seed(db_path=DB_PATH):
    if os.path.exists(db_path):
        return db_path
    rng = random.Random(42)  # fixed seed — same rows forever
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.executescript("""
        CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, city TEXT);
        CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT,
                               category TEXT, price REAL);
        CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER,
                             order_date TEXT,
                             FOREIGN KEY (customer_id) REFERENCES customers(id));
        CREATE TABLE order_items (order_id INTEGER, product_id INTEGER,
                                  quantity INTEGER,
                                  FOREIGN KEY (order_id) REFERENCES orders(id),
                                  FOREIGN KEY (product_id) REFERENCES products(id));
    """)
    cur.executemany("INSERT INTO customers (name, city) VALUES (?, ?)",
                    CUSTOMERS)
    cur.executemany("INSERT INTO products (name, category, price) VALUES (?, ?, ?)",
                    PRODUCTS)
    oid = 1
    start = date(2026, 1, 1)
    for day in range(120):  # four months of orders
        for _ in range(rng.randint(0, 2)):
            cid = rng.randint(1, len(CUSTOMERS))
            d = (start + timedelta(days=day)).isoformat()
            cur.execute("INSERT INTO orders (customer_id, order_date) VALUES (?, ?)",
                        (cid, d))
            for _ in range(rng.randint(1, 3)):
                cur.execute("INSERT INTO order_items VALUES (?, ?, ?)",
                            (oid, rng.randint(1, len(PRODUCTS)),
                             rng.randint(1, 3)))
            oid += 1
    con.commit()
    con.close()
    return db_path


def connect(db_path=DB_PATH):
    seed(db_path)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


def schema_summary(db_path=DB_PATH):
    con = connect(db_path)
    out = {}
    for (name,) in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"):
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({name})")]
        out[name] = cols
    con.close()
    return out
