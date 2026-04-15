from fastapi import FastAPI, Request, Depends, HTTPException, status, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import os

from app.models.database import get_db, Admin
from app.dependencies import templates, serializer, get_current_user

app = FastAPI(title="Agentic AI Timetable System")

pwd_context = CryptContext(schemes=["sha256_crypt", "bcrypt"], deprecated="auto")

# Static
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request, user = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/dashboard")
    return RedirectResponse(url="/login")

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    admin = db.query(Admin).filter(Admin.username == username).first()
    if admin and pwd_context.verify(password, admin.password_hash):
        response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
        session_token = serializer.dumps(username)
        response.set_cookie(key="session", value=session_token, httponly=True)
        return response
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("session")
    return response

# Import routers
from app.routes import dashboard, timetable
app.include_router(dashboard.router)
app.include_router(timetable.router)
