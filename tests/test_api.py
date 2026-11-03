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


def test_search_stores_leads_and_reports_counts(tmp_path):
    client = make_client(tmp_path)

    response = client.post("/api/search", json=SEARCH)

    assert response.status_code == 200
    assert response.json() == {"total": 5, "found": 3, "without_site": 2, "added": 3}


def test_searching_twice_adds_nothing_new(tmp_path):
    client = make_client(tmp_path)
    client.post("/api/search", json=SEARCH)

    response = client.post("/api/search", json=SEARCH)

    assert response.json()["added"] == 0
    assert len(client.get("/api/leads").json()) == 3


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
    client.post("/api/search", json=SEARCH)

    names = [item["name"] for item in client.get("/api/leads").json()]

    assert names == ["Alto", "Baixo", "Com Site"]


def test_leads_carry_their_evaluation(tmp_path):
    client = make_client(tmp_path)
    client.post("/api/search", json=SEARCH)

    saved = {item["id"]: item for item in client.get("/api/leads").json()}

    assert saved["node-1"]["evaluation"]["opportunity"]["level"] == "media"
    assert saved["node-1"]["evaluation"]["offers"][0]["label"] == "Landing page"
    assert saved["node-3"]["evaluation"]["opportunity"]["level"] == "indeterminada"


def test_leads_carry_the_site_state(tmp_path):
    client = make_client(tmp_path)
    client.post("/api/search", json=SEARCH)

    saved = {item["id"]: item for item in client.get("/api/leads").json()}

    assert saved["node-1"]["site_state"] == "sem_site_na_fonte"
    assert saved["node-3"]["site_state"] == "site_informado"
    assert saved["node-3"]["website"] == "https://comsite.com.br"
    assert saved["node-3"]["other_links"] == []


def test_patch_updates_status_and_notes(tmp_path):
    client = make_client(tmp_path)
    client.post("/api/search", json=SEARCH)

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
    client.post("/api/search", json=SEARCH)

    response = client.patch("/api/leads/node-2", json={"status": "inventado"})

    assert response.status_code == 422


def test_patch_returns_404_for_unknown_lead(tmp_path):
    response = make_client(tmp_path).patch(
        "/api/leads/node-404", json={"status": "fechado"}
    )

    assert response.status_code == 404


def searched_client(tmp_path):
    client = make_client(tmp_path)
    client.post("/api/search", json=SEARCH)
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
    client.post("/api/search", json=SEARCH)

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
