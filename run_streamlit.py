"""Start the Streamlit app with the project's virtual environment when available."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parent
    app_path = project_root / "app" / "main.py"

    interpreter_path = "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
    project_python = project_root / ".venv" / interpreter_path
    python = str(project_python) if project_python.is_file() else sys.executable
    command = [python, "-m", "streamlit", "run", str(app_path), *sys.argv[1:]]
    return subprocess.call(command, cwd=project_root)


if __name__ == "__main__":
    raise SystemExit(main())
