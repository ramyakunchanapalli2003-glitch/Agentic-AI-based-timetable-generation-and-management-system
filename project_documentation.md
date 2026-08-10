# Agentic AI Timetable Generator - Comprehensive Documentation

## 1. Project Overview
The **Agentic AI Timetable Generator** is an intelligent, full-stack web application designed to automate the complex process of creating academic schedules. Built with Python and FastAPI, it utilizes custom agentic algorithms to generate collision-free timetables that respect complex constraints, such as faculty availability across multiple departments, continuous lab sessions, and mandatory lunch breaks. 

The system features a visually rich frontend dashboard for managing, editing, and previewing generated timetables, along with the ability to export perfect landscape-oriented PDF versions.

---

## 2. Technology Stack
### Backend
- **Framework**: FastAPI (Python 3)
- **Server**: Uvicorn
- **Template Engine**: Jinja2
- **PDF Generation**: `xhtml2pdf`

### Database
- **ORM**: SQLAlchemy
- **Local Environment**: SQLite (`timetable.db`)
- **Production Environment**: PostgreSQL (hosted via Supabase)
- **Migrations**: Custom `init_db.py`, `migrate_db.py`, and `sync_sequences.py` scripts.

### Frontend
- **Structure**: HTML5
- **Styling**: Vanilla CSS (Modularized in `static/css`)
- **Interactivity**: Vanilla JavaScript
- **Templates**: Base layouts extended by individual pages (`base.html`, `dashboard.html`, `setup.html`, etc.)

---

## 3. Project Directory Structure
```text
agentic_ai_timetable/
├── .env / .env.example       # Environment variables (Database URLs)
├── README.md                 # Basic setup and execution instructions
├── requirements.txt          # Python dependencies
├── init_db.py                # Script to initialize database schema
├── migrate_db.py             # Script to migrate from SQLite to PostgreSQL
├── sync_sequences.py         # Postgres sequence synchronization
├── app/
│   ├── main.py               # Application entry point, middleware, and auth routes
│   ├── dependencies.py       # Reusable FastAPI dependencies (e.g., auth checks)
│   ├── agents/               # Core AI Logic
│   │   ├── generation.py     # GenerationAgent (creates timetables)
│   │   └── validation.py     # ValidationAgent (verifies timetables)
│   ├── models/               # Database Models
│   │   └── database.py       # SQLAlchemy setup and schema definitions
│   └── routes/               # API Endpoints
│       ├── dashboard.py      # Dashboard views and statistics
│       └── timetable.py      # Timetable CRUD, PDF download, and generation logic
├── database/                 
│   └── timetable.db          # Local SQLite database file
├── static/                   # Static assets (CSS, JS)
│   ├── css/
│   │   └── index.css
│   └── js/
└── templates/                # Jinja2 HTML Templates
    ├── base.html             # Main layout
    ├── login.html            # Authentication page
    ├── dashboard.html        # Main dashboard
    ├── setup.html            # Timetable generation form
    ├── view_timetable.html   # Generated timetable preview
    ├── edit_timetable.html   # Edit constraints interface
    └── pdf_template.html     # HTML structure for PDF export
```

---

## 4. Database Schema (Models)
The application relies on three primary tables defined in `app/models/database.py`.

### 1. Admin Table (`admins`)
Handles user authentication for the dashboard.
- `id` (Integer, Primary Key)
- `username` (String, Unique)
- `password_hash` (String, bcrypt/sha256_crypt)

### 2. Timetable Table (`timetables`)
Stores the configuration and the finalized JSON structure of the generated schedules.
- `id` (Integer, Primary Key)
- `department` (String) - e.g., "Computer Science"
- `course` (String) - e.g., "B.Tech"
- `semester` (Integer)
- `subject_config` (JSON) - The raw input configuration (subjects, faculty, types, periods).
- `generated_data` (JSON) - The finalized 2D array representation of the schedule.
- `created_at` (DateTime)

