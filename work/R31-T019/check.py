#!/usr/bin/env python3
"""Run the PowerShell guide's isolated Git-state check and save its output."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[2]
GUIDE_TEST = ROOT / "tests" / "guides" / "powershell_prerequisites.py"
ACTUAL = Path(__file__).resolve().parent / "actual.txt"


def main():
    assert GUIDE_TEST.is_file()
    with tempfile.TemporaryDirectory(prefix="R31-T019-check-") as directory:
        env = os.environ.copy()
        env["TMPDIR"] = directory
        try:
            result = subprocess.run(
                [sys.executable, str(GUIDE_TEST)],
                cwd=ROOT,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=True,
            )
        except subprocess.CalledProcessError as error:
            print(error.stdout, end="", file=sys.stderr)
            raise

        assert '"result": "PASS"' in result.stdout
        ACTUAL.write_text(result.stdout, encoding="utf-8")
        print(result.stdout, end="")


if __name__ == "__main__":
    main()
