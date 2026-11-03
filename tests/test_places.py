import asyncio
import json
import re
from urllib.parse import unquote_plus

import httpx
import pytest

import contacts
import overpass
import places


def node(name, place="suburb", lat=-23.5, lon=-46.6, **extra):
    return {"type": "node", "lat": lat, "lon": lon, "tags": {"name": name, "place": place}, **extra}


def test_from_overpass_keeps_the_name_and_a_rounded_point():
    result = places.from_overpass({"elements": [node("Pinheiros", lat=-23.563571234, lon=-46.685701234)]})

    assert result == [{"name": "Pinheiros", "lat": -23.56357, "lon": -46.6857}]


def test_from_overpass_uses_the_center_of_ways_and_relations():
    way = {"type": "way", "center": {"lat": -23.5, "lon": -46.6}, "tags": {"name": "Mooca", "place": "suburb"}}

    assert places.from_overpass({"elements": [way]})[0]["lat"] == -23.5


def test_from_overpass_ignores_elements_without_name_point_or_place():
    elements = [
        node(""),
        {"type": "node", "lat": -23.5, "lon": -46.6, "tags": {"place": "suburb"}},
        {"type": "way", "tags": {"name": "Sem ponto", "place": "suburb"}},
        {"type": "node", "lat": -23.5, "lon": -46.6, "tags": {"name": "Estrada", "place": "locality"}},
        {"type": "node", "lat": -23.5, "lon": -46.6, "tags": {"name": "Rio"}},
    ]

    assert places.from_overpass({"elements": elements}) == []


def test_from_overpass_dedupes_by_name_ignoring_case_and_accents():
    result = places.from_overpass({"elements": [node("Saúde"), node("SAUDE"), node("saude")]})

    assert len(result) == 1


def test_from_overpass_prefers_the_suburb_over_smaller_places():
    elements = [
        node("Vila Nova", place="neighbourhood", lat=-23.1),
        node("Vila Nova", place="suburb", lat=-23.2),
        node("Vila Nova", place="quarter", lat=-23.3),
    ]

    assert places.from_overpass({"elements": elements})[0]["lat"] == -23.2


def test_from_overpass_sorts_ignoring_accents():
    result = places.from_overpass({"elements": [node("Zona"), node("Água Branca"), node("Bela Vista")]})

    assert [item["name"] for item in result] == ["Água Branca", "Bela Vista", "Zona"]


def test_save_writes_a_file_that_loads_back(tmp_path, monkeypatch):
    path = tmp_path / "bairros.json"
    places.save([{"name": "Pinheiros", "lat": -23.5, "lon": -46.6}], path)
    monkeypatch.setattr(places, "DATA", path)
    places.neighborhoods.cache_clear()

    try:
        assert places.names("São Paulo") == ["Pinheiros"]
    finally:
        places.neighborhoods.cache_clear()
    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["city"] == "São Paulo"
    assert document["source"] == "OpenStreetMap (Overpass)"
    assert document["downloaded_at"]


def test_the_shipped_file_is_a_sane_list_of_sao_paulo_neighborhoods():
    items = places.neighborhoods()
    keys = [contacts.text_key(item["name"]) for item in items]

    assert len(items) > 300
    assert len(keys) == len(set(keys))
    for popular in ("Pinheiros", "Vila Madalena", "Moema", "Saúde", "Itaim Bibi", "Mooca"):
        assert contacts.text_key(popular) in keys
    assert all(-24.1 < item["lat"] < -23.3 and -46.9 < item["lon"] < -46.3 for item in items)


def test_names_only_for_sao_paulo():
    assert "Pinheiros" in places.names("São Paulo")
    assert "Pinheiros" in places.names("  sao paulo ")
    assert places.names("Santos") == []


def test_find_ignores_case_and_accents():
    found = places.find("saude", "São Paulo")

    assert found["name"] == "Saúde"
    assert found["uf"] == "SP"
    assert -24.1 < found["lat"] < -23.3


def test_find_returns_nothing_for_unknown_names_and_other_cities():
    assert places.find("Bairro Que Não Existe", "São Paulo") is None
    assert places.find("Pinheiros", "Santos") is None
    assert places.find("", "São Paulo") is None


def test_refresh_downloads_and_saves(tmp_path, monkeypatch):
    path = tmp_path / "novo.json"
    monkeypatch.setattr(places, "DATA", path)
    places.neighborhoods.cache_clear()
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"elements": [node("Pinheiros"), node("Moema")]})
    )
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        places.httpx, "AsyncClient", lambda **kwargs: real_client(transport=transport, **kwargs)
    )

    try:
        assert asyncio.run(places.refresh()) == 2
        assert places.names("São Paulo") == ["Moema", "Pinheiros"]
    finally:
        places.neighborhoods.cache_clear()


def test_search_with_a_known_place_skips_nominatim_and_searches_around_its_point():
    queries = []

    def handler(request):
        assert "nominatim" not in request.url.host
        queries.append(request.content.decode())
        return httpx.Response(200, json={"elements": []})

    async def no_sleep(seconds):
        raise AssertionError("não deveria esperar")

    place = {"name": "Pinheiros", "lat": -23.5636, "lon": -46.6857, "uf": "SP"}

    result = asyncio.run(
        overpass.search(
            "restaurante", "Pinheiros", "São Paulo",
            transport=httpx.MockTransport(handler), sleep=no_sleep, place=place,
        )
    )

    assert result == {"total": 0, "leads": []}
    assert len(queries) == 1
    box = re.search(r"\((-?[\d.]+),(-?[\d.]+),(-?[\d.]+),(-?[\d.]+)\)", unquote_plus(queries[0]))
    south, west, north, east = (float(value) for value in box.groups())
    assert (south, west, north, east) == pytest.approx(
        (-23.5716, -46.6937, -23.5556, -46.6777), abs=1e-6
    )


def test_search_with_a_known_place_fills_city_and_uf():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"elements": [{"type": "node", "id": 1, "lat": -23.56, "lon": -46.68, "tags": {"name": "Cantina"}}]},
        )
    )
    place = {"name": "Pinheiros", "lat": -23.5636, "lon": -46.6857, "uf": "SP"}

    lead = asyncio.run(
        overpass.search("restaurante", "Pinheiros", "São Paulo", transport=transport, place=place)
    )["leads"][0]

    assert (lead["city"], lead["uf"], lead["neighborhood"]) == ("São Paulo", "SP", "Pinheiros")


@pytest.mark.parametrize("status", [502, 504])
def test_search_with_a_known_place_still_retries(status):
    answers = iter([status, 200])
    waits = []

    def handler(request):
        code = next(answers)
        return httpx.Response(code, json={"elements": []})

    async def sleep(seconds):
        waits.append(seconds)

    place = {"name": "Pinheiros", "lat": -23.5636, "lon": -46.6857, "uf": "SP"}

    asyncio.run(
        overpass.search(
            "restaurante", "Pinheiros", "São Paulo",
            transport=httpx.MockTransport(handler), sleep=sleep, place=place,
        )
    )

    assert waits == [overpass.RETRY_WAITS[0]]
