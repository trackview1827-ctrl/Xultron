from datetime import UTC, datetime

from app.services.chat import _provider_context
from app.services.time_context import current_time_context, time_context_prompt


def test_current_time_context_uses_unix_utc_and_active_iana_zone():
    now = datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC)

    context = current_time_context("Asia/Dubai", now)

    assert context == {
        "unixTime": 1767225601,
        "utcTime": "2026-01-01T00:00:01Z",
        "timeZone": "Asia/Dubai",
        "utcOffset": "+04:00",
        "localTime": "2026-01-01T04:00:01+04:00",
    }


def test_current_time_context_falls_back_to_utc_for_invalid_or_malformed_zone():
    for zone in ("not/a-real-zone", "UTC\x00corrupted"):
        context = current_time_context(zone, datetime(2026, 1, 1, tzinfo=UTC))

        assert context["timeZone"] == "UTC"
        assert context["utcOffset"] == "+00:00"


def test_provider_context_always_includes_trusted_time_in_low_data_mode(app):
    settings = {
        "timeZone": "Asia/Dubai",
        "memoryEnabled": False,
        "personaName": "Xultron",
        "customInstructions": "",
        "conversationHistory": False,
    }
    with app.app_context():
        messages = _provider_context("user", None, "x" * 8000, settings, low_data=True)

    assert messages[0]["role"] == "system"
    assert "Trusted current server time" in messages[0]["content"]
    assert "Unix timestamp (seconds):" in messages[0]["content"]
    assert "Active time zone: Asia/Dubai (UTC+04:00)" in messages[0]["content"]
    assert messages[-1] == {"role": "user", "content": "x" * 8000}


def test_time_context_prompt_is_server_derived_and_explicit():
    prompt = time_context_prompt("UTC", datetime(2026, 1, 1, tzinfo=UTC))

    assert "Unix timestamp (seconds): 1767225600" in prompt
    assert "UTC: 2026-01-01T00:00:00Z" in prompt
    assert "Active time zone: UTC (UTC+00:00)" in prompt
