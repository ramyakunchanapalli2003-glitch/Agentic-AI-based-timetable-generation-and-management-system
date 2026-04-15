from fastapi import FastAPI, Request, Depends, HTTPException, status, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from passlib.context import CryptContext
import os
import time

from app.models.database import get_db, Admin, SessionLocal, init_db, DB_URL
from app.dependencies import templates, serializer, get_current_user

app = FastAPI(title="Agentic AI Timetable System")

@app.on_event("startup")
async def startup_event():
    # Ensure database directory exists
    db_dir = "./database"
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)

    # Log DB type for debugging (mask credentials)
    if DB_URL.startswith("postgresql"):
        print(f"[STARTUP] Using PostgreSQL database")
    else:
        print(f"[STARTUP] Using SQLite database")

    # Retry DB connection up to 3 times
    for attempt in range(3):
        try:
            init_db()
            print(f"[STARTUP] Database initialized successfully (attempt {attempt + 1})")
            break
        except Exception as e:
            print(f"[STARTUP] DB init attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(2)
            else:
                print("[STARTUP] WARNING: Could not initialize database after 3 attempts. App will start but DB operations may fail.")
                return

    db = SessionLocal()
    try:
        admin = db.query(Admin).filter(Admin.username == "admin").first()
        hashed_password = pwd_context.hash("admin123")
        if not admin:
            new_admin = Admin(username="admin", password_hash=hashed_password)
            db.add(new_admin)
            db.commit()
            print("[STARTUP] Default admin user created")
        else:
            # Always refresh hash to ensure compatibility with current scheme
            admin.password_hash = hashed_password
            db.commit()
            print("[STARTUP] Admin password hash refreshed")
    except Exception as e:
        db.rollback()
        print(f"[STARTUP] Error creating admin user: {e}")
    finally:
        db.close()

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
    return templates.TemplateResponse(request=request, name="login.html", context={"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    try:
        admin = db.query(Admin).filter(Admin.username == username).first()
        if admin and pwd_context.verify(password, admin.password_hash):
            response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
            session_token = serializer.dumps(username)
            response.set_cookie(key="session", value=session_token, httponly=True)
            return response
    except Exception as e:
        print(f"Login error: {e}")
        # If hash verification fails due to scheme issues, try to fix the hash
        try:
            admin = db.query(Admin).filter(Admin.username == username).first()
            if admin:
                admin.password_hash = pwd_context.hash("admin123")
                db.commit()
                print("Admin password hash regenerated due to scheme incompatibility")
                # Retry verification
                if pwd_context.verify(password, admin.password_hash):
                    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
                    session_token = serializer.dumps(username)
                    response.set_cookie(key="session", value=session_token, httponly=True)
                    return response
        except Exception as e2:
            print(f"Hash regeneration also failed: {e2}")
        return templates.TemplateResponse(request=request, name="login.html", context={"request": request, "error": "Login error. Please try again."})
    return templates.TemplateResponse(request=request, name="login.html", context={"request": request, "error": "Invalid credentials"})

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("session")
    return response

# Import routers
from app.routes import dashboard, timetable
app.include_router(dashboard.router)
app.include_router(timetable.router)
