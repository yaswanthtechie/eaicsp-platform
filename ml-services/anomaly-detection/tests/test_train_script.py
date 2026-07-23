import subprocess
import sys
import unittest
from pathlib import Path


class TrainScriptTests(unittest.TestCase):
    def test_train_script_runs(self):
        repo_root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, str(repo_root / "src" / "train.py")],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )

        self.assertEqual(
            result.returncode,
            0,
            msg=result.stderr or result.stdout,
        )


if __name__ == "__main__":
    unittest.main()
