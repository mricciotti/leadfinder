import os
from contextlib import closing
from datetime import date
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
            added = db.add_leads(conn, result["leads"])
        return {
            "total": result["total"],
            "found": len(result["leads"]),
            "without_site": sum(
                lead["site_state"] == "sem_site_na_fonte" for lead in result["leads"]
            ),
            "added": added,
        }

    @app.patch("/api/leads/{lead_id}")
    def update_lead(lead_id: str, body: UpdateIn):
        with closing(db.connect(db_path)) as conn:
            lead = db.update_lead(conn, lead_id, **body.changes())
        if lead is None:
            raise HTTPException(404, "Lead não encontrado.")
        return scoring.with_evaluation(lead)

    return app


app = create_app(os.environ.get("LEADFINDER_DB", "leads.db"))
