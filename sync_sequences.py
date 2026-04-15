import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

def sync_sequences():
    load_dotenv()
    pg_url = os.getenv("DATABASE_URL")
    
    if not pg_url or "sqlite" in pg_url:
        print("ERROR: DATABASE_URL not set properly.")
        return
        
    if pg_url.startswith("postgres://"):
        pg_url = pg_url.replace("postgres://", "postgresql://", 1)

    print("Syncing database sequences...")
    engine = create_engine(pg_url)
    
    with engine.connect() as conn:
        tables = ["admins", "timetables", "agent_logs"]
        for table in tables:
            try:
                # Update the sequence to the maximum ID currently in the table
                query = text(f"SELECT setval('{table}_id_seq', COALESCE((SELECT MAX(id) + 1 FROM {table}), 1), false);")
                conn.execute(query)
                print(f"Successfully synced sequence for {table}")
            except Exception as e:
                print(f"Warning for {table}: {e}")
        
        conn.commit()

    print("\n✅ Sequences synced successfully! You should now be able to insert new rows without errors.")

if __name__ == "__main__":
    sync_sequences()
