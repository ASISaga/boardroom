# boardroom-mvp: native Python Agent Framework orchestration

Replaces `boardroom-mvp`'s Foundry visual-workflow YAML with a **native
Python orchestration**, ahead of the Dec 1, 2026 retirement of Foundry's
visual workflow designer — and, per explicit direction, **without any
PowerFx or .NET runtime dependency**, deployed as a Foundry Hosted Agent,
serving AG-UI natively (no Node.js, no bridge).

## Why not the PowerFx YAML approach (an earlier direction, now abandoned)

An earlier version of this project migrated the original Foundry-exported
YAML into `agent_framework.declarative`'s loader format. That loader is
**inherently PowerFx-based** — confirmed by reading its own module
docstring and `eval()` method directly: any expression beyond a single
bare custom-function call requires a real coreclr (.NET) runtime via the
`powerfx` Python package (a C#-implementation bridge via `pythonnet`).
There is no PowerFx-free dialect within that specific loader.

Given the explicit requirement to avoid PowerFx/.NET entirely, this
project instead expresses the **same orchestration logic as native
Python**, using `agent_framework`'s `@workflow`/`@step` functional API —
real `while`/`if` control flow, zero PowerFx, zero .NET dependency
anywhere in the call chain. Verified directly: `agent_framework`'s core
`@workflow`/`@step` decorators (`agent_framework._workflows._functional`)
have no PowerFx/coreclr dependency at all; only the separate
`agent_framework_declarative` package (not used here) has that
dependency.

## Files

| File | Purpose |
|---|---|
| `boardroom_orchestration.py` | The orchestration logic itself — founder leads, routes to CFO/CMO based on a `[ROUTE:X]` tag in its own reply, loops until `[COMPLETE]` or a turn limit, all as plain Python `while`/`if` control flow inside an `@workflow`-decorated function. |
| `main.py` | Wires real Foundry-backed agents (`FoundryChatClient.as_agent(...)`) into the orchestration and serves it via `agent_framework.ag_ui`'s native FastAPI AG-UI endpoint. |
| `test_boardroom_orchestration.py` | 4 tests of the orchestration logic in isolation, with mock agents — no Foundry, no HTTP, no PowerFx. |
| `test_main_agui_endpoint.py` | Full end-to-end test: a real HTTP POST through a real FastAPI `TestClient`, hitting the real AG-UI endpoint, running the real orchestration with mock agents, producing a real, complete AG-UI SSE stream. |
| `Dockerfile` | Plain `python:3.12-slim` — **no .NET runtime layer**, since none is needed. |
| `requirements.txt` | No `agent-framework-declarative`, no `powerfx`. |

## What's genuinely verified — and this time, nothing was blocked

Unlike the earlier PowerFx-based version of this project (where full
routing/loop/completion testing was blocked by the lack of a .NET runtime
in the build sandbox), **every test in this version ran to full, genuine
completion**:

- **`test_boardroom_orchestration.py`** — 4/4 tests pass, exercising:
  routing to CFO with a subsequent founder completion, routing to CMO,
  hitting the `MAX_TURNS` limit without ever completing (confirms the loop
  terminates rather than running forever), and a same-turn completion with
  no specialist routing at all.
- **`test_main_agui_endpoint.py`** — a genuine HTTP request through
  `FastAPI`'s `TestClient`, hitting the real
  `add_agent_framework_fastapi_endpoint`-mounted route, with the real
  `CompleteFunctionalWorkflowAgent` wrapper, producing a complete, correct
  AG-UI SSE event sequence: `RUN_STARTED` →
  `TEXT_MESSAGE_START/CONTENT/END` → `MESSAGES_SNAPSHOT` → `RUN_FINISHED`,
  with the founder's actual routing decision and completion text present
  in the output.
- Every API surface used (`FunctionalWorkflowAgent`, `SupportsAgentRun`,
  `Agent.run`, `FoundryChatClient.as_agent`,
  `add_agent_framework_fastapi_endpoint`) was checked against its real,
  installed signature — and one real gap was found and fixed this way:
  `FunctionalWorkflowAgent` (Microsoft's own adapter for wrapping a
  `FunctionalWorkflow` as agent-shaped) is missing `create_session`/
  `get_session`, so it does **not** fully satisfy `SupportsAgentRun` as
  shipped — confirmed via `isinstance()` — hence
  `CompleteFunctionalWorkflowAgent`'s two-method addition in `main.py`,
  also confirmed via `isinstance()` to close the gap completely.

**Still not verified — genuinely could not be, in this environment:**
- **Real Foundry connectivity.** `FoundryChatClient` calls were verified
  for correct *construction* only — no live Foundry project/model
  deployment was available. Test against your real
  `founder-mvp`/`cfo-mvp`/`cmo-mvp` deployments before production use.
- **The Dockerfile.** Not built or run in this environment (no Docker
  daemon available) — though it's now considerably simpler than the
  earlier .NET-inclusive version, since there's nothing exotic left to go
  wrong (`python:3.12-slim` + `pip install`).

## Org-chart-as-data — the honest tradeoff of dropping YAML

Since YAML (and its PowerFx-based "data, not code" property) is gone, the
"org chart evolves without code changes" property is **not fully
preserved** — this is the direct, explicit tradeoff of the no-PowerFx
requirement. What remains true: adding a new specialist as the company
grows is still a small, additive, isolated change —

```python
# In boardroom_orchestration.py:
SPECIALIST_ROUTES: dict[str, str] = {
    "cfo": "cfo-mvp",
    "cmo": "cmo-mvp",
    "regional-head-emea": "regional-head-emea-mvp",  # new
}
```

```python
# In main.py:
AGENT_NAME_TO_FOUNDRY_DEPLOYMENT: dict[str, str] = {
    ...,
    "regional-head-emea-mvp": os.environ.get("REGIONAL_HEAD_EMEA_MODEL_DEPLOYMENT", ...),  # new
}
```

— but it is a code change (a Python file edit + redeploy), not a pure data
edit a non-developer could make. If the "org chart as pure data, zero code
changes" property becomes a hard requirement later, that would need either
(a) accepting the PowerFx/.NET dependency after all, or (b) building a
small custom, non-PowerFx expression/config format specifically for this
purpose — a larger, separate design exercise not undertaken here.

## Deploying as a Foundry Hosted Agent

```bash
docker build -t boardroom-mvp-workflow .
docker tag boardroom-mvp-workflow <your-acr>.azurecr.io/boardroom-mvp-workflow:latest
docker push <your-acr>.azurecr.io/boardroom-mvp-workflow:latest
```

Deploy via the same Hosted Agent mechanism as your existing
`founder-mvp`/`cfo-mvp`/`cmo-mvp` agents, with these environment variables:

| Variable | Required | Notes |
|---|---|---|
| `FOUNDRY_PROJECT_ENDPOINT` | Yes | Same project as your existing agents |
| `DEFAULT_MODEL_DEPLOYMENT` | Yes | Fallback model deployment name |
| `FOUNDER_MODEL_DEPLOYMENT` | No | Override if founder needs a different model |
| `CFO_MODEL_DEPLOYMENT` | No | Override if CFO needs a different model |
| `CMO_MODEL_DEPLOYMENT` | No | Override if CMO needs a different model |
| `AG_UI_ALLOW_ORIGINS` | No | Comma-separated CORS origins; defaults to `*` |
| `PORT` | No | Defaults to `8000` |

## Frontend connection

Point the Web Components frontend's `CopilotKitClient` (or any other
AG-UI-compatible client) **directly** at this container's own URL — no
intermediate hop, no Node.js runtime, no protocol bridge. There is no
separate frontend-adapter project in this plan.
