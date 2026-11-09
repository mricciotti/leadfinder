import httpx
import pytest
from fastapi.testclient import TestClient

import main
import overpass


def lead(lead_id, name, score, **overrides):
    return {
        "id": lead_id,
        "name": name,
        "segment": "restaurante",
        "neighborhood": "Pinheiros",
        "phone": None,
        "phone_national": None,
        "phone_kind": None,
        "address": None,
        "city": "São Paulo",
        "uf": "SP",
        "email": None,
        "instagram": None,
        "facebook": None,
        "other_links": [],
        "website": None,
        "site_state": "sem_site_na_fonte",
        "lat": -23.56,
        "lon": -46.69,
        "score": score,
        **overrides,
    }


async def fake_searcher(segment, neighborhood, city, **extra):
    return {
        "total": 5,
        "leads": [
            lead("node-1", "Baixo", 1),
            lead("node-2", "Alto", 6),
            lead(
                "node-3",
                "Com Site",
                2,
                website="https://comsite.com.br",
                site_state="site_informado",
            ),
        ],
    }


def make_client(tmp_path, searcher=fake_searcher):
    return TestClient(main.create_app(tmp_path / "api.db", searcher))


SEARCH = {"segment": "restaurante", "neighborhood": "Pinheiros"}


def test_index_is_served(tmp_path):
    response = make_client(tmp_path).get("/")

    assert response.status_code == 200
    assert "Prospecção" in response.text


def test_segments_lists_every_segment_with_its_label(tmp_path):
    response = make_client(tmp_path).get("/api/segments")

    assert {"key": "restaurante", "label": "Restaurante"} in response.json()
    assert len(response.json()) == len(overpass.SEGMENTS)


def save_all(client, body=SEARCH):
    preview = client.post("/api/search", json=body).json()
    ids = [item["id"] for item in preview["leads"] if not item["saved"] and not item["duplicate"]]
    return client.post(f"/api/search/{preview['search_id']}/save", json={"ids": ids})


def test_search_returns_a_preview_and_saves_nothing(tmp_path):
    client = make_client(tmp_path)

    response = client.post("/api/search", json=SEARCH)

    body = response.json()
    assert response.status_code == 200
    assert body["search_id"]
    assert (body["total"], body["found"], body["new"], body["known"], body["duplicates"]) == (5, 3, 3, 0, 0)
    assert body["without_site"] == 2
    assert len(body["leads"]) == 3
    assert client.get("/api/leads").json() == []
    assert client.get("/api/areas").json() == []


def test_preview_leads_carry_the_evaluation_and_flags(tmp_path):
    body = make_client(tmp_path).post("/api/search", json=SEARCH).json()

    first = body["leads"][0]
    assert first["evaluation"]["priority"]["level"] in ("alta", "normal", "baixa")
    assert first["evaluation"]["offers"] is not None
    assert (first["saved"], first["duplicate"], first["saved_status"]) == (False, False, None)
    assert isinstance(first["recommended"], bool)


def test_preview_is_sorted_by_priority_then_opportunity(tmp_path):
    names = [item["name"] for item in make_client(tmp_path).post("/api/search", json=SEARCH).json()["leads"]]

    assert names == ["Alto", "Baixo", "Com Site"]


async def mixed_searcher(segment, neighborhood, city, **extra):
    return {
        "total": 4,
        "leads": [
            lead("node-1", "Bom Com Telefone", 3, phone="+55 11 98888-7777", phone_national="11988887777", phone_kind="celular"),
            lead("node-2", "Sem Contato", 0),
            lead("node-3", "Site Com Telefone", 3, phone="+55 11 3815-2600", phone_national="1138152600", phone_kind="fixo", website="https://a.com.br", site_state="site_informado"),
            lead("node-4", "So Instagram", 1, instagram="https://instagram.com/x", site_state="so_rede_social"),
        ],
    }


def test_recommended_are_new_leads_with_a_contact_channel_and_no_own_site(tmp_path):
    body = make_client(tmp_path, mixed_searcher).post("/api/search", json=SEARCH).json()

    recommended = sorted(item["name"] for item in body["leads"] if item["recommended"])
    assert recommended == ["Bom Com Telefone", "So Instagram"]
    assert body["recommended"] == 2


