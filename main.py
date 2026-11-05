import os
from contextlib import closing
from datetime import date
from uuid import uuid4
from pathlib import Path
from typing import Annotated, Literal

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, field_validator

import contacts
import db
import export
import filters
import overpass
import places
import scoring

INDEX = Path(__file__).parent / "static" / "index.html"
MAX_PREVIEWS = 10
RECOMMENDED_SITE_STATES = ("sem_site_na_fonte", "so_rede_social")


class SearchIn(BaseModel):
    segment: str
    neighborhood: str = Field(min_length=2)
    city: str = "São Paulo"


class LeadFilter(BaseModel):
    segment: str | None = None
    neighborhood: str | None = None
    city: str | None = None
    uf: str | None = None
    status: Literal[db.STATUSES] | None = None
    site: Literal[tuple(filters.SITE_FILTERS)] | None = None
    priority: Literal[scoring.PRIORITY_ORDER] | None = None
    offer: Literal[tuple(scoring.OFFERS)] | None = None
    phone: bool = False
    email: bool = False
    instagram: bool = False
    favorite: bool = False
    not_contacted: bool = False


class SaveIn(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=5000)


def is_recommended(lead):
    return (
        not lead["saved"]
        and not lead["duplicate"]
        and lead["evaluation"]["contact"]["channel"]
        and lead["site_state"] in RECOMMENDED_SITE_STATES
    )


def build_preview(conn, leads):
    saved = db.statuses_of(conn, [lead["id"] for lead in leads])
    shown = []
    kept = []
    for lead in leads:
        known = lead["id"] in saved
        duplicate = not known and (
            db.same_place_elsewhere(conn, lead)
            or any(db.same_place(lead, other) for other in kept)
        )
        if not known and not duplicate:
            kept.append(lead)
        shown.append(
            {
                **lead,
                "manual_whatsapp": None,
                "saved": known,
                "saved_status": saved.get(lead["id"]),
                "duplicate": duplicate,
            }
        )
    ranked = scoring.ranked(shown)
    return [{**lead, "recommended": bool(is_recommended(lead))} for lead in ranked]


def checked_phone(value, kinds):
    if not value:
        return ""
    national, kind = contacts.normalize_phone(value)
    if kind not in kinds:
        raise ValueError("Telefone inválido. Inclua o DDD.")
    return national


class UpdateIn(BaseModel):
    status: str | None = None
    notes: str | None = Field(default=None, max_length=2000)
    favorite: bool | None = None
    absence_confirmed: bool | None = None
    manual_phone: str | None = Field(default=None, max_length=40)
    manual_whatsapp: str | None = Field(default=None, max_length=40)
    manual_instagram: str | None = Field(default=None, max_length=200)
    manual_website: str | None = Field(default=None, max_length=500)

    @field_validator("status")
    @classmethod
    def status_must_exist(cls, value):
        if value is not None and value not in db.STATUSES:
            raise ValueError("Status inválido.")
        return value

    @field_validator("manual_phone")
    @classmethod
    def phone_must_have_ddd(cls, value):
        return checked_phone(value, ("celular", "fixo", "outro"))

    @field_validator("manual_whatsapp")
    @classmethod
    def whatsapp_must_have_ddd(cls, value):
        return checked_phone(value, ("celular", "fixo"))

    @field_validator("manual_instagram")
    @classmethod
    def instagram_must_be_a_profile(cls, value):
        if not value:
            return ""
        handle = contacts.normalize_instagram(value)
        if handle is None:
            raise ValueError("Instagram inválido. Use o @ ou o link do perfil.")
        return handle

    @field_validator("manual_website")
    @classmethod
    def website_must_be_own_site(cls, value):
        if not value:
            return ""
        url = contacts.normalize_url(value)
        if url is None:
            raise ValueError("Site inválido.")
        if contacts.classify_url(url) != "propria":
            raise ValueError("Isso não é um site próprio. Use o campo Instagram ou as anotações.")
        return url

    def changes(self):
        result = {}
        for key, value in self.model_dump(exclude_unset=True).items():
            if key in db.MANUAL_FIELDS:
                result[key] = value or None
            elif value is not None:
                result[key] = value
        return result


