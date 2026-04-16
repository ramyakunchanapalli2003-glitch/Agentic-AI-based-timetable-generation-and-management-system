from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import datetime
import os
from dotenv import load_dotenv

# Load local .env if present (Render environment variables will still work)
load_dotenv()

# Get database URL from environment, fallback to local SQLite
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./database/timetable.db")

# Normalize postgres scheme if needed
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

# Configure connection settings
connect_args = {}

if DB_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

elif DB_URL.startswith("postgresql"):
    # Ensure SSL for Supabase/PostgreSQL cloud hosting
    if "sslmode=" not in DB_URL:
        separator = "&" if "?" in DB_URL else "?"
        DB_URL = f"{DB_URL}{separator}sslmode=require"

# Create engine
engine = create_engine(
    DB_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=300,
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base model
Base = declarative_base()


# =========================
# Models
# =========================

class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)


class Timetable(Base):
    __tablename__ = "timetables"

    id = Column(Integer, primary_key=True, index=True)
    department = Column(String, nullable=False)
    course = Column(String, nullable=False)
    semester = Column(Integer, nullable=False)
    subject_config = Column(JSON)
    generated_data = Column(JSON)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    logs = relationship(
        "AgentLog",
        back_populates="timetable",
        cascade="all, delete-orphan"
    )


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id = Column(Integer, primary_key=True, index=True)
    timetable_id = Column(Integer, ForeignKey("timetables.id"))
    agent_name = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    status = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    timetable = relationship("Timetable", back_populates="logs")


# =========================
# Database Helpers
# =========================

def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
