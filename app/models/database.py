from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy import create_engine
import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# Use environment variable for database URL, fallback to local SQLite
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./database/timetable.db")

# SQLAlchemy requires postgresql:// instead of postgres:// 
if DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

# SQLite specific connect args
connect_args = {}
if DB_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False
elif DB_URL.startswith("postgresql"):
    connect_args["sslmode"] = "require"

engine = create_engine(DB_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Admin(Base):
    __tablename__ = "admins"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)

class Timetable(Base):
    __tablename__ = "timetables"
    id = Column(Integer, primary_key=True, index=True)
    department = Column(String)
    course = Column(String)
    semester = Column(Integer)
    subject_config = Column(JSON)  # Store subjects as JSON
    generated_data = Column(JSON)  # Store timetable structure as JSON
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    logs = relationship("AgentLog", back_populates="timetable", cascade="all, delete-orphan")

class AgentLog(Base):
    __tablename__ = "agent_logs"
    id = Column(Integer, primary_key=True, index=True)
    timetable_id = Column(Integer, ForeignKey("timetables.id"))
    agent_name = Column(String)
    message = Column(Text)
    status = Column(String) # e.g., "SUCCESS", "FAILED"
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    timetable = relationship("Timetable", back_populates="logs")

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
