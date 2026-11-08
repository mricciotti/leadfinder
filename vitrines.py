import base64
import hashlib
import html
import json
import re
from datetime import date
from pathlib import Path
from string import Template
from urllib.parse import quote, urlsplit

import contacts
import scoring

TEMPLATES = Path(__file__).parent / "templates"
SLUG_RE = re.compile(r"^[a-z0-9-]{3,60}$")
HANDLE_RE = re.compile(r"[A-Za-z0-9_.]{1,30}")

PALETTES = {
    "ouro": {"ink": "#11110e", "paper": "#f4f0e6", "coffee": "#201e18", "gold": "#cf9f56", "gold_dk": "#8f6a30"},
    "floresta": {"ink": "#0e1f19", "paper": "#f1efe4", "coffee": "#17352b", "gold": "#d3b77b", "gold_dk": "#8a6d2f"},
    "terracota": {"ink": "#1a0f0b", "paper": "#f8efe4", "coffee": "#2b1710", "gold": "#e8863a", "gold_dk": "#a14a14"},
    "azul": {"ink": "#0b1520", "paper": "#eef3f7", "coffee": "#12263a", "gold": "#4cc3d9", "gold_dk": "#0b6f84"},
}

PHOTOS = {
    "beleza": [
        "photo-1503951914875-452162b0f3f1",
        "photo-1599351431202-1e0f0137899a",
        "photo-1621605815971-fbc98d665033",
        "photo-1593702295094-aea22597af65",
        "photo-1622296089863-eb7fc530daa8",
    ],
    "pet": [
        "photo-1516734212186-a967f81ad0d7",
        "photo-1517849845537-4d257902454a",
        "photo-1548199973-03cce0bbc87b",
        "photo-1583337130417-3346a1be7dee",
        "photo-1552053831-71594a27632d",
    ],
}

APPOINTMENT = "Olá! Quero agendar um horário"
ENQUIRY = "Olá! Gostaria de falar com vocês"
INFO = "Olá! Gostaria de mais informações"
CONSULT = "Consulte a disponibilidade."

