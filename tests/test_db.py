import sqlite3

import pytest

import db


@pytest.fixture
def conn(tmp_path):
    connection = db.connect(tmp_path / "test.db")
    yield connection
    connection.close()


def lead(lead_id="node-1", **overrides):
    base = {
        "id": lead_id,
        "name": "Lugar",
        "segment": "restaurante",
        "neighborhood": "Pinheiros",
        "phone": None,
        "address": None,
        "instagram": None,
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


def test_adding_the_same_lead_again_keeps_status_and_notes(conn):
    db.add_leads(conn, [lead()])
    db.update_lead(conn, "node-1", status="contatado", notes="Falei com o dono")

    added = db.add_leads(conn, [lead(score=5)])

    saved = db.list_leads(conn)[0]
    assert added == 0
    assert saved["status"] == "contatado"
    assert saved["notes"] == "Falei com o dono"
    assert len(db.list_leads(conn)) == 1


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
