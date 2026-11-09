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


OLD_STAGE_CHECK = "CHECK (status IN ('novo', 'contatado', 'respondeu', 'fechado', 'descartado'))"


@pytest.fixture
def v2_db(tmp_path):
    path = tmp_path / "v2.db"
    with closing(sqlite3.connect(path)) as old:
        old.row_factory = sqlite3.Row
        old.execute(OLD_SCHEMA)
        db.add_presence_columns(old)
        db.add_manual_check(old)
        old.execute(
            "INSERT INTO leads (id, name, segment, neighborhood, status, notes, favorite, manual_instagram)"
            " VALUES ('node-1', 'Contatado', 'cafe', 'Saúde', 'contatado', 'Ligar sexta', 1, 'perfil')"
        )
        old.execute(
            "INSERT INTO leads (id, name, segment, neighborhood, status)"
            " VALUES ('node-2', 'Descartado', 'cafe', 'Saúde', 'descartado')"
        )
        old.execute("INSERT INTO status_changes (lead_id, status) VALUES ('node-1', 'contatado')")
        old.execute("PRAGMA user_version = 2")
        old.commit()
    return path


def test_prospecto_is_a_stage_between_novo_and_contatado():
    assert db.STATUSES[:3] == ("novo", "prospecto", "contatado")


def test_update_lead_accepts_the_prospecto_stage_and_records_it(conn):
    db.add_leads(conn, [lead()])

    saved = db.update_lead(conn, "node-1", status="prospecto")

    assert saved["status"] == "prospecto"
    history = conn.execute("SELECT status FROM status_changes WHERE lead_id = 'node-1'").fetchall()
    assert [row["status"] for row in history] == ["prospecto"]


def test_new_database_already_accepts_prospecto(tmp_path):
    with closing(db.connect(tmp_path / "novo.db")) as conn:
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'leads'").fetchone()[0]

    assert "'prospecto'" in sql


def test_migration_three_lets_an_old_database_accept_prospecto(v2_db):
    with closing(db.connect(v2_db)) as conn:
        db.add_leads(conn, [lead("node-9")])
        saved = db.update_lead(conn, "node-9", status="prospecto")
        sql = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'leads'").fetchone()[0]

    assert saved["status"] == "prospecto"
    assert OLD_STAGE_CHECK not in sql
    assert "'prospecto'" in sql


def test_migration_three_keeps_every_lead_with_its_data(v2_db):
    with closing(db.connect(v2_db)) as conn:
        saved = {item["id"]: item for item in db.list_leads(conn)}

    assert set(saved) == {"node-1", "node-2"}
    assert saved["node-1"]["status"] == "contatado"
    assert saved["node-1"]["notes"] == "Ligar sexta"
    assert saved["node-1"]["favorite"] == 1
    assert saved["node-1"]["instagram"] == "perfil"
    assert saved["node-2"]["status"] == "descartado"


def test_migration_three_keeps_the_status_history_and_its_link_to_leads(v2_db):
    with closing(db.connect(v2_db)) as conn:
        history = conn.execute("SELECT lead_id, status FROM status_changes").fetchall()
        tables = {row[0]: row[1] for row in conn.execute("SELECT name, sql FROM sqlite_master WHERE type = 'table'")}

    assert [(row["lead_id"], row["status"]) for row in history] == [("node-1", "contatado")]
    assert set(tables) == {"leads", "status_changes", "vitrines"}
    assert "REFERENCES leads" in tables["status_changes"]
    assert "leads_old" not in tables["status_changes"] and "leads_new" not in tables["status_changes"]


def test_migration_three_backs_up_the_database_first(v2_db):
    db.connect(v2_db).close()

    backups = list(v2_db.parent.glob("v2.db.bak-*"))
    assert len(backups) == 1
    with closing(sqlite3.connect(backups[0])) as copy:
        sql = copy.execute("SELECT sql FROM sqlite_master WHERE name = 'leads'").fetchone()[0]
        count = copy.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    assert OLD_STAGE_CHECK in sql
    assert count == 2


def test_migration_three_still_rejects_an_unknown_stage(v2_db):
    with closing(db.connect(v2_db)) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            db.update_lead(conn, "node-1", status="inventado")


def test_migration_three_runs_only_once(v2_db):
    db.connect(v2_db).close()
    db.connect(v2_db).close()

    assert len(list(v2_db.parent.glob("v2.db.bak-*"))) == 1
    with closing(sqlite3.connect(v2_db)) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == len(db.MIGRATIONS)


def test_migration_three_is_atomic_when_it_fails(v2_db, monkeypatch):
    def broken(conn):
        conn.execute("ALTER TABLE leads RENAME TO leads_x")
        raise RuntimeError("falhou no meio")

    monkeypatch.setattr(db, "MIGRATIONS", (*db.MIGRATIONS[:2], broken))

    with pytest.raises(RuntimeError):
        db.connect(v2_db)

    with closing(sqlite3.connect(v2_db)) as conn:
        names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        count = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert names == {"leads", "status_changes"}
    assert count == 2
    assert version == 2


