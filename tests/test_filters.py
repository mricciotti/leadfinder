from contextlib import closing

import pytest

import db
import filters
import scoring
from main import LeadFilter
from test_db import lead


@pytest.fixture
def leads(tmp_path):
    with closing(db.connect(tmp_path / "filters.db")) as conn:
        db.add_leads(
            conn,
            [
                lead(
                    "node-1",
                    name="Sem Site",
                    phone="+55 11 3815-2600",
                    phone_national="1138152600",
                    phone_kind="fixo",
                ),
                lead(
                    "node-2",
                    name="Com Site",
                    website="https://comsite.com.br",
                    site_state="site_informado",
                    email="oi@comsite.com.br",
                    lat=-23.6,
                ),
                lead(
                    "node-3",
                    name="So Insta",
                    site_state="so_rede_social",
                    instagram="https://instagram.com/soinsta",
                    lat=-23.7,
                ),
                lead(
                    "node-4",
                    name="Outro Bairro",
                    segment="bar",
                    neighborhood="Saúde",
                    city="Santos",
                    lat=-23.8,
                ),
                lead("node-5", name="Rio", city="Rio de Janeiro", uf="RJ", lat=-22.9),
            ],
        )
        db.update_lead(conn, "node-1", favorite=True, status="contatado")
        db.update_lead(conn, "node-5", absence_confirmed=True)
        return scoring.ranked(db.list_leads(conn))


def names(leads, **wanted):
    chosen = filters.apply(leads, LeadFilter(**wanted).model_dump())
    return sorted(lead["name"] for lead in chosen)


def test_no_filter_keeps_everything(leads):
    assert len(names(leads)) == 5


@pytest.mark.parametrize(
    "site, expected",
    [
        ("com_site", ["Com Site"]),
        ("sem_site_na_fonte", ["Outro Bairro", "Sem Site"]),
        ("so_rede_social", ["So Insta"]),
        ("ausencia_confirmada", ["Rio"]),
        ("site_com_problemas", []),
        ("nao_verificado", []),
    ],
)
def test_site_filter(leads, site, expected):
    assert names(leads, site=site) == expected


def test_phone_filter(leads):
    assert names(leads, phone=True) == ["Sem Site"]


def test_email_filter(leads):
    assert names(leads, email=True) == ["Com Site"]


def test_instagram_filter(leads):
    assert names(leads, instagram=True) == ["So Insta"]


def test_priority_filter(leads):
    assert names(leads, priority="alta") == ["So Insta"]


def test_offer_filter(leads):
    assert names(leads, offer="pagina_propria") == ["So Insta"]
    assert names(leads, offer="landing_page") == ["Outro Bairro", "Rio", "Sem Site"]


def test_favorite_filter(leads):
    assert names(leads, favorite=True) == ["Sem Site"]


def test_not_contacted_and_status_filters(leads):
    assert "Sem Site" not in names(leads, not_contacted=True)
    assert names(leads, status="contatado") == ["Sem Site"]


def test_place_filters_ignore_case_and_accents(leads):
    assert names(leads, neighborhood="saude") == ["Outro Bairro"]
    assert names(leads, city="SANTOS") == ["Outro Bairro"]
    assert names(leads, uf="RJ") == ["Rio"]
    assert names(leads, segment="bar") == ["Outro Bairro"]


def test_filters_combine(leads):
    assert names(leads, site="sem_site_na_fonte", phone=True) == ["Sem Site"]
    assert names(leads, site="sem_site_na_fonte", segment="bar", phone=True) == []


def test_options_are_distinct_ignoring_case_and_accents(leads):
    leads[0]["neighborhood"] = "pinheiros"
    leads[1]["neighborhood"] = "Saude"

    result = filters.options(leads)

    assert len(result["neighborhoods"]) == 2
    assert result["ufs"] == ["RJ", "SP"]
    assert result["segments"] == ["bar", "restaurante"]


def test_areas_group_leads_by_segment_neighborhood_and_city(leads):
    result = filters.areas(leads)

    keys = {(area["segment"], area["neighborhood"], area["city"]) for area in result}
    assert keys == {
        ("restaurante", "Pinheiros", "São Paulo"),
        ("bar", "Saúde", "Santos"),
        ("restaurante", "Pinheiros", "Rio de Janeiro"),
    }


def test_areas_count_leads_priorities_and_contacts(leads):
    area = next(item for item in filters.areas(leads) if item["city"] == "São Paulo")

    assert area["total"] == 3
    assert area["high_priority"] == 1
    assert area["contacted"] == 1
    assert area["last_seen"]


def test_areas_merge_spellings_that_differ_only_by_case_and_accent(leads):
    leads[0]["neighborhood"] = "pinheiros"
    leads[1]["neighborhood"] = "PINHEIROS"

    sao_paulo = [item for item in filters.areas(leads) if item["city"] == "São Paulo"]

    assert len(sao_paulo) == 1
    assert sao_paulo[0]["total"] == 3


def test_areas_accept_old_leads_without_a_city(leads):
    leads[3]["city"] = None

    assert any(item["city"] is None for item in filters.areas(leads))


def test_areas_are_ordered_by_the_latest_update(leads):
    for lead in leads:
        lead["source_seen_at"] = "2026-01-01 10:00:00"
    leads[3]["source_seen_at"] = "2026-06-01 10:00:00"

    assert filters.areas(leads)[0]["neighborhood"] == "Saúde"


def only_sao_paulo_in_pinheiros(leads):
    for lead in leads:
        if lead["name"] == "Rio":
            lead["neighborhood"] = "Mooca"
        if lead["name"] == "So Insta":
            lead["city"] = None


def test_areas_merge_old_leads_without_city_into_the_only_known_city(leads):
    only_sao_paulo_in_pinheiros(leads)

    pinheiros = [item for item in filters.areas(leads) if item["neighborhood"] == "Pinheiros"]

    assert len(pinheiros) == 1
    assert (pinheiros[0]["city"], pinheiros[0]["total"]) == ("São Paulo", 3)


def test_areas_keep_old_leads_without_city_apart_when_the_city_is_ambiguous(leads):
    for lead in leads:
        if lead["name"] == "So Insta":
            lead["city"] = None

    cities = sorted(str(item["city"]) for item in filters.areas(leads) if item["neighborhood"] == "Pinheiros")

    assert cities == ["None", "Rio de Janeiro", "São Paulo"]


def test_areas_show_the_city_even_when_the_first_lead_has_none(leads):
    only_sao_paulo_in_pinheiros(leads)
    assert leads[0]["city"] is None

    area = next(item for item in filters.areas(leads) if item["neighborhood"] == "Pinheiros")

    assert (area["city"], area["uf"]) == ("São Paulo", "SP")


def test_not_contacted_includes_possible_prospects(leads):
    for lead in leads:
        if lead["name"] == "So Insta":
            lead["status"] = "prospecto"

    assert "So Insta" in [
        item["name"] for item in filters.apply(leads, LeadFilter(not_contacted=True).model_dump())
    ]


def test_areas_do_not_count_possible_prospects_as_contacted(leads):
    for lead in leads:
        lead["status"] = "prospecto"

    assert all(area["contacted"] == 0 for area in filters.areas(leads))
