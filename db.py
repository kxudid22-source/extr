import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "messenger888.db")

def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,            -- telegram user id
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        balance INTEGER DEFAULT 0,
        is_admin INTEGER DEFAULT 0,
        created_at TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS numbers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        number TEXT UNIQUE,
        owner_id INTEGER,
        price INTEGER DEFAULT 0,
        status TEXT DEFAULT 'available',  -- available / sold
        purchased_at TEXT,
        FOREIGN KEY(owner_id) REFERENCES users(id)
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        description TEXT,
        price INTEGER,
        price_stars INTEGER DEFAULT 50,
        stock INTEGER DEFAULT 0,
        category TEXT
    )
    """)
    # migration: add price_stars
    try:
        c.execute("ALTER TABLE products ADD COLUMN price_stars INTEGER DEFAULT 50")
    except Exception:
        pass
    try:
        c.execute("ALTER TABLE numbers ADD COLUMN price_stars INTEGER DEFAULT 75")
    except Exception:
        pass
    c.execute("""
    CREATE TABLE IF NOT EXISTS purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER,
        price INTEGER,
        purchased_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(product_id) REFERENCES products(id)
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id INTEGER,
        username TEXT UNIQUE,
        display_name TEXT,
        bio TEXT,
        created_at TEXT,
        FOREIGN KEY(owner_id) REFERENCES users(id)
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS friends (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        friend_id INTEGER,
        status TEXT DEFAULT 'pending',  -- pending / accepted / rejected
        created_at TEXT,
        UNIQUE(user_id, friend_id)
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_id INTEGER,
        to_id INTEGER,
        text TEXT,
        created_at TEXT,
        read INTEGER DEFAULT 0
    )
    """)
    # migration: last_seen
    try:
        c.execute("ALTER TABLE users ADD COLUMN last_seen TEXT")
    except Exception:
        pass
    c.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    conn.commit()

    # seed products
    c.execute("SELECT COUNT(*) FROM products")
    if c.fetchone()[0] == 0:
        seed = [
            ("VIP статус", "Золотой значок и приоритет в поиске", 500, 100, 999, "status"),
            ("Премиум аватар", "Уникальная рамка для аватара", 200, 50, 999, "cosmetic"),
            ("Буст аккаунта", "Поднимает аккаунт в топе поиска на 7 дней", 300, 75, 999, "boost"),
            ("Стикер-пак", "Набор эксклюзивных стикеров", 150, 50, 999, "cosmetic"),
            ("Номер +888 (рандом)", "Случайный номер +888 для мессенджера", 100, 80, 999, "number"),
        ]
        c.executemany("INSERT INTO products(name,description,price,price_stars,stock,category) VALUES (?,?,?,?,?,?)", seed)
        conn.commit()

    # seed +888 numbers
    c.execute("SELECT COUNT(*) FROM numbers WHERE number LIKE '+888%'")
    if c.fetchone()[0] == 0:
        import random
        for _ in range(50):
            num = "+888" + "".join(str(random.randint(0,9)) for _ in range(9))
            c.execute("INSERT OR IGNORE INTO numbers(number,price,price_stars,status) VALUES (?,?,?,?)", (num, 100, 75, "available"))
        conn.commit()
    # seed +39 numbers (free)
    c.execute("SELECT COUNT(*) FROM numbers WHERE number LIKE '+39%'")
    if c.fetchone()[0] == 0:
        import random
        for _ in range(100):
            num = "+39" + "".join(str(random.randint(0,9)) for _ in range(9))
            c.execute("INSERT OR IGNORE INTO numbers(number,price,price_stars,status) VALUES (?,?,?,?)", (num, 0, 0, "available"))
        conn.commit()
    conn.close()

def now():
    return datetime.utcnow().isoformat()

def get_setting(key, default=None):
    conn = get_conn()
    r = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return r["value"] if r else default

def set_setting(key, value):
    conn = get_conn()
    conn.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    conn.commit()
    conn.close()