### 3. Agent Log Table (`agent_logs`)
Maintains an audit trail of the AI's decision-making process for transparency and debugging.
- `id` (Integer, Primary Key)
- `timetable_id` (Integer, Foreign Key to `timetables.id`)
- `agent_name` (String) - e.g., "Pipeline", "GenerationAgent"
- `message` (Text) - Specific action or error description.
- `status` (String) - "SUCCESS", "INFO", or "FAILED".
- `timestamp` (DateTime)

---

## 5. Core Algorithms & Logic (The "Agents")
The core intelligence of the application is split into two classes located in `app/agents/`. The system uses predefined slots (7 periods per day, including a fixed lunch slot at index 3: `12:30-02:00`).

### GenerationAgent (`generation.py`)
Responsible for constructing the timetable from scratch based on provided subjects.
**Key Mechanisms:**
1. **Faculty Normalization**: Cleans faculty names (removes titles like Dr., Prof., splits by commas/ands) to accurately track individuals globally across different timetables.
2. **Lab Placement (Priority 1)**: 
   - Identifies subjects of type "Lab".
   - Attempts to place them in continuous blocks (usually size 2 or 3).
   - **Crucial Constraint**: Ensures that a continuous lab block *never* crosses the lunch break.
3. **Lecture Placement (Priority 2)**: 
   - Randomly places single-period lectures in available slots (excluding lunch).
4. **Collision Avoidance**: Before placing any faculty member in a slot, it checks the `busy_faculty` dictionary, which contains the schedules of all *other* generated timetables in the database, ensuring no professor is double-booked across the university.

### ValidationAgent (`validation.py`)
Acts as a strict quality assurance checker after generation. If validation fails, the timetable is rejected.
**Verification Checks:**
1. **Period Counts**: Ensures the exact number of weekly periods requested for a subject matches the generated output.
2. **Lunch Sanctity**: Verifies that the designated lunch slot (Index 3) contains only "LUNCH" and no academic subjects.
3. **Lab Continuity**: Ensures lab sessions are not isolated (unless specifically configured as a 1-period lab).
4. **Global Faculty Collision**: Does a final sweep across all existing database timetables to guarantee absolute zero faculty double-booking.

---

## 6. Application Routes & Navigation

### Authentication (`app/main.py`)
- `GET /`, `GET /login`: Redirects to or serves the login page.
- `POST /login`: Validates credentials against the `admins` table. Sets an HTTP-only secure cookie session.
- `GET /logout`: Clears the session cookie.

### Dashboard (`app/routes/dashboard.py`)
- `GET /dashboard`: Protected route displaying metrics (Total timetables, recent generations, agent logs) and a grid/list of existing timetables.

### Timetable Operations (`app/routes/timetable.py`)
- `GET /setup`: Renders the UI to input constraints (Department, Course, Semester, Subjects).
- `POST /generate`: Triggers the Generation and Validation agents. Saves to DB if successful, logs actions, and redirects to the view page.
- `GET /view/{tt_id}`: Renders a visual grid of a specific timetable.
- `GET /download/{tt_id}`: Converts the timetable into a PDF using `xhtml2pdf` and `pdf_template.html`.
- `GET /edit-config/{tt_id}`: Loads existing configuration into the setup UI for modification.
- `POST /regenerate/{tt_id}`: Re-runs the agents with updated constraints, replacing the old `generated_data` and updating logs.
- `POST /delete/{tt_id}`: Removes the timetable and its associated logs from the database.

---

## 7. Deployment & Environment Setup
The application is designed to be deployment-ready for platforms like Render, Railway, or Heroku.

**Local Execution:**
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Production Details:**
- Relies on the `DATABASE_URL` environment variable.
- Middleware: Uses `ProxyHeadersMiddleware` to trust proxy headers from hosting platforms, ensuring secure cookies and redirects work correctly over HTTPS.
- Automatic DB initialization and admin user creation on startup (with robust retry mechanisms for cloud database latency).

---
*This documentation encompasses the complete architecture, logical flow, and technical specifications of the Agentic AI Timetable Generator project.*