SEGMENT_COPY = {
    "restaurante": {"label": "Restaurante", "palette": "terracota", "lead_in": ENQUIRY, "photos": None, "services": [("Fazer um pedido", "Combine o pedido direto pelo WhatsApp."), ("Tirar uma dúvida", "Pergunte o que precisar antes de ir.")]},
    "lanchonete": {"label": "Lanchonete", "palette": "terracota", "lead_in": ENQUIRY, "photos": None, "services": [("Fazer um pedido", "Combine o pedido direto pelo WhatsApp."), ("Tirar uma dúvida", "Pergunte o que precisar antes de ir.")]},
    "bar": {"label": "Bar", "palette": "ouro", "lead_in": ENQUIRY, "photos": None, "services": [("Fazer um pedido", "Combine direto pelo WhatsApp."), ("Tirar uma dúvida", "Pergunte o que precisar antes de ir.")]},
    "cafe": {"label": "Café", "palette": "terracota", "lead_in": ENQUIRY, "photos": None, "services": [("Fazer um pedido", "Combine o pedido direto pelo WhatsApp."), ("Tirar uma dúvida", "Pergunte o que precisar antes de ir.")]},
    "padaria": {"label": "Padaria", "palette": "terracota", "lead_in": ENQUIRY, "photos": None, "services": [("Fazer uma encomenda", "Combine a encomenda direto pelo WhatsApp."), ("Tirar uma dúvida", "Pergunte o que precisar antes de ir.")]},
    "confeitaria": {"label": "Confeitaria e doceria", "palette": "terracota", "lead_in": ENQUIRY, "photos": None, "services": [("Fazer uma encomenda", "Combine a encomenda direto pelo WhatsApp."), ("Tirar uma dúvida", "Pergunte o que precisar antes de ir.")]},
    "sorveteria": {"label": "Sorveteria", "palette": "terracota", "lead_in": ENQUIRY, "photos": None, "services": [("Fazer um pedido", "Combine direto pelo WhatsApp."), ("Tirar uma dúvida", "Pergunte o que precisar antes de ir.")]},
    "salao": {"label": "Cabelo e beleza", "palette": "ouro", "lead_in": APPOINTMENT, "photos": "beleza", "services": [("Corte", "Corte do seu jeito."), ("Barba", "Contorno, alinhamento e acabamento."), ("Coloração", CONSULT), ("Sobrancelha", "Um detalhe que muda a expressão.")]},
    "dentista": {"label": "Odontologia", "palette": "azul", "lead_in": APPOINTMENT, "photos": None, "services": [("Consulta", CONSULT), ("Limpeza", CONSULT), ("Avaliação", CONSULT)]},
    "clinica": {"label": "Clínica", "palette": "azul", "lead_in": APPOINTMENT, "photos": None, "services": [("Consulta", CONSULT), ("Retorno", CONSULT), ("Informações", CONSULT)]},
    "veterinario": {"label": "Veterinário", "palette": "floresta", "lead_in": APPOINTMENT, "photos": "pet", "services": [("Consulta", CONSULT), ("Vacinação", CONSULT), ("Banho e tosa", CONSULT)]},
    "petshop": {"label": "Pet shop", "palette": "floresta", "lead_in": APPOINTMENT, "photos": "pet", "services": [("Banho", "Cuidado e higiene para o seu pet."), ("Tosa", "Acabamento conforme a pelagem."), ("Banho e tosa", "Os dois em um só horário."), ("Produtos", CONSULT)]},
    "otica": {"label": "Ótica", "palette": "azul", "lead_in": APPOINTMENT, "photos": None, "services": [("Exame de vista", CONSULT), ("Óculos de grau", CONSULT), ("Óculos de sol", CONSULT)]},
    "oficina": {"label": "Oficina mecânica", "palette": "azul", "lead_in": APPOINTMENT, "photos": None, "services": [("Revisão", CONSULT), ("Freios", CONSULT), ("Suspensão", CONSULT), ("Orçamento", CONSULT)]},
    "imobiliaria": {"label": "Imobiliária", "palette": "azul", "lead_in": INFO, "photos": None, "services": [("Comprar", CONSULT), ("Alugar", CONSULT), ("Vender ou anunciar", CONSULT)]},
    "academia": {"label": "Academia", "palette": "floresta", "lead_in": APPOINTMENT, "photos": None, "services": [("Conhecer a academia", CONSULT), ("Planos", CONSULT), ("Horários", CONSULT)]},
}
DEFAULT_COPY = {"label": "Negócio local", "palette": "ouro", "lead_in": INFO, "photos": None, "services": [("Falar com a equipe", CONSULT)]}

STEPS_WHATSAPP = (
    ("Escolha", "Marque o que você precisa, sem explicar tudo por mensagem."),
    ("Envie", "A mensagem sai pronta no WhatsApp, com o seu nome e a sua escolha."),
    ("Combine", "Você e o negócio acertam os detalhes direto na conversa."),
)
STEPS_PHONE = (
    ("Escolha", "Veja as opções e decida o que você precisa."),
    ("Ligue", "Fale direto com o negócio pelo telefone."),
    ("Combine", "Acerte os detalhes durante a ligação."),
)

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700;800;900&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">'
)
ICON_CHAT = '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 .8C7.6.8.8 7.6.8 16c0 2.7.7 5.2 2 7.5L.7 31.2l7.9-2.1c2.2 1.2 4.8 1.9 7.4 1.9 8.4 0 15.2-6.8 15.2-15.2S24.4.8 16 .8Zm0 27.4a12.1 12.1 0 0 1-6.2-1.7l-.5-.3-4.7 1.2 1.3-4.6-.3-.5a12.2 12.2 0 1 1 10.4 5.9Zm6.7-9.1c-.4-.2-2.2-1.1-2.5-1.2-.3-.1-.6-.2-.8.2s-1 1.2-1.2 1.4c-.2.2-.4.3-.8.1s-1.6-.6-3-1.8c-1.1-1-1.8-2.1-2-2.5-.2-.4 0-.6.2-.8l.5-.6.3-.5c.1-.2 0-.5 0-.7s-.8-1.9-1.1-2.6c-.3-.7-.6-.6-.8-.6h-.7c-.2 0-.7.1-1.1.5s-1.4 1.3-1.4 3.2 1.4 3.7 3.4 5.4 5.5 6.1c.8.3 1.5.5 2 .6.8.1 1.5.1 2.1.1.7-.1 2.2-.9 2.5-1.8.3-.9.3-1.7.2-1.8-.2-.2-.4-.3-.8-.5Z"/></svg>'
ICON_CALL = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6.62 10.79a15.05 15.05 0 006.59 6.59l2.2-2.2a1 1 0 011.01-.24c1.12.37 2.33.57 3.58.57a1 1 0 011 1V20a1 1 0 01-1 1A17 17 0 013 4a1 1 0 011-1h3.5a1 1 0 011 1c0 1.25.2 2.46.57 3.58a1 1 0 01-.25 1.01l-2.2 2.2z"/></svg>'

