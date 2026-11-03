import json
import sqlite3
from contextlib import closing
from datetime import datetime

import contacts

STATUSES = ("novo", "contatado", "respondeu", "fechado", "descartado")
SOURCE_SITE_STATES = ("nao_verificado", "sem_site_na_fonte", "so_rede_social", "site_informado")
SITE_STATES = (
    *SOURCE_SITE_STATES,
    "site_ok",
    "site_com_problemas",
    "site_inacessivel",
    "ausencia_confirmada",
)
SAME_PLACE_DEGREES = 0.0005
MANUAL_FIELDS = ("manual_phone", "manual_whatsapp", "manual_instagram", "manual_website")
EDITABLE = ("status", "notes", "favorite", *MANUAL_FIELDS)


def sql_list(values):
    return ", ".join(f"'{value}'" for value in values)


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
    status TEXT NOT NULL DEFAULT 'novo' CHECK (status IN ({sql_list(STATUSES)})),
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

PRESENCE_COLUMNS = (
    "phone_national TEXT",
    "phone_kind TEXT",
    "city TEXT",
    "uf TEXT",
    "email TEXT",
    "email_kind TEXT",
    "facebook TEXT",
    "other_links TEXT NOT NULL DEFAULT '[]'",
    "website TEXT",
    f"site_state TEXT NOT NULL DEFAULT 'nao_verificado' CHECK (site_state IN ({sql_list(SITE_STATES)}))",
    "source TEXT NOT NULL DEFAULT 'osm'",
    "source_seen_at TEXT",
    "checked_at TEXT",
    "check_result TEXT",
    "favorite INTEGER NOT NULL DEFAULT 0 CHECK (favorite IN (0, 1))",
)

UPSERT_SQL = f"""
INSERT INTO leads (
    id, name, segment, neighborhood, phone, phone_national, phone_kind, address,
    city, uf, email, instagram, facebook, other_links, website, site_state,
    lat, lon, score, source_seen_at
) VALUES (
    :id, :name, :segment, :neighborhood, :phone, :phone_national, :phone_kind, :address,
    :city, :uf, :email, :instagram, :facebook, :other_links, :website, :site_state,
    :lat, :lon, :score, CURRENT_TIMESTAMP
)
ON CONFLICT (id) DO UPDATE SET
    name = excluded.name,
    phone = COALESCE(excluded.phone, leads.phone),
    phone_national = COALESCE(excluded.phone_national, leads.phone_national),
    phone_kind = COALESCE(excluded.phone_kind, leads.phone_kind),
    address = COALESCE(excluded.address, leads.address),
    city = COALESCE(excluded.city, leads.city),
    uf = COALESCE(excluded.uf, leads.uf),
    email = COALESCE(excluded.email, leads.email),
    instagram = COALESCE(excluded.instagram, leads.instagram),
    facebook = COALESCE(excluded.facebook, leads.facebook),
    other_links = CASE WHEN excluded.other_links <> '[]'
        THEN excluded.other_links ELSE leads.other_links END,
    website = excluded.website,
    site_state = CASE
        WHEN leads.site_state IN ({sql_list(SOURCE_SITE_STATES)})
            OR leads.website IS NOT excluded.website
        THEN excluded.site_state ELSE leads.site_state END,
    absence_confirmed_at = CASE WHEN leads.website IS NOT excluded.website
        THEN NULL ELSE leads.absence_confirmed_at END,
    lat = excluded.lat,
    lon = excluded.lon,
    score = excluded.score,
    source_seen_at = CURRENT_TIMESTAMP
WHERE leads.status <> 'descartado'
"""


def add_presence_columns(conn):
    for column in PRESENCE_COLUMNS:
        conn.execute(f"ALTER TABLE leads ADD COLUMN {column}")
    conn.execute("UPDATE leads SET source_seen_at = created_at")
    rows = conn.execute("SELECT id, phone FROM leads WHERE phone IS NOT NULL").fetchall()
    for row in rows:
        conn.execute(
            "UPDATE leads SET phone_national = ?, phone_kind = ? WHERE id = ?",
            (*contacts.normalize_phone(row["phone"]), row["id"]),
        )


