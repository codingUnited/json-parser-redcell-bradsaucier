import pytest
import json_parser as jp

def test_extra_data_reports_offset():
    txt = '[1] 2'
    with pytest.raises(SyntaxError) as ei:
        jp.parse(txt)
    assert "extra data after root value" in str(ei.value)

def test_root_must_be_object_or_array():
    with pytest.raises(SyntaxError) as ei:
        jp.parse('true')
    # message includes actual kind and position
    msg = str(ei.value)
    assert "payload must be object or array at root" in msg
    assert "got LITERAL" in msg or "got STRING" in msg

def test_duplicate_key_rejected_by_default():
    with pytest.raises(SyntaxError):
        jp.parse('{"a":1,"a":2}')

def test_missing_comma_in_object_reports_expected():
    with pytest.raises(SyntaxError) as ei:
        jp.parse('{"a":1 "b":2}')
    msg = str(ei.value)
    # Should mention expected COMMA
    assert "expected COMMA" in msg

def test_missing_closing_bracket_in_array():
    with pytest.raises(SyntaxError) as ei:
        jp.parse('[1,2')
    assert "unexpected end of input" in str(ei.value) or "expected BRACKET" in str(ei.value)
