import os
import subprocess
import pytest

TEST_DIR = os.path.dirname(__file__)

VALID_FILES = [
    "valid.json",
    "valid2.json"
]

INVALID_FILES = [
    "invalid.json",
    "invalid2.json"
]

@pytest.mark.parametrize("filename", VALID_FILES)
def test_valid_cases(filename):
    path = os.path.join(TEST_DIR, filename)
    result = subprocess.run(["python", "json_parser.py", path])
    assert result.returncode == 0

@pytest.mark.parametrize("filename", INVALID_FILES)
def test_invalid_cases(filename):
    path = os.path.join(TEST_DIR, filename)
    result = subprocess.run(["python", "json_parser.py", path])
    assert result.returncode == 1
