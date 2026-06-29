from app.db.session import engine
from app.db.base import Base
from app.core.config import settings

def init_db():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    import sys
    print(f"Creating database tables on: {settings.DATABASE_URL}")
    init_db()
    print("Tables created successfully.")
