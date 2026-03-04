from app.db.session import engine
from sqlalchemy import text

def run_migration():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE news ADD COLUMN city VARCHAR"))
            conn.execute(text("ALTER TABLE news ADD COLUMN state VARCHAR"))
            conn.commit()
            print("Migration success: Columns added to 'news' table.")
        except Exception as e:
            print(f"Migration error (maybe columns exist): {e}")

if __name__ == "__main__":
    run_migration()
