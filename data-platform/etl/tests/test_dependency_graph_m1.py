
from etl.src.config_loader import load_pipeline_config
from etl.src.dependency_graph import generate_dependency_graph


def test_dependency_graph_contains_all_edges(tmp_path):
    config = load_pipeline_config()
    graph = generate_dependency_graph(config, tmp_path / "pipeline.dot")
    assert '"sales" -> "inventory"' in graph
    assert '"inventory" -> "shipments"' in graph
    assert (tmp_path / "pipeline.dot").exists()