PAGE = Template((TEMPLATES / "vitrine.html").read_text(encoding="utf-8"))
CSS = (TEMPLATES / "vitrine.css").read_text(encoding="utf-8")
SCRIPT = (TEMPLATES / "vitrine.js").read_text(encoding="utf-8")
SCRIPT_HASH = "sha256-" + base64.b64encode(hashlib.sha256(SCRIPT.encode("utf-8")).digest()).decode()
CSP = (
    "default-src 'none'; "
    "style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
    f"script-src '{SCRIPT_HASH}'; img-src https://images.unsplash.com data:; "
    "frame-src https://www.openstreetmap.org; base-uri 'none'; form-action 'none'"
)


def esc(value):
    return html.escape(str(value), quote=True)


def slugify(text):
    return re.sub(r"-+", "-", contacts.text_key(text).replace(" ", "-")).strip("-")


def slug_for(lead, existing):
    base = slugify(lead["name"])[:50]
    if len(base) < 3:
        base = f"negocio-{base}".strip("-")
    with_place = f"{base}-{slugify(lead['neighborhood'])}"[:60].strip("-")
    for candidate in (base, with_place):
        if SLUG_RE.match(candidate) and candidate not in existing:
            return candidate
    number = 2
    while f"{with_place[:56]}-{number}" in existing:
        number += 1
    return f"{with_place[:56]}-{number}"


def instagram_handle(value):
    text = (value or "").strip()
    if not text:
        return ""
    if "://" in text or "instagram.com" in text or "instagr.am" in text:
        parts = urlsplit(text if "://" in text else f"https://{text}")
        text = next((piece for piece in parts.path.split("/") if piece), "")
    text = text.lstrip("@")
    return text if HANDLE_RE.fullmatch(text) else ""


def whatsapp_digits(lead):
    manual = re.sub(r"\D", "", lead.get("manual_whatsapp") or "")
    if len(manual) in (10, 11):
        return f"55{manual}"
    if lead.get("phone_kind") == "celular" and lead.get("phone_national"):
        return f"55{lead['phone_national']}"
    return ""


def phone_link(lead):
    national, kind = lead.get("phone_national"), lead.get("phone_kind")
    if not national:
        return ""
    return f"tel:+55{national}" if kind in ("celular", "fixo") else f"tel:{national}"


def clean_text(value, limit):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def clean_services(items):
    cleaned = []
    for item in items or []:
        name = clean_text(item.get("name"), 60)
        if name:
            cleaned.append({"name": name, "text": clean_text(item.get("text"), 160), "model": False})
    return cleaned[:8]


def clean_menu(items):
    cleaned = []
    for item in items or []:
        name = clean_text(item.get("name"), 60)
        if name:
            cleaned.append({"name": name, "price": clean_text(item.get("price"), 20)})
    return cleaned[:40]


def content_for(lead, overrides=None):
    overrides = overrides or {}
    copy = SEGMENT_COPY.get(lead["segment"], DEFAULT_COPY)
    national = lead.get("phone_national")
    kind = lead.get("phone_kind")
    is_food = lead["segment"] in scoring.FOOD_SEGMENTS
    services = clean_services(overrides.get("services")) or [
        {"name": name, "text": text, "model": True} for name, text in copy["services"]
    ]
    photos = PHOTOS.get(copy["photos"], [])
    return {
        "segment": lead["segment"],
        "name": clean_text(overrides.get("name"), 80) or lead["name"],
        "category": clean_text(overrides.get("category"), 40) or copy["label"],
        "neighborhood": lead["neighborhood"],
        "city": lead.get("city") or "",
        "address": clean_text(overrides.get("address"), 160) or lead.get("address") or "",
        "hours": clean_text(overrides.get("hours"), 120),
        "phone_text": contacts.format_phone(national) if national and kind in ("celular", "fixo", "outro") else "",
        "phone_link": phone_link(lead),
        "whatsapp": whatsapp_digits(lead),
        "instagram": instagram_handle(lead.get("instagram")),
        "lat": lead.get("lat"),
        "lon": lead.get("lon"),
        "services": services,
        "menu": clean_menu(overrides.get("menu")) if is_food else [],
        "is_food": is_food,
        "lead_in": copy["lead_in"],
        "palette": copy["palette"],
        "photos": list(photos),
    }


