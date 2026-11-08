import base64
import hashlib
import json
import re
from html.parser import HTMLParser

import pytest

import vitrines

PAYLOADS = ['<script>alert(1)</script>', '"><img src=x onerror=alert(1)>', "A & B 'aspas'"]


def lead(**overrides):
    base = {
        "id": "node-1",
        "name": "Janis Bull Barbearia",
        "segment": "salao",
        "neighborhood": "Vila Mariana",
        "city": "São Paulo",
        "address": "Rua Doutor Nicolau de Sousa Queirós",
        "phone_national": "11980150754",
        "phone_kind": "celular",
        "manual_whatsapp": None,
        "instagram": None,
        "lat": -23.5776824,
        "lon": -46.6397332,
    }
    base.update(overrides)
    return base


def html_of(lead_data=None, overrides=None, preview=True, year=2026):
    content = vitrines.content_for(lead_data or lead(), overrides)
    return vitrines.render(content, preview, year)


def inline_scripts(page):
    return re.findall(r"<script>(.*?)</script>", page, re.S)


def markup(page):
    return re.sub(r"<script>.*?</script>", "", page, flags=re.S)


class Attributes(HTMLParser):
    def __init__(self):
        super().__init__()
        self.found = []

    def handle_starttag(self, tag, attrs):
        self.found.extend((tag, name, value) for name, value in attrs)


def attributes(page):
    parser = Attributes()
    parser.feed(page)
    return parser.found


def event_attributes(page):
    return [item for item in attributes(page) if item[1].startswith("on")]


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Janis Bull Barbearia", "janis-bull-barbearia"),
        ("Café São José!", "cafe-sao-jose"),
        ("  Padaria   do   Zé  ", "padaria-do-ze"),
        ("Bar & Grill 24h", "bar-grill-24h"),
    ],
)
def test_slug_normalizes_accents_spaces_and_symbols(name, expected):
    assert vitrines.slug_for(lead(name=name), set()) == expected


def test_slug_with_a_clash_gets_the_neighborhood_and_then_a_number():
    first = vitrines.slug_for(lead(), set())
    second = vitrines.slug_for(lead(), {first})
    third = vitrines.slug_for(lead(), {first, second})

    assert (first, second, third) == ("janis-bull-barbearia", "janis-bull-barbearia-vila-mariana", "janis-bull-barbearia-vila-mariana-2")


@pytest.mark.parametrize("name", ["A", "!!!", "ÁÉ", "x" * 200, "../../etc/passwd", "Nome/Com Barra"])
def test_slug_always_matches_the_allowed_pattern(name):
    slug = vitrines.slug_for(lead(name=name), set())

    assert vitrines.SLUG_RE.match(slug)


def test_slug_stays_inside_the_limit_even_with_many_clashes():
    existing = set()
    for _ in range(5):
        existing.add(vitrines.slug_for(lead(name="x" * 200, neighborhood="y" * 80), existing))

    assert all(vitrines.SLUG_RE.match(slug) for slug in existing)
    assert len(existing) == 5


def test_whatsapp_comes_from_a_mobile_phone_or_from_the_manual_field():
    assert vitrines.whatsapp_digits(lead()) == "5511980150754"
    assert vitrines.whatsapp_digits(lead(phone_kind="fixo", phone_national="1138152600")) == ""
    assert vitrines.whatsapp_digits(lead(phone_kind="fixo", phone_national="1138152600", manual_whatsapp="1138152600")) == "551138152600"
    assert vitrines.whatsapp_digits(lead(manual_whatsapp="11911112222")) == "5511911112222"
    assert vitrines.whatsapp_digits(lead(phone_kind="outro", phone_national="08001234567")) == ""
    assert vitrines.whatsapp_digits(lead(phone_national=None, phone_kind=None)) == ""


@pytest.mark.parametrize(
    "value, expected",
    [
        ("@janis.bull", "janis.bull"),
        ("janisbull", "janisbull"),
        ("https://www.instagram.com/janisbullbarbearia/", "janisbullbarbearia"),
        ("instagram.com/janis_bull?igsh=abc", "janis_bull"),
        ("https://instagram.com/", ""),
        ('x"><script>', ""),
        ("", ""),
        (None, ""),
    ],
)
def test_instagram_handle(value, expected):
    assert vitrines.instagram_handle(value) == expected


def test_content_uses_model_services_until_real_ones_are_registered():
    model = vitrines.content_for(lead())
    real = vitrines.content_for(lead(), {"services": [{"name": "Corte social", "text": "Na tesoura"}]})

    assert model["services"] and all(item["model"] for item in model["services"])
    assert [(item["name"], item["model"]) for item in real["services"]] == [("Corte social", False)]


