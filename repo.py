import sqlite3
import os
from db import get_conn, now

def upsert_user(tg_id, username=None, first_name=None, last_name=None):
    conn = get_conn()
    existing = conn.execute("SELECT id FROM users WHERE id=?", (tg_id,)).fetchone()
    if existing:
        conn.execute("""
            UPDATE users SET username=?, first_name=?, last_name=? WHERE id=?
        """, (username, first_name, last_name, tg_id))
    else:
        conn.execute("""
            INSERT INTO users(id, username, first_name, last_name, balance, created_at)
            VALUES (?,?,?,?,0,?)
        """, (tg_id, username, first_name, last_name, now()))
    conn.commit()
    conn.close()

def get_user(tg_id):
    conn = get_conn()
    r = conn.execute("SELECT * FROM users WHERE id=?", (tg_id,)).fetchone()
    conn.close()
    return dict(r) if r else None

def add_balance(tg_id, amount):
    conn = get_conn()
    conn.execute("UPDATE users SET balance=balance+? WHERE id=?", (amount, tg_id))
    conn.commit()
    conn.close()

def buy_number(user_id, number_id=None):
    conn = get_conn()
    if number_id is None:
        row = conn.execute("SELECT * FROM numbers WHERE status='available' AND number LIKE '+888%' ORDER BY RANDOM() LIMIT 1").fetchone()
    else:
        row = conn.execute("SELECT * FROM numbers WHERE id=? AND status='available' AND number LIKE '+888%'", (number_id,)).fetchone()
    if not row:
        conn.close()
        return None
    conn.execute("UPDATE numbers SET status='sold', owner_id=?, purchased_at=? WHERE id=?", (user_id, now(), row["id"]))
    conn.commit()
    conn.close()
    return dict(row)

