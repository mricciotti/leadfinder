import os
from contextlib import closing
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

import db
import overpass

INDEX = Path(__file__).parent / "static" / "index.html"


class SearchIn(BaseModel):
    segment: str
    neighborhood: str = Field(min_length=2)
    city: str = "São Paulo"


class UpdateIn(BaseModel):
    status: str | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("status")
    @classmethod
    def status_must_exist(cls, value):
        if value is not None and value not in db.STATUSES:
            raise ValueError("Status inválido.")
        return value


def create_app(db_path, searcher=overpass.search):
    app = FastAPI()

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
    def list_leads():
        with closing(db.connect(db_path)) as conn:
            return db.list_leads(conn)

    @app.post("/api/search")
    async def search(body: SearchIn):
        if body.segment not in overpass.SEGMENTS:
            raise HTTPException(400, "Segmento desconhecido.")
        try:
            result = await searcher(
                body.segment, body.neighborhood.strip(), body.city.strip()
            )
        except overpass.PlaceNotFound:
            raise HTTPException(
                404, "Não encontrei esse bairro. Confira o nome e a cidade."
            )
        except httpx.HTTPError:
            raise HTTPException(
                502,
                "O OpenStreetMap não respondeu. Tente de novo em alguns instantes.",
            )
        with closing(db.connect(db_path)) as conn:
            added = db.add_leads(conn, result["leads"])
        return {
            "total": result["total"],
            "found": len(result["leads"]),
            "added": added,
        }

    @app.patch("/api/leads/{lead_id}")
    def update_lead(lead_id: str, body: UpdateIn):
        with closing(db.connect(db_path)) as conn:
            lead = db.update_lead(conn, lead_id, body.status, body.notes)
        if lead is None:
            raise HTTPException(404, "Lead não encontrado.")
        return lead

    return app


app = create_app(os.environ.get("LEADFINDER_DB", "leads.db"))
