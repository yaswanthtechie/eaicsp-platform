import os
# These must be set BEFORE any `app.*` import, because
# app/core/config.py reads os.environ at import time.

os.environ["SECRET_KEY"] = "test-secret-key"
# Use a dedicated test database so running the suite never
# touches (or seeds, or deletes rows from) a real dev database.
os.environ["DATABASE_URL"] = "sqlite:///./test_platform.db"
 
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
 
import pytest
from app.database import Base, engine
from app.seed import seed_database

# DATABASE SETUP
 
@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
 
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
 
    seed_database()
 
    yield
 
    Base.metadata.drop_all(bind=engine)
