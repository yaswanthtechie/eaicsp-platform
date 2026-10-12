import re
from pathlib import Path
from app.core.permissions import PERMISSIONS, ROLE_PERMISSIONS
# =============================================================
# README PATH
# =============================================================

README_PATH = Path(__file__).resolve().parents[1] / "README.md"


# =============================================================
# README PERMISSION MATRIX PARSER
# =============================================================

def _parse_readme_permission_matrix():
    """
    Extract the Role -> Permissions Markdown table from README.md.

    Expected format:

        | Role | Permissions |
        | --- | --- |
        | `ceo` | `inventory:read`, `inventory:write` |

    The parser does not depend on a specific README heading.
    """

    assert README_PATH.exists(), (
        f"README.md was not found at: {README_PATH}"
    )

    readme = README_PATH.read_text(encoding="utf-8")
    lines = readme.splitlines()

    # ---------------------------------------------------------
    # Find the Role / Permissions table header
    # ---------------------------------------------------------

    header_index = None

    for index, line in enumerate(lines):
        stripped = line.strip()

        if not stripped.startswith("|"):
            continue

        cells = [
            cell.strip().lower()
            for cell in stripped.strip("|").split("|")
        ]

        if len(cells) >= 2:
            if cells[0] == "role" and cells[1] == "permissions":
                header_index = index
                break

    assert header_index is not None, (
        "Could not find the Role-Permissions Markdown table in "
        "README.md.\n"
        "Expected a table header like:\n"
        "| Role | Permissions |"
    )

    # ---------------------------------------------------------
    # Parse rows immediately after the header
    # ---------------------------------------------------------

    rows = []

    for line in lines[header_index + 1:]:
        stripped = line.strip()

        # The table has ended.
        if not stripped.startswith("|"):
            if rows:
                break
            continue

        cells = [
            cell.strip()
            for cell in stripped.strip("|").split("|")
        ]

        # We only support a two-column Role / Permissions table.
        if len(cells) != 2:
            if rows:
                break
            continue

        role_cell = cells[0]
        permissions_cell = cells[1]

        # -----------------------------------------------------
        # Ignore Markdown separator row
        # -----------------------------------------------------

        if re.fullmatch(r":?-{3,}:?", role_cell):
            continue

        # -----------------------------------------------------
        # Extract role
        # -----------------------------------------------------

        role_match = re.fullmatch(
            r"`([a-z_]+)`",
            role_cell,
        )

        if role_match:
            role = role_match.group(1)
        else:
            # Also support a plain role name if needed.
            role = role_cell.strip().strip("`").strip()

        if not role:
            continue

        # -----------------------------------------------------
        # Extract permissions
        # -----------------------------------------------------

        permissions = {
            permission.strip()
            for permission in re.findall(
                r"`([^`]+)`",
                permissions_cell,
            )
            if permission.strip()
        }

        # Support plain comma-separated permissions as fallback.
        if not permissions and permissions_cell.strip():
            permissions = {
                permission.strip().strip("`")
                for permission in permissions_cell.split(",")
                if permission.strip()
            }

        rows.append((role, permissions))

    assert rows, (
        "The Role-Permissions table was found, "
        "but no role rows were found."
    )

    # ---------------------------------------------------------
    # Detect duplicate roles
    # ---------------------------------------------------------

    roles = [role for role, _ in rows]

    duplicate_roles = {
        role
        for role in roles
        if roles.count(role) > 1
    }

    assert not duplicate_roles, (
        "README permission matrix contains duplicate roles: "
        f"{sorted(duplicate_roles)}"
    )

    return dict(rows)


# =============================================================
# README PERMISSION MATRIX == ROLE_PERMISSIONS
# =============================================================

