import httpx
import pytest
from fastapi.testclient import TestClient

import main
import overpass


def lead(lead_id, name, score):
    return {
        "id": lead_id,
        "name": name,
        "segment": "restaurante",
        "neighborhood": "Pinheiros",
        "phone": None,
        "address": None,
        "instagram": None,
        "lat": -23.56,
        "lon": -46.69,
        "score": score,
    }


async def fake_searcher(segment, neighborhood, city):
    return {
        "total": 5,
        "leads": [lead("node-1", "Baixo", 1), lead("node-2", "Alto", 6)],
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
    assert response.json() == {"total": 5, "found": 2, "added": 2}


def test_searching_twice_adds_nothing_new(tmp_path):
    client = make_client(tmp_path)
    client.post("/api/search", json=SEARCH)

    response = client.post("/api/search", json=SEARCH)

    assert response.json()["added"] == 0
    assert len(client.get("/api/leads").json()) == 2


def test_search_passes_trimmed_inputs_and_default_city(tmp_path):
    received = {}

    async def spy(segment, neighborhood, city):
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
    async def not_found(segment, neighborhood, city):
        raise overpass.PlaceNotFound()

    response = make_client(tmp_path, not_found).post("/api/search", json=SEARCH)

    assert response.status_code == 404
    assert "bairro" in response.json()["detail"]


def test_search_reports_network_failure_as_502(tmp_path):
    async def offline(segment, neighborhood, city):
        raise httpx.ConnectError("sem rede")

    response = make_client(tmp_path, offline).post("/api/search", json=SEARCH)

    assert response.status_code == 502


def test_leads_come_back_best_score_first(tmp_path):
    client = make_client(tmp_path)
    client.post("/api/search", json=SEARCH)

    names = [item["name"] for item in client.get("/api/leads").json()]

    assert names == ["Alto", "Baixo"]


def test_patch_updates_status_and_notes(tmp_path):
    client = make_client(tmp_path)
    client.post("/api/search", json=SEARCH)

    response = client.patch(
        "/api/leads/node-2", json={"status": "contatado", "notes": "Mandei mensagem"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "contatado"
    assert response.json()["notes"] == "Mandei mensagem"
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