def map_url(content):
    place = ", ".join(part for part in (content["address"], content["neighborhood"], content["city"]) if part)
    return "https://www.google.com/maps/search/?api=1&query=" + quote(f"{content['name']} {place}")


def reviews_url(content):
    return "https://www.google.com/maps/search/?api=1&query=" + quote(
        f"{content['name']} {content['neighborhood']} {content['city']}"
    )


def primary_action(content):
    if content["whatsapp"]:
        return f"https://wa.me/{content['whatsapp']}", "Chamar no WhatsApp", True
    if content["phone_link"]:
        return content["phone_link"], "Ligar agora", False
    return map_url(content), "Como chegar", False


def palette_css(content):
    colors = PALETTES[content["palette"]]
    rules = [
        ":root{" + "".join(f"--{key.replace('_', '-')}:{value};" for key, value in colors.items())
        + "--line:color-mix(in srgb, var(--paper) 14%, transparent);}"
    ]
    if content["photos"]:
        photo = f"https://images.unsplash.com/{content['photos'][0]}?auto=format&fit=crop&w=1400&q=85"
        rules.append(
            ".hero-photo{background:linear-gradient(90deg,color-mix(in srgb, var(--ink) 90%, transparent),"
            f"color-mix(in srgb, var(--ink) 55%, transparent)),url('{photo}') 50% 35% / cover;}}"
        )
    else:
        rules.append(
            ".hero-photo{background:radial-gradient(90% 120% at 85% 20%,color-mix(in srgb, var(--gold) 28%, transparent),transparent 60%),"
            "linear-gradient(135deg,var(--ink),var(--coffee));}"
        )
    return "\n".join(rules)


def brand_parts(content):
    words = content["name"].split()
    initials = "".join(word[0] for word in words[:2] if word[0].isalnum()).upper() or "•"
    first = words[0] if words else content["name"]
    rest = " ".join(words[1:]) or content["category"]
    return initials, first, rest


def nav_links(content):
    items = [("#servicos", "Cardápio" if content["menu"] else "Serviços"), ("#como", "Como funciona")]
    if content["photos"]:
        items.append(("#galeria", "Galeria"))
    items += [("#avaliacoes", "Avaliações"), ("#agendar", "Contato")]
    return items


def header_html(content):
    initials, first, rest = brand_parts(content)
    links = nav_links(content)
    url, text, _ = primary_action(content)
    desktop = "".join(f'<a href="{href}">{label}</a>' for href, label in links)
    mobile = "".join(f'<a href="{href}">{label}</a>' for href, label in links)
    return (
        '<header class="top"><div class="wrap nav">'
        f'<a class="brand" href="#inicio" aria-label="{esc(content["name"])}"><span class="mark"><span class="display">{esc(initials)}</span></span>'
        f'<span class="brand-name display">{esc(first)} <small>{esc(rest)}</small></span></a>'
        f'<nav class="links" aria-label="Principal">{desktop}</nav>'
        f'<a class="btn gold small" href="#agendar">Contato <span aria-hidden="true">↗</span></a>'
        '<button class="menu-btn" type="button" data-menu-button aria-expanded="false" aria-controls="menu" aria-label="Menu">'
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 6h18M3 12h18M3 18h18"/></svg></button>'
        f'</div><div class="menu" id="menu" data-menu hidden>{mobile}</div></header>'
    )


