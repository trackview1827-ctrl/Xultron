"""Trusted server time context for model-backed responses."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def current_time_context(time_zone: str | None, now: datetime | None = None) -> dict[str, int | str]:
    """Return one UTC-clock snapshot and its conversion for an IANA time zone.

    The active time zone is a user setting, so it is intentionally never accepted
    from an individual chat request. Invalid or unavailable zones fail safely to UTC.
    """
    utc_now = (now or datetime.now(UTC)).astimezone(UTC)
    zone_name = str(time_zone or "UTC")
    try:
        zone = ZoneInfo(zone_name)
    except (ValueError, ZoneInfoNotFoundError):
        zone_name = "UTC"
        local_now = utc_now
    else:
        local_now = utc_now.astimezone(zone)
    offset = local_now.strftime("%z")
    formatted_offset = f"{offset[:3]}:{offset[3:]}"
    return {
        "unixTime": int(utc_now.timestamp()),
        "utcTime": utc_now.isoformat().replace("+00:00", "Z"),
        "timeZone": zone_name,
        "utcOffset": formatted_offset,
        "localTime": local_now.isoformat(),
    }


def time_context_prompt(time_zone: str | None, now: datetime | None = None) -> str:
    """Format immutable server time as a provider system message."""
    context = current_time_context(time_zone, now)
    return (
        "Trusted current server time. Treat these values as authoritative for time-sensitive answers: "
        f"Unix timestamp (seconds): {context['unixTime']}. "
        f"UTC: {context['utcTime']}. "
        f"Active time zone: {context['timeZone']} (UTC{context['utcOffset']}). "
        f"Local time: {context['localTime']}."
    )
