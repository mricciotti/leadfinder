import httpx

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "leadfinder-personal/0.1"
MIN_HALF_SPAN = 0.008

SEGMENTS = {
    "restaurante": ("Restaurante", [("amenity", "restaurant")]),
    "lanchonete": ("Lanchonete", [("amenity", "fast_food")]),
    "bar": ("Bar", [("amenity", "bar"), ("amenity", "pub")]),
    "cafe": ("Café", [("amenity", "cafe")]),
    "padaria": ("Padaria", [("shop", "bakery")]),
    "salao": ("Salão de beleza", [("shop", "hairdresser"), ("shop", "beauty")]),
    "dentista": ("Dentista", [("amenity", "dentist"), ("healthcare", "dentist")]),
    "academia": ("Academia", [("leisure", "fitness_centre")]),
}

WEBSITE_TAGS = ("website", "contact:website", "url", "contact:url")
PHONE_TAGS = (
    "phone",
    "contact:phone",
    "mobile",
    "contact:mobile",
    "contact:whatsapp",
    "whatsapp",
)
INSTAGRAM_TAGS = ("contact:instagram", "instagram")


class PlaceNotFound(Exception):
    pass


def normalize_bbox(south, west, north, east):
    center_lat = (south + north) / 2
    center_lon = (west + east) / 2
    half_lat = max((north - south) / 2, MIN_HALF_SPAN)
    half_lon = max((east - west) / 2, MIN_HALF_SPAN)
    return (
        center_lat - half_lat,
        center_lon - half_lon,
        center_lat + half_lat,
        center_lon + half_lon,
    )


def bbox_from_nominatim(results):
    if not results:
        raise PlaceNotFound()
    south, north, west, east = (float(value) for value in results[0]["boundingbox"])
    return normalize_bbox(south, west, north, east)


def build_query(segment, bbox):
    south, west, north, east = bbox
    area = f"({south},{west},{north},{east})"
    filters = "".join(
        f'nwr["{key}"="{value}"]["name"]{area};'
        for key, value in SEGMENTS[segment][1]
    )
    return f"[out:json][timeout:90];({filters});out center tags;"


def first_value(tags, keys):
    for key in keys:
        value = tags.get(key)
        if value:
            return value.split(";")[0].strip()
    return None


def build_address(tags):
    parts = [
        tags.get("addr:street"),
        tags.get("addr:housenumber"),
        tags.get("addr:suburb"),
    ]
    return ", ".join(part for part in parts if part) or None


def score(phone, hours, address, instagram):
    return (
        (3 if phone else 0)
        + (1 if hours else 0)
        + (1 if address else 0)
        + (1 if instagram else 0)
    )


def parse_places(data, segment, neighborhood):
    named = [
        element
        for element in data.get("elements", [])
        if element.get("tags", {}).get("name")
    ]
    leads = []
    for element in named:
        tags = element["tags"]
        if any(tags.get(key) for key in WEBSITE_TAGS):
            continue
        point = element if "lat" in element else element.get("center", {})
        phone = first_value(tags, PHONE_TAGS)
        instagram = first_value(tags, INSTAGRAM_TAGS)
        address = build_address(tags)
        leads.append(
            {
                "id": f"{element['type']}-{element['id']}",
                "name": tags["name"],
                "segment": segment,
                "neighborhood": neighborhood,
                "phone": phone,
                "address": address,
                "instagram": instagram,
                "lat": point.get("lat"),
                "lon": point.get("lon"),
                "score": score(phone, tags.get("opening_hours"), address, instagram),
            }
        )
    return {"total": len(named), "leads": leads}


async def geocode(client, neighborhood, city):
    response = await client.get(
        NOMINATIM_URL,
        params={
            "q": f"{neighborhood}, {city}, Brasil",
            "format": "jsonv2",
            "limit": 1,
            "countrycodes": "br",
        },
    )
    response.raise_for_status()
    return bbox_from_nominatim(response.json())


async def search(segment, neighborhood, city):
    async with httpx.AsyncClient(
        timeout=90, headers={"User-Agent": USER_AGENT}
    ) as client:
        bbox = await geocode(client, neighborhood, city)
        response = await client.post(
            OVERPASS_URL, data={"data": build_query(segment, bbox)}
        )
        response.raise_for_status()
    return parse_places(response.json(), segment, neighborhood)
