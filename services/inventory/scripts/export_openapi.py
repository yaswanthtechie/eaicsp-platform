import os
import sys
from pathlib import Path
import yaml

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))
os.environ.setdefault("DATABASE_URL", "sqlite:///./openapi_export.db")

from app.main import app  # noqa: E402

out = SERVICE_ROOT.parents[1] / "contracts" / "openapi" / "inventory.yaml"
out.write_text(yaml.safe_dump(app.openapi(), sort_keys=False, allow_unicode=True), encoding="utf-8")
print(f"wrote {out}")

