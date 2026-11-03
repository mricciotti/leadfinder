import asyncio
import json
from datetime import date
from functools import lru_cache
from pathlib import Path

import httpx

import contacts
import overpass

DATA = Path(__file__).parent / "bairros_sp.json"
CITY = "São Paulo"
UF = "SP"
CLASS_ORDER = ("suburb", "quarter", "neighbourhood")

QUERY = """
[out:json][timeout:120];
area(3600298285)->.sp;
nwr(area.sp)["place"~"^(suburb|neighbourhood|quarter)$"]["name"];
out tags center;
"""


def from_overpass(data):
    best = {}
    for element in data.get("elements", []):
        tags = element.get("tags", {})
        name = (tags.get("name") or "").strip()
        point = element if "lat" in element else element.get("center")
        if tags.get("place") not in CLASS_ORDER or not name or not point:
            continue
        key = contacts.text_key(name)
        rank = CLASS_ORDER.index(tags["place"])
        if key not in best or rank < best[key][0]:
            best[key] = (
                rank,
                {"name": name, "lat": round(point["lat"], 5), "lon": round(point["lon"], 5)},
            )
    items = [item for _, item in best.values()]
    return sorted(items, key=lambda item: contacts.text_key(item["name"]))


def save(neighborhoods, path=None):
    document = {
        "city": CITY,
        "uf": UF,
        "source": "OpenStreetMap (Overpass)",
        "downloaded_at": date.today().isoformat(),
        "neighborhoods": neighborhoods,
    }
    (path or DATA).write_text(
        json.dumps(document, ensure_ascii=False, indent=1), encoding="utf-8"
    )


@lru_cache(maxsize=1)
def neighborhoods():
    return tuple(json.loads(DATA.read_text(encoding="utf-8"))["neighborhoods"])


def names(city):
    if contacts.text_key(city) != contacts.text_key(CITY):
        return []
    return [item["name"] for item in neighborhoods()]


def find(neighborhood, city):
    if contacts.text_key(city) != contacts.text_key(CITY):
        return None
    wanted = contacts.text_key(neighborhood)
    return next(
        (
            {**item, "uf": UF}
            for item in neighborhoods()
            if contacts.text_key(item["name"]) == wanted
        ),
        None,
    )


async def refresh():
    async with httpx.AsyncClient(
        timeout=150, headers={"User-Agent": overpass.USER_AGENT}
    ) as client:
        data = await overpass.query_overpass(client, QUERY, asyncio.sleep)
    items = from_overpass(data)
    save(items)
    return len(items)


if __name__ == "__main__":
    print(f"{asyncio.run(refresh())} bairros gravados em {DATA.name}")
