import json

from app.core.permissions import ROLE_PERMISSIONS


def test_v1_roles_unchanged():
    with open("tests/fixtures/permissions_v1.json", "r", encoding="utf-8") as f:
        v1 = json.load(f)

    for role, perms in v1.items():
        assert role in ROLE_PERMISSIONS
        assert set(ROLE_PERMISSIONS[role]) == set(perms)