def hero_html(content):
    url, text, is_whatsapp = primary_action(content)
    long = " long" if len(content["category"]) > 16 else ""
    lead_text = (
        "Escolha o serviço e chame no WhatsApp com a mensagem já escrita."
        if content["whatsapp"]
        else "Veja as opções e fale direto com o negócio."
    )
    if content["menu"]:
        lead_text = "Veja o cardápio e fale direto com o negócio."
    first = (
        '<a class="btn gold" href="#agendar">Montar minha mensagem <span aria-hidden="true">↗</span></a>'
        if content["whatsapp"]
        else f'<a class="btn gold" href="{esc(url)}">{esc(text)} <span aria-hidden="true">↗</span></a>'
    )
    second = (
        f'<a class="btn line" href="{esc(map_url(content))}">Como chegar</a>'
        if url != map_url(content)
        else ""
    )
    tag = '<span class="photo-tag">Imagem ilustrativa</span>' if content["photos"] else ""
    place = " · ".join(part for part in (content["neighborhood"], content["city"]) if part)
    return (
        '<section class="hero grain" id="inicio"><div class="hero-photo"></div>'
        '<div class="wrap hero-copy"><div>'
        f'<p class="eyebrow gold-line" style="color:var(--gold);margin:0 0 1.6rem">{esc(place)}</p>'
        f'<h1 class="display{long}">{esc(content["category"])}<br><span class="g">EM {esc(content["neighborhood"])}.</span></h1>'
        f'<p class="lead">{esc(lead_text)}</p>'
        f'<div class="cta">{first}{second}</div>'
        f'</div></div>{tag}</section>'
    )


def strip_html(content):
    items = [content["category"]]
    street = ", ".join(part for part in (content["address"], content["neighborhood"]) if part)
    if street:
        items.append(street)
    if content["hours"]:
        items.append(content["hours"])
    if content["phone_text"]:
        items.append(f"{'WhatsApp' if content['whatsapp'] else 'Telefone'} {content['phone_text']}")
    return '<div class="strip"><div class="wrap">' + "".join(f"<span>{esc(item)}</span>" for item in items) + "</div></div>"


def heading(first, second, eyebrow, tone="", note=""):
    return (
        f'<div class="head"><div><p class="eyebrow gold-line {tone}" style="margin:0 0 1rem">{eyebrow}</p>'
        f'<h2 class="display">{esc(first)}<br><span class="g">{esc(second)}</span></h2></div>{note}</div>'
    )


def services_html(content):
    model = '<span class="model">MODELO</span>'
    if content["menu"]:
        rows = "".join(
            f'<div class="svc reveal"><span class="n">{i:02d}</span><div><h3>{esc(item["name"])}</h3></div>'
            f'<span class="price">{esc(item["price"])}</span></div>'
            for i, item in enumerate(content["menu"], 1)
        )
        head = heading("O", "CARDÁPIO.", "Cardápio")
        footer = ""
    else:
        any_model = any(item["model"] for item in content["services"])
        rows = "".join(
            f'<a class="svc reveal" href="#agendar" data-service-link="{esc(item["name"])}"><span class="n">{i:02d}</span>'
            f'<div><h3>{esc(item["name"])}{model if item["model"] else ""}</h3>'
            + (f'<p>{esc(item["text"])}</p>' if item["text"] else "")
            + '</div><span class="go" aria-hidden="true">↗</span></a>'
            for i, item in enumerate(content["services"], 1)
        )
        if content["is_food"]:
            first, second = ("PEÇA", "PELO WHATSAPP.") if content["whatsapp"] else ("FALE", "COM A GENTE.")
        else:
            first, second = "ESCOLHA", "O SERVIÇO."
        head = heading(first, second, f"Serviços {model}" if any_model else "Serviços", note="<p>Clique em uma opção e a mensagem sai pronta.</p>" if content["whatsapp"] else "")
        footer = '<p class="note">Lista de exemplo para esta prévia. Os serviços e valores reais entram aqui depois que você confirmar.</p>' if any_model else ""
    return f'<section class="block paper" id="servicos"><div class="wrap">{head}<div class="services">{rows}</div>{footer}</div></section>'


def steps_html(content):
    steps = STEPS_WHATSAPP if content["whatsapp"] else STEPS_PHONE
    cards = "".join(
        f'<div class="step reveal"><div class="n">{i}</div><h3>{esc(title)}</h3><p>{esc(text)}</p></div>'
        for i, (title, text) in enumerate(steps, 1)
    )
    note = "<p>O cliente chega no WhatsApp já com o pedido escrito.</p>" if content["whatsapp"] else ""
    head = heading("DO CLIQUE", "À CONVERSA.", "Como funciona", "eyebrow gd", note)
    return f'<section class="block coffee" id="como"><div class="wrap">{head}<div class="steps">{cards}</div></div></section>'


