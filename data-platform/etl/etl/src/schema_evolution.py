from pathlib import Path
from shutil import move


def handle_schema_evolution(file_path, source_config, project_root=None):
    """Handle unexpected source columns according to the source policy.

    Current supported policy is quarantine: the source file is moved out of
    the normal ingestion folder and a ValueError is raised so callers cannot
    accidentally continue with silent column loss.
    """
    policy = getattr(source_config, "schema_evolution", "quarantine")
    if policy != "quarantine":
        raise ValueError(f"Unsupported schema_evolution policy: {policy}")
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]
    quarantine_dir = root / "data" / "quarantine"
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    destination = quarantine_dir / Path(file_path).name
    move(str(file_path), str(destination))
    return destination
