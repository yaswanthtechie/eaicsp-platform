
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


SERVICE_DIR = Path(__file__).resolve().parents[1]


def test_revision_ids_fit_postgres_version_table():
    config = Config(str(SERVICE_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(SERVICE_DIR / "alembic"))
    script = ScriptDirectory.from_config(config)
    revisions = list(script.walk_revisions())

    assert revisions
    for rev in revisions:
        assert len(rev.revision) <= 32, rev.revision
    assert len(script.get_heads()) == 1