def test_statuses_of_returns_only_the_saved_ids_with_their_stage(conn):
    db.add_leads(conn, [lead("node-1"), lead("node-2", lat=-23.7)])
    db.update_lead(conn, "node-2", status="prospecto")

    assert db.statuses_of(conn, ["node-1", "node-2", "node-404"]) == {"node-1": "novo", "node-2": "prospecto"}


def test_statuses_of_an_empty_list_is_empty(conn):
    assert db.statuses_of(conn, []) == {}


def test_same_place_needs_another_osm_type_the_same_name_and_a_short_distance():
    node = lead("node-1", name="Cantina São José")

    assert db.same_place(node, lead("way-9", name="cantina sao jose", lat=-23.5603, lon=-46.6903))
    assert not db.same_place(node, lead("node-2", name="Cantina São José"))
    assert not db.same_place(node, lead("way-9", name="Outro Nome"))
    assert not db.same_place(node, lead("way-9", name="Cantina São José", lat=-23.57))
    assert not db.same_place(node, lead("way-9", name="Cantina São José", lat=None))


@pytest.fixture
def v3_db(tmp_path):
    path = tmp_path / "v3.db"
    with closing(sqlite3.connect(path)) as old:
        old.row_factory = sqlite3.Row
        old.execute(OLD_SCHEMA)
        db.add_presence_columns(old)
        db.add_manual_check(old)
        db.allow_prospect_stage(old)
        old.execute(
            "INSERT INTO leads (id, name, segment, neighborhood, status, notes, favorite)"
            " VALUES ('node-1', 'Contatado', 'cafe', 'Saúde', 'contatado', 'Ligar sexta', 1)"
        )
        old.execute("INSERT INTO status_changes (lead_id, status, changed_at) VALUES ('node-1', 'contatado', '2026-11-01 12:00:00')")
        old.execute("PRAGMA user_version = 3")
        old.commit()
    return path


def test_migration_four_adds_the_outreach_columns_and_table_without_losing_data(v3_db):
    with closing(db.connect(v3_db)) as conn:
        saved = db.list_leads(conn)[0]
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}

    assert (saved["id"], saved["status"], saved["notes"], saved["favorite"]) == ("node-1", "contatado", "Ligar sexta", 1)
    assert saved["follow_up_at"] is None and saved["do_not_contact_at"] is None
    assert saved["contacted_at"] == "2026-11-01 12:00:00"
    assert "vitrines" in tables