def test_leads_already_saved_are_marked_and_never_recommended(tmp_path):
    client = make_client(tmp_path, mixed_searcher)
    save_all(client)
    client.patch("/api/leads/node-1", json={"status": "contatado"})

    body = client.post("/api/search", json=SEARCH).json()

    saved = {item["id"]: item for item in body["leads"]}
    assert all(item["saved"] for item in saved.values())
    assert saved["node-1"]["saved_status"] == "contatado"
    assert (body["new"], body["known"], body["recommended"]) == (0, 4, 0)


def test_the_same_place_nearby_as_another_osm_type_is_a_duplicate(tmp_path):
    async def first(segment, neighborhood, city, **extra):
        return {"total": 1, "leads": [lead("node-1", "Cantina São José", 1)]}

    async def second(segment, neighborhood, city, **extra):
        return {"total": 1, "leads": [lead("way-9", "cantina sao jose", 1)]}

    save_all(make_client(tmp_path, first))
    body = make_client(tmp_path, second).post("/api/search", json=SEARCH).json()

    only = body["leads"][0]
    assert (only["duplicate"], only["recommended"]) == (True, False)
    assert (body["new"], body["duplicates"]) == (0, 1)


def test_save_stores_only_the_chosen_leads(tmp_path):
    client = make_client(tmp_path)
    preview = client.post("/api/search", json=SEARCH).json()

    response = client.post(f"/api/search/{preview['search_id']}/save", json={"ids": ["node-2"]})

    assert response.status_code == 200
    assert response.json() == {"added": 1, "refreshed": 0}
    assert [item["id"] for item in client.get("/api/leads").json()] == ["node-2"]


def test_save_refreshes_leads_already_in_the_list_without_touching_the_user_data(tmp_path):
    client = make_client(tmp_path)
    first = client.post("/api/search", json=SEARCH).json()
    client.post(f"/api/search/{first['search_id']}/save", json={"ids": ["node-1"]})
    client.patch("/api/leads/node-1", json={"status": "contatado", "notes": "Ligar sexta", "favorite": True})

    async def changed(segment, neighborhood, city, **extra):
        return {
            "total": 2,
            "leads": [
                lead("node-1", "Baixo Renomeado", 1, phone="+55 11 3815-2600", phone_national="1138152600", phone_kind="fixo"),
                lead("node-2", "Alto", 6),
            ],
        }

    second_client = TestClient(main.create_app(tmp_path / "api.db", changed))
    second = second_client.post("/api/search", json=SEARCH).json()
    response = second_client.post(f"/api/search/{second['search_id']}/save", json={"ids": ["node-2"]})

    assert response.json() == {"added": 1, "refreshed": 1}
    saved = {item["id"]: item for item in second_client.get("/api/leads").json()}
    assert saved["node-1"]["name"] == "Baixo Renomeado"
    assert saved["node-1"]["phone"] == "+55 11 3815-2600"
    assert (saved["node-1"]["status"], saved["node-1"]["notes"], saved["node-1"]["favorite"]) == ("contatado", "Ligar sexta", 1)


def test_save_ignores_a_chosen_duplicate_of_a_saved_place(tmp_path):
    async def first(segment, neighborhood, city, **extra):
        return {"total": 1, "leads": [lead("node-1", "Cantina", 1)]}

    async def second(segment, neighborhood, city, **extra):
        return {"total": 1, "leads": [lead("way-9", "Cantina", 1)]}

    save_all(make_client(tmp_path, first))
    client = TestClient(main.create_app(tmp_path / "api.db", second))
    preview = client.post("/api/search", json=SEARCH).json()

    response = client.post(f"/api/search/{preview['search_id']}/save", json={"ids": ["way-9"]})

    assert response.json() == {"added": 0, "refreshed": 0}
    assert [item["id"] for item in client.get("/api/leads").json()] == ["node-1"]


def test_save_with_an_unknown_search_says_the_preview_expired(tmp_path):
    response = make_client(tmp_path).post("/api/search/naoexiste/save", json={"ids": ["node-1"]})

    assert response.status_code == 404
    assert "expirou" in response.json()["detail"]


def test_save_rejects_ids_that_are_not_in_the_preview(tmp_path):
    client = make_client(tmp_path)
    preview = client.post("/api/search", json=SEARCH).json()

    response = client.post(f"/api/search/{preview['search_id']}/save", json={"ids": ["node-999"]})

    assert response.status_code == 400
    assert client.get("/api/leads").json() == []


def test_save_needs_at_least_one_id(tmp_path):
    client = make_client(tmp_path)
    preview = client.post("/api/search", json=SEARCH).json()

    assert client.post(f"/api/search/{preview['search_id']}/save", json={"ids": []}).status_code == 422


