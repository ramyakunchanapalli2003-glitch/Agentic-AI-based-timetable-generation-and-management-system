from app.models.database import init_db, SessionLocal, Admin
from passlib.context import CryptContext
import os

pwd_context = CryptContext(schemes=["sha256_crypt", "bcrypt"], deprecated="auto")

def setup():
    print("Starting database setup...")
    # Ensure database directory exists
    db_dir = "./database"
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
        print(f"Created directory: {db_dir}")
        
    print("Initializing tables...")
    init_db()
    print("Tables initialized.")
    
    db = SessionLocal()
    try:
        # Check if admin exists
        admin = db.query(Admin).filter(Admin.username == "admin").first()
        if not admin:
            print("Creating default admin...")
            hashed_password = pwd_context.hash("admin123")
            new_admin = Admin(username="admin", password_hash=hashed_password)
            db.add(new_admin)
            db.commit()
            print("Default admin created: admin / admin123")
        else:
            print("Admin user already exists.")
    except Exception as e:
        print(f"Error during setup: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    setup()
