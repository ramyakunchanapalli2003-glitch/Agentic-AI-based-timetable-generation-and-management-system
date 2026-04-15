from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session
import json
import datetime

from io import BytesIO
from xhtml2pdf import pisa

from app.models.database import get_db, Timetable, AgentLog
from app.dependencies import templates, login_required
from app.agents.generation import GenerationAgent
from app.agents.validation import ValidationAgent

router = APIRouter()

@router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request, user = Depends(login_required)):
    return templates.TemplateResponse("setup.html", {"request": request, "user": user})

@router.post("/generate")
async def generate_timetable(
    request: Request, 
    department: str = Form(...),
    course: str = Form(...),
    semester: int = Form(...),
    subjects_json: str = Form(...),
    db: Session = Depends(get_db), 
    user = Depends(login_required)
):
    subjects = json.loads(subjects_json)

    # Check for duplicate timetable
    existing = db.query(Timetable).filter(
        Timetable.department == department,
        Timetable.course == course,
        Timetable.semester == semester
    ).first()
    if existing:
        return templates.TemplateResponse("setup.html", {
            "request": request,
            "error": f"A timetable for {department} - {course} - Semester {semester} already exists. Please delete the existing one first from the dashboard.",
            "user": user
        })
    
    existing_timetables = db.query(Timetable).all()
    busy_faculty = {} # day -> slot_idx -> set of normalized faculty names
    
    def normalize_name_set(name):
        """Helper to get set of normalized names from a string."""
        if not name: return set()
        raw_names = []
        for delimiter in [',', '&', ' and ']:
            if delimiter in name:
                if not raw_names:
                    raw_names = [n.strip() for n in name.split(delimiter)]
                else:
                    new_names = []
                    for rn in raw_names:
                        new_names.extend([n.strip() for n in rn.split(delimiter)])
                    raw_names = new_names
        if not raw_names: raw_names = [name.strip()]
        normalized = set()
        titles = ["dr.", "prof.", "mr.", "mrs.", "ms.", "er."]
        for n in raw_names:
            n_clean = n.lower()
            for title in titles:
                if n_clean.startswith(title):
                    n_clean = n_clean[len(title):].strip()
            if n_clean: normalized.add(n_clean)
        return normalized

    for tt in existing_timetables:
        if not tt.generated_data:
            continue
        for day, slots in tt.generated_data.items():
            if day not in busy_faculty:
                busy_faculty[day] = {}
            for idx, slot in enumerate(slots):
                if slot and "faculty" in slot:
                    if idx not in busy_faculty[day]:
                        busy_faculty[day][idx] = set()
                    # Add all normalized names for this faculty string
                    busy_faculty[day][idx].update(normalize_name_set(slot['faculty']))

    gen_agent = GenerationAgent(subjects, busy_faculty=busy_faculty)
    timetable_data, gen_logs = gen_agent.generate()
    
    success = False
    final_logs = []
    
    if timetable_data:
        val_agent = ValidationAgent(subjects, timetable_data, busy_faculty=busy_faculty)
        success, val_logs = val_agent.validate()
        final_logs = gen_logs + val_logs
    else:
        final_logs = gen_logs
        success = False

    if success:
        new_tt = Timetable(
            department=department,
            course=course,
            semester=semester,
            subject_config=subjects,
            generated_data=timetable_data
        )
        db.add(new_tt)
        db.flush() # Get ID before commit if needed, or just commit

        for log_msg in final_logs:
            status = "SUCCESS" if "success" in log_msg.lower() or "passed" in log_msg.lower() else "INFO"
            if "error" in log_msg.lower() or "failed" in log_msg.lower():
                status = "FAILED"
            
            log_entry = AgentLog(
                timetable_id=new_tt.id,
                agent_name="Pipeline",
                message=log_msg,
                status=status
            )
            db.add(log_entry)
        db.commit()
    else:
        # If it failed, we don't save the timetable, but we can't save logs either 
        # because they need a timetable_id. For now, we'll just return error.
        return templates.TemplateResponse("setup.html", {
            "request": request, 
            "error": "Failed to generate valid collision-free timetable. Check input constraints.",
            "user": user
        })

    return RedirectResponse(url=f"/view/{new_tt.id}", status_code=303)

@router.get("/view/{tt_id}", response_class=HTMLResponse)
async def view_timetable(request: Request, tt_id: int, db: Session = Depends(get_db), user = Depends(login_required)):
    tt = db.query(Timetable).filter(Timetable.id == tt_id).first()
    if not tt:
        raise HTTPException(status_code=404, detail="Timetable not found")
    
    return templates.TemplateResponse("view_timetable.html", {
        "request": request,
        "timetable": tt,
        "data": tt.generated_data,
        "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
        "slots": [
            "09:30-10:30", "10:30-11:30", "11:30-12:30", 
            "12:30-02:00", "02:00-03:00", "03:00-04:00", "04:00-05:00"
        ],
        "user": user
    })

