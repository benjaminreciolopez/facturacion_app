from fastapi import APIRouter, Request
from app.core.templates import templates

router = APIRouter()

@router.get("/offline")
async def offline(request: Request):
    return templates.TemplateResponse("offline.html", {"request": request})
