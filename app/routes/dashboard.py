from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.database import get_db, Timetable, AgentLog
from app.dependencies import templates, login_required

router = APIRouter()

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, db: Session = Depends(get_db), user = Depends(login_required)):
    # Stats
    total_timetables = db.query(Timetable).count()
    last_timetable = db.query(Timetable).order_by(Timetable.created_at.desc()).first()
    
    all_timetables = db.query(Timetable).order_by(Timetable.created_at.desc()).all()
    recent_logs = db.query(AgentLog).order_by(AgentLog.timestamp.desc()).limit(10).all()

    # Unique values for filters
    departments = sorted(set(t.department for t in all_timetables))
    courses = sorted(set(t.course for t in all_timetables))

    # Toast message from query params (e.g. after delete)
    toast = request.query_params.get("toast", "")

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "total": total_timetables,
        "last_date": last_timetable.created_at if last_timetable else "N/A",
        "recent_timetables": all_timetables,
        "recent_logs": recent_logs,
        "departments": departments,
        "courses": courses,
        "toast": toast
    })
