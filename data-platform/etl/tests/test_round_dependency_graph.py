from etl.src.config_loader import load_pipeline_config

def test_round_sources_are_dependency_ordered():
    config=load_pipeline_config()
    positions={s.name:i for i,s in enumerate(config.sources)}
    for s in config.sources:
        if s.depends_on:
            assert positions[s.depends_on] < positions[s.name]
    assert [s.name for s in config.sources] == ["sales","inventory","shipments"]
