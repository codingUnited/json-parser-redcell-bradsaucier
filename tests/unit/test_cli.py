import os
import subprocess
import sys
import tempfile
import pathlib

def test_cli_streaming_placeholder_prints_ok(monkeypatch):
    data = "[1,2,3]"
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(data)
        fname = f.name
    try:
        # Force stream mode with a tiny threshold so it prints the placeholder
        cmd = [sys.executable, "json_parser.py", fname, "--streaming-threshold", "1"]
        cp = subprocess.run(cmd, capture_output=True, text=True)
        assert cp.returncode == 0
        assert "OK (stream mode placeholder)" in (cp.stdout + cp.stderr)
    finally:
        pathlib.Path(fname).unlink(missing_ok=True)
