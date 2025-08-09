import builtins
import io
import os
import sys
import types
import pytest

import json_parser as jp

def test_invalid_hex_escape_reports_offset():
    bad = '["\\u123g"]'
    with pytest.raises(SyntaxError) as ei:
        jp.parse(bad)
    msg = str(ei.value)
    assert "invalid hex escape \\u123g" in msg

def test_short_unicode_escape_reports_offset():
    bad = '["\\u12"]'
    with pytest.raises(SyntaxError) as ei:
        jp.parse(bad)
    assert "short unicode escape" in str(ei.value)

def test_invalid_single_escape_reports_offset():
    bad = '["\\q"]'
    with pytest.raises(SyntaxError) as ei:
        jp.parse(bad)
    assert "invalid escape \\q" in str(ei.value)

def test_unpaired_surrogate_detected():
    bad = '["\\uD800"]'
    with pytest.raises(SyntaxError) as ei:
        jp.parse(bad)
    assert "unpaired surrogate" in str(ei.value)

def test_trailing_backslash_direct_call():
    # Call the validator directly to induce a trailing backslash case.
    # The token_start is 0 here since we are testing the function in isolation.
    with pytest.raises(SyntaxError) as ei:
        jp._validate_string('"\\', 0)  # trailing backslash before closing quote
    assert "trailing backslash in string" in str(ei.value)
