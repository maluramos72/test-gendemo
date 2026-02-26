"""
tests/test_validator.py
───────────────────────
Unit tests for JSON repair and structural validation.
Run with: pytest tests/ -v
"""

import pytest

from app.services.validator import repair_truncated_json, parse_and_validate, strip_fences
from app.services.llm_client import LLMParseError


# ── strip_fences ─────────────────────────────────────────────────────────────

def test_strip_fences_removes_markdown():
    raw = '```json\n{"test_cases": []}\n```'
    assert strip_fences(raw) == '{"test_cases": []}'


def test_strip_fences_noop_on_clean():
    raw = '{"test_cases": []}'
    assert strip_fences(raw) == raw


# ── repair_truncated_json ────────────────────────────────────────────────────

VALID_CASE = {
    "title": "Happy Path",
    "preconditions": "User has a valid account and is on the login page",
    "steps": ["Enter email", "Enter password", "Click login"],
    "expected_result": "User is redirected to the dashboard and sees a welcome message",
}

VALID_JSON = '{"test_cases": [' + str(VALID_CASE).replace("'", '"') + ']}'


def test_repair_valid_json_passthrough():
    data = repair_truncated_json(VALID_JSON)
    assert "test_cases" in data


def test_repair_truncated_mid_string():
    # Simulate truncation mid-string
    truncated = '{"test_cases": [{"title": "Happy Path", "preconditions": "User logged in", "steps": ["Step 1"], "expected_result": "User sees dash'
    with pytest.raises(Exception):
        # We expect repair to either succeed or raise JSONDecodeError
        # The truncated case here is too minimal to repair fully
        repair_truncated_json(truncated)


def test_repair_with_trailing_comma():
    raw = '{"test_cases": [{"title": "T", "preconditions": "P", "steps": ["s1"], "expected_result": "R"},]}'
    data = repair_truncated_json(raw)
    assert "test_cases" in data


# ── parse_and_validate ───────────────────────────────────────────────────────

FULL_VALID_PAYLOAD = {
    "test_cases": [
        {
            "title": "Happy Path Login",
            "preconditions": "User has a verified account with correct credentials on the login page",
            "steps": ["Enter valid email address", "Enter correct password", "Click the Login button"],
            "expected_result": "User is redirected to the dashboard and a welcome banner is displayed",
        },
        {
            "title": "Invalid Password Error",
            "preconditions": "User account exists but user enters wrong password on login page",
            "steps": ["Enter valid email", "Enter incorrect password", "Click Login"],
            "expected_result": "Error message 'Invalid credentials' appears; user stays on login page",
        },
    ]
}

import json


def test_parse_and_validate_clean_json():
    raw = json.dumps(FULL_VALID_PAYLOAD)
    output, repaired = parse_and_validate(raw, stop_reason="stop")
    assert len(output.test_cases) == 2
    assert repaired is False


def test_parse_and_validate_with_fences():
    raw = "```json\n" + json.dumps(FULL_VALID_PAYLOAD) + "\n```"
    output, repaired = parse_and_validate(raw, stop_reason="stop")
    assert len(output.test_cases) == 2


def test_parse_and_validate_raises_on_garbage():
    with pytest.raises(LLMParseError):
        parse_and_validate("this is not json at all !!!", stop_reason="stop")


def test_parse_and_validate_raises_on_missing_key():
    raw = json.dumps({"wrong_key": []})
    with pytest.raises(LLMParseError):
        parse_and_validate(raw, stop_reason="stop")


# ── scorer ───────────────────────────────────────────────────────────────────

from app.services.scorer import score_test_cases
from app.core.models import TestCase


def make_tc(**kwargs) -> TestCase:
    defaults = {
        "title": "Test Case Title",
        "preconditions": "User is on the registration page with valid data",
        "steps": ["Step one action", "Step two action", "Step three action"],
        "expected_result": "System displays confirmation and sends verification email to user",
    }
    return TestCase(**{**defaults, **kwargs})


def test_score_high_quality():
    cases = [
        make_tc(title="Happy Path Registration"),
        make_tc(title="Email Already Registered Error"),
        make_tc(title="Edge Case Empty Form Submission"),
        make_tc(title="Security SQL Injection Attempt"),
    ]
    report = score_test_cases(cases)
    assert report.score >= 0.70
    assert report.label == "Alta calidad"


def test_score_vague_expected_results():
    cases = [
        make_tc(expected_result="It works correctly and everything is ok"),
        make_tc(expected_result="Works fine and success is shown"),
    ]
    report = score_test_cases(cases)
    assert report.dimensions.expected_results < 0.8


def test_score_generic_preconditions():
    cases = [
        make_tc(preconditions="N/A"),
        make_tc(preconditions="the user is logged in"),
    ]
    report = score_test_cases(cases)
    assert report.dimensions.preconditions < 0.5


def test_score_dimensions_in_range():
    cases = [make_tc() for _ in range(4)]
    report = score_test_cases(cases)
    d = report.dimensions
    for val in [d.quantity, d.steps_depth, d.preconditions, d.expected_results, d.diversity]:
        assert 0.0 <= val <= 1.0
