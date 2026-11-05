import contacts

FOOD_SEGMENTS = {
    "restaurante",
    "lanchonete",
    "bar",
    "cafe",
    "padaria",
    "confeitaria",
    "sorveteria",
}

CONTACT_POINTS = {
    "celular": 3,
    "fixo": 2,
    "outro": 1,
    "whatsapp": 2,
    "whatsapp_informado": 3,
    "email_proprio": 2,
    "email_generico": 1,
    "instagram": 2,
    "outras_redes": 1,
    "endereco": 1,
}
CONTACT_LEVELS = (("alta", 5), ("media", 2), ("baixa", 0))

CONTACT_REASONS = {
    "celular": "Celular no mapa",
    "fixo": "Telefone fixo no mapa",
    "outro": "Telefone 0800 ou similar no mapa",
    "whatsapp": "Celular pode ter WhatsApp (não confirmado)",
    "whatsapp_informado": "WhatsApp informado por você",
    "email_proprio": "E-mail com domínio próprio",
    "email_generico": "E-mail em provedor genérico (Gmail, Outlook e afins)",
    "instagram": "Instagram identificado",
    "outras_redes": "Facebook ou outros links identificados",
    "endereco": "Endereço no mapa",
}

OPPORTUNITY_BY_STATE = {
    "ausencia_confirmada": ("maxima", "Você confirmou que não tem site"),
    "so_rede_social": ("alta", "No mapa, o site aponta só para rede social, página de links ou delivery"),
    "site_inacessivel": ("alta", "O site não abriu na verificação"),
    "site_com_problemas": ("media", "A verificação encontrou problemas no site"),
    "sem_site_na_fonte": ("media", "Sem site no mapa, ainda não verificado"),
    "site_informado": ("indeterminada", "Site no mapa, ainda não testado"),
    "site_ok": ("baixa", "O site funcionou na verificação"),
    "nao_verificado": ("indeterminada", "Presença digital ainda não verificada"),
}
FREE_SITE_OPPORTUNITY = ("alta", "O site usa um subdomínio gratuito, sem domínio próprio")

OFFERS = {
    "landing_page": ("Landing page", "Não há site próprio conhecido"),
    "pagina_propria": ("Página própria", "A presença digital depende de rede social ou página de links"),
    "cardapio_proprio": ("Cardápio próprio", "Os pedidos passam por delivery, que cobra comissão"),
    "cardapio_digital": ("Cardápio digital com QR code", "Negócio de comida sem site próprio"),
    "dominio_proprio": ("Site com domínio próprio", "O site está num subdomínio gratuito"),
    "reformulacao": ("Reformulação do site", "O site tem problemas ou não abre"),
}

PRIORITY_ORDER = ("alta", "normal", "baixa")
OPPORTUNITY_ORDER = ("maxima", "alta", "media", "indeterminada", "baixa")
HIGH_OPPORTUNITY = ("maxima", "alta")
NO_OWN_SITE = ("sem_site_na_fonte", "ausencia_confirmada", "so_rede_social")


def contact(lead):
    found = []
    if lead["phone_kind"] in ("celular", "fixo", "outro"):
        found.append(lead["phone_kind"])
    if lead["manual_whatsapp"]:
        found.append("whatsapp_informado")
    elif lead["phone_kind"] == "celular":
        found.append("whatsapp")
    kind = contacts.email_kind(lead["email"])
    if kind:
        found.append(f"email_{kind}")
    if lead["instagram"]:
        found.append("instagram")
    if lead["facebook"] or lead["other_links"]:
        found.append("outras_redes")
    if lead["address"]:
        found.append("endereco")
    points = sum(CONTACT_POINTS[key] for key in found)
    level = next(name for name, minimum in CONTACT_LEVELS if points >= minimum)
    reasons = [CONTACT_REASONS[key] for key in found]
    if lead["phone"] and lead["phone_kind"] == "invalido":
        reasons.append("Telefone no mapa em formato não reconhecido")
    if not reasons:
        reasons.append("Nenhum canal de contato no mapa")
    channel = any(key != "endereco" for key in found)
    return {"level": level, "points": points, "reasons": reasons, "channel": channel}


def has_free_site(lead):
    return bool(lead["website"]) and contacts.is_free_site(lead["website"])


def opportunity(lead):
    level, reason = OPPORTUNITY_BY_STATE[lead["site_state"]]
    reasons = [reason]
    if has_free_site(lead):
        reasons.append(FREE_SITE_OPPORTUNITY[1])
        if level not in HIGH_OPPORTUNITY:
            level = FREE_SITE_OPPORTUNITY[0]
    return {"level": level, "reasons": reasons}


def offer_keys(lead):
    state = lead["site_state"]
    link_kinds = {contacts.classify_url(url) for url in lead["other_links"]}
    keys = []
    if state in ("sem_site_na_fonte", "ausencia_confirmada"):
        keys.append("landing_page")
    if state == "so_rede_social":
        if link_kinds - {"delivery"} or lead["instagram"] or lead["facebook"]:
            keys.append("pagina_propria")
        if "delivery" in link_kinds:
            keys.append("cardapio_proprio")
    if lead["segment"] in FOOD_SEGMENTS and state in NO_OWN_SITE:
        keys.append("cardapio_digital")
    if has_free_site(lead):
        keys.append("dominio_proprio")
    if state in ("site_com_problemas", "site_inacessivel"):
        keys.append("reformulacao")
    return keys


def offers(lead):
    return [
        {"key": key, "label": OFFERS[key][0], "reason": OFFERS[key][1]}
        for key in offer_keys(lead)
    ]


def priority(opportunity_level, channel):
    if opportunity_level in HIGH_OPPORTUNITY and channel:
        return {"level": "alta", "reason": "Oportunidade alta e pelo menos um canal de contato"}
    if opportunity_level in HIGH_OPPORTUNITY:
        return {"level": "normal", "reason": "Oportunidade alta, mas sem canal de contato conhecido"}
    if opportunity_level == "baixa":
        return {"level": "baixa", "reason": "Oportunidade baixa"}
    return {"level": "normal", "reason": "Oportunidade ainda não é alta"}


def evaluate(lead):
    contact_score = contact(lead)
    opportunity_score = opportunity(lead)
    return {
        "contact": contact_score,
        "opportunity": opportunity_score,
        "offers": offers(lead),
        "priority": priority(opportunity_score["level"], contact_score["channel"]),
    }


def with_evaluation(lead):
    return {**lead, "evaluation": evaluate(lead)}


def rank_key(lead):
    evaluation = lead["evaluation"]
    return (
        PRIORITY_ORDER.index(evaluation["priority"]["level"]),
        OPPORTUNITY_ORDER.index(evaluation["opportunity"]["level"]),
        -evaluation["contact"]["points"],
        lead["name"].lower(),
    )


def ranked(leads):
    return sorted((with_evaluation(lead) for lead in leads), key=rank_key)
