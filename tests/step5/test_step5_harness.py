import os
import sys
import subprocess
import pytest

# Force sys.path to include repo root
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(REPO_ROOT)

TEST_DIR = os.path.dirname(__file__)

# List all .json files in step5/
json_files = sorted(f for f in os.listdir(TEST_DIR) if f.endswith(".json"))

# Adapted filters to match current filenames
VALID_FILES = [f for f in json_files if f.startswith("pass")]
INVALID_FILES = [f for f in json_files if f.startswith("fail")]

# Hard fail if test files are missing
if not VALID_FILES:
    raise RuntimeError("No pass*.json files found in step5 directory")
if not INVALID_FILES:
    raise RuntimeError("No fail*.json files found in step5 directory")

@pytest.mark.parametrize("filename", VALID_FILES)
def test_valid_json_returns_0(filename):
    path = os.path.join(TEST_DIR, filename)
    result = subprocess.run(["python", "json_parser.py", path])
    assert result.returncode == 0, f"Expected 0 from {filename}, got {result.returncode}"

@pytest.mark.parametrize("filename", INVALID_FILES)
def test_invalid_json_returns_1(filename):
    path = os.path.join(TEST_DIR, filename)
    result = subprocess.run(["python", "json_parser.py", path])
    assert result.returncode == 1, f"Expected 1 from {filename}, got {result.returncode}"
