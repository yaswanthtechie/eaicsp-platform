import json
from pathlib import Path
from typing import Any, Optional


class WatermarkManager:
    """Manages the state of the pipeline to enable incremental processing."""

    def __init__(self, filepath: str | Path):
        self.filepath = Path(filepath)

    def get_watermark(self) -> Optional[Any]:
        """Reads the highest processed value from the previous run."""
        if not self.filepath.exists():
            return None
        try:
            with open(self.filepath, 'r') as f:
                data = json.load(f)
                return data.get("last_watermark")
        except (json.JSONDecodeError, OSError):
            return None

    def set_watermark(self, value: Any) -> None:
        """Saves the new highest value after a successful pipeline run."""
        # Safely extract Python natives from NumPy scalars (e.g., int64, float64)
        value = value.item() if hasattr(value, 'item') else value
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(self.filepath, 'w') as f:
            json.dump({"last_watermark": value}, f, indent=2)