def test_migration_four_backs_up_the_database_first(v3_db):
    db.connect(v3_db).close()

    backups = list(v3_db.parent.glob("v3.db.bak-*"))
    assert len(backups) == 1
    with closing(sqlite3.connect(backups[0])) as copy:
        tables = {row[0] for row in copy.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert "vitrines" not in tables


def test_new_leads_have_no_follow_up_or_do_not_contact_date(conn):
    db.add_leads(conn, [lead()])

    saved = db.list_leads(conn)[0]

    assert (saved["follow_up_at"], saved["do_not_contact_at"], saved["contacted_at"]) == (None, None, None)


def test_contacted_at_is_the_latest_time_the_lead_became_contacted(conn):
    db.add_leads(conn, [lead()])
    conn.execute("INSERT INTO status_changes (lead_id, status, changed_at) VALUES ('node-1', 'contatado', '2026-11-01 10:00:00')")
    conn.execute("INSERT INTO status_changes (lead_id, status, changed_at) VALUES ('node-1', 'novo', '2026-11-02 10:00:00')")
    conn.execute("INSERT INTO status_changes (lead_id, status, changed_at) VALUES ('node-1', 'contatado', '2026-11-03 10:00:00')")

    assert db.get_lead(conn, "node-1")["contacted_at"] == "2026-11-03 10:00:00"


def test_do_not_contact_is_dated_and_reversible(conn):
    db.add_leads(conn, [lead()])

    marked = db.update_lead(conn, "node-1", do_not_contact=True)
    first_date = marked["do_not_contact_at"]
    again = db.update_lead(conn, "node-1", do_not_contact=True)
    undone = db.update_lead(conn, "node-1", do_not_contact=False)

    assert first_date
    assert again["do_not_contact_at"] == first_date
    assert undone["do_not_contact_at"] is None


def test_follow_up_sent_is_recorded_only_once(conn):
    db.add_leads(conn, [lead()])
    conn.execute("UPDATE leads SET follow_up_at = '2026-11-01 10:00:00'")

    saved = db.update_lead(conn, "node-1", follow_up_sent=True)

    assert saved["follow_up_at"] == "2026-11-01 10:00:00"


def test_follow_up_sent_is_dated_the_first_time(conn):
    db.add_leads(conn, [lead()])

    assert db.update_lead(conn, "node-1", follow_up_sent=True)["follow_up_at"]


def test_reimport_keeps_do_not_contact_and_follow_up(conn):
    db.add_leads(conn, [lead()])
    db.update_lead(conn, "node-1", do_not_contact=True, follow_up_sent=True)

    db.add_leads(conn, [lead(name="Lugar Novo")])

    saved = db.list_leads(conn)[0]
    assert saved["name"] == "Lugar Novo"
    assert saved["do_not_contact_at"] and saved["follow_up_at"]


def test_vitrine_is_created_found_updated_and_marked_exported(conn):
    db.add_leads(conn, [lead()])

    created = db.create_vitrine(conn, "node-1", "lugar-pinheiros")
    updated = db.update_vitrine(conn, "lugar-pinheiros", content={"hours": "10h às 20h"}, approved=True)
    exported = db.mark_exported(conn, "lugar-pinheiros")

    assert (created["slug"], created["approved"], created["content"]) == ("lugar-pinheiros", False, {})
    assert (updated["content"], updated["approved"]) == ({"hours": "10h às 20h"}, True)
    assert exported["exported_at"]
    assert db.vitrine_of_lead(conn, "node-1")["slug"] == "lugar-pinheiros"
    assert db.vitrine_by_slug(conn, "lugar-pinheiros")["lead_id"] == "node-1"
    assert db.vitrine_slugs(conn) == {"lugar-pinheiros"}
    assert db.vitrine_slug_by_lead(conn) == {"node-1": "lugar-pinheiros"}


def test_vitrine_slug_and_lead_are_unique(conn):
    db.add_leads(conn, [lead("node-1"), lead("node-2", lat=-23.7)])
    db.create_vitrine(conn, "node-1", "lugar")

    with pytest.raises(sqlite3.IntegrityError):
        db.create_vitrine(conn, "node-2", "lugar")
    with pytest.raises(sqlite3.IntegrityError):
        db.create_vitrine(conn, "node-1", "outro")


@pytest.mark.parametrize("slug", ["../x", "ab", "a" * 61, "COM-MAIUSCULA", "com espaco", "com/barra", ""])
def test_vitrine_lookup_rejects_slugs_outside_the_pattern(conn, slug):
    assert db.vitrine_by_slug(conn, slug) is None


def test_vitrine_table_refuses_a_slug_outside_the_length_limits(conn):
    db.add_leads(conn, [lead()])

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO vitrines (lead_id, slug) VALUES ('node-1', 'ab')")


@pytest.mark.parametrize("slug", ["ab", "../x", "COM-MAIUSCULA", "com/barra", "a" * 61])
def test_create_vitrine_refuses_a_slug_outside_the_pattern_before_touching_the_table(conn, slug):
    db.add_leads(conn, [lead()])

    with pytest.raises(ValueError):
        db.create_vitrine(conn, "node-1", slug)

    assert conn.execute("SELECT COUNT(*) FROM vitrines").fetchone()[0] == 0


@pytest.fixture
def v4_db(tmp_path):
    path = tmp_path / "v4.db"
    with closing(sqlite3.connect(path)) as old:
        old.row_factory = sqlite3.Row
        old.execute(OLD_SCHEMA)
        db.add_presence_columns(old)
        db.add_manual_check(old)
        db.allow_prospect_stage(old)
        db.add_outreach(old)
        old.execute(
            "INSERT INTO leads (id, name, segment, neighborhood, status, notes, favorite)"
            " VALUES ('node-1', 'Antigo', 'cafe', 'Saúde', 'contatado', 'Ligar sexta', 1)"
        )
        old.execute("PRAGMA user_version = 4")
        old.commit()
    return path


def test_migration_five_adds_an_empty_zone_without_losing_data(v4_db):
    with closing(db.connect(v4_db)) as conn:
        saved = db.list_leads(conn)[0]

    assert (saved["id"], saved["status"], saved["notes"], saved["favorite"]) == ("node-1", "contatado", "Ligar sexta", 1)
    assert saved["zone"] is None


def test_migration_five_backs_up_the_database_first(v4_db):
    db.connect(v4_db).close()

    backups = list(v4_db.parent.glob("v4.db.bak-*"))
    assert len(backups) == 1
    with closing(sqlite3.connect(backups[0])) as copy:
        columns = {row[1] for row in copy.execute("PRAGMA table_info(leads)")}
    assert "zone" not in columns


def test_a_lead_without_a_zone_key_is_saved_with_no_zone(conn):
    db.add_leads(conn, [lead()])

    assert db.list_leads(conn)[0]["zone"] is None


def test_the_zone_of_a_lead_is_saved(conn):
    db.add_leads(conn, [lead(zone="sul")])

    assert db.list_leads(conn)[0]["zone"] == "sul"


def test_reimporting_fills_an_empty_zone_but_never_changes_a_set_one(conn):
    db.add_leads(conn, [lead("node-1"), lead("node-2", zone="sul")])

    db.add_leads(conn, [lead("node-1", zone="oeste"), lead("node-2", zone="norte")])

    zones_by_id = {item["id"]: item["zone"] for item in db.list_leads(conn)}
    assert zones_by_id == {"node-1": "oeste", "node-2": "sul"}


def test_reimporting_without_a_zone_keeps_the_saved_zone(conn):
    db.add_leads(conn, [lead(zone="leste")])

    db.add_leads(conn, [lead(zone=None)])

    assert db.list_leads(conn)[0]["zone"] == "leste"
