import os
import subprocess
import pytest

TEST_DIR = os.path.dirname(__file__)
VALID = os.path.join(TEST_DIR, "valid.json")
INVALID = os.path.join(TEST_DIR, "invalid.json")

def test_valid_json_returns_0():
    """Accepts types: true, false, null, numbers, strings"""
    result = subprocess.run(["python", "json_parser.py", VALID])
    assert result.returncode == 0

def test_invalid_json_returns_1():
    """Rejects malformed type declarations"""
    result = subprocess.run(["python", "json_parser.py", INVALID])
    assert result.returncode == 1
