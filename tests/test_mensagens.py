import re

import pytest

import mensagens

WORST = {
    "name": "Bestlaser Paulista - Depilação a Laser",
    "neighborhood": "Vila Mariana",
}
LINK = "https://previas.exemplo.com.br/bestlaser-paulista-depilacao-a-laser-vila-mariana"
PROBLEM = "o certificado de segurança do site está vencido ou inválido (o navegador mostra alerta)"


def built(case, **extra):
    return mensagens.build(case, WORST, LINK, "Salão de beleza", extra.get("problem", PROBLEM))


@pytest.mark.parametrize("case", list(mensagens.MESSAGES))
def test_every_message_fits_the_limit_even_with_the_longest_values(case):
    result = built(case)

    assert len(result["text"]) <= mensagens.MAX_LENGTH
    assert result["warnings"] == []


@pytest.mark.parametrize("case", list(mensagens.MESSAGES))
def test_every_message_is_fully_filled(case):
    text = built(case)["text"]

    assert "{" not in text and "}" not in text
    assert LINK in text


@pytest.mark.parametrize("case", ["sem_site", "so_rede_social", "delivery", "site_com_problemas"])
def test_approach_messages_end_with_the_link_as_a_small_request(case):
    text = built(case)["text"]

    assert text.endswith(LINK)
    assert re.search(r"dar uma olhada|abrir", text[-130:])


def test_follow_up_offers_a_way_out():
    text = built("follow_up")["text"]

    assert "é só me avisar que eu não escrevo mais" in text


@pytest.mark.parametrize("case", list(mensagens.MESSAGES))
def test_no_message_uses_forbidden_words_or_asks_if_they_want_a_site(case):
    text = built(case)["text"]

    assert not re.search(r"\bIA\b|intelig[eê]ncia artificial|desenvolvedor|tecnologia|quer um site", text, re.I)


@pytest.mark.parametrize("case", list(mensagens.MESSAGES))
def test_messages_use_em_before_the_neighborhood_never_no(case):
    text = built(case)["text"]

    assert " no Vila Mariana" not in text and " na Vila Mariana" not in text


def test_segment_label_is_lowercased_in_the_message():
    text = built("so_rede_social")["text"]

    assert "quem procura salão de beleza em Vila Mariana" in text


def test_problem_text_is_used_only_by_the_problem_case():
    assert PROBLEM in built("site_com_problemas")["text"]
    assert PROBLEM not in built("sem_site")["text"]


def test_first_person_name_is_stated_without_a_gendered_article():
    for case in ("sem_site", "so_rede_social", "delivery", "site_com_problemas"):
        assert "Meu nome é Matheus." in built(case)["text"]


def offer(*keys):
    return [{"key": key} for key in keys]


def test_case_follows_the_main_offer():
    assert mensagens.case_for(offer("landing_page", "cardapio_digital")) == "sem_site"
    assert mensagens.case_for(offer("pagina_propria", "cardapio_digital")) == "so_rede_social"
    assert mensagens.case_for(offer("cardapio_proprio", "cardapio_digital")) == "delivery"
    assert mensagens.case_for(offer("dominio_proprio")) == "sem_site"
    assert mensagens.case_for([]) == "sem_site"


def test_problem_case_needs_a_real_problem_otherwise_it_falls_back():
    assert mensagens.case_for(offer("reformulacao"), PROBLEM) == "site_com_problemas"
    assert mensagens.case_for(offer("reformulacao")) == "sem_site"
    assert mensagens.case_for(offer("reformulacao", "landing_page")) == "sem_site"


def test_checker_flags_long_text_and_each_forbidden_expression():
    assert mensagens.problems_with("a" * 401)
    assert mensagens.problems_with("Oi, sou desenvolvedor aqui")
    assert mensagens.problems_with("Feito com IA")
    assert mensagens.problems_with("Usamos inteligência artificial")
    assert mensagens.problems_with("Nossa tecnologia")
    assert mensagens.problems_with("Quer um site?")
    assert mensagens.problems_with("Oi, Maria e Mario") == []


def test_a_very_long_business_name_triggers_a_warning_instead_of_a_silent_cut():
    lead = {"name": "N" * 300, "neighborhood": "Vila Mariana"}

    result = mensagens.build("sem_site", lead, LINK, "Salão de beleza")

    assert result["warnings"] and "caracteres" in result["warnings"][0]
    assert len(result["text"]) > mensagens.MAX_LENGTH
