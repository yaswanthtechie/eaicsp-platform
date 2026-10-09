
"""Generate a small, deterministic dependency graph from pipeline config."""

from pathlib import Path


def dependency_edges(config):
    edges = []
    for source in config.sources:
        if source.depends_on:
            edges.append((source.depends_on, source.name))
        else:
            edges.append(("SOURCE", source.name))
    return edges


def generate_dependency_graph(config, output_path=None):
    """Return Graphviz DOT text; optionally persist it."""
    lines = [
        "digraph pipeline_dependencies {",
        '  rankdir=LR;',
        '  "SOURCE" [shape=box];',
    ]
    for upstream, downstream in dependency_edges(config):
        lines.append(f'  "{upstream}" -> "{downstream}";')
    lines.append("}")
    graph = "\n".join(lines) + "\n"

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(graph, encoding="utf-8")

    return graph
