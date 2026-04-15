# Agentic AI Timetable Generator

An intelligent, full-stack timetable generation system built with Python and FastAPI. The application uses agentic algorithms to autonomously generate conflict-free academic schedules, handling complex constraints like faculty availability, continuous lab sessions, and lunch breaks.

## 🚀 Features

- **AI-Powered Scheduling**: Automatically generates collision-free timetables ensuring no faculty member is booked in two places at the same time.
- **Smart Constraints Processing**: 
  - Automatically avoids scheduling continuous labs across lunch breaks.
  - Groups continuous periods of the same subject.
  - Dynamically supports different courses (B.Tech, M.Tech, B.Pharm, MCA, MBA, PhD) and departments.
- **Full Stack Dashboard**: A visually rich frontend dashboard for managing, editing, and previewing generated timetables.
- **PDF Exports**: Download perfectly formatted, landscape-oriented PDF versions of your timetables in a single click.
- **Persistent Storage**: Fully supports both local SQLite databases and cloud PostgreSQL hosted databases (via Supabase).

## 🛠️ Tech Stack

- **Backend Context**: [FastAPI](https://fastapi.tiangolo.com/), Python 3
- **Database**: [SQLAlchemy](https://www.sqlalchemy.org/) ORM, PostgreSQL (Supabase) / SQLite
- **Frontend**: HTML5, Vanilla CSS, JS, Jinja2 Templates
- **PDF Generation**: xhtml2pdf

## ⚙️ Local Setup Instructions

1. **Clone the repository** (if you haven't already).
2. **Install core dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure the Database**:
   - For a **local SQLite** database, no configuration is needed.
   - For **Supabase/PostgreSQL**, rename `.env.example` to `.env` and fill in your Supabase connection URI:
     ```env
     DATABASE_URL="postgresql://postgres.[your-project-ref]:[PASSWORD]@aws-0-eu-central-1.pooler.supabase.com:6543/postgres"
     ```
   *(If migrating from local SQLite to Supabase, you can run `python migrate_db.py` alongside `python sync_sequences.py` to port your historic data over cleanly).*

4. **Run the Application**:
   ```bash
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
5. **Access the portal**:
   Open your browser and navigate to: `http://127.0.0.1:8000`

## ☁️ Deployment

This app is production-ready and configured to effortlessly deploy on Render, Railway, or Heroku. 
1. Connect your Github repository to your hosting provider.
2. Set the Environment Variable `DATABASE_URL` to your production database connection string.
3. Use the start command:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