def create_app(db_path, searcher=overpass.search):
    app = FastAPI()
    previews = {}

    def filtered_leads(wanted):
        with closing(db.connect(db_path)) as conn:
            leads = db.list_leads(conn)
        return filters.apply(scoring.ranked(leads), wanted.model_dump())

    @app.get("/")
    def index():
        return FileResponse(INDEX)

    @app.get("/api/segments")
    def segments():
        return [
            {"key": key, "label": label}
            for key, (label, _) in overpass.SEGMENTS.items()
        ]

    @app.get("/api/leads")
    def list_leads(wanted: Annotated[LeadFilter, Query()]):
        return filtered_leads(wanted)

    @app.get("/api/leads-table")
    def leads_table(wanted: Annotated[LeadFilter, Query()]):
        return export.table(filtered_leads(wanted))

    @app.get("/api/neighborhoods")
    def neighborhoods(city: str = places.CITY):
        return places.names(city)

    @app.get("/api/areas")
    def searched_areas():
        with closing(db.connect(db_path)) as conn:
            return filters.areas(scoring.ranked(db.list_leads(conn)))

    @app.get("/api/filter-options")
    def filter_options():
        with closing(db.connect(db_path)) as conn:
            return filters.options(db.list_leads(conn))

    @app.get("/api/export/{kind}")
    def export_leads(kind: Literal["leads", "completo"], wanted: Annotated[LeadFilter, Query()]):
        leads = filtered_leads(wanted)
        if not leads:
            raise HTTPException(404, "Nenhum lead para exportar com esses filtros.")
        content = export.leads_csv(leads) if kind == "leads" else export.full_csv(leads)
        name = export.file_name(kind, wanted.model_dump(), date.today())
        return Response(
            content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    @app.post("/api/search")
    async def search(body: SearchIn):
        if body.segment not in overpass.SEGMENTS:
            raise HTTPException(400, "Segmento desconhecido.")
        neighborhood, city = body.neighborhood.strip(), body.city.strip()
        known_place = places.find(neighborhood, city)
        extra = {"place": known_place} if known_place else {}
        try:
            result = await searcher(body.segment, neighborhood, city, **extra)
        except overpass.PlaceNotFound:
            raise HTTPException(
                404, "Não encontrei esse bairro. Confira o nome e a cidade."
            )
        except httpx.HTTPError:
            raise HTTPException(
                502,
                "O OpenStreetMap não respondeu, mesmo depois de algumas tentativas. Espere um minuto e tente de novo.",
            )
        with closing(db.connect(db_path)) as conn:
            shown = build_preview(conn, result["leads"])
        search_id = uuid4().hex
        previews[search_id] = {lead["id"]: lead for lead in result["leads"]}
        while len(previews) > MAX_PREVIEWS:
            del previews[next(iter(previews))]
        return {
            "search_id": search_id,
            "total": result["total"],
            "found": len(shown),
            "new": sum(not lead["saved"] and not lead["duplicate"] for lead in shown),
            "known": sum(lead["saved"] for lead in shown),
            "duplicates": sum(lead["duplicate"] for lead in shown),
            "without_site": sum(
                lead["site_state"] == "sem_site_na_fonte" for lead in shown
            ),
            "recommended": sum(lead["recommended"] for lead in shown),
            "leads": shown,
        }

    @app.post("/api/search/{search_id}/save")
    def save_search(search_id: str, body: SaveIn):
        found = previews.get(search_id)
        if found is None:
            raise HTTPException(404, "A prévia expirou. Faça a busca de novo.")
        if any(lead_id not in found for lead_id in body.ids):
            raise HTTPException(400, "Algum lead escolhido não faz parte desta busca.")
        with closing(db.connect(db_path)) as conn:
            saved = db.statuses_of(conn, list(found))
            chosen = [found[lead_id] for lead_id in dict.fromkeys(body.ids) if lead_id not in saved]
            refreshed = [lead for lead_id, lead in found.items() if lead_id in saved]
            added = db.add_leads(conn, chosen + refreshed)
        del previews[search_id]
        return {"added": added, "refreshed": len(refreshed)}

    @app.patch("/api/leads/{lead_id}")
    def update_lead(lead_id: str, body: UpdateIn):
        with closing(db.connect(db_path)) as conn:
            lead = db.update_lead(conn, lead_id, **body.changes())
        if lead is None:
            raise HTTPException(404, "Lead não encontrado.")
        return scoring.with_evaluation(lead)

    return app


app = create_app(os.environ.get("LEADFINDER_DB", "leads.db"))
