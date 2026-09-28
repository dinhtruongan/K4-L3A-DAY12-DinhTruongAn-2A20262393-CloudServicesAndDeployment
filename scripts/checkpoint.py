"""Run a command and retain its output, exit code, revision and environment."""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    name, *command = sys.argv[1:]
    if command and command[0] == "--":
        command.pop(0)
    if command[0] == "python":
        command[0] = sys.executable
    directory = ROOT / "evidence"
    directory.mkdir(exist_ok=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                            encoding="utf-8", errors="replace", stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    output = result.stdout
    # Commands recorded here must never include secret values in arguments.
    for key, value in env.items():
        if value and len(value) >= 8 and any(s in key for s in ("TOKEN", "SECRET", "API_KEY", "PASSWORD")):
            output = output.replace(value, "[REDACTED]")
    (directory / f"{name}.txt").write_text(output, encoding="utf-8")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    metadata = {"command": command, "started_utc": started,
                "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "revision": revision, "working_tree": subprocess.check_output(
                    ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True),
                "python": platform.python_version(), "platform": platform.platform(),
                "exit_code": result.returncode, "output": f"{name}.txt"}
    (directory / f"{name}.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(output)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
