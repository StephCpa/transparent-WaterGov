"""Generated documentation and examples must match the code."""

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class GeneratedFiles(unittest.TestCase):
    def test_up_to_date(self):
        p = subprocess.run([sys.executable, str(ROOT / "tools" / "gen_docs.py"), "--check"],
                           capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()