def gallery_html(content):
    if not content["photos"]:
        return ""
    model = '<span class="model">MODELO</span>'
    figures = "".join(
        f'<figure><img loading="lazy" alt="Imagem ilustrativa de {esc(content["category"].lower())}" '
        f'src="https://images.unsplash.com/{photo}?auto=format&amp;fit=crop&amp;w=900&amp;q=80"></figure>'
        for photo in content["photos"][:5]
    )
    head = heading("O VISUAL", "FALA.", f"Galeria {model}", "eyebrow gd", "<p>Aqui entram as fotos reais do espaço e dos trabalhos.</p>")
    return (
        f'<section class="block" id="galeria"><div class="wrap">{head}<div class="gallery reveal">{figures}</div>'
        f'<p class="note">Imagens ilustrativas. Serão substituídas por fotos reais de {esc(content["name"])}.</p></div></section>'
    )


def reviews_html(content):
    head = heading("QUEM VEM,", "AVALIA.", "Reputação")
    return (
        f'<section class="block paper" id="avaliacoes"><div class="wrap">{head}'
        f'<a class="review reveal" target="_blank" rel="noopener noreferrer" href="{esc(reviews_url(content))}">'
        f'<h3>{esc(content["name"])}</h3><p>Veja o que os clientes dizem sobre {esc(content["name"])} direto no Google Maps.</p>'
        '<span class="more">Ver avaliações no Google ↗</span></a></div></section>'
    )


def map_block(content):
    if content["lat"] is None or content["lon"] is None:
        return ""
    lat, lon = content["lat"], content["lon"]
    bbox = f"{lon - 0.004},{lat - 0.0028},{lon + 0.004},{lat + 0.0028}"
    src = f"https://www.openstreetmap.org/export/embed.html?bbox={bbox}&amp;layer=mapnik&amp;marker={lat},{lon}"
    return (
        f'<div class="map"><iframe title="Mapa de {esc(content["name"])}" loading="lazy" src="{src}"></iframe>'
        '<span class="attr">© Contribuidores do OpenStreetMap</span></div>'
    )


def book_html(content):
    model = '<span class="model">MODELO</span>'
    map_part = map_block(content)
    solo = "" if map_part else " solo"
    if content["whatsapp"]:
        picks = "".join(
            f'<button class="pick" type="button" data-pick="{esc(item["name"])}" aria-pressed="false">{esc(item["name"])} <span aria-hidden="true">↗</span></button>'
            for item in content["services"]
        )
        any_model = any(item["model"] for item in content["services"])
        form = (
            f'<div class="form" data-builder data-phone="{esc(content["whatsapp"])}" data-lead-in="{esc(content["lead_in"])}">'
            f'<p class="eyebrow" style="margin:0;opacity:.6">01 / Escolha {model if any_model else ""}</p>'
            f'<div class="picks">{picks}</div>'
            '<label class="eyebrow" style="opacity:.6" for="cliente">02 / Seu nome (opcional)</label>'
            '<input class="field" id="cliente" data-client maxlength="40" placeholder="Como podemos te chamar?">'
            '<div class="bubble"><small>Mensagem que o cliente envia</small><span data-preview></span></div>'
            '<a class="btn gold wide" data-send href="#" target="_blank" rel="noopener noreferrer">Enviar pelo WhatsApp <span aria-hidden="true">↗</span></a></div>'
        )
        title = ("FALE", "COM A GENTE.") if content["is_food"] or content["segment"] == "imobiliaria" else ("RESERVE", "SEU HORÁRIO.")
    else:
        lines = []
        if content["phone_text"]:
            lines.append(f'<p>Telefone: {esc(content["phone_text"])}</p>')
        street = ", ".join(part for part in (content["address"], content["neighborhood"]) if part)
        if street:
            lines.append(f"<p>{esc(street)}</p>")
        action = (
            f'<a class="btn gold wide" href="{esc(content["phone_link"])}">Ligar agora <span aria-hidden="true">↗</span></a>'
            if content["phone_link"]
            else f'<a class="btn gold wide" href="{esc(map_url(content))}">Como chegar <span aria-hidden="true">↗</span></a>'
        )
        form = f'<div class="form contact-card">{"".join(lines)}{action}</div>'
        title = ("FALE", "COM A GENTE.")
    head = heading(title[0], title[1], "Contato", "eyebrow gd")
    return (
        f'<section class="block coffee" id="agendar"><div class="wrap">{head}'
        f'<div class="book reveal{solo}">{form}{map_part}</div></div></section>'
    )


