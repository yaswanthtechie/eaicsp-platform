"""
Guard test: shared-entity IDs written as string literals in app/, scripts/
and tests/ must use the blueprint's canonical formats (section 2). A test
that feeds a bad ID on purpose marks the line with `# noncanonical-ok`.
"""

import re
from pathlib import Path

SERVICE_DIR = Path(__file__).resolve().parents[1]

CANONICAL = re.compile(r"^(SKU-\d{6}|SUP-\d{5}|WH-[A-Z]{3}-\d{2}|PO-\d{4}-\d{6})$")
ID_LITERAL = re.compile(
    r"""["']((?:SKU|SUP|WH|PO)(?:\d+|-[A-Za-z0-9-]*\d[A-Za-z0-9-]*))["']"""
)


def test_no_non_canonical_id_literals():
    offenders = []
    for folder in ("app", "scripts", "tests"):
        for path in (SERVICE_DIR / folder).rglob("*.py"):
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1
            ):
                if "noncanonical-ok" in line:
                    continue
                for value in ID_LITERAL.findall(line):
                    if not CANONICAL.match(value):
                        offenders.append(
                            f"{path.relative_to(SERVICE_DIR)}:{lineno}: {value}"
                        )

    assert not offenders, "Non-canonical IDs:\n" + "\n".join(offenders)

