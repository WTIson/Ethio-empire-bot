import sqlite3
from contextlib import contextmanager
from datetime import date

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id       INTEGER PRIMARY KEY,
    username      TEXT,
    name          TEXT,
    age           INTEGER,
    gender        TEXT,          -- 'male' / 'female' / 'other'
    looking_for   TEXT,          -- 'male' / 'female' / 'any'
    bio           TEXT,
    city          TEXT,
    photo_file_id TEXT,
    photo_status  TEXT DEFAULT 'none',  -- none / pending / approved / rejected
    banned        INTEGER DEFAULT 0,
    is_premium    INTEGER DEFAULT 0,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS swipes (
    from_id     INTEGER,
    to_id       INTEGER,
    action      TEXT,        -- 'like' / 'pass'
    created_at  TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (from_id, to_id)
);

CREATE TABLE IF NOT EXISTS matches (
    user1       INTEGER,
    user2       INTEGER,
    created_at  TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (user1, user2)
);

CREATE TABLE IF NOT EXISTS reports (
    reporter_id INTEGER,
    target_id   INTEGER,
    reason      TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


# ---------- users ----------

def upsert_user_field(user_id: int, **fields):
    with get_conn() as conn:
        exists = conn.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not exists:
            conn.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        for key, value in fields.items():
            conn.execute(f"UPDATE users SET {key}=? WHERE user_id=?", (value, user_id))


def get_user(user_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()


def set_photo_status(user_id: int, status: str):
    upsert_user_field(user_id, photo_status=status)


def ban_user(user_id: int):
    upsert_user_field(user_id, banned=1)


def is_profile_complete(user_id: int) -> bool:
    u = get_user(user_id)
    if not u:
        return False
    required = ["name", "age", "gender", "looking_for", "bio", "city", "photo_file_id"]
    return all(u[field] is not None for field in required)


# ---------- swiping ----------

def record_swipe(from_id: int, to_id: int, action: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO swipes (from_id, to_id, action) VALUES (?, ?, ?)",
            (from_id, to_id, action),
        )


def has_swiped(from_id: int, to_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM swipes WHERE from_id=? AND to_id=?", (from_id, to_id)
        ).fetchone()
        return row is not None


def likes_today(user_id: int) -> int:
    today = date.today().isoformat()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as c FROM swipes WHERE from_id=? AND action='like' AND date(created_at)=?",
            (user_id, today),
        ).fetchone()
        return row["c"]


def mutual_like_exists(a: int, b: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM swipes WHERE from_id=? AND to_id=? AND action='like'", (b, a)
        ).fetchone()
        return row is not None


def create_match(a: int, b: int):
    user1, user2 = sorted([a, b])
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO matches (user1, user2) VALUES (?, ?)", (user1, user2)
        )


def next_candidate(user_id: int):
    """Return the next profile the user hasn't swiped on yet, matching preference."""
    me = get_user(user_id)
    if not me:
        return None

    looking_for = me["looking_for"]
    gender_filter = "" if looking_for == "any" else "AND u.gender = :looking_for"

    query = f"""
        SELECT u.* FROM users u
        WHERE u.user_id != :me
          AND u.banned = 0
          AND u.photo_status = 'approved'
          {gender_filter}
          AND u.user_id NOT IN (
              SELECT to_id FROM swipes WHERE from_id = :me
          )
        ORDER BY RANDOM()
        LIMIT 1
    """
    with get_conn() as conn:
        row = conn.execute(query, {"me": user_id, "looking_for": looking_for}).fetchone()
        return row


# ---------- reports ----------

def add_report(reporter_id: int, target_id: int, reason: str = ""):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO reports (reporter_id, target_id, reason) VALUES (?, ?, ?)",
            (reporter_id, target_id, reason),
        )
