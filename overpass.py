import asyncio

import httpx

import contacts
import zones

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "leadfinder-personal/0.1"
MIN_HALF_SPAN = 0.008
ZONE_TIMEOUT = 180
RETRY_STATUSES = (429, 502, 503, 504)
RETRY_WAITS = (5, 15, 30)

SEGMENTS = {
    "restaurante": ("Restaurante", [("amenity", "restaurant")]),
    "lanchonete": ("Lanchonete", [("amenity", "fast_food")]),
    "bar": ("Bar", [("amenity", "bar"), ("amenity", "pub")]),
    "cafe": ("Café", [("amenity", "cafe")]),
    "padaria": ("Padaria", [("shop", "bakery")]),
    "salao": ("Salão de beleza", [("shop", "hairdresser"), ("shop", "beauty")]),
    "dentista": ("Dentista", [("amenity", "dentist"), ("healthcare", "dentist")]),
    "academia": ("Academia", [("leisure", "fitness_centre")]),
    "clinica": (
        "Clínica e consultório",
        [
            ("amenity", "doctors"),
            ("amenity", "clinic"),
            ("healthcare", "doctor"),
            ("healthcare", "clinic"),
        ],
    ),
    "oficina": ("Oficina mecânica", [("shop", "car_repair")]),
    "petshop": ("Pet shop", [("shop", "pet"), ("shop", "pet_grooming")]),
    "veterinario": ("Veterinário", [("amenity", "veterinary")]),
    "confeitaria": (
        "Confeitaria e doceria",
        [("shop", "pastry"), ("shop", "confectionery")],
    ),
    "sorveteria": ("Sorveteria", [("amenity", "ice_cream")]),
    "otica": ("Ótica", [("shop", "optician")]),
    "imobiliaria": ("Imobiliária", [("office", "estate_agent")]),
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
FACEBOOK_TAGS = ("contact:facebook", "facebook")
OTHER_LINK_TAGS = ("contact:tiktok", "contact:youtube", "contact:linkedin", "contact:twitter")
EMAIL_TAGS = ("email", "contact:email")
NEIGHBORHOOD_TAGS = ("addr:suburb", "addr:neighbourhood")


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


def uf_from_nominatim(results):
    address = results[0].get("address", {}) if results else {}
    return contacts.normalize_uf(address.get("ISO3166-2-lvl4"))


def build_query(segment, bbox):
    south, west, north, east = bbox
    area = f"({south},{west},{north},{east})"
    filters = "".join(
        f'nwr["{key}"="{value}"]["name"]{area};'
        for key, value in SEGMENTS[segment][1]
    )
    return f"[out:json][timeout:90];({filters});out center tags;"


def build_zone_query(segment, districts):
    names = "|".join(districts)
    filters = "".join(
        f'nwr["{key}"="{value}"]["name"](area.zone);'
        for key, value in SEGMENTS[segment][1]
    )
    return (
        f"[out:json][timeout:{ZONE_TIMEOUT}];"
        f'area["name"="{zones.CITY}"]["boundary"="administrative"]["admin_level"="8"]->.city;'
        f'rel(area.city)["boundary"="administrative"]["admin_level"="9"]["name"~"^({names})$"]->.districts;'
        "foreach.districts->.district("
        ".district out tags;"
        ".district map_to_area->.zone;"
        f"({filters});out center tags;"
        ");"
    )


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


def presence(tags):
    found = {
        "instagram": first_value(tags, INSTAGRAM_TAGS),
        "facebook": first_value(tags, FACEBOOK_TAGS),
        "other_links": [
            first_value(tags, (key,)) for key in OTHER_LINK_TAGS if tags.get(key)
        ],
        "website": None,
        "site_state": "sem_site_na_fonte",
    }
    url = contacts.normalize_url(first_value(tags, WEBSITE_TAGS))
    if url is None:
        return found
    kind = contacts.classify_url(url)
    if kind == "propria":
        return {**found, "website": url, "site_state": "site_informado"}
    if kind in ("instagram", "facebook") and not found[kind]:
        found[kind] = url
    else:
        found["other_links"].append(url)
    return {**found, "site_state": "so_rede_social"}


def score(phone, hours, address, instagram):
    return (
        (3 if phone else 0)
        + (1 if hours else 0)
        + (1 if address else 0)
        + (1 if instagram else 0)
    )


def group_by_district(data):
    current, districts, seen, elements = None, {}, set(), []
    for element in data.get("elements", []):
        tags = element.get("tags", {})
        if tags.get("boundary") == "administrative":
            current = tags.get("name")
            continue
        key = (element["type"], element["id"])
        if key not in seen:
            seen.add(key)
            districts[key] = current
            elements.append(element)
    return elements, districts


def parse_places(data, segment, neighborhood, city=None, uf=None, zone=None):
    if zone:
        elements, districts = group_by_district(data)
    else:
        elements, districts = data.get("elements", []), {}
    named = [element for element in elements if element.get("tags", {}).get("name")]
    leads = []
    for element in named:
        tags = element["tags"]
        point = element if "lat" in element else element.get("center", {})
        phone = first_value(tags, PHONE_TAGS)
        phone_national, phone_kind = contacts.normalize_phone(phone)
        address = build_address(tags)
        links = presence(tags)
        leads.append(
            {
                "id": f"{element['type']}-{element['id']}",
                "name": tags["name"],
                "segment": segment,
                "neighborhood": (
                    first_value(tags, NEIGHBORHOOD_TAGS)
                    or districts.get((element["type"], element["id"]))
                    or neighborhood
                    if zone
                    else neighborhood
                ),
                "zone": zone,
                "phone": phone,
                "phone_national": phone_national,
                "phone_kind": phone_kind,
                "address": address,
                "city": tags.get("addr:city") or city,
                "uf": contacts.normalize_uf(tags.get("addr:state")) or uf,
                "email": first_value(tags, EMAIL_TAGS),
                **links,
                "lat": point.get("lat"),
                "lon": point.get("lon"),
                "score": score(
                    phone, tags.get("opening_hours"), address, links["instagram"]
                ),
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
            "addressdetails": 1,
        },
    )
    response.raise_for_status()
    results = response.json()
    return bbox_from_nominatim(results), uf_from_nominatim(results)


async def query_overpass(client, query, sleep):
    for wait in (*RETRY_WAITS, None):
        try:
            response = await client.post(OVERPASS_URL, data={"data": query})
            if response.status_code not in RETRY_STATUSES:
                response.raise_for_status()
                return response.json()
            failure = httpx.HTTPStatusError(
                "O Overpass está ocupado.", request=response.request, response=response
            )
        except httpx.TimeoutException as error:
            failure = error
        if wait is None:
            raise failure
        await sleep(wait)


async def search(
    segment,
    neighborhood,
    city,
    transport=None,
    sleep=asyncio.sleep,
    place=None,
    zone=None,
):
    timeout = ZONE_TIMEOUT + 20 if zone else 90
    async with httpx.AsyncClient(
        timeout=timeout, headers={"User-Agent": USER_AGENT}, transport=transport
    ) as client:
        if zone:
            uf = zones.UF
            query = build_zone_query(segment, zones.districts(zone))
        elif place:
            bbox = normalize_bbox(place["lat"], place["lon"], place["lat"], place["lon"])
            uf = place["uf"]
            query = build_query(segment, bbox)
        else:
            bbox, uf = await geocode(client, neighborhood, city)
            query = build_query(segment, bbox)
        data = await query_overpass(client, query, sleep)
    return parse_places(data, segment, neighborhood, city, uf, zone)
