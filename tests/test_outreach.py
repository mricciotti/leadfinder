from contextlib import closing
from datetime import datetime, timezone

import pytest

import db
import outreach
from test_db import lead


def at(text):
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)


@pytest.fixture
def conn(tmp_path):
    connection = db.connect(tmp_path / "outreach.db")
    yield connection
    connection.close()


def contacted(conn, lead_id, when):
    conn.execute("INSERT INTO status_changes (lead_id, status, changed_at) VALUES (?, 'contatado', ?)", (lead_id, f"{when}:00"))
    conn.commit()


def test_a_day_is_the_brazilian_day_not_the_utc_day():
    start, end = outreach.day_bounds(at("2026-11-08 02:30"))

    assert (start, end) == (at("2026-11-07 03:00"), at("2026-11-08 03:00"))


def test_at_three_utc_a_new_brazilian_day_begins():
    assert outreach.day_bounds(at("2026-11-08 03:00"))[0] == at("2026-11-08 03:00")
    assert outreach.day_bounds(at("2026-11-08 02:59"))[0] == at("2026-11-07 03:00")


def test_sent_today_counts_distinct_leads_contacted_inside_the_day(conn):
    db.add_leads(conn, [lead("node-1"), lead("node-2", lat=-23.7), lead("node-3", lat=-23.8)])
    contacted(conn, "node-1", "2026-11-08 12:00")
    contacted(conn, "node-1", "2026-11-08 13:00")
    contacted(conn, "node-2", "2026-11-08 03:00")
    contacted(conn, "node-3", "2026-11-08 02:59")

    assert outreach.sent_today(conn, at("2026-11-08 20:00")) == 2


def test_sent_today_ignores_the_end_of_the_day_and_other_stages(conn):
    db.add_leads(conn, [lead("node-1"), lead("node-2", lat=-23.7)])
    contacted(conn, "node-1", "2026-11-09 03:00")
    conn.execute("INSERT INTO status_changes (lead_id, status, changed_at) VALUES ('node-2', 'respondeu', '2026-11-08 12:00:00')")

    assert outreach.sent_today(conn, at("2026-11-08 20:00")) == 0


def test_today_reports_the_limit_and_what_is_left(conn):
    db.add_leads(conn, [lead(f"node-{i}", lat=-23.5 - i / 100) for i in range(3)])
    for i in range(3):
        contacted(conn, f"node-{i}", "2026-11-08 12:00")

    assert outreach.today(conn, at("2026-11-08 20:00")) == {"sent": 3, "limit": 15, "remaining": 12}


def test_remaining_never_goes_below_zero(conn):
    db.add_leads(conn, [lead(f"node-{i}", lat=-23.5 - i / 100) for i in range(17)])
    for i in range(17):
        contacted(conn, f"node-{i}", "2026-11-08 12:00")

    assert outreach.today(conn, at("2026-11-08 20:00"))["remaining"] == 0


def queued(**overrides):
    base = {
        "id": "node-1",
        "status": "novo",
        "do_not_contact_at": None,
        "vitrine_slug": "lugar",
        "evaluation": {"contact": {"channel": True}},
    }
    base.update(overrides)
    return base


def test_queue_holds_unapproached_reachable_leads_with_a_vitrine():
    leads = [queued(id="a"), queued(id="b", status="prospecto")]

    assert [item["id"] for item in outreach.daily_queue(leads, 15)] == ["a", "b"]


@pytest.mark.parametrize(
    "change",
    [
        {"status": "contatado"},
        {"status": "descartado"},
        {"status": "respondeu"},
        {"vitrine_slug": None},
        {"do_not_contact_at": "2026-11-01 10:00:00"},
        {"evaluation": {"contact": {"channel": False}}},
    ],
)
def test_queue_leaves_out_everyone_who_does_not_qualify(change):
    assert outreach.daily_queue([queued(**change)], 15) == []


def test_queue_is_cut_to_what_is_left_of_the_daily_limit_keeping_the_order():
    leads = [queued(id=f"n{i}") for i in range(20)]

    assert [item["id"] for item in outreach.daily_queue(leads, 3)] == ["n0", "n1", "n2"]
    assert outreach.daily_queue(leads, 0) == []


def due(**overrides):
    base = {"status": "contatado", "follow_up_at": None, "do_not_contact_at": None, "contacted_at": "2026-11-05 12:00:00"}
    base.update(overrides)
    return base


def test_follow_up_is_due_after_three_days():
    assert outreach.follow_up_due(due(), at("2026-11-08 12:00"))
    assert outreach.follow_up_due(due(), at("2026-11-20 12:00"))


def test_follow_up_is_not_due_one_minute_early():
    assert not outreach.follow_up_due(due(), at("2026-11-08 11:59"))


def test_follow_up_is_due_only_once():
    assert not outreach.follow_up_due(due(follow_up_at="2026-11-08 12:00:00"), at("2026-11-20 12:00"))


@pytest.mark.parametrize(
    "change",
    [
        {"status": "novo"},
        {"status": "respondeu"},
        {"status": "fechado"},
        {"do_not_contact_at": "2026-11-06 10:00:00"},
        {"contacted_at": None},
    ],
)
def test_follow_up_skips_everyone_who_does_not_qualify(change):
    assert not outreach.follow_up_due(due(**change), at("2026-11-20 12:00"))


def test_follow_ups_keeps_only_the_due_ones():
    leads = [{"id": "a", **due()}, {"id": "b", **due(follow_up_at="2026-11-07 10:00:00")}, {"id": "c", **due(contacted_at="2026-11-08 10:00:00")}]

    assert [item["id"] for item in outreach.follow_ups(leads, at("2026-11-08 12:00"))] == ["a"]


def test_follow_up_counts_from_the_latest_time_the_lead_became_contacted(conn):
    db.add_leads(conn, [lead()])
    db.update_lead(conn, "node-1", status="contatado")
    conn.execute("UPDATE status_changes SET changed_at = '2026-11-01 10:00:00'")
    saved = db.get_lead(conn, "node-1")

    assert outreach.follow_up_due(saved, at("2026-11-08 12:00"))
