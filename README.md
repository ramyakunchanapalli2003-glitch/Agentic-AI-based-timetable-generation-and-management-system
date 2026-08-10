# Agentic AI Timetable Generator & Manager

An intelligent, full-stack timetable generation and management system built with Python, FastAPI, and Google Gemini API. The application features a **Gemini LLM Planning Agent** that acts as an autonomous coordinator, orchestrating constraint-aware timetable generation, validation, auto-retry regeneration (up to 3 attempts), and database persistence using existing tool functions.

---

## 🚀 Features

- **🤖 Gemini LLM Planning Agent**:
  - Accepts natural language instructions from administrators (e.g., *"Generate timetable with continuous labs and avoid faculty clashes"*).
  - Understands scheduling goals and plans execution workflows.
  - Automatically executes `generate_timetable`, `validate_timetable`, `regenerate_timetable` (up to 3 attempts), and `save_timetable` tools.
  - Maintains detailed step-by-step agent execution logs visible on the dashboard.
- **🛡️ Built-in Fallback Mechanism**:
  - If the AI instruction is left empty or the `GEMINI_API_KEY` is not set/unavailable, the system automatically uses the direct Python scheduling pipeline.
- **⚡ Smart Constraints Engine (Pure Python)**:
  - Global cross-timetable faculty collision checking.
  - Mandatory lunch break enforcement (12:30 PM - 02:00 PM).
  - Lab session continuity (prevents continuous lab blocks from crossing lunch).
  - Subject weekly period count validation.
- **📊 Full-Stack Dashboard**: Jinja2 & HTML5 frontend to setup, view, edit, regenerate, and manage generated schedules.
- **📄 Landscape PDF Export**: Single-click export of generated timetables to PDF format using `xhtml2pdf`.
- **☁️ Multi-Database Support**: Seamless switching between local SQLite (`database/timetable.db`) and Cloud PostgreSQL (Supabase).

---

## 🛠️ Tech Stack

- **LLM Integration**: [Google GenAI SDK](https://github.com/googleapis/python-genai) (`google-genai`), Gemini 2.0 / Flash
- **Backend**: [FastAPI](https://fastapi.tiangolo.com/), Python 3.11, Uvicorn
- **Database**: [SQLAlchemy](https://www.sqlalchemy.org/) ORM, PostgreSQL (Supabase) / SQLite
- **Frontend**: HTML5, Vanilla CSS, Vanilla JavaScript, Jinja2 Templates
- **PDF Export**: `xhtml2pdf`

---

## ⚙️ Local Setup & How to Run

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Environment Variables (.env)
Create or edit your `.env` file in the project root:

```env
# Database Connection (Leave empty or set for Supabase)
DATABASE_URL="postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres"

# Google Gemini API Key (Required for AI Planning Agent)
GEMINI_API_KEY="your-google-gemini-api-key"
```

> [!NOTE]
> If `GEMINI_API_KEY` is not provided, the application will still run normally using the fallback scheduling engine.

### 3. Initialize Database (Optional)
If running for the first time or setting up a clean database:
```bash
python init_db.py
```

### 4. Run the Development Server
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 5. Access the Web Portal
Open your browser and navigate to:
[http://localhost:8000](http://localhost:8000)

**Default Login Credentials**:
- **Username**: `admin`
- **Password**: `admin123`

---

## 🧪 How to Verify it's Working

### Method 1: Testing AI Agent Mode
1. Log in to `http://localhost:8000/login`.
2. Click **Generate New** on the dashboard.
3. Fill in Department, Course, Semester, and Subjects.
4. In the **AI Scheduling Instruction (Optional)** box, enter an instruction:
   > *"Generate timetable with continuous labs and avoid faculty clashes."*
5. Click **Run Generation Agent Pipeline**.
6. View the generated schedule and check the **Agent Logs** section on the dashboard to see `GeminiPlanningAgent` logs (Planning, Generation, Validation, Timetable Saved).

### Method 2: Testing Fallback / Standard Mode
1. Leave the **AI Scheduling Instruction** box empty (or clear `GEMINI_API_KEY` from `.env`).
2. Click **Run Generation Agent Pipeline**.
3. Verify that schedule generation completes normally using the standard pipeline.

---

## ☁️ Deployment (Render)

This project is configured for effortless deployment on Render, Railway, or Heroku:

1. Connect your repository to Render.
2. Set Environment Variables on Render:
   - `DATABASE_URL`: Supabase connection URI.
   - `GEMINI_API_KEY`: Your Gemini API key.
3. Set the **Start Command**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips="*"
   ```