def test_content_overrides_are_cleaned_and_limited():
    content = vitrines.content_for(
        lead(),
        {
            "name": "  Nome   Novo  ",
            "category": "x" * 100,
            "address": "Rua A,   10",
            "hours": "10h às 20h" + "!" * 300,
            "services": [{"name": "   ", "text": "sem nome"}, {"name": "Barba", "text": "t" * 500}] + [{"name": f"s{i}"} for i in range(20)],
            "inexistente": "ignorado",
        },
    )

    assert content["name"] == "Nome Novo"
    assert len(content["category"]) == 40
    assert content["address"] == "Rua A, 10"
    assert len(content["hours"]) == 120
    assert len(content["services"]) == 8
    assert content["services"][0]["name"] == "Barba" and len(content["services"][0]["text"]) == 160
    assert "inexistente" not in content


def test_menu_is_kept_only_for_food_segments():
    items = [{"name": "Feijoada", "price": "R$ 40"}]

    assert vitrines.content_for(lead(segment="restaurante"), {"menu": items})["menu"] == items
    assert vitrines.content_for(lead(segment="salao"), {"menu": items})["menu"] == []


def test_phone_is_shown_only_when_it_is_valid():
    assert vitrines.content_for(lead(phone_kind="invalido", phone_national=None))["phone_text"] == ""
    assert vitrines.content_for(lead())["phone_text"] == "(11) 98015-0754"


@pytest.mark.parametrize("payload", PAYLOADS)
def test_every_text_from_the_lead_and_from_edits_is_escaped(payload):
    page = html_of(
        lead(name=payload, address=payload, neighborhood=payload, city=payload, instagram="x"),
        {"category": payload, "hours": payload, "services": [{"name": payload, "text": payload}]},
    )

    assert len(inline_scripts(page)) == 1
    assert "alert(1)" not in inline_scripts(page)[0]
    assert "<img src=x" not in page
    assert "<script>alert" not in page
    assert event_attributes(page) == []
    assert not any(tag == "img" and name == "src" and value == "x" for tag, name, value in attributes(page))
    assert "&lt;" in page or "&amp;" in page


def test_food_menu_items_and_prices_are_escaped():
    page = html_of(lead(segment="restaurante"), {"menu": [{"name": PAYLOADS[1], "price": PAYLOADS[0]}]})

    assert "<img src=x" not in page and "<script>alert" not in page


def test_page_has_a_single_fixed_script_and_the_csp_allows_exactly_its_hash():
    page = html_of()
    script = inline_scripts(page)[0]
    expected = "sha256-" + base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode()
    csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', page).group(1)

    assert len(inline_scripts(page)) == 1
    assert f"script-src '{expected}'" in csp.replace("&#x27;", "'")
    assert csp.startswith("default-src &#x27;none&#x27;")
    assert "unsafe-eval" not in csp and "script-src &#x27;unsafe-inline" not in csp


def test_script_is_identical_for_every_page_so_it_never_carries_lead_data():
    first = inline_scripts(html_of(lead(name="Um")))[0]
    second = inline_scripts(html_of(lead(name="Dois", segment="petshop", phone_kind="fixo", phone_national="1138152600")))[0]

    assert first == second == vitrines.SCRIPT


def test_page_has_no_event_attributes_javascript_urls_or_external_scripts():
    page = html_of(lead(instagram="@janis"), {"hours": "10h às 20h"})

    assert event_attributes(page) == []
    assert "javascript:" not in page.lower()
    assert not re.search(r"<script[^>]+src=", page)
    assert all('rel="noopener noreferrer"' in tag for tag in re.findall(r'<a [^>]*target="_blank"[^>]*>', page))


def test_unapproved_page_has_the_banner_noindex_and_the_demo_footer():
    page = html_of(preview=True)

    assert "Prévia criada para <b>Janis Bull Barbearia</b>" in page
    assert '<meta name="robots" content="noindex, nofollow">' in page
    assert "Página de demonstração criada para Janis Bull Barbearia." in page
    assert "<body>" in page


def test_approved_page_has_no_banner_no_noindex_and_a_normal_footer():
    page = html_of(preview=False, year=2027)

    assert "Prévia criada para" not in page
    assert "noindex" not in page
    assert "Página de demonstração" not in page
    assert "© 2027 Janis Bull Barbearia." in page
    assert '<body class="approved">' in page


def test_mobile_phone_gets_the_whatsapp_button_and_the_message_builder():
    page = html_of()

    assert "Chamar no WhatsApp" in page
    assert 'href="https://wa.me/5511980150754"' in page
    assert 'data-builder data-phone="5511980150754"' in page
    assert "data-lead-in=" in page and "Olá! Quero agendar um horário" in page
    assert "Montar minha mensagem" in page


def test_landline_gets_a_call_button_and_no_whatsapp_or_builder():
    page = html_of(lead(phone_kind="fixo", phone_national="1138152600"))

    assert "Ligar agora" in page
    assert 'href="tel:+551138152600"' in page
    assert "wa.me" not in markup(page)
    assert "data-builder" not in markup(page)
    assert "WhatsApp" not in markup(page)
    assert 'class="fab call"' in page


def test_manual_whatsapp_on_a_landline_enables_the_whatsapp_button():
    page = html_of(lead(phone_kind="fixo", phone_national="1138152600", manual_whatsapp="1138152600"))

    assert 'href="https://wa.me/551138152600"' in page and "data-builder" in page


def test_without_any_phone_the_page_still_renders_with_a_map_action_only():
    page = html_of(lead(phone_kind=None, phone_national=None))

    assert "wa.me" not in markup(page) and "tel:" not in markup(page) and "data-builder" not in markup(page)
    assert "Como chegar" in page
    assert 'class="fab' not in page


def test_sections_without_data_are_left_out():
    page = html_of(lead(address=None, instagram=None, lat=None, lon=None, segment="oficina"))

    assert "<iframe" not in page
    assert "instagram.com/" not in page
    assert "Endereço" not in page
    assert 'id="galeria"' not in page
    assert "Imagem ilustrativa" not in page


def test_hours_appear_only_when_registered():
    assert "10h às 20h" not in html_of()
    assert "Segunda a sábado, 10h às 20h" in html_of(overrides={"hours": "Segunda a sábado, 10h às 20h"})


def test_instagram_link_is_built_by_the_code_from_the_handle():
    page = html_of(lead(instagram="https://www.instagram.com/janisbull/"))

    assert 'href="https://instagram.com/janisbull"' in page


def test_map_uses_the_openstreetmap_embed_with_the_lead_coordinates():
    page = html_of()

    assert "https://www.openstreetmap.org/export/embed.html?bbox=" in page
    assert "marker=-23.5776824,-46.6397332" in page
    assert "© Contribuidores do OpenStreetMap" in page


def test_beauty_and_pet_segments_get_a_photo_gallery_marked_as_illustrative():
    for segment in ("salao", "petshop", "veterinario"):
        page = html_of(lead(segment=segment))
        assert 'id="galeria"' in page
        assert "Imagem ilustrativa" in page
        assert "images.unsplash.com/" in page
        assert page.count('<span class="model">MODELO</span>') >= 2


def test_segments_without_configured_photos_get_a_plain_hero_and_no_gallery():
    page = html_of(lead(segment="dentista"))

    assert 'id="galeria"' not in page
    assert "images.unsplash.com" not in page.split("<style>")[1].split("</style>")[0]


def test_model_services_are_marked_and_registered_ones_are_not():
    assert html_of().count('<span class="model">MODELO</span>') >= 4
    page = html_of(overrides={"services": [{"name": "Corte social"}]})
    services = page.split('id="servicos"')[1].split('id="como"')[0]

    assert "MODELO" not in services
    assert "Lista de exemplo" not in services


def test_food_without_menu_says_order_by_whatsapp_and_has_no_menu_section():
    page = html_of(lead(segment="restaurante"))

    assert "PEÇA" in page and "PELO WHATSAPP." in page
    assert "CARDÁPIO" not in page


def test_food_with_menu_lists_items_with_registered_prices_only():
    page = html_of(lead(segment="restaurante"), {"menu": [{"name": "Feijoada", "price": "R$ 40"}, {"name": "Suco"}]})
    menu = page.split('id="servicos"')[1].split('id="como"')[0]

    assert "CARDÁPIO." in menu and "Feijoada" in menu and "R$ 40" in menu and "Suco" in menu
    assert menu.count('class="price"') == 2
    assert menu.count("R$") == 1


def test_health_segments_use_neutral_text_without_result_promises():
    for segment in ("dentista", "clinica", "veterinario"):
        page = html_of(lead(segment=segment))
        assert not re.search(r"melhor|garant|resultado|sem dor|cura|tratamento", markup(page), re.I)


def test_page_never_invents_ratings_hours_prices_or_years():
    page = html_of()
    visible = re.sub(r"<style>.*?</style>|<script>.*?</script>", "", page, flags=re.S)

    assert "★" not in visible
    assert not re.search(r"\d[,.]\d\s*/\s*5", visible)
    assert not re.search(r"R\$\s*\d", visible)
    assert not re.search(r"há\s+\d+\s+anos|desde\s+\d{4}|\d+\s+anos", visible, re.I)
    assert not re.search(r"\d{1,2}h\s*(às|-|–)\s*\d{1,2}h", visible)
    assert "Ver avaliações no Google" in visible


def test_hero_states_the_category_and_the_neighborhood_without_promises():
    page = html_of()

    assert "Cabelo e beleza<br><span class=\"g\">EM Vila Mariana.</span>" in page


def test_long_category_names_get_a_smaller_hero():
    assert 'class="display long"' in html_of(lead(segment="confeitaria"))
    assert 'class="display long"' not in html_of(lead(segment="salao"))


def test_unknown_segment_falls_back_to_a_neutral_page():
    page = html_of(lead(segment="inventado"))

    assert "Negócio local" in page and "MODELO" in page


def test_each_segment_has_a_known_palette_and_a_real_label():
    for key, copy in vitrines.SEGMENT_COPY.items():
        assert copy["palette"] in vitrines.PALETTES
        assert copy["label"].strip() and copy["services"]


def test_every_overpass_segment_has_vitrine_copy():
    import overpass

    assert set(overpass.SEGMENTS) <= set(vitrines.SEGMENT_COPY)


def vitrine_record(**overrides):
    base = {"slug": "janis-bull", "approved": False, "content": {}, "updated_at": "2026-11-08 10:00:00"}
    base.update(overrides)
    return base


def full_lead(**overrides):
    return {
        **lead(),
        "website": None,
        "manual_phone": None,
        "manual_instagram": None,
        "manual_website": None,
        "manual_checked_at": None,
        "source_seen_at": "2026-11-03 20:00:00",
        **overrides,
    }


def test_client_folder_has_exactly_the_two_files():
    data = full_lead()
    files = vitrines.client_files(data, vitrine_record(), vitrines.content_for(data))

    assert set(files) == {"dados.json", "PROMPT.md"}
    json.loads(files["dados.json"])


def test_client_data_gives_origin_and_date_to_every_field():
    data = full_lead()
    parsed = json.loads(vitrines.client_files(data, vitrine_record(), vitrines.content_for(data))["dados.json"])

    for name, item in parsed["campos"].items():
        assert item["valor"] not in (None, "", {}), name
        assert item["origem"] and item["data"], name
    assert parsed["campos"]["telefone"]["origem"] == "osm"
    assert parsed["campos"]["whatsapp"]["origem"].startswith("osm (celular")


def test_client_data_marks_manual_origin_and_lists_what_is_missing():
    data = full_lead(manual_instagram="janis", instagram="janis", manual_whatsapp="11911112222", manual_checked_at="2026-11-05 09:00:00")
    record = vitrine_record(content={"hours": "10h às 20h", "address": "Rua A, 10"}, updated_at="2026-11-06 10:00:00")
    parsed = json.loads(vitrines.client_files(data, record, vitrines.content_for(data, record["content"]))["dados.json"])

    assert parsed["campos"]["instagram"] == {"valor": "janis", "origem": "manual", "data": "2026-11-05 09:00:00"}
    assert parsed["campos"]["whatsapp"]["origem"] == "manual"
    assert parsed["campos"]["horario"] == {"valor": "10h às 20h", "origem": "manual", "data": "2026-11-06 10:00:00"}
    assert parsed["campos"]["endereco"]["origem"] == "manual"
    assert parsed["campos_ausentes"] == []


def test_client_data_does_not_invent_fields_it_does_not_have():
    data = full_lead(address=None, phone_national=None, phone_kind=None, lat=None, lon=None)
    parsed = json.loads(vitrines.client_files(data, vitrine_record(), vitrines.content_for(data))["dados.json"])

    assert {"endereco", "telefone", "whatsapp", "instagram", "horario"} <= set(parsed["campos_ausentes"])
    assert "telefone" not in parsed["campos"] and "coordenadas" not in parsed["campos"]
    assert parsed["servicos_cadastrados"] == []


def test_client_data_keeps_only_registered_services_not_the_model_ones():
    data = full_lead()
    record = vitrine_record(content={"services": [{"name": "Corte social", "text": "Na tesoura"}]})
    parsed = json.loads(vitrines.client_files(data, record, vitrines.content_for(data, record["content"]))["dados.json"])

    assert parsed["servicos_cadastrados"] == [{"nome": "Corte social", "texto": "Na tesoura"}]


def test_client_prompt_carries_the_rules_the_slug_and_the_name():
    data = full_lead()
    prompt = vitrines.client_files(data, vitrine_record(), vitrines.content_for(data))["PROMPT.md"]

    for expected in ("Use só os dados de `dados.json`", "[PREENCHER", "RELATORIO.md", "/s/janis-bull", "Janis Bull Barbearia", "Não publique nada"):
        assert expected in prompt
    assert "Não invente preço, depoimento" in prompt