def final_html(content):
    url, text, _ = primary_action(content)
    return (
        '<section class="final"><div class="wrap"><h2 class="display">VAMOS<br>CONVERSAR?</h2>'
        f'<a class="btn" href="{esc(url)}">{esc(text)} <span aria-hidden="true">↗</span></a></div></section>'
    )


def footer_html(content, preview, year):
    initials, first, rest = brand_parts(content)
    street = ", ".join(part for part in (content["address"], content["neighborhood"]) if part)
    label = "Endereço" if content["address"] else "Local"
    address = (
        f'<div><h3 class="eyebrow">{label}</h3><p>{esc(street)}<br>{esc(content["city"])}</p>'
        f'<p style="margin-top:.8rem"><a href="{esc(map_url(content))}">Abrir no mapa ↗</a></p></div>'
        if street
        else "<div></div>"
    )
    contact = []
    if content["phone_text"] and content["phone_link"]:
        contact.append(f'<a href="{esc(content["phone_link"])}">{esc(content["phone_text"])}</a>')
    if content["instagram"]:
        contact.append(f'<a href="https://instagram.com/{esc(content["instagram"])}" target="_blank" rel="noopener noreferrer">@{esc(content["instagram"])} ↗</a>')
    if content["hours"]:
        contact.append(esc(content["hours"]))
    contact_block = f'<div><h3 class="eyebrow">Contato</h3><p>{"<br>".join(contact)}</p></div>' if contact else "<div></div>"
    legal = (
        f"Página de demonstração criada para {esc(content['name'])}."
        if preview
        else f"© {year} {esc(content['name'])}."
    )
    return (
        '<footer><div class="wrap"><div class="foot">'
        f'<div><div class="display" style="font-size:3.4rem">{esc(first.upper())}<br><span style="color:var(--gold)">{esc(rest.upper())}.</span></div></div>'
        f'{address}{contact_block}</div>'
        f'<div class="legal"><span>{legal}</span><span>Mapa: © Contribuidores do OpenStreetMap</span></div></div></footer>'
    )


def fab_html(content):
    url, text, is_whatsapp = primary_action(content)
    if is_whatsapp:
        return f'<a class="fab" href="{esc(url)}" aria-label="{esc(text)}">{ICON_CHAT}</a>'
    if content["phone_link"]:
        return f'<a class="fab call" href="{esc(url)}" aria-label="{esc(text)}">{ICON_CALL}</a>'
    return ""


def render(content, preview, year=None):
    year = year or date.today().year
    banner = (
        f'<div class="preview">Prévia criada para <b>{esc(content["name"])}</b>. '
        "Textos, serviços e imagens marcados como modelo são exemplos para você aprovar e ajustar.</div>"
        if preview
        else ""
    )
    robots = '<meta name="robots" content="noindex, nofollow">' if preview else ""
    page = PAGE.substitute(
        csp=esc(CSP),
        robots=robots,
        theme_color=PALETTES[content["palette"]]["ink"],
        title=esc(content["name"]),
        fonts=FONTS,
        css=CSS,
        palette=palette_css(content),
        banner=banner,
        header=header_html(content),
        hero=hero_html(content),
        strip=strip_html(content),
        sections="".join(
            (services_html(content), steps_html(content), gallery_html(content), reviews_html(content), book_html(content))
        ),
        final=final_html(content),
        footer=footer_html(content, preview, year),
        fab=fab_html(content),
        script=SCRIPT,
    )
    return page.replace("<body>", "<body>" if preview else '<body class="approved">', 1)


def field(value, origin, when):
    return {"valor": value, "origem": origin, "data": when}


