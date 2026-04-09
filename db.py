import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "bookstore.db")


def get_connection():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = get_connection()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            price REAL NOT NULL,
            original_price REAL,
            images TEXT,
            category TEXT,
            trending INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            total REAL NOT NULL,
            address TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Pending'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL
        )
    """)

    # ---- old schema fix ----
    cur.execute("PRAGMA table_info(orders)")
    columns = [row[1] for row in cur.fetchall()]

    if "address" not in columns:
        cur.execute("ALTER TABLE orders ADD COLUMN address TEXT NOT NULL DEFAULT ''")

    if "phone" not in columns:
        cur.execute("ALTER TABLE orders ADD COLUMN phone TEXT NOT NULL DEFAULT ''")

    if "status" not in columns:
        cur.execute("ALTER TABLE orders ADD COLUMN status TEXT NOT NULL DEFAULT 'Pending'")

    con.commit()

    cur.execute("SELECT COUNT(*) FROM books")
    books_count = cur.fetchone()[0]

    if books_count == 0:
        sample_books = [
            ("Atomic Habits", "James Clear", 399, 499, "photo.png", "Self Help", 1),
            ("Deep Work", "Cal Newport", 349, 449, "Screenshot_1.png", "Productivity", 1),
            ("The Alchemist", "Paulo Coelho", 299, 399, "Screenshot_2.png", "Fiction", 0),
        ]

        cur.executemany("""
            INSERT INTO books (title, author, price, original_price, images, category, trending)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, sample_books)

        con.commit()

    con.close()