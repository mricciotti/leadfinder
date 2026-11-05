import pytest

import scoring


def lead(**overrides):
    base = {
        "id": "node-1",
        "name": "Lugar",
        "segment": "salao",
        "phone": None,
        "phone_kind": None,
        "manual_whatsapp": None,
        "email": None,
        "instagram": None,
        "facebook": None,
        "other_links": [],
        "address": None,
        "website": None,
        "site_state": "sem_site_na_fonte",
    }
    base.update(overrides)
    return base


def test_celular_counts_more_than_a_landline():
    celular = scoring.contact(lead(phone="x", phone_kind="celular"))
    fixo = scoring.contact(lead(phone="x", phone_kind="fixo"))

    assert celular["points"] > fixo["points"]


def test_celular_adds_a_potential_whatsapp():
    result = scoring.contact(lead(phone="x", phone_kind="celular"))

    assert "Celular pode ter WhatsApp (não confirmado)" in result["reasons"]


def test_whatsapp_informed_by_you_counts_more_than_a_potential_one():
    informed = scoring.contact(lead(manual_whatsapp="11988887777"))
    potential = scoring.contact(lead(phone="x", phone_kind="celular"))

    assert "WhatsApp informado por você" in informed["reasons"]
    assert informed["channel"] is True
    assert scoring.CONTACT_POINTS["whatsapp_informado"] > scoring.CONTACT_POINTS["whatsapp"]
    assert not any("não confirmado" in reason for reason in informed["reasons"])
    assert potential["points"] > 0


def test_landline_has_no_whatsapp():
    result = scoring.contact(lead(phone="x", phone_kind="fixo"))

    assert not any("WhatsApp" in reason for reason in result["reasons"])


def test_own_email_counts_more_than_a_generic_one():
    own = scoring.contact(lead(email="oi@lugar.com.br"))
    generic = scoring.contact(lead(email="lugar@gmail.com"))

    assert own["points"] > generic["points"] > 0


def test_instagram_counts():
    result = scoring.contact(lead(instagram="lugar"))

    assert result["points"] == scoring.CONTACT_POINTS["instagram"]
    assert result["channel"] is True


def test_other_links_count():
    result = scoring.contact(lead(other_links=["https://tiktok.com/@lugar"]))

    assert result["points"] == scoring.CONTACT_POINTS["outras_redes"]


def test_address_alone_is_not_a_contact_channel():
    result = scoring.contact(lead(address="Rua A, 10"))

    assert result["points"] == scoring.CONTACT_POINTS["endereco"]
    assert result["channel"] is False


def test_unrecognized_phone_is_explained_but_scores_nothing():
    result = scoring.contact(lead(phone="3815-2600", phone_kind="invalido"))

    assert result["points"] == 0
    assert result["reasons"] == ["Telefone no mapa em formato não reconhecido"]


def test_nothing_known_says_so():
    result = scoring.contact(lead())

    assert result["level"] == "baixa"
    assert result["reasons"] == ["Nenhum canal de contato no mapa"]


def test_celular_alone_is_high_contact():
    assert scoring.contact(lead(phone="x", phone_kind="celular"))["level"] == "alta"


@pytest.mark.parametrize(
    "state, level",
    [
        ("ausencia_confirmada", "maxima"),
        ("so_rede_social", "alta"),
        ("site_inacessivel", "alta"),
        ("site_com_problemas", "media"),
        ("sem_site_na_fonte", "media"),
        ("site_informado", "indeterminada"),
        ("site_ok", "baixa"),
        ("nao_verificado", "indeterminada"),
    ],
)
def test_opportunity_by_site_state(state, level):
    assert scoring.opportunity(lead(site_state=state))["level"] == level


def test_missing_site_in_the_source_says_it_was_not_verified():
    reasons = scoring.opportunity(lead(site_state="sem_site_na_fonte"))["reasons"]

    assert "não verificado" in reasons[0]


def test_nao_verificado_is_never_low():
    assert scoring.opportunity(lead(site_state="nao_verificado"))["level"] != "baixa"


def test_free_subdomain_is_a_high_opportunity():
    result = scoring.opportunity(
        lead(site_state="site_ok", website="https://lugar.wixsite.com/site")
    )

    assert result["level"] == "alta"
    assert "O site usa um subdomínio gratuito, sem domínio próprio" in result["reasons"]


def offer_keys(**overrides):
    return [offer["key"] for offer in scoring.offers(lead(**overrides))]


def test_no_site_gets_a_landing_page():
    assert offer_keys(site_state="sem_site_na_fonte") == ["landing_page"]


def test_social_only_gets_an_own_page():
    assert offer_keys(site_state="so_rede_social", instagram="https://instagram.com/lugar") == [
        "pagina_propria"
    ]


def test_link_page_gets_an_own_page():
    assert offer_keys(site_state="so_rede_social", other_links=["https://linktr.ee/lugar"]) == [
        "pagina_propria"
    ]


def test_delivery_only_gets_an_own_menu():
    assert offer_keys(
        site_state="so_rede_social", other_links=["https://www.ifood.com.br/delivery/lugar"]
    ) == ["cardapio_proprio"]


def test_food_without_own_site_gets_a_digital_menu():
    assert offer_keys(segment="restaurante", site_state="sem_site_na_fonte") == [
        "landing_page",
        "cardapio_digital",
    ]


def test_food_with_own_site_gets_no_digital_menu_yet():
    assert offer_keys(
        segment="restaurante", site_state="site_informado", website="https://lugar.com.br"
    ) == []


def test_free_subdomain_gets_an_own_domain():
    assert offer_keys(site_state="site_informado", website="https://lugar.blogspot.com") == [
        "dominio_proprio"
    ]


@pytest.mark.parametrize("state", ["site_com_problemas", "site_inacessivel"])
def test_broken_site_gets_a_redesign(state):
    assert offer_keys(site_state=state, website="https://lugar.com.br") == ["reformulacao"]


def test_unverified_lead_gets_no_offer():
    assert offer_keys(site_state="nao_verificado") == []


def test_high_priority_example():
    result = scoring.evaluate(
        lead(
            site_state="so_rede_social",
            instagram="https://instagram.com/lugar",
            phone="+55 11 98888-7777",
            phone_kind="celular",
        )
    )

    assert result["priority"]["level"] == "alta"
    assert "Instagram identificado" in result["contact"]["reasons"]
    assert "Celular no mapa" in result["contact"]["reasons"]
    assert result["opportunity"]["level"] == "alta"


def test_redesign_example():
    result = scoring.evaluate(
        lead(
            site_state="site_com_problemas",
            website="https://lugar.com.br",
            phone="+55 11 3815-2600",
            phone_kind="fixo",
        )
    )

    assert result["opportunity"]["level"] == "media"
    assert [offer["label"] for offer in result["offers"]] == ["Reformulação do site"]
    assert result["priority"]["level"] == "normal"


def test_high_opportunity_without_channel_is_not_high_priority():
    result = scoring.evaluate(lead(site_state="ausencia_confirmada"))

    assert result["priority"]["level"] == "normal"


def test_low_opportunity_is_low_priority():
    result = scoring.evaluate(lead(site_state="site_ok", website="https://lugar.com.br"))

    assert result["priority"]["level"] == "baixa"


def test_changing_a_weight_changes_the_result(monkeypatch):
    before = scoring.contact(lead(instagram="lugar"))

    monkeypatch.setitem(scoring.CONTACT_POINTS, "instagram", 5)

    after = scoring.contact(lead(instagram="lugar"))
    assert (before["points"], before["level"]) == (2, "media")
    assert (after["points"], after["level"]) == (5, "alta")


def test_changing_an_opportunity_level_changes_the_priority(monkeypatch):
    target = lead(site_state="sem_site_na_fonte", phone="x", phone_kind="fixo")
    before = scoring.evaluate(target)["priority"]["level"]

    monkeypatch.setitem(
        scoring.OPPORTUNITY_BY_STATE, "sem_site_na_fonte", ("alta", "Sem site no mapa")
    )

    assert (before, scoring.evaluate(target)["priority"]["level"]) == ("normal", "alta")


def test_no_reason_mentions_ratings_or_an_active_business():
    texts = [
        *scoring.CONTACT_REASONS.values(),
        *(reason for _, reason in scoring.OPPORTUNITY_BY_STATE.values()),
        *(reason for _, reason in scoring.OFFERS.values()),
        scoring.FREE_SITE_OPPORTUNITY[1],
    ]

    assert not [text for text in texts if any(word in text.lower() for word in ("avalia", "nota", "ativ"))]


def test_ranked_puts_high_priority_first():
    leads = [
        lead(id="node-1", name="Baixa", site_state="site_ok", website="https://a.com.br"),
        lead(id="node-2", name="Alta", site_state="so_rede_social", instagram="alta"),
        lead(id="node-3", name="Normal"),
    ]

    assert [item["name"] for item in scoring.ranked(leads)] == ["Alta", "Normal", "Baixa"]


@pytest.mark.parametrize("segment", ["confeitaria", "sorveteria"])
def test_new_food_segments_get_a_digital_menu_when_they_have_no_own_site(segment):
    assert "cardapio_digital" in offer_keys(segment=segment, site_state="sem_site_na_fonte")


@pytest.mark.parametrize("segment", ["clinica", "oficina", "petshop", "veterinario", "otica", "imobiliaria"])
def test_other_new_segments_get_a_landing_page_but_no_menu(segment):
    keys = offer_keys(segment=segment, site_state="sem_site_na_fonte")

    assert keys == ["landing_page"]
