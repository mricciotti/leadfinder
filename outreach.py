from datetime import datetime, timedelta, timezone

import db

DAILY_LIMIT = 15
FOLLOW_UP_DAYS = 3
BRAZIL = timezone(timedelta(hours=-3))
STAMP = "%Y-%m-%d %H:%M:%S"


def utc_now():
    return datetime.now(timezone.utc)


def parse(stamp):
    return datetime.strptime(stamp, STAMP).replace(tzinfo=timezone.utc)


def day_bounds(now):
    local = now.astimezone(BRAZIL)
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


def sent_today(conn, now):
    start, end = day_bounds(now)
    return conn.execute(
        "SELECT COUNT(DISTINCT lead_id) FROM status_changes"
        " WHERE status = 'contatado' AND changed_at >= ? AND changed_at < ?",
        (start.strftime(STAMP), end.strftime(STAMP)),
    ).fetchone()[0]


def today(conn, now):
    sent = sent_today(conn, now)
    return {"sent": sent, "limit": DAILY_LIMIT, "remaining": max(0, DAILY_LIMIT - sent)}


def reachable(lead):
    return bool(lead["evaluation"]["contact"]["channel"]) and not lead["do_not_contact_at"]


def in_queue(lead):
    return (
        lead["status"] in db.NOT_APPROACHED
        and reachable(lead)
        and bool(lead.get("vitrine_slug"))
    )


def daily_queue(leads, remaining):
    return [lead for lead in leads if in_queue(lead)][:remaining]


def follow_up_due(lead, now):
    if lead["status"] != "contatado" or lead["follow_up_at"] or lead["do_not_contact_at"]:
        return False
    if not lead["contacted_at"]:
        return False
    return now - parse(lead["contacted_at"]) >= timedelta(days=FOLLOW_UP_DAYS)


def follow_ups(leads, now):
    return [lead for lead in leads if follow_up_due(lead, now)]
