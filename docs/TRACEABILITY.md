# Requirement traceability

This matrix ties the remaining lifecycle requirements to executable checks.

| Requirement | Implementation | Validation |
| --- | --- | --- |
| Settings/Core navigation keeps the active conversation and draft while the app is running | `frontend/src/stores/AppContext.tsx`, `frontend/src/features/chat/HomePage.tsx`, `frontend/src/layouts/AppShell.tsx` | `frontend/src/test/appBehavior.test.tsx` keeps `activeConversationId` and `activeDraft` across a settings update |
| Closing and reopening starts with a new empty active session | Active conversation is held in in-memory React context, not browser storage | App provider state has no persistence side effect; add an end-to-end browser restart check before release |
| Agent selects declared capabilities and observes results before completion | `backend/app/services/planner.py`, `backend/app/services/tasks.py`, `backend/app/agent/registry.py` | `backend/tests/test_dynamic_agent.py`, `backend/tests/test_tasks.py` |
| Failed/cancelled work can re-enter planning without stale execution state | `backend/app/services/tasks.py:retry_task` clears stale plan and observation | `test_retry_clears_stale_plan_and_observation_for_replanning` |
| Side effects remain denied by default and undeclared tools are rejected | `backend/app/agent/registry.py` | `backend/tests/test_tool_registry.py` |
| Termux APIs are not invoked by the verification runtime | Runtime planner explicitly uses bounded backend facts and marks device automation unsupported | `backend/tests/test_hardening.py` and verification tests |

Run the focused checks with:

```sh
cd frontend && npm test -- src/test/appBehavior.test.tsx
cd backend && pytest -q tests/test_tasks.py tests/test_dynamic_agent.py tests/test_tool_registry.py
```
