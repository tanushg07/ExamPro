"""
Tests for the services/validation module.
Covers sanitize_html, sanitize_code, validate_json_size, and
validate_time_difference without requiring a running database.
"""
import json
import pytest
from datetime import datetime, timedelta, timezone

from app.services.validation import (
    sanitize_html,
    sanitize_code,
    validate_json_size,
    validate_time_difference,
    MAX_JSON_SIZE,
)


# ---------------------------------------------------------------------------
# sanitize_html
# ---------------------------------------------------------------------------

def test_sanitize_html_returns_none_for_empty():
    assert sanitize_html(None) is None
    assert sanitize_html('') == ''


def test_sanitize_html_strips_script_tags():
    dirty = '<p>Hello</p><script>alert("xss")</script>'
    clean = sanitize_html(dirty)
    # bleach removes the <script> element but may keep inner text — the
    # important invariant is that no executable <script> tag survives.
    assert '<script>' not in clean
    assert '</script>' not in clean
    assert '<p>Hello</p>' in clean


def test_sanitize_html_keeps_allowed_tags():
    html = '<p>Text <b>bold</b> <i>italic</i></p><ul><li>item</li></ul>'
    clean = sanitize_html(html)
    assert '<p>' in clean
    assert '<b>' in clean
    assert '<i>' in clean
    assert '<ul>' in clean
    assert '<li>' in clean


def test_sanitize_html_strips_disallowed_tags():
    html = '<div><p>OK</p></div><a href="evil">link</a>'
    clean = sanitize_html(html)
    assert '<div>' not in clean
    assert '<a' not in clean
    # The text content inside the stripped tags should survive
    assert 'OK' in clean
    assert 'link' in clean


def test_sanitize_html_allows_span_with_class():
    html = '<span class="highlight">text</span>'
    clean = sanitize_html(html)
    assert '<span class="highlight">' in clean


def test_sanitize_html_strips_span_with_forbidden_attr():
    html = '<span style="color:red">text</span>'
    clean = sanitize_html(html)
    # style attribute should be stripped
    assert 'style=' not in clean


# ---------------------------------------------------------------------------
# sanitize_code
# ---------------------------------------------------------------------------

def test_sanitize_code_returns_none_for_empty():
    assert sanitize_code(None) is None
    assert sanitize_code('') == ''


def test_sanitize_code_keeps_pre_code_span():
    code = '<pre><code><span class="kw">def</span> foo():</code></pre>'
    clean = sanitize_code(code)
    assert '<pre>' in clean
    assert '<code>' in clean
    assert '<span class="kw">' in clean


def test_sanitize_code_strips_script():
    dirty = '<code>print("hi")</code><script>evil()</script>'
    clean = sanitize_code(dirty)
    # The <script> tag itself must not survive sanitisation.
    assert '<script>' not in clean
    assert '</script>' not in clean


# ---------------------------------------------------------------------------
# validate_json_size
# ---------------------------------------------------------------------------

def test_validate_json_size_empty_returns_empty_dict():
    assert validate_json_size(None) == {}
    assert validate_json_size({}) == {}


def test_validate_json_size_valid_small_dict():
    data = {'key': 'value', 'number': 42}
    result = validate_json_size(data)
    assert result == data


def test_validate_json_size_parses_json_string():
    data = {'a': 1}
    result = validate_json_size(json.dumps(data))
    assert result == data


def test_validate_json_size_invalid_string_returns_error():
    result = validate_json_size('not valid json{{')
    assert result.get('error') == 'Invalid JSON format'
    assert result.get('truncated') is True


def test_validate_json_size_oversized_returns_error():
    big = {'data': 'x' * (MAX_JSON_SIZE + 1)}
    result = validate_json_size(big)
    assert result.get('error') == 'JSON data too large'
    assert result.get('truncated') is True
    assert result.get('original_size', 0) > MAX_JSON_SIZE


def test_validate_json_size_exactly_at_limit():
    # Build a dict whose serialised form is exactly MAX_JSON_SIZE chars
    wrapper = '{"data": ""}'
    filler_len = MAX_JSON_SIZE - len(wrapper) + len('""') - 2  # account for quotes
    filler = 'a' * max(filler_len, 0)
    data = {'data': filler}
    serialised = json.dumps(data)
    if len(serialised) <= MAX_JSON_SIZE:
        result = validate_json_size(data)
        assert result == data


# ---------------------------------------------------------------------------
# validate_time_difference
# ---------------------------------------------------------------------------

def test_validate_time_difference_none_client_time():
    is_valid, diff = validate_time_difference(None)
    assert not is_valid
    assert diff is None


def test_validate_time_difference_within_tolerance():
    now = datetime.utcnow()
    client_time = now + timedelta(seconds=30)  # 30-second drift
    is_valid, diff = validate_time_difference(client_time, server_time=now)
    assert is_valid
    assert abs(diff - 30) < 1


def test_validate_time_difference_exceeds_tolerance():
    now = datetime.utcnow()
    client_time = now + timedelta(minutes=10)  # 10-minute drift
    is_valid, diff = validate_time_difference(client_time, server_time=now)
    assert not is_valid
    assert diff > 300


def test_validate_time_difference_custom_max():
    now = datetime.utcnow()
    client_time = now + timedelta(seconds=400)
    # Default max is 300 s — should fail
    is_valid, _ = validate_time_difference(client_time, server_time=now)
    assert not is_valid
    # With a higher limit it should pass
    is_valid2, _ = validate_time_difference(client_time, server_time=now, max_diff_seconds=600)
    assert is_valid2


def test_validate_time_difference_string_input():
    now = datetime.utcnow()
    # Provide client time as ISO string (UTC, no offset)
    client_str = (now + timedelta(seconds=10)).isoformat()
    is_valid, diff = validate_time_difference(client_str, server_time=now)
    assert is_valid
    assert diff < 300


def test_validate_time_difference_uses_server_now_when_not_provided():
    """When server_time is omitted the function should default to utcnow()."""
    client_time = datetime.utcnow() + timedelta(seconds=5)
    is_valid, diff = validate_time_difference(client_time)
    # Should be within the default tolerance
    assert is_valid


def test_validate_time_difference_negative_drift():
    """Client time lagging behind server time is still a drift."""
    now = datetime.utcnow()
    client_time = now - timedelta(seconds=400)  # client is behind
    is_valid, diff = validate_time_difference(client_time, server_time=now)
    assert not is_valid
    assert diff > 300