@router.get("/download/{tt_id}")
async def download_pdf(tt_id: int, db: Session = Depends(get_db), user = Depends(login_required)):
    tt = db.query(Timetable).filter(Timetable.id == tt_id).first()
    if not tt:
        raise HTTPException(status_code=404, detail="Timetable not found")
    
    html_content = templates.get_template("pdf_template.html").render({
        "timetable": tt,
        "data": tt.generated_data,
        "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
        "slots": [
            "09:30-10:30", "10:30-11:30", "11:30-12:30", 
            "12:30-02:00", "02:00-03:00", "03:00-04:00", "04:00-05:00"
        ]
    })
    
    result = BytesIO()
    pisa_status = pisa.CreatePDF(html_content, dest=result)
    
    if pisa_status.err:
        raise HTTPException(status_code=500, detail="PDF generation failed")
    
    pdf_data = result.getvalue()
    result.close()
    
    return Response(
        content=pdf_data,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=timetable_{tt.department}_{tt.semester}.pdf"}
    )

@router.get("/edit-config/{tt_id}", response_class=HTMLResponse)
async def edit_page(request: Request, tt_id: int, db: Session = Depends(get_db), user = Depends(login_required)):
    tt = db.query(Timetable).filter(Timetable.id == tt_id).first()
    if not tt:
        raise HTTPException(status_code=404, detail="Timetable not found")
    return templates.TemplateResponse("edit_timetable.html", {
        "request": request, 
        "timetable": tt, 
        "user": user,
        "subjects": tt.subject_config
    })

@router.post("/regenerate/{tt_id}")
async def regenerate_timetable(
    request: Request, 
    tt_id: int,
    department: str = Form(...),
    course: str = Form(...),
    semester: int = Form(...),
    subjects_json: str = Form(...),
    db: Session = Depends(get_db), 
    user = Depends(login_required)
):
    tt = db.query(Timetable).filter(Timetable.id == tt_id).first()
    if not tt:
        raise HTTPException(status_code=404, detail="Timetable not found")

    subjects = json.loads(subjects_json)
    
    # We clear busy_faculty except for other timetables
    existing_timetables = db.query(Timetable).filter(Timetable.id != tt_id).all()
    busy_faculty = {} # day -> slot_idx -> set of normalized faculty names
    
    # Re-use the normalize_name_set logic from /generate
    # (Actually it's better to move it to a helper, but for now I'll just keep it or duplicate it if needed)
    # The /generate route already has it. I'll define it here too or move it up.
    
    def normalize_name_set(name):
        if not name: return set()
        raw_names = []
        for delimiter in [',', '&', ' and ']:
            if delimiter in name:
                if not raw_names:
                    raw_names = [n.strip() for n in name.split(delimiter)]
                else:
                    new_names = []
                    for rn in raw_names:
                        new_names.extend([n.strip() for n in rn.split(delimiter)])
                    raw_names = new_names
        if not raw_names: raw_names = [name.strip()]
        normalized = set()
        titles = ["dr.", "prof.", "mr.", "mrs.", "ms.", "er."]
        for n in raw_names:
            n_clean = n.lower()
            for title in titles:
                if n_clean.startswith(title):
                    n_clean = n_clean[len(title):].strip()
            if n_clean: normalized.add(n_clean)
        return normalized

    for ott in existing_timetables:
        if not ott.generated_data:
            continue
        for day, slots in ott.generated_data.items():
            if day not in busy_faculty:
                busy_faculty[day] = {}
            for idx, slot in enumerate(slots):
                if slot and "faculty" in slot:
                    if idx not in busy_faculty[day]:
                        busy_faculty[day][idx] = set()
                    busy_faculty[day][idx].update(normalize_name_set(slot['faculty']))

    gen_agent = GenerationAgent(subjects, busy_faculty=busy_faculty)
    timetable_data, gen_logs = gen_agent.generate()
    
    if timetable_data:
        val_agent = ValidationAgent(subjects, timetable_data, busy_faculty=busy_faculty)
        success, val_logs = val_agent.validate()
        final_logs = gen_logs + val_logs
        
        if success:
            tt.department = department
            tt.course = course
            tt.semester = semester
            tt.subject_config = subjects
            tt.generated_data = timetable_data
            
            # Clear old logs and add new ones
            db.query(AgentLog).filter(AgentLog.timetable_id == tt.id).delete()
            
            for log_msg in final_logs:
                status = "SUCCESS" if "success" in log_msg.lower() or "passed" in log_msg.lower() else "INFO"
                if "error" in log_msg.lower() or "failed" in log_msg.lower():
                    status = "FAILED"
                
                log_entry = AgentLog(
                    timetable_id=tt.id,
                    agent_name="Pipeline",
                    message=log_msg,
                    status=status
                )
                db.add(log_entry)
            db.commit()
            return RedirectResponse(url=f"/view/{tt.id}?toast=Timetable+re-generated+successfully", status_code=303)

    return templates.TemplateResponse("edit_timetable.html", {
        "request": request, 
        "timetable": tt,
        "error": "Failed to re-generate valid collision-free timetable with updated constraints.",
        "user": user,
        "subjects": subjects
    })

@router.post("/delete/{tt_id}")
async def delete_timetable(tt_id: int, db: Session = Depends(get_db), user = Depends(login_required)):
    tt = db.query(Timetable).filter(Timetable.id == tt_id).first()
    if not tt:
        raise HTTPException(status_code=404, detail="Timetable not found")
    db.delete(tt)
    db.commit()
    return RedirectResponse(url="/dashboard?toast=Timetable+deleted+successfully", status_code=303)
