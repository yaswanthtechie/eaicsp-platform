import pytest

from app.services.sanctions_service import (
    load_all_sanctions,
)


@pytest.fixture(
    scope="session",
    autouse=True,
)
def load_sanctions():
   

    load_all_sanctions()