def test_readme_permission_matrix_matches_code():
    """
    The permissions documented in README.md must exactly match
    ROLE_PERMISSIONS in app/core/permissions.py.
    """

    readme_matrix = _parse_readme_permission_matrix()

    code_matrix = {
        role: set(permissions)
        for role, permissions in ROLE_PERMISSIONS.items()
    }

    readme_roles = set(readme_matrix.keys())
    code_roles = set(code_matrix.keys())

    # ---------------------------------------------------------
    # Check roles
    # ---------------------------------------------------------

    assert readme_roles == code_roles, (
        "README roles do not match app/core/permissions.py.\n"
        f"Missing from README: "
        f"{sorted(code_roles - readme_roles)}\n"
        f"Extra in README: "
        f"{sorted(readme_roles - code_roles)}"
    )

    # ---------------------------------------------------------
    # Check permissions role-by-role
    # ---------------------------------------------------------

    mismatches = []

    for role in sorted(code_roles):
        readme_permissions = readme_matrix[role]
        code_permissions = code_matrix[role]

        if readme_permissions != code_permissions:
            mismatches.append(
                {
                    "role": role,
                    "missing_from_readme": sorted(
                        code_permissions - readme_permissions
                    ),
                    "extra_in_readme": sorted(
                        readme_permissions - code_permissions
                    ),
                }
            )

    assert not mismatches, (
        "README permission matrix does not match "
        "app/core/permissions.py.\n"
        f"Mismatches:\n{mismatches}"
    )


# =============================================================
# README CONTAINS EXACTLY ALL ROLES FROM CODE
# =============================================================

def test_readme_has_all_roles_from_code():
    """
    Every role in ROLE_PERMISSIONS must appear in README.md,
    and README must not document an unknown role.
    """

    readme_matrix = _parse_readme_permission_matrix()

    expected_roles = set(ROLE_PERMISSIONS.keys())
    readme_roles = set(readme_matrix.keys())

    missing_roles = expected_roles - readme_roles
    extra_roles = readme_roles - expected_roles

    assert not missing_roles, (
        "README is missing roles from "
        "app/core/permissions.py: "
        f"{sorted(missing_roles)}"
    )

    assert not extra_roles, (
        "README contains roles not defined in "
        "app/core/permissions.py: "
        f"{sorted(extra_roles)}"
    )


# =============================================================
# README CONTAINS ONLY VALID PERMISSIONS
# =============================================================

def test_readme_permission_matrix_has_no_unknown_permissions():
    """
    Every permission documented in README.md must exist in
    PERMISSIONS in app/core/permissions.py.
    """

    readme_matrix = _parse_readme_permission_matrix()

    unknown_permissions = {
        permission
        for permissions in readme_matrix.values()
        for permission in permissions
        if permission not in PERMISSIONS
    }

    assert not unknown_permissions, (
        "README contains permissions that are not defined in "
        "app/core/permissions.py:\n"
        f"{sorted(unknown_permissions)}"
    )


# =============================================================
# README ROLE COUNT == CODE ROLE COUNT
# =============================================================

def test_readme_role_count_matches_code():
    """
    Prevents the README from accidentally documenting an older
    8-role matrix after the role model has been expanded.
    """

    readme_matrix = _parse_readme_permission_matrix()

    assert len(readme_matrix) == len(ROLE_PERMISSIONS), (
        "README role count does not match code.\n"
        f"README: {len(readme_matrix)}\n"
        f"Code: {len(ROLE_PERMISSIONS)}"
    )


# =============================================================
# README CURRENTLY DOCUMENTS 18 ROLES
# =============================================================

def test_readme_documents_18_roles():
    """
    Round 12+13 Milestone 2 requires the expanded 18-role model:
    8 original V1 roles + 10 new roles.
    """

    readme_matrix = _parse_readme_permission_matrix()

    assert len(readme_matrix) == 18, (
        "Round 12+13 README permission matrix must contain "
        "exactly 18 roles.\n"
        f"Found: {len(readme_matrix)}"
    )


# =============================================================
# README PERMISSIONS ARE SET-EQUIVALENT TO CODE
# =============================================================

def test_readme_permissions_are_exact_per_role():
    """
    Explicit role-by-role equality check.

    This protects against accidentally adding/removing a
    permission from one role in README.md.
    """

    readme_matrix = _parse_readme_permission_matrix()

    for role, expected_permissions in ROLE_PERMISSIONS.items():
        assert readme_matrix[role] == set(expected_permissions), (
            f"README permissions for role '{role}' do not match code.\n"
            f"README: {sorted(readme_matrix[role])}\n"
            f"Code: {sorted(expected_permissions)}"
        )
