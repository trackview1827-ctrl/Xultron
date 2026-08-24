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