def client_files(lead, vitrine, content):
    manual_when = lead.get("manual_checked_at")
    seen = lead.get("source_seen_at")
    edited = vitrine["updated_at"]
    known = {
        "nome": field(content["name"], "manual" if vitrine["content"].get("name") else "osm", edited if vitrine["content"].get("name") else seen),
        "segmento": field(content["category"], "manual" if vitrine["content"].get("category") else "osm", edited if vitrine["content"].get("category") else seen),
        "bairro": field(lead["neighborhood"], "osm", seen),
        "cidade": field(lead.get("city"), "osm", seen),
        "endereco": field(content["address"], "manual" if vitrine["content"].get("address") else "osm", edited if vitrine["content"].get("address") else seen),
        "telefone": field(content["phone_text"], "manual" if lead.get("manual_phone") else "osm", manual_when if lead.get("manual_phone") else seen),
        "whatsapp": field(
            content["whatsapp"],
            "manual" if lead.get("manual_whatsapp") else "osm (celular, WhatsApp não confirmado)",
            manual_when if lead.get("manual_whatsapp") else seen,
        ),
        "instagram": field(content["instagram"], "manual" if lead.get("manual_instagram") else "osm", manual_when if lead.get("manual_instagram") else seen),
        "site": field(lead.get("website"), "manual" if lead.get("manual_website") else "osm", manual_when if lead.get("manual_website") else seen),
        "horario": field(content["hours"], "manual", edited),
        "coordenadas": field({"lat": content["lat"], "lon": content["lon"]} if content["lat"] is not None else None, "osm", seen),
    }
    present = {key: value for key, value in known.items() if value["valor"]}
    missing = [key for key in ("endereco", "telefone", "whatsapp", "instagram", "horario") if key not in present]
    registered_services = [item for item in content["services"] if not item["model"]]
    data = {
        "aviso": "Todo campo aqui tem origem e data. O que não está aqui não foi registrado: não invente.",
        "slug": vitrine["slug"],
        "campos": present,
        "campos_ausentes": missing,
        "servicos_cadastrados": [{"nome": item["name"], "texto": item["text"]} for item in registered_services],
        "cardapio_cadastrado": content["menu"],
        "vitrine_aprovada": vitrine["approved"],
    }
    prompt = PROMPT_TEMPLATE.substitute(slug=vitrine["slug"], nome=content["name"])
    return {"dados.json": json.dumps(data, ensure_ascii=False, indent=2), "PROMPT.md": prompt}


PROMPT_TEMPLATE = Template(
    """# Personalizar a vitrine de $nome

Leia `dados.json` nesta pasta. Ele tem tudo o que sabemos do negócio, com a origem e a data de cada campo.

## Regras

1. **Use só os dados de `dados.json`.** Não invente preço, depoimento, nota ou número de avaliações, horário, anos de mercado, número de clientes, nome de equipe nem serviço. Fato que falta vira `[PREENCHER: o que falta]` no texto, e vai para a lista de perguntas ao dono.
2. Nada de foto do negócio que não tenha sido enviada pelo dono. Imagem de banco de fotos só como ilustração, sempre com a legenda "Imagem ilustrativa".
3. O WhatsApp só vale se `whatsapp` tiver origem `manual` ou se for celular. Mesmo assim, "WhatsApp não confirmado" significa que o botão pode não funcionar: avise no relatório.
4. HTML e CSS estáticos, sem build. JavaScript só para interação, nunca com dado do negócio dentro do código, e sem chamar serviços externos além de fontes, mapa e imagens ilustrativas já usados na vitrine base.
5. Todo texto vindo de `dados.json` deve ser escapado. Links montados por você, nunca copiados de campo livre.
6. Enquanto o dono não aprovar: faixa fixa "Prévia criada para $nome" e `<meta name="robots" content="noindex, nofollow">`.
7. Não publique nada e não envie mensagem a ninguém. Quem publica e envia é o Matheus, à mão.

## Base

A vitrine automática está na prévia local (`/s/$slug`). Use como ponto de partida e melhore o texto, a organização e o visual com os dados reais.

## Entrega

Grave o site em `site/` e termine com `site/RELATORIO.md` contendo: o que perguntar ao dono, o que conferir antes de enviar, e todo campo marcado `[PREENCHER]`.
"""
)
