from etl.src.config_loader import load_pipeline_config


def test_config_loads_expected_sources():
    config = load_pipeline_config()

    names = config.source_names()
    assert "sales" in names
    assert "inventory" in names


def test_inventory_depends_on_sales_and_sales_is_earlier():
    config = load_pipeline_config()

    names = config.source_names()
    inventory = config.get_source("inventory")

    assert inventory.depends_on == "sales"
    assert names.index("sales") < names.index("inventory")


def test_sales_source_has_no_dependency():
    config = load_pipeline_config()
    sales = config.get_source("sales")

    assert sales.depends_on is None


def test_get_source_missing_name_raises():
    config = load_pipeline_config()

    try:
        config.get_source("does_not_exist")
        assert False, "expected KeyError"
    except KeyError:
        pass


def test_archive_config_present():
    config = load_pipeline_config()

    assert config.archive.table == "sales_fact"
    assert config.archive.archive_table == "sales_fact_archive"
    assert config.archive.cutoff_days > 0
