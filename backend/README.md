# Xultron backend

Flask API backend for Xultron.

## Runtime

- Python 3.11 or newer is required.
- The backend uses `datetime.UTC` and is intentionally not advertised as Python 3.10 compatible.

## Validation

Run from this directory:

```bash
python -m compileall app tests
python -m pytest
```

## Trusted time context

Every model-backed chat request receives a server-generated system message with the
current Unix timestamp in seconds, the equivalent UTC ISO-8601 value, and the user's
saved IANA time zone converted to its current local time and UTC offset. IANA zones,
such as `Asia/Dubai` (`UTC+04:00`), are used instead of fixed offsets so daylight-saving
rules are applied where relevant. The per-user zone is read only from validated settings,
never from chat message content.

`GET /api/v1/system/health` retains its existing `time` field and also exposes
`utcTime` and integer `unixTime` for clients that need the canonical server clock.
