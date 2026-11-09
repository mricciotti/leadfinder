import contacts
import db
import zones

SITE_FILTERS = {
    "com_site": ("site_informado", "site_ok", "site_com_problemas", "site_inacessivel"),
    "sem_site_na_fonte": ("sem_site_na_fonte",),
    "so_rede_social": ("so_rede_social",),
    "ausencia_confirmada": ("ausencia_confirmada",),
    "site_com_problemas": ("site_com_problemas", "site_inacessivel"),
    "nao_verificado": ("nao_verificado",),
}


def same_text(value, wanted):
    return contacts.text_key(value) == contacts.text_key(wanted)


def matches(lead, wanted):
    evaluation = lead["evaluation"]
    offer_keys = [offer["key"] for offer in evaluation["offers"]]
    if wanted["segment"] and lead["segment"] != wanted["segment"]:
        return False
    if wanted.get("zone") and lead.get("zone") != wanted["zone"]:
        return False
    if wanted["neighborhood"] and not same_text(lead["neighborhood"], wanted["neighborhood"]):
        return False
    if wanted["city"] and not same_text(lead["city"], wanted["city"]):
        return False
    if wanted["uf"] and lead["uf"] != wanted["uf"]:
        return False
    if wanted["status"] and lead["status"] != wanted["status"]:
        return False
    if wanted["site"] and lead["site_state"] not in SITE_FILTERS[wanted["site"]]:
        return False
    if wanted["priority"] and evaluation["priority"]["level"] != wanted["priority"]:
        return False
    if wanted["offer"] and wanted["offer"] not in offer_keys:
        return False
    if wanted["phone"] and not lead["phone"]:
        return False
    if wanted["email"] and not lead["email"]:
        return False
    if wanted["instagram"] and not lead["instagram"]:
        return False
    if wanted["favorite"] and not lead["favorite"]:
        return False
    if wanted["not_contacted"] and lead["status"] not in db.NOT_APPROACHED:
        return False
    return True


def apply(leads, wanted):
    return [lead for lead in leads if matches(lead, wanted)]


def distinct(values):
    seen = {}
    for value in values:
        if value and contacts.text_key(value) not in seen:
            seen[contacts.text_key(value)] = value
    return sorted(seen.values(), key=contacts.text_key)


def options(leads):
    return {
        "segments": distinct(lead["segment"] for lead in leads),
        "neighborhoods": distinct(lead["neighborhood"] for lead in leads),
        "cities": distinct(lead["city"] for lead in leads),
        "ufs": distinct(lead["uf"] for lead in leads),
    }


def place_of(lead):
    if lead.get("zone"):
        return (lead["segment"], "zona", lead["zone"])
    return (lead["segment"], "bairro", contacts.text_key(lead["neighborhood"]))


def areas(leads):
    cities_by_place = {}
    for lead in leads:
        if lead["city"]:
            cities_by_place.setdefault(place_of(lead), set()).add(contacts.text_key(lead["city"]))

    found = {}
    for lead in leads:
        place = place_of(lead)
        city = contacts.text_key(lead["city"])
        if not city and len(cities_by_place.get(place, ())) == 1:
            city = next(iter(cities_by_place[place]))
        key = (*place, city)
        if key not in found:
            found[key] = {
                "segment": lead["segment"],
                "neighborhood": zones.label(lead["zone"]) if lead.get("zone") else lead["neighborhood"],
                "zone": lead.get("zone"),
                "city": None,
                "uf": None,
                "total": 0,
                "high_priority": 0,
                "contacted": 0,
                "last_seen": "",
            }
        area = found[key]
        if lead["city"] and not area["city"]:
            area["city"], area["uf"] = lead["city"], lead["uf"]
        area["total"] += 1
        if lead["evaluation"]["priority"]["level"] == "alta":
            area["high_priority"] += 1
        if lead["status"] not in db.NOT_APPROACHED:
            area["contacted"] += 1
        area["last_seen"] = max(area["last_seen"], lead["source_seen_at"] or "")
    return sorted(found.values(), key=lambda area: area["last_seen"], reverse=True)
