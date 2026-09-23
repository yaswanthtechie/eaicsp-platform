import os
# These must be set BEFORE any `app.*` import, because
# app/core/config.py reads os.environ at import time.

os.environ["SECRET_KEY"] = "test-secret-key"
# Use a dedicated test database so running the suite never
# touches (or seeds, or deletes rows from) a real dev database.
os.environ["DATABASE_URL"] = "sqlite:///./test_platform.db"

# Seed credentials for the test database. These are test fixtures only --
# the real deployment supplies them from the environment (see .env.example).
TEST_SEED_PASSWORDS = {
    "CEO_PASSWORD": "ceocompany@123",
    "VP_OPERATIONS_PASSWORD": "vpoperations@123",
    "PROCUREMENT_MANAGER_PASSWORD": "procurement@123",
    "LOGISTICS_MANAGER_PASSWORD": "logistics@123",
    "COMPLIANCE_OFFICER_PASSWORD": "compliance@123",
    "WAREHOUSE_MANAGER_PASSWORD": "warehouse@123",
    "ANALYST_PASSWORD": "analyst@1234",
    "SUPPLIER_PASSWORD": "supplier@123",
}

for _key, _value in TEST_SEED_PASSWORDS.items():
    os.environ.setdefault(_key, _value)
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