def test_a_preview_can_be_saved_only_once(tmp_path):
    client = make_client(tmp_path)
    preview = client.post("/api/search", json=SEARCH).json()
    url = f"/api/search/{preview['search_id']}/save"
    client.post(url, json={"ids": ["node-1"]})

    assert client.post(url, json={"ids": ["node-2"]}).status_code == 404


def test_only_the_latest_previews_are_kept(tmp_path):
    client = make_client(tmp_path)
    ids = [client.post("/api/search", json=SEARCH).json()["search_id"] for _ in range(main.MAX_PREVIEWS + 1)]

    assert client.post(f"/api/search/{ids[0]}/save", json={"ids": ["node-1"]}).status_code == 404
    assert client.post(f"/api/search/{ids[-1]}/save", json={"ids": ["node-1"]}).status_code == 200


def test_search_passes_trimmed_inputs_and_default_city(tmp_path):
    received = {}

    async def spy(segment, neighborhood, city, **extra):
        received.update(segment=segment, neighborhood=neighborhood, city=city)
        return {"total": 0, "leads": []}

    make_client(tmp_path, spy).post(
        "/api/search", json={"segment": "bar", "neighborhood": "  Mooca  "}
    )

    assert received == {"segment": "bar", "neighborhood": "Mooca", "city": "São Paulo"}


def test_search_rejects_unknown_segment(tmp_path):
    response = make_client(tmp_path).post(
        "/api/search", json={"segment": "foguete", "neighborhood": "Mooca"}
    )

    assert response.status_code == 400


def test_search_rejects_a_too_short_neighborhood(tmp_path):
    response = make_client(tmp_path).post(
        "/api/search", json={"segment": "bar", "neighborhood": "x"}
    )

    assert response.status_code == 422


def test_search_reports_unknown_neighborhood_as_404(tmp_path):
    async def not_found(segment, neighborhood, city, **extra):
        raise overpass.PlaceNotFound()

    response = make_client(tmp_path, not_found).post("/api/search", json=SEARCH)

    assert response.status_code == 404
    assert "bairro" in response.json()["detail"]


def test_search_reports_network_failure_as_502(tmp_path):
    async def offline(segment, neighborhood, city, **extra):
        raise httpx.ConnectError("sem rede")

    response = make_client(tmp_path, offline).post("/api/search", json=SEARCH)

    assert response.status_code == 502


def test_leads_come_back_ranked_by_opportunity(tmp_path):
    client = make_client(tmp_path)
    save_all(client)

    names = [item["name"] for item in client.get("/api/leads").json()]

    assert names == ["Alto", "Baixo", "Com Site"]


def test_leads_carry_their_evaluation(tmp_path):
    client = make_client(tmp_path)
    save_all(client)

    saved = {item["id"]: item for item in client.get("/api/leads").json()}

    assert saved["node-1"]["evaluation"]["opportunity"]["level"] == "media"
    assert saved["node-1"]["evaluation"]["offers"][0]["label"] == "Landing page"
    assert saved["node-3"]["evaluation"]["opportunity"]["level"] == "indeterminada"


def test_leads_carry_the_site_state(tmp_path):
    client = make_client(tmp_path)
    save_all(client)

    saved = {item["id"]: item for item in client.get("/api/leads").json()}

    assert saved["node-1"]["site_state"] == "sem_site_na_fonte"
    assert saved["node-3"]["site_state"] == "site_informado"
    assert saved["node-3"]["website"] == "https://comsite.com.br"
    assert saved["node-3"]["other_links"] == []


