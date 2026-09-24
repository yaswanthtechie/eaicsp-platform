from etl.src.config_loader import load_pipeline_config

def test_round_sources_are_dependency_ordered():
    config=load_pipeline_config()
    positions={s.name:i for i,s in enumerate(config.sources)}
    for s in config.sources:
        if s.depends_on:
            assert positions[s.depends_on] < positions[s.name]
    assert [s.name for s in config.sources] == ["sales","inventory","shipments"]


def test_misordered_dependency_is_rejected():
    from types import SimpleNamespace
    import pytest
    from etl.src.config_loader import validate_dependency_order
    sources = [
        SimpleNamespace(name="sales", depends_on=None),
        SimpleNamespace(name="shipments", depends_on="inventory"),
        SimpleNamespace(name="inventory", depends_on=None),
    ]
    with pytest.raises(ValueError, match="must appear earlier"):
        validate_dependency_order(sources)