def add_manual_check(conn):
    for column in (*MANUAL_FIELDS, "manual_checked_at", "absence_confirmed_at"):
        conn.execute(f"ALTER TABLE leads ADD COLUMN {column} TEXT")
    conn.execute(
        """
        CREATE TABLE status_changes (
            id INTEGER PRIMARY KEY,
            lead_id TEXT NOT NULL REFERENCES leads (id),
            status TEXT NOT NULL,
            changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


MIGRATIONS = (add_presence_columns, add_manual_check)


def schema_version(conn):
    return conn.execute("PRAGMA user_version").fetchone()[0]


def backup(conn, path):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    with closing(sqlite3.connect(f"{path}.bak-{stamp}")) as target:
        conn.backup(target)


def migrate(conn, path):
    if schema_version(conn) == len(MIGRATIONS):
        return
    has_leads = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'leads'"
    ).fetchone()
    if has_leads:
        backup(conn, path)
    conn.execute("BEGIN IMMEDIATE")
    conn.execute(SCHEMA)
    version = schema_version(conn)
    for migration in MIGRATIONS[version:]:
        migration(conn)
    conn.execute(f"PRAGMA user_version = {len(MIGRATIONS)}")
    conn.commit()


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    migrate(conn, path)
    return conn


def to_lead(row):
    lead = dict(row)
    lead["other_links"] = json.loads(lead["other_links"])
    if lead["manual_phone"]:
        lead["phone"] = contacts.format_phone(lead["manual_phone"])
        lead["phone_national"], lead["phone_kind"] = contacts.normalize_phone(lead["manual_phone"])
    if lead["manual_instagram"]:
        lead["instagram"] = lead["manual_instagram"]
    if lead["manual_website"] and lead["manual_website"] != lead["website"]:
        lead["website"] = lead["manual_website"]
        lead["site_state"] = "site_informado"
    if lead["absence_confirmed_at"]:
        lead["site_state"] = "ausencia_confirmada"
    return lead


def is_known(conn, lead_id):
    return conn.execute("SELECT 1 FROM leads WHERE id = ?", (lead_id,)).fetchone()


def same_place_elsewhere(conn, lead):
    if lead["lat"] is None or lead["lon"] is None:
        return False
    kind = lead["id"].split("-")[0]
    nearby = conn.execute(
        "SELECT id, name FROM leads WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?",
        (
            lead["lat"] - SAME_PLACE_DEGREES,
            lead["lat"] + SAME_PLACE_DEGREES,
            lead["lon"] - SAME_PLACE_DEGREES,
            lead["lon"] + SAME_PLACE_DEGREES,
        ),
    ).fetchall()
    return any(
        row["id"].split("-")[0] != kind
        and contacts.text_key(row["name"]) == contacts.text_key(lead["name"])
        for row in nearby
    )


def add_leads(conn, leads):
    before = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    for lead in leads:
        if not is_known(conn, lead["id"]) and same_place_elsewhere(conn, lead):
            continue
        conn.execute(UPSERT_SQL, {**lead, "other_links": json.dumps(lead["other_links"])})
    conn.commit()
    return conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0] - before


def list_leads(conn):
    rows = conn.execute(
        "SELECT * FROM leads ORDER BY score DESC, name COLLATE NOCASE"
    ).fetchall()
    return [to_lead(row) for row in rows]


def update_lead(conn, lead_id, **changes):
    absence = changes.pop("absence_confirmed", None)
    unknown = set(changes) - set(EDITABLE)
    if unknown:
        raise ValueError(f"Campos desconhecidos: {sorted(unknown)}")
    current = conn.execute("SELECT status FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if current is None:
        return None
    values = dict(changes)
    stamped = []
    if absence is True:
        values["manual_website"] = None
        stamped.append("absence_confirmed_at")
    elif absence is False or values.get("manual_website"):
        values["absence_confirmed_at"] = None
    if absence is not None or any(key in changes for key in MANUAL_FIELDS):
        stamped.append("manual_checked_at")
    assignments = [f"{key} = ?" for key in values] + [
        f"{key} = CURRENT_TIMESTAMP" for key in stamped
    ]
    if assignments:
        conn.execute(
            f"UPDATE leads SET {', '.join(assignments)} WHERE id = ?",
            (*values.values(), lead_id),
        )
    if changes.get("status", current["status"]) != current["status"]:
        conn.execute(
            "INSERT INTO status_changes (lead_id, status) VALUES (?, ?)",
            (lead_id, changes["status"]),
        )
    conn.commit()
    row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    return to_lead(row)
