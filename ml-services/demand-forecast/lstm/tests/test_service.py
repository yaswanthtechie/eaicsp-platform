from pathlib import Path
import sys


SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))

import service


def test_service_configuration():
    assert service.MODEL_PATH
    assert service.MC_SAMPLES
