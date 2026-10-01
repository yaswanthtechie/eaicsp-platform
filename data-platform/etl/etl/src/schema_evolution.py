from pathlib import Path
from shutil import move
from datetime import datetime


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
    original = Path(file_path)
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    destination = quarantine_dir / f"{original.stem}__quarantined_{stamp}{original.suffix}"
    move(str(original), str(destination))
    return destination
