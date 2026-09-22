
"""Generate the ETL dependency graph from the selected environment."""

import argparse

from etl.src.config_loader import load_pipeline_config
from etl.src.dependency_graph import generate_dependency_graph


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="docs/pipeline_dependency_graph.dot")
    parser.add_argument("--config", default=None)
    args = parser.parse_args()

    config = load_pipeline_config(args.config)
    path = generate_dependency_graph(config, args.output)
    print(path)


if __name__ == "__main__":
    main()
