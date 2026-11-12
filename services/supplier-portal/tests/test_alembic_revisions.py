from alembic.config import Config
from alembic.script import ScriptDirectory


def test_revision_ids_fit_postgres_version_table():
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    revisions = list(script.walk_revisions())

    assert revisions
    for rev in revisions:
        assert len(rev.revision) <= 32, rev.revision
    assert len(script.get_heads()) == 1
