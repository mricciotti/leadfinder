import sqlite3

STATUSES = ("novo", "contatado", "respondeu", "fechado", "descartado")

_STATUSES_SQL = ", ".join(f"'{status}'" for status in STATUSES)

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS leads (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    segment TEXT NOT NULL,
    neighborhood TEXT NOT NULL,
    phone TEXT,
    address TEXT,
    instagram TEXT,
    lat REAL,
    lon REAL,
    score INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'novo' CHECK (status IN ({_STATUSES_SQL})),
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

INSERT_SQL = """
INSERT OR IGNORE INTO leads
    (id, name, segment, neighborhood, phone, address, instagram, lat, lon, score)
VALUES
    (:id, :name, :segment, :neighborhood, :phone, :address, :instagram, :lat, :lon, :score)
"""


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    return conn


def add_leads(conn, leads):
    before = conn.total_changes
    conn.executemany(INSERT_SQL, leads)
    conn.commit()
    return conn.total_changes - before


def list_leads(conn):
    rows = conn.execute(
        "SELECT * FROM leads ORDER BY score DESC, name COLLATE NOCASE"
    ).fetchall()
    return [dict(row) for row in rows]


def update_lead(conn, lead_id, status=None, notes=None):
    fields = {
        key: value
        for key, value in (("status", status), ("notes", notes))
        if value is not None
    }
    if fields:
        assignments = ", ".join(f"{key} = ?" for key in fields)
        conn.execute(
            f"UPDATE leads SET {assignments} WHERE id = ?",
            (*fields.values(), lead_id),
        )
        conn.commit()
    row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    return dict(row) if row else None
