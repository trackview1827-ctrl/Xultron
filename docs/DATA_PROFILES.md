# Xultron data profiles

Xultron uses two strictly separated profiles. They are not Git branches.

## Clean source profile

The GitHub repository contains source code, tests, documentation and placeholder
configuration only. It must not contain chat history, memory, user identifiers,
real PIN hashes, provider credentials, session metadata, databases, logs or built
artifacts. `scripts/check-clean-tree.sh` enforces the tracked-file boundary and is
part of the full release gate.

## Local runtime profile

Personal runtime state stays only on the device in ignored files:

- `backend/instance/` for the database, encrypted provider credentials and local
  backend identity configuration.
- `frontend/.env.local` for the local login-screen display values used at build time.

These files must never be committed, pushed, copied into a release archive or put
on a data-bearing Git branch. A second Git version containing personal data is not
created because Git history is difficult to erase reliably.

## Erasing local conversational data

Stop Xultron, then run:

```bash
python scripts/purge-local-data.py --yes
```

The command deletes conversations, messages, memories, idempotency responses,
sessions, guest users and device activity. It keeps the local identity, settings
and encrypted provider configuration so the installation can still be used.
