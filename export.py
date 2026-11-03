import csv
import io
import re

import contacts
import overpass

FORMULA_START = ("=", "@", "\t", "\r")
PHONE_LIKE = re.compile(r"[+-][\d\s().-]*")

SITE_LABELS = {
    "nao_verificado": "Não verificado",
    "sem_site_na_fonte": "Sem site no mapa (não verificado)",
    "so_rede_social": "Só rede social, página de links ou delivery",
    "site_informado": "Site informado, não testado",
    "site_ok": "Site funcionando",
    "site_com_problemas": "Site com problemas",
    "site_inacessivel": "Site inacessível",
    "ausencia_confirmada": "Sem site (confirmado manualmente)",
}
LEVEL_LABELS = {
    "maxima": "máxima",
    "alta": "alta",
    "media": "média",
    "normal": "normal",
    "baixa": "baixa",
    "indeterminada": "indeterminada",
}
EMAIL_KIND_LABELS = {"proprio": "próprio", "generico": "genérico"}


def csv_safe(value):
    text = "" if value is None else str(value)
    if text.startswith(FORMULA_START):
        return f"'{text}"
    if text.startswith(("+", "-")) and not PHONE_LIKE.fullmatch(text):
        return f"'{text}"
    return text


def to_csv(rows):
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), delimiter=";", lineterminator="\r\n")
    writer.writeheader()
    writer.writerows({key: csv_safe(value) for key, value in row.items()} for row in rows)
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def whatsapp(lead):
    if lead["manual_whatsapp"]:
        return lead["manual_whatsapp"], "informado por você"
    if lead["phone_kind"] == "celular":
        return lead["phone_national"], "potencial (celular, não confirmado)"
    return None, None


def last_check(lead):
    return max(filter(None, (lead["manual_checked_at"], lead["checked_at"])), default=None)


def reasons(evaluation):
    return " | ".join(
        [*evaluation["contact"]["reasons"], *evaluation["opportunity"]["reasons"]]
    )


def offer_labels(evaluation):
    return " | ".join(offer["label"] for offer in evaluation["offers"])


def points_label(points):
    return f"{points} ponto" if points == 1 else f"{points} pontos"


def lead_row(lead):
    evaluation = lead["evaluation"]
    contact = evaluation["contact"]
    number, whatsapp_status = whatsapp(lead)
    return {
        "Nome": lead["name"],
        "Categoria": overpass.SEGMENTS.get(lead["segment"], (lead["segment"],))[0],
        "Telefone": contacts.format_phone(lead["phone_national"]) or lead["phone"],
        "WhatsApp": contacts.format_phone(number),
        "Situação do WhatsApp": whatsapp_status,
        "Link do WhatsApp": contacts.whatsapp_url(number) if number else None,
        "E-mail": lead["email"],
        "Tipo do e-mail": EMAIL_KIND_LABELS.get(contacts.email_kind(lead["email"])),
        "Website": lead["website"],
        "Instagram": lead["instagram"],
        "Facebook": lead["facebook"],
        "Outras redes": " | ".join(lead["other_links"]),
        "Endereço": lead["address"],
        "Bairro": lead["neighborhood"],
        "Cidade": lead["city"],
        "UF": lead["uf"],
        "Situação do site": SITE_LABELS[lead["site_state"]],
        "Ofertas": offer_labels(evaluation),
        "Prioridade": LEVEL_LABELS[evaluation["priority"]["level"]],
        "Nota de contato": f"{LEVEL_LABELS[contact['level']]} ({points_label(contact['points'])})",
        "Nota de oportunidade": LEVEL_LABELS[evaluation["opportunity"]["level"]],
        "Motivos": reasons(evaluation),
        "Origem": "OpenStreetMap + checagem manual" if lead["manual_checked_at"] else "OpenStreetMap",
        "Última verificação (UTC)": last_check(lead),
    }


def full_row(lead):
    evaluation = lead["evaluation"]
    stored = {key: value for key, value in lead.items() if key != "evaluation"}
    return {
        **stored,
        "other_links": " | ".join(lead["other_links"]),
        "priority": evaluation["priority"]["level"],
        "contact_level": evaluation["contact"]["level"],
        "contact_points": evaluation["contact"]["points"],
        "opportunity_level": evaluation["opportunity"]["level"],
        "offers": offer_labels(evaluation),
        "reasons": reasons(evaluation),
    }


def leads_csv(leads):
    return to_csv([lead_row(lead) for lead in leads])


def table(leads):
    rows = [lead_row(lead) for lead in leads]
    return {
        "columns": list(rows[0]) if rows else [],
        "ids": [lead["id"] for lead in leads],
        "rows": [list(row.values()) for row in rows],
    }


def full_csv(leads):
    return to_csv([full_row(lead) for lead in leads])


def file_name(kind, wanted, today):
    parts = [
        "leads" if kind == "leads" else "leads-completo",
        wanted["segment"],
        wanted["neighborhood"],
        wanted["city"],
        today.isoformat(),
    ]
    return "-".join(contacts.text_key(part).replace(" ", "-") for part in parts if part) + ".csv"