def get_free_number(user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM numbers WHERE status='available' AND number LIKE '+39%' ORDER BY RANDOM() LIMIT 1").fetchone()
    if not row:
        conn.close()
        return None
    conn.execute("UPDATE numbers SET status='sold', owner_id=?, purchased_at=? WHERE id=?", (user_id, now(), row["id"]))
    conn.commit()
    conn.close()
    return dict(row)

def issue_product(user_id, product_id):
    conn = get_conn()
    prod = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not prod:
        conn.close()
        return None
    conn.execute("UPDATE products SET stock=stock-1 WHERE id=?", (product_id,))
    conn.execute("INSERT INTO purchases(user_id,product_id,price,purchased_at) VALUES(?,?,?,?)", (user_id, product_id, 0, now()))
    issued_number = None
    if prod["category"] == "number":
        num_row = conn.execute("SELECT * FROM numbers WHERE status='available' AND number LIKE '+888%' ORDER BY RANDOM() LIMIT 1").fetchone()
        if num_row:
            conn.execute("UPDATE numbers SET status='sold', owner_id=?, purchased_at=? WHERE id=?", (user_id, now(), num_row["id"]))
            issued_number = num_row["number"]
    conn.commit()
    conn.close()
    result = dict(prod)
    if issued_number:
        result["issued_number"] = issued_number
    return result

def issue_number(user_id, prefix="+888"):
    conn = get_conn()
    row = conn.execute("SELECT * FROM numbers WHERE status='available' AND number LIKE ? ORDER BY RANDOM() LIMIT 1", (prefix+"%",)).fetchone()
    if not row:
        import random
        number = prefix + "".join(str(random.randint(0,9)) for _ in range(9))
        conn.execute("INSERT INTO numbers(number,owner_id,status,purchased_at,price) VALUES (?,?,?,?,?)", (number, user_id, "sold", now(), 0))
        conn.commit()
        conn.close()
        return {"number": number, "owner_id": user_id}
    conn.execute("UPDATE numbers SET status='sold', owner_id=?, purchased_at=? WHERE id=?", (user_id, now(), row["id"]))
    conn.commit()
    conn.close()
    return dict(row)

def is_admin(user_id):
    admin_ids = os.getenv("ADMIN_IDS", os.getenv("ADMIN_ID", "")).split(",")
    admin_ids = [x.strip() for x in admin_ids if x.strip()]
    if str(user_id) in admin_ids:
        return True
    u = get_user(user_id)
    return bool(u and u.get("is_admin"))

def get_user_numbers(user_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM numbers WHERE owner_id=?", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_products():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM products ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def buy_product(user_id, product_id):
    conn = get_conn()
    prod = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    if not prod or prod["stock"] <= 0:
        conn.close()
        return None, "out_of_stock"
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not user or user["balance"] < prod["price"]:
        conn.close()
        return None, "no_balance"
    # deduct
    conn.execute("UPDATE users SET balance=balance-? WHERE id=?", (prod["price"], user_id))
    conn.execute("UPDATE products SET stock=stock-1 WHERE id=?", (product_id,))
    conn.execute("INSERT INTO purchases(user_id,product_id,price,purchased_at) VALUES(?,?,?,?)",
                (user_id, product_id, prod["price"], now()))
    # if number product, issue a number
    if prod["category"] == "number":
        num_row = conn.execute("SELECT * FROM numbers WHERE status='available' ORDER BY RANDOM() LIMIT 1").fetchone()
        if num_row:
            conn.execute("UPDATE numbers SET status='sold', owner_id=?, purchased_at=? WHERE id=?", (user_id, now(), num_row["id"]))
    conn.commit()
    conn.close()
    return dict(prod), "ok"

def ensure_account(user_id, username, display_name=None, bio=None):
    conn = get_conn()
    existing = conn.execute("SELECT * FROM accounts WHERE owner_id=?", (user_id,)).fetchone()
    if existing:
        conn.execute("UPDATE accounts SET username=?, display_name=?, bio=? WHERE owner_id=?",
                    (username, display_name or username, bio, user_id))
    else:
        conn.execute("INSERT INTO accounts(owner_id,username,display_name,bio,created_at) VALUES(?,?,?,?,?)",
                    (user_id, username, display_name or username, bio, now()))
    conn.commit()
    conn.close()

def search_accounts(q):
    conn = get_conn()
    like = f"%{q}%"
    rows = conn.execute("SELECT a.*, u.first_name FROM accounts a LEFT JOIN users u ON u.id=a.owner_id WHERE a.username LIKE ? OR a.display_name LIKE ? LIMIT 50", (like, like)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_account_by_user(user_id):
    conn = get_conn()
    r = conn.execute("SELECT * FROM accounts WHERE owner_id=?", (user_id,)).fetchone()
    conn.close()
    return dict(r) if r else None

def send_friend_request(user_id, friend_user_id):
    if user_id == friend_user_id:
        return False, "self"
    conn = get_conn()
    try:
        conn.execute("INSERT INTO friends(user_id,friend_id,status,created_at) VALUES(?,?,?,?)",
                    (user_id, friend_user_id, "pending", now()))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return False, "exists"
    conn.close()
    return True, "ok"

def respond_friend(req_id, accept):
    conn = get_conn()
    status = "accepted" if accept else "rejected"
    conn.execute("UPDATE friends SET status=? WHERE id=?", (status, req_id))
    if accept:
        row = conn.execute("SELECT user_id,friend_id FROM friends WHERE id=?", (req_id,)).fetchone()
        if row:
            # mirror
            try:
                conn.execute("INSERT INTO friends(user_id,friend_id,status,created_at) VALUES(?,?,?,?)",
                            (row["friend_id"], row["user_id"], "accepted", now()))
            except sqlite3.IntegrityError:
                conn.execute("UPDATE friends SET status='accepted' WHERE user_id=? AND friend_id=?", (row["friend_id"], row["user_id"]))
    conn.commit()
    conn.close()

def get_friends(user_id):
    conn = get_conn()
    rows = conn.execute("""
        SELECT f.*, u.username, u.first_name FROM friends f
        LEFT JOIN users u ON u.id=f.friend_id
        WHERE f.user_id=? AND f.status='accepted'
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_pending_requests(user_id):
    conn = get_conn()
    rows = conn.execute("""
        SELECT f.*, u.username, u.first_name FROM friends f
        LEFT JOIN users u ON u.id=f.user_id
        WHERE f.friend_id=? AND f.status='pending'
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_last_seen(user_id):
    conn = get_conn()
    conn.execute("UPDATE users SET last_seen=? WHERE id=?", (now(), user_id))
    conn.commit()
    conn.close()

def is_online(user_id, threshold_seconds=120):
    u = get_user(user_id)
    if not u or not u.get("last_seen"):
        return False
    from datetime import datetime, timedelta
    try:
        ls = datetime.fromisoformat(u["last_seen"])
    except Exception:
        return False
    return (datetime.utcnow() - ls).total_seconds() < threshold_seconds

def send_message(from_id, to_id, text):
    conn = get_conn()
    conn.execute("INSERT INTO messages(from_id,to_id,text,created_at) VALUES (?,?,?,?)", (from_id, to_id, text, now()))
    conn.commit()
    conn.close()

def get_messages(user_id, peer_id, since_id=0):
    conn = get_conn()
    rows = conn.execute("""
        SELECT m.*, u.first_name, u.username FROM messages m
        LEFT JOIN users u ON u.id=m.from_id
        WHERE ((m.from_id=? AND m.to_id=?) OR (m.from_id=? AND m.to_id=?)) AND m.id > ?
        ORDER BY m.id ASC
    """, (user_id, peer_id, peer_id, user_id, since_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_conversations(user_id):
    conn = get_conn()
    rows = conn.execute("""
        SELECT DISTINCT CASE WHEN from_id=? THEN to_id ELSE from_id END as peer_id
        FROM messages WHERE from_id=? OR to_id=?
    """, (user_id, user_id, user_id)).fetchall()
    peers = [r["peer_id"] for r in rows]
    result = []
    for pid in peers:
        u = get_user(pid)
        last = conn.execute("""
            SELECT text, created_at FROM messages
            WHERE (from_id=? AND to_id=?) OR (from_id=? AND to_id=?)
            ORDER BY id DESC LIMIT 1
        """, (user_id, pid, pid, user_id)).fetchone()
        result.append({
            "peer_id": pid,
            "first_name": u.get("first_name") if u else None,
            "username": u.get("username") if u else None,
            "online": is_online(pid),
            "last_text": last["text"] if last else None,
            "last_time": last["created_at"] if last else None,
        })
    conn.close()
    return result

def mark_read(user_id, peer_id):
    conn = get_conn()
    conn.execute("UPDATE messages SET read=1 WHERE to_id=? AND from_id=?", (user_id, peer_id))
    conn.commit()
    conn.close()

def get_unread_count(user_id):
    conn = get_conn()
    c = conn.execute("SELECT COUNT(*) FROM messages WHERE to_id=? AND read=0", (user_id,)).fetchone()[0]
    conn.close()
    return c

def set_admin(user_id, value=1):
    conn = get_conn()
    repo_upsert = None
    conn.execute("UPDATE users SET is_admin=? WHERE id=?", (value, user_id))
    conn.commit()
    conn.close()

def get_all_users(limit=50):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_stats():
    conn = get_conn()
    users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    numbers = conn.execute("SELECT COUNT(*) FROM numbers").fetchone()[0]
    sold = conn.execute("SELECT COUNT(*) FROM numbers WHERE status='sold'").fetchone()[0]
    products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    conn.close()
    return {"users": users, "numbers": numbers, "sold_numbers": sold, "products": products}
