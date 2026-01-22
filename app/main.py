from fastapi import FastAPI, Depends, Query, Form, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.requests import Request
import os
import secrets
import hashlib

from .database import get_db, init_db
from .models import Company, Attendee

app = FastAPI(title="BGSA CEO Conference App")

# Simple auth config
AUTH_USERNAME = "outpost"
AUTH_PASSWORD = "zachiscool"
SESSION_SECRET = os.getenv("SESSION_SECRET", secrets.token_hex(32))

# Store active sessions (in production, use Redis or similar)
active_sessions = set()

# Mount static files
static_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Templates
templates_path = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_path)


def create_session_token():
    token = secrets.token_hex(32)
    active_sessions.add(token)
    return token


def verify_session(session_token: str = Cookie(None)):
    return session_token and session_token in active_sessions


@app.on_event("startup")
def startup():
    init_db()


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = None):
    return templates.TemplateResponse("login.html", {"request": request, "error": error})


@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    if username.lower() == AUTH_USERNAME.lower() and password == AUTH_PASSWORD:
        response = RedirectResponse(url="/", status_code=303)
        token = create_session_token()
        response.set_cookie(key="session_token", value=token, httponly=True, max_age=86400)
        return response
    return RedirectResponse(url="/login?error=1", status_code=303)


@app.get("/logout")
def logout(session_token: str = Cookie(None)):
    if session_token in active_sessions:
        active_sessions.discard(session_token)
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session_token")
    return response


@app.get("/", response_class=HTMLResponse)
def home(request: Request, session_token: str = Cookie(None)):
    if not verify_session(session_token):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/prospects")
def get_prospects(
    filter: str = Query("all", pattern="^(all|gate|truck|other)$"),
    search: str = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    dedupe: bool = Query(True),
    db: Session = Depends(get_db),
    session_token: str = Cookie(None)
):
    if not verify_session(session_token):
        return {"error": "Unauthorized"}

    # Require 2+ characters for search (return empty if too short)
    if search and len(search) < 2:
        return []

    query = db.query(Attendee).join(Company)

    # Apply filter
    if filter == "gate":
        query = query.filter(Company.category.in_(["gate", "both"]))
        query = query.order_by(Attendee.gate_fit_score.desc(), Attendee.id)
    elif filter == "truck":
        query = query.filter(Company.category.in_(["truck", "both"]))
        query = query.order_by(Attendee.truck_fit_score.desc(), Attendee.id)
    elif filter == "other":
        query = query.filter(Company.category == "other")
        query = query.order_by(Company.name, Attendee.id)
    else:
        query = query.order_by(Attendee.combined_score.desc(), Attendee.id)

    # Apply search
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Attendee.first_name.ilike(search_term)) |
            (Attendee.last_name.ilike(search_term)) |
            (Company.name.ilike(search_term))
        )

    attendees = query.all()

    # Deduplicate: one attendee per company (keep first by score order)
    # But show all attendees when searching (user wants to find specific people)
    if dedupe and not search:
        seen_companies = set()
        deduped = []
        for a in attendees:
            if a.company_id not in seen_companies:
                seen_companies.add(a.company_id)
                deduped.append(a)
        attendees = deduped

    # Apply pagination after deduplication
    total = len(attendees)
    attendees = attendees[offset:offset + limit]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "prospects": [
            {
                "id": a.id,
                "name": a.full_name,
                "company_name": a.company.name,
                "job_title": a.job_title,
                "dc_count": a.company.dc_count,
                "truck_count": a.company.truck_count,
                "gate_fit_score": a.gate_fit_score,
                "truck_fit_score": a.truck_fit_score,
                "hook": a.company.hook,
                "category": a.company.category,
                "ticket_type": a.ticket_type,
            }
            for a in attendees
        ]
    }


@app.get("/api/prospects/{prospect_id}")
def get_prospect(prospect_id: int, db: Session = Depends(get_db), session_token: str = Cookie(None)):
    if not verify_session(session_token):
        return {"error": "Unauthorized"}

    attendee = db.query(Attendee).join(Company).filter(Attendee.id == prospect_id).first()

    if not attendee:
        return {"error": "Not found"}

    return {
        "id": attendee.id,
        "name": attendee.full_name,
        "company_name": attendee.company.name,
        "job_title": attendee.job_title,
        # Company data
        "company_overview": attendee.company.overview,
        "dc_count": attendee.company.dc_count,
        "truck_count": attendee.company.truck_count,
        "gate_fit_score": attendee.gate_fit_score,
        "truck_fit_score": attendee.truck_fit_score,
        "category": attendee.company.category,
        "hook": attendee.company.hook,
        "company_bullets": attendee.company.company_bullets or [],
        # CSV metadata
        "email": attendee.email,
        "linkedin_url": attendee.linkedin_url,
        "ticket_type": attendee.ticket_type,
        "job_function": attendee.job_function,
        "management_level": attendee.management_level,
    }
