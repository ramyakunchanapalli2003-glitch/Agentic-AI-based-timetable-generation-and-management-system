import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Base, Admin, Timetable, AgentLog

def migrate_data():
    print("Starting migration process...")

    # Load from .env if present
    load_dotenv()

    # 1. Connect to local SQLite
    sqlite_url = "sqlite:///./database/timetable.db"
    print(f"Connecting to source SQLite: {sqlite_url}")
    sqlite_engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    
    # Verify tables exist in SQLite
    Base.metadata.create_all(bind=sqlite_engine)
    
    SqliteSession = sessionmaker(autocommit=False, autoflush=False, bind=sqlite_engine)
    sqlite_db = SqliteSession()

    # 2. Connect to Supabase PostgreSQL (from .env)
    pg_url = os.getenv("DATABASE_URL")
    if not pg_url or "sqlite" in pg_url:
        print("ERROR: DATABASE_URL is not set or is set to SQLite. Please set DATABASE_URL in your .env file to your Supabase PostgreSQL URI.")
        return

    if pg_url.startswith("postgres://"):
        pg_url = pg_url.replace("postgres://", "postgresql://", 1)

    print(f"Connecting to target PostgreSQL: {pg_url.split('@')[-1]} (password hidden)")
    try:
        pg_engine = create_engine(pg_url)
        # Create all tables in PostgreSQL if they don't exist
        Base.metadata.create_all(bind=pg_engine)
        PgSession = sessionmaker(autocommit=False, autoflush=False, bind=pg_engine)
        pg_db = PgSession()
    except Exception as e:
        print(f"ERROR: Failed to connect to PostgreSQL. {e}")
        return

    try:
        # A helper function to generic copy table data
        def copy_table(model_class, table_name):
            print(f"--- Migrating {table_name} ---")
            sqlite_records = sqlite_db.query(model_class).all()
            if not sqlite_records:
                print(f"No records found in SQLite for {table_name}. Skipping.")
                return
            
            # Check if Postgres already has data in this table
            pg_count = pg_db.query(model_class).count()
            if pg_count > 0:
                print(f"WARNING: PostgreSQL already has {pg_count} records in {table_name}. Skipping to prevent duplication.")
                return

            print(f"Found {len(sqlite_records)} records to migrate for {table_name}...")
            
            # Ensure identity matching by avoiding manual ID insertions where possible, 
            # but we want IDs to match. For simplistic SQLAlchemy migrations across engines:
            for record in sqlite_records:
                # We detach record from sqlite session and add to pg session
                sqlite_db.expunge(record)
                from sqlalchemy.orm import make_transient
                make_transient(record)
                pg_db.add(record)
            
            pg_db.commit()
            print(f"Successfully migrated {len(sqlite_records)} records into {table_name}.")

        # Order matters! Copy Admin, then Timetable, then AgentLog (because AgentLog has a foreign key to Timetable)
        copy_table(Admin, "Admins")
        copy_table(Timetable, "Timetables")
        copy_table(AgentLog, "AgentLogs")

        print("\nAll data migrated successfully!")
        print("You can now securely use your Supabase PostgreSQL database.")
        print("Existing SQLite data remains untouched in ./database/timetable.db as a backup.")

    except Exception as e:
        pg_db.rollback()
        print(f"ERROR during migration: {e}")
    finally:
        sqlite_db.close()
        pg_db.close()

if __name__ == "__main__":
    migrate_data()
