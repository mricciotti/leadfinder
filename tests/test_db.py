import sqlite3
from contextlib import closing

import pytest

import db

OLD_SCHEMA = """
CREATE TABLE leads (
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
    status TEXT NOT NULL DEFAULT 'novo' CHECK (status IN ('novo', 'contatado', 'respondeu', 'fechado', 'descartado')),
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


@pytest.fixture
def conn(tmp_path):
    connection = db.connect(tmp_path / "test.db")
    yield connection
    connection.close()


@pytest.fixture
def old_db(tmp_path):
    path = tmp_path / "old.db"
    with closing(sqlite3.connect(path)) as old:
        old.execute(OLD_SCHEMA)
        old.execute(
            "INSERT INTO leads (id, name, segment, neighborhood, phone, score, status, notes, created_at)"
            " VALUES ('node-5', 'Cantina Velha', 'restaurante', 'Mooca', '+55 11 98888-7777', 4,"
            " 'contatado', 'Ligar de novo', '2026-10-21 12:00:00')"
        )
        old.commit()
    return path


def lead(lead_id="node-1", **overrides):
    base = {
        "id": lead_id,
        "name": "Lugar",
        "segment": "restaurante",
        "neighborhood": "Pinheiros",
        "phone": None,
        "phone_national": None,
        "phone_kind": None,
        "address": None,
        "city": "São Paulo",
        "uf": "SP",
        "email": None,
        "instagram": None,
        "facebook": None,
        "other_links": [],
        "website": None,
        "site_state": "sem_site_na_fonte",
        "lat": -23.56,
        "lon": -46.69,
        "score": 0,
    }
    base.update(overrides)
    return base


def test_add_leads_returns_how_many_were_new(conn):
    added = db.add_leads(conn, [lead("node-1"), lead("node-2")])

    assert added == 2
    assert len(db.list_leads(conn)) == 2


def test_new_leads_start_as_novo_with_empty_notes(conn):
    db.add_leads(conn, [lead()])

    saved = db.list_leads(conn)[0]

    assert saved["status"] == "novo"
    assert saved["notes"] == ""
    assert saved["favorite"] == 0
    assert saved["source"] == "osm"
    assert saved["source_seen_at"]


def test_adding_the_same_lead_again_keeps_status_and_notes(conn):
    db.add_leads(conn, [lead()])
    db.update_lead(conn, "node-1", status="contatado", notes="Falei com o dono")

    added = db.add_leads(conn, [lead(score=5)])

    saved = db.list_leads(conn)[0]
    assert added == 0
    assert saved["status"] == "contatado"
    assert saved["notes"] == "Falei com o dono"
    assert len(db.list_leads(conn)) == 1


def test_reimport_updates_data_from_the_map(conn):
    db.add_leads(conn, [lead()])
    conn.execute("UPDATE leads SET favorite = 1")

    db.add_leads(
        conn,
        [
            lead(
                name="Lugar Novo",
                phone="+55 11 3815-2600",
                website="https://lugar.com.br",
                site_state="site_informado",
                other_links=["https://linktr.ee/lugar"],
                score=3,
            )
        ],
    )

    saved = db.list_leads(conn)[0]
    assert saved["name"] == "Lugar Novo"
    assert saved["phone"] == "+55 11 3815-2600"
    assert saved["website"] == "https://lugar.com.br"
    assert saved["site_state"] == "site_informado"
    assert saved["other_links"] == ["https://linktr.ee/lugar"]
    assert saved["score"] == 3
    assert saved["favorite"] == 1


def test_reimport_without_a_contact_keeps_the_known_one(conn):
    db.add_leads(conn, [lead(phone="+55 11 3815-2600", email="oi@lugar.com.br")])

    db.add_leads(conn, [lead()])

    saved = db.list_leads(conn)[0]
    assert saved["phone"] == "+55 11 3815-2600"
    assert saved["email"] == "oi@lugar.com.br"


def test_reimport_keeps_a_verified_site_state_while_the_site_is_the_same(conn):
    db.add_leads(conn, [lead()])
    conn.execute("UPDATE leads SET site_state = 'ausencia_confirmada'")

    db.add_leads(conn, [lead()])

    assert db.list_leads(conn)[0]["site_state"] == "ausencia_confirmada"


def test_reimport_resets_a_verified_site_state_when_the_site_changes(conn):
    db.add_leads(conn, [lead()])
    conn.execute("UPDATE leads SET site_state = 'ausencia_confirmada'")

    db.add_leads(
        conn, [lead(website="https://lugar.com.br", site_state="site_informado")]
    )

    assert db.list_leads(conn)[0]["site_state"] == "site_informado"


def test_reimport_leaves_discarded_leads_untouched(conn):
    db.add_leads(conn, [lead()])
    db.update_lead(conn, "node-1", status="descartado")

    db.add_leads(conn, [lead(name="Lugar Novo", score=6)])

    saved = db.list_leads(conn)[0]
    assert saved["status"] == "descartado"
    assert saved["name"] == "Lugar"


def test_same_place_as_point_and_area_is_stored_once(conn):
    db.add_leads(conn, [lead("node-1", name="Cantina São José")])

    added = db.add_leads(
        conn, [lead("way-9", name="cantina sao jose", lat=-23.5603, lon=-46.6903)]
    )

    assert added == 0
    assert [saved["id"] for saved in db.list_leads(conn)] == ["node-1"]


def test_same_name_far_away_is_another_place(conn):
    db.add_leads(conn, [lead("node-1", name="Cantina")])

    added = db.add_leads(conn, [lead("way-9", name="Cantina", lat=-23.57)])

    assert added == 1


def test_two_points_with_the_same_name_nearby_are_kept(conn):
    db.add_leads(conn, [lead("node-1", name="Cantina")])

    added = db.add_leads(conn, [lead("node-2", name="Cantina")])

    assert added == 1


def test_same_place_in_one_batch_is_stored_once(conn):
    added = db.add_leads(
        conn, [lead("node-1", name="Cantina"), lead("way-9", name="Cantina")]
    )

    assert added == 1


def test_list_leads_orders_by_score_then_name(conn):
    db.add_leads(
        conn,
        [
            lead("node-1", name="Zeta", score=3),
            lead("node-2", name="alfa", score=3),
            lead("node-3", name="Beta", score=6),
        ],
    )

    names = [saved["name"] for saved in db.list_leads(conn)]

    assert names == ["Beta", "alfa", "Zeta"]


def test_update_lead_changes_status_and_notes(conn):
    db.add_leads(conn, [lead()])

    updated = db.update_lead(conn, "node-1", status="respondeu", notes="Quer orçamento")

    assert updated["status"] == "respondeu"
    assert updated["notes"] == "Quer orçamento"


def test_update_lead_changes_only_the_given_field(conn):
    db.add_leads(conn, [lead()])
    db.update_lead(conn, "node-1", notes="Primeira nota")

    updated = db.update_lead(conn, "node-1", status="fechado")

    assert updated["status"] == "fechado"
    assert updated["notes"] == "Primeira nota"


def test_update_lead_allows_clearing_notes(conn):
    db.add_leads(conn, [lead()])
    db.update_lead(conn, "node-1", notes="algo")

    updated = db.update_lead(conn, "node-1", notes="")

    assert updated["notes"] == ""


def test_update_lead_returns_none_for_unknown_id(conn):
    assert db.update_lead(conn, "node-404", status="fechado") is None


def test_database_rejects_unknown_status(conn):
    db.add_leads(conn, [lead()])

    with pytest.raises(sqlite3.IntegrityError):
        db.update_lead(conn, "node-1", status="inventado")


def test_database_rejects_unknown_site_state(conn):
    with pytest.raises(sqlite3.IntegrityError):
        db.add_leads(conn, [lead(site_state="inventado")])


def test_migration_keeps_old_leads_with_their_status_notes_and_id(old_db):
    with closing(db.connect(old_db)) as conn:
        saved = db.list_leads(conn)

    assert len(saved) == 1
    assert saved[0]["id"] == "node-5"
    assert saved[0]["status"] == "contatado"
    assert saved[0]["notes"] == "Ligar de novo"
    assert saved[0]["site_state"] == "nao_verificado"
    assert saved[0]["source_seen_at"] == "2026-10-21 12:00:00"
    assert saved[0]["phone_national"] == "11988887777"
    assert saved[0]["phone_kind"] == "celular"
    assert saved[0]["other_links"] == []
    assert saved[0]["favorite"] == 0


def test_migration_backs_up_the_old_database_first(old_db):
    db.connect(old_db).close()

    backups = list(old_db.parent.glob("old.db.bak-*"))
    assert len(backups) == 1
    with closing(sqlite3.connect(backups[0])) as copy:
        columns = [row[1] for row in copy.execute("PRAGMA table_info(leads)")]
        notes = copy.execute("SELECT notes FROM leads").fetchone()[0]
    assert "site_state" not in columns
    assert notes == "Ligar de novo"


def test_migration_runs_only_once(old_db):
    db.connect(old_db).close()
    db.connect(old_db).close()

    with closing(sqlite3.connect(old_db)) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert version == len(db.MIGRATIONS)
    assert len(list(old_db.parent.glob("old.db.bak-*"))) == 1


def test_new_database_needs_no_backup(tmp_path):
    db.connect(tmp_path / "novo.db").close()

    assert list(tmp_path.glob("novo.db.bak-*")) == []


def test_migration_from_version_one_adds_the_manual_check(tmp_path):
    path = tmp_path / "v1.db"
    with closing(sqlite3.connect(path)) as old:
        old.row_factory = sqlite3.Row
        old.execute(db.SCHEMA)
        db.add_presence_columns(old)
        old.execute("INSERT INTO leads (id, name, segment, neighborhood) VALUES ('node-1', 'Lugar', 'bar', 'Mooca')")
        old.execute("PRAGMA user_version = 1")
        old.commit()

    with closing(db.connect(path)) as conn:
        saved = db.list_leads(conn)[0]
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}

    assert saved["manual_phone"] is None
    assert saved["absence_confirmed_at"] is None
    assert "status_changes" in tables
    assert len(list(tmp_path.glob("v1.db.bak-*"))) == 1


def test_update_lead_toggles_favorite(conn):
    db.add_leads(conn, [lead()])

    assert db.update_lead(conn, "node-1", favorite=True)["favorite"] == 1
    assert db.update_lead(conn, "node-1", favorite=False)["favorite"] == 0


def test_update_lead_rejects_unknown_fields(conn):
    db.add_leads(conn, [lead()])

    with pytest.raises(ValueError):
        db.update_lead(conn, "node-1", score=6)


def test_status_changes_are_recorded(conn):
    db.add_leads(conn, [lead()])

    db.update_lead(conn, "node-1", status="contatado")
    db.update_lead(conn, "node-1", status="contatado")
    db.update_lead(conn, "node-1", notes="sem mudar etapa")
    db.update_lead(conn, "node-1", status="respondeu")

    history = conn.execute(
        "SELECT status, changed_at FROM status_changes WHERE lead_id = 'node-1' ORDER BY id"
    ).fetchall()
    assert [row["status"] for row in history] == ["contatado", "respondeu"]
    assert all(row["changed_at"] for row in history)


def test_manual_contacts_override_the_map_and_are_dated(conn):
    db.add_leads(conn, [lead(phone="+55 11 3815-2600", phone_national="1138152600", phone_kind="fixo")])

    saved = db.update_lead(
        conn,
        "node-1",
        manual_phone="11988887777",
        manual_whatsapp="11988887777",
        manual_instagram="lugar",
    )

    assert saved["phone"] == "(11) 98888-7777"
    assert (saved["phone_national"], saved["phone_kind"]) == ("11988887777", "celular")
    assert saved["instagram"] == "lugar"
    assert saved["manual_whatsapp"] == "11988887777"
    assert saved["manual_checked_at"]


def test_clearing_a_manual_contact_brings_back_the_map_value(conn):
    db.add_leads(conn, [lead(instagram="do_mapa")])
    db.update_lead(conn, "node-1", manual_instagram="manual")

    saved = db.update_lead(conn, "node-1", manual_instagram=None)

    assert saved["instagram"] == "do_mapa"


def test_manual_website_makes_the_site_informed(conn):
    db.add_leads(conn, [lead()])

    saved = db.update_lead(conn, "node-1", manual_website="https://lugar.com.br")

    assert saved["website"] == "https://lugar.com.br"
    assert saved["site_state"] == "site_informado"


def test_reimport_never_overwrites_manual_data(conn):
    db.add_leads(conn, [lead()])
    db.update_lead(conn, "node-1", manual_phone="11988887777", manual_instagram="manual")

    db.add_leads(conn, [lead(phone="+55 11 3815-2600", instagram="do_mapa")])

    saved = db.list_leads(conn)[0]
    assert saved["phone"] == "(11) 98888-7777"
    assert saved["instagram"] == "manual"
    assert saved["manual_instagram"] == "manual"


def test_confirming_absence_is_dated_and_reversible(conn):
    db.add_leads(conn, [lead()])

    confirmed = db.update_lead(conn, "node-1", absence_confirmed=True)
    undone = db.update_lead(conn, "node-1", absence_confirmed=False)

    assert confirmed["site_state"] == "ausencia_confirmada"
    assert confirmed["absence_confirmed_at"]
    assert undone["site_state"] == "sem_site_na_fonte"
    assert undone["absence_confirmed_at"] is None


def test_confirming_absence_clears_a_manual_website(conn):
    db.add_leads(conn, [lead()])
    db.update_lead(conn, "node-1", manual_website="https://lugar.com.br")

    saved = db.update_lead(conn, "node-1", absence_confirmed=True)

    assert saved["manual_website"] is None
    assert saved["site_state"] == "ausencia_confirmada"


def test_manual_website_clears_a_confirmed_absence(conn):
    db.add_leads(conn, [lead()])
    db.update_lead(conn, "node-1", absence_confirmed=True)

    saved = db.update_lead(conn, "node-1", manual_website="https://lugar.com.br")

    assert saved["absence_confirmed_at"] is None
    assert saved["site_state"] == "site_informado"


def test_reimport_keeps_a_confirmed_absence_while_the_map_has_no_site(conn):
    db.add_leads(conn, [lead()])
    db.update_lead(conn, "node-1", absence_confirmed=True)

    db.add_leads(conn, [lead()])

    assert db.list_leads(conn)[0]["site_state"] == "ausencia_confirmada"


def test_reimport_drops_a_confirmed_absence_when_the_map_gets_a_site(conn):
    db.add_leads(conn, [lead()])
    db.update_lead(conn, "node-1", absence_confirmed=True)

    db.add_leads(conn, [lead(website="https://lugar.com.br", site_state="site_informado")])

    assert db.list_leads(conn)[0]["site_state"] == "site_informado"