def test_patch_updates_status_and_notes(tmp_path):
    client = make_client(tmp_path)
    save_all(client)

    response = client.patch(
        "/api/leads/node-2", json={"status": "contatado", "notes": "Mandei mensagem"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "contatado"
    assert response.json()["notes"] == "Mandei mensagem"
    assert response.json()["evaluation"]["priority"]["level"] == "normal"
    saved = {item["id"]: item for item in client.get("/api/leads").json()}
    assert saved["node-2"]["status"] == "contatado"


def test_patch_rejects_invalid_status(tmp_path):
    client = make_client(tmp_path)
    save_all(client)

    response = client.patch("/api/leads/node-2", json={"status": "inventado"})

    assert response.status_code == 422


def test_patch_returns_404_for_unknown_lead(tmp_path):
    response = make_client(tmp_path).patch(
        "/api/leads/node-404", json={"status": "fechado"}
    )

    assert response.status_code == 404


def searched_client(tmp_path):
    client = make_client(tmp_path)
    save_all(client)
    return client


def test_leads_can_be_filtered_by_query(tmp_path):
    client = searched_client(tmp_path)

    with_site = client.get("/api/leads", params={"site": "com_site"}).json()
    without_site = client.get("/api/leads", params={"site": "sem_site_na_fonte"}).json()

    assert [item["name"] for item in with_site] == ["Com Site"]
    assert len(without_site) == 2


def test_unknown_filter_value_is_rejected(tmp_path):
    response = searched_client(tmp_path).get("/api/leads", params={"site": "inventado"})

    assert response.status_code == 422


def test_filter_options_list_the_saved_places(tmp_path):
    response = searched_client(tmp_path).get("/api/filter-options")

    assert response.json() == {
        "segments": ["restaurante"],
        "neighborhoods": ["Pinheiros"],
        "cities": ["São Paulo"],
        "ufs": ["SP"],
    }


def test_leads_csv_download_respects_filters(tmp_path):
    response = searched_client(tmp_path).get(
        "/api/export/leads", params={"site": "com_site", "neighborhood": "pinheiros"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'filename="leads-pinheiros-' in response.headers["content-disposition"]
    lines = response.content.decode("utf-8-sig").splitlines()
    assert len(lines) == 2
    assert lines[1].startswith("Com Site;")


def test_full_csv_download(tmp_path):
    response = searched_client(tmp_path).get("/api/export/completo")

    assert response.status_code == 200
    assert 'filename="leads-completo-' in response.headers["content-disposition"]
    assert len(response.content.decode("utf-8-sig").splitlines()) == 4


def test_empty_export_returns_no_file(tmp_path):
    response = searched_client(tmp_path).get("/api/export/leads", params={"favorite": True})

    assert response.status_code == 404
    assert response.json()["detail"] == "Nenhum lead para exportar com esses filtros."


def test_unknown_export_kind_is_rejected(tmp_path):
    assert searched_client(tmp_path).get("/api/export/xlsx").status_code == 422


def test_patch_toggles_favorite(tmp_path):
    client = searched_client(tmp_path)

    response = client.patch("/api/leads/node-1", json={"favorite": True})

    assert response.json()["favorite"] == 1
    assert [item["id"] for item in client.get("/api/leads", params={"favorite": True}).json()] == ["node-1"]


def test_patch_records_a_manual_check(tmp_path):
    client = searched_client(tmp_path)

    response = client.patch(
        "/api/leads/node-1",
        json={
            "manual_phone": "(11) 98888-7777",
            "manual_whatsapp": "11 98888-7777",
            "manual_instagram": "@baixo.oficial",
            "manual_website": "",
        },
    )

    lead = response.json()
    assert response.status_code == 200
    assert lead["phone"] == "(11) 98888-7777"
    assert lead["manual_whatsapp"] == "11988887777"
    assert lead["instagram"] == "baixo.oficial"
    assert lead["manual_website"] is None
    assert "WhatsApp informado por você" in lead["evaluation"]["contact"]["reasons"]


def test_patch_confirms_and_undoes_absence(tmp_path):
    client = searched_client(tmp_path)

    confirmed = client.patch("/api/leads/node-1", json={"absence_confirmed": True}).json()
    undone = client.patch("/api/leads/node-1", json={"absence_confirmed": False}).json()

    assert confirmed["site_state"] == "ausencia_confirmada"
    assert confirmed["evaluation"]["opportunity"]["level"] == "maxima"
    assert undone["site_state"] == "sem_site_na_fonte"


@pytest.mark.parametrize(
    "field, value",
    [
        ("manual_phone", "3815-2600"),
        ("manual_whatsapp", "0800 123 4567"),
        ("manual_instagram", "não é handle"),
        ("manual_instagram", "https://facebook.com/x"),
        ("manual_website", "https://instagram.com/x"),
        ("manual_website", "ftp://lugar.com.br"),
    ],
)
def test_patch_rejects_invalid_manual_data(tmp_path, field, value):
    response = searched_client(tmp_path).patch("/api/leads/node-1", json={field: value})

    assert response.status_code == 422


def test_leads_table_has_the_leads_csv_columns_and_respects_filters(tmp_path):
    client = searched_client(tmp_path)
    csv_header = client.get("/api/export/leads").content.decode("utf-8-sig").splitlines()[0]

    table = client.get("/api/leads-table", params={"site": "com_site"}).json()

    assert table["columns"] == csv_header.split(";")
    assert table["ids"] == ["node-3"]
    assert table["rows"][0][0] == "Com Site"


def test_leads_table_shows_formulas_as_plain_text(tmp_path):
    async def tricky(segment, neighborhood, city, **extra):
        return {"total": 1, "leads": [lead("node-9", "=HYPERLINK(\"x\")", 1)]}

    client = make_client(tmp_path, tricky)
    save_all(client)

    assert client.get("/api/leads-table").json()["rows"][0][0] == "=HYPERLINK(\"x\")"


def test_empty_leads_table(tmp_path):
    table = searched_client(tmp_path).get("/api/leads-table", params={"favorite": True}).json()

    assert table == {"columns": [], "ids": [], "rows": []}


def test_areas_list_what_was_already_searched(tmp_path):
    areas = searched_client(tmp_path).get("/api/areas").json()

    assert len(areas) == 1
    assert areas[0]["segment"] == "restaurante"
    assert areas[0]["neighborhood"] == "Pinheiros"
    assert areas[0]["total"] == 3


def test_areas_is_empty_before_any_search(tmp_path):
    assert make_client(tmp_path).get("/api/areas").json() == []


def test_neighborhoods_lists_sao_paulo_by_default(tmp_path):
    names = make_client(tmp_path).get("/api/neighborhoods").json()

    assert len(names) > 300
    assert "Pinheiros" in names and "Vila Madalena" in names


def test_neighborhoods_are_empty_for_other_cities(tmp_path):
    assert make_client(tmp_path).get("/api/neighborhoods", params={"city": "Santos"}).json() == []


def capture_searcher():
    received = {}

    async def searcher(segment, neighborhood, city, **extra):
        received.update(extra=extra)
        return {"total": 0, "leads": []}

    return received, searcher


def test_search_gives_the_known_place_to_the_searcher(tmp_path):
    received, searcher = capture_searcher()

    make_client(tmp_path, searcher).post(
        "/api/search", json={"segment": "bar", "neighborhood": "saude", "city": "São Paulo"}
    )

    place = received["extra"]["place"]
    assert place["name"] == "Saúde"
    assert place["uf"] == "SP"


def test_search_does_not_pass_a_place_for_a_name_outside_the_list(tmp_path):
    received, searcher = capture_searcher()

    make_client(tmp_path, searcher).post(
        "/api/search", json={"segment": "bar", "neighborhood": "Lugar Inventado", "city": "São Paulo"}
    )

    assert received["extra"] == {}


def test_search_does_not_pass_a_place_for_another_city(tmp_path):
    received, searcher = capture_searcher()

    make_client(tmp_path, searcher).post(
        "/api/search", json={"segment": "bar", "neighborhood": "Pinheiros", "city": "Santos"}
    )

    assert received["extra"] == {}


def test_patch_moves_a_lead_to_possible_prospect(tmp_path):
    client = searched_client(tmp_path)

    response = client.patch("/api/leads/node-1", json={"status": "prospecto"})

    assert response.status_code == 200
    assert response.json()["status"] == "prospecto"
    assert [item["id"] for item in client.get("/api/leads", params={"status": "prospecto"}).json()] == ["node-1"]


def test_leads_can_be_filtered_by_the_prospecto_stage_and_exported(tmp_path):
    client = searched_client(tmp_path)
    client.patch("/api/leads/node-1", json={"status": "prospecto"})

    response = client.get("/api/export/leads", params={"status": "prospecto"})

    assert response.status_code == 200
    assert len(response.content.decode("utf-8-sig").splitlines()) == 2


def test_the_same_place_twice_in_one_search_is_shown_once_and_not_recommended_twice(tmp_path):
    async def twice(segment, neighborhood, city, **extra):
        both = dict(phone="+55 11 98888-7777", phone_national="11988887777", phone_kind="celular")
        return {
            "total": 2,
            "leads": [
                lead("node-1", "Museo Verônica", 3, **both),
                lead("way-9", "Museo Veronica", 3, **both),
            ],
        }

    body = make_client(tmp_path, twice).post("/api/search", json=SEARCH).json()

    flags = {item["id"]: (item["duplicate"], item["recommended"]) for item in body["leads"]}
    assert flags == {"node-1": (False, True), "way-9": (True, False)}
    assert (body["new"], body["duplicates"], body["recommended"]) == (1, 1, 1)


def test_two_different_places_with_the_same_name_far_apart_are_both_kept(tmp_path):
    async def far(segment, neighborhood, city, **extra):
        return {"total": 2, "leads": [lead("node-1", "Cantina", 1), lead("way-9", "Cantina", 1, lat=-23.7)]}

    body = make_client(tmp_path, far).post("/api/search", json=SEARCH).json()

    assert (body["new"], body["duplicates"]) == (2, 0)


ZONE_SEARCH = {"segment": "restaurante", "zone": "sul"}


async def zone_searcher(segment, neighborhood, city, **extra):
    return {
        "total": 2,
        "leads": [
            lead("node-1", "Na Zona Sul", 3, neighborhood="Moema", zone="sul"),
            lead("node-2", "Outro Lugar", 1, neighborhood="Saúde", zone="sul"),
        ],
    }


def test_zones_lists_the_five_zones_with_their_labels(tmp_path):
    response = make_client(tmp_path).get("/api/zones")

    assert response.status_code == 200
    assert response.json() == [
        {"key": "centro", "label": "Centro"},
        {"key": "norte", "label": "Zona Norte"},
        {"key": "leste", "label": "Zona Leste"},
        {"key": "sul", "label": "Zona Sul"},
        {"key": "oeste", "label": "Zona Oeste"},
    ]


def test_zone_search_gives_the_searcher_the_zone_and_the_label(tmp_path):
    received = {}

    async def searcher(segment, neighborhood, city, **extra):
        received.update(segment=segment, neighborhood=neighborhood, city=city, extra=extra)
        return {"total": 0, "leads": []}

    response = make_client(tmp_path, searcher).post("/api/search", json=ZONE_SEARCH)

    assert response.status_code == 200
    assert (received["segment"], received["neighborhood"], received["city"]) == ("restaurante", "Zona Sul", "São Paulo")
    assert received["extra"] == {"zone": "sul"}


def test_zone_search_ignores_a_neighborhood_sent_along(tmp_path):
    received, searcher = capture_searcher()

    make_client(tmp_path, searcher).post(
        "/api/search", json={**ZONE_SEARCH, "neighborhood": "Pinheiros", "city": "Santos"}
    )

    assert received["extra"]["zone"] == "sul"
    assert "place" not in received["extra"]


@pytest.mark.parametrize(
    "body",
    [
        {"segment": "restaurante"},
        {"segment": "restaurante", "zone": "lua"},
        {"segment": "restaurante", "neighborhood": "P"},
    ],
)
def test_search_needs_a_valid_zone_or_a_neighborhood(tmp_path, body):
    assert make_client(tmp_path).post("/api/search", json=body).status_code == 422


def test_saving_a_zone_search_keeps_the_zone_and_the_neighborhood_of_each_lead(tmp_path):
    client = make_client(tmp_path, zone_searcher)

    save_all(client, ZONE_SEARCH)

    saved = {item["name"]: item for item in client.get("/api/leads").json()}
    assert saved["Na Zona Sul"]["zone"] == "sul"
    assert saved["Na Zona Sul"]["neighborhood"] == "Moema"
    assert saved["Outro Lugar"]["neighborhood"] == "Saúde"


def test_leads_can_be_filtered_by_zone(tmp_path):
    client = make_client(tmp_path, zone_searcher)
    save_all(client, ZONE_SEARCH)

    assert len(client.get("/api/leads", params={"zone": "sul"}).json()) == 2
    assert client.get("/api/leads", params={"zone": "norte"}).json() == []
    assert client.get("/api/leads", params={"zone": "lua"}).status_code == 422


def test_the_export_follows_the_zone_filter(tmp_path):
    client = make_client(tmp_path, zone_searcher)
    save_all(client, ZONE_SEARCH)

    assert client.get("/api/export/leads", params={"zone": "sul"}).status_code == 200
    assert client.get("/api/export/leads", params={"zone": "norte"}).status_code == 404


def test_searched_zones_appear_as_one_area_with_the_zone(tmp_path):
    client = make_client(tmp_path, zone_searcher)
    save_all(client, ZONE_SEARCH)

    areas = client.get("/api/areas").json()

    assert len(areas) == 1
    assert (areas[0]["zone"], areas[0]["neighborhood"], areas[0]["total"]) == ("sul", "Zona Sul", 2)
