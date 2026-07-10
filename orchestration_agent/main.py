"""
main.py — Foundry Hosted Agent entry point for boardroom-mvp.

Builds the boardroom-mvp orchestration (see boardroom_orchestration.py —
native Python @workflow/@step, no YAML, no PowerFx, no .NET runtime
dependency), wires each named agent reference (founder-mvp, cfo-mvp,
cmo-mvp) to a real Foundry-hosted chat agent via FoundryChatClient, and
serves it via agent_framework.ag_ui's native FastAPI endpoint — no Node.js
runtime, no bridge.

WHY A THIN WRAPPER CLASS IS STILL NEEDED (verified, not assumed)
--------------------------------------------------------------------
add_agent_framework_fastapi_endpoint accepts SupportsAgentRun | Workflow |
AgentFrameworkAgent | AgentFrameworkWorkflow (verified directly against
agent_framework_ag_ui/_endpoint.py). The FunctionalWorkflow object
returned by build_boardroom_workflow() (a @workflow-decorated function)
is NEITHER a graph-based Workflow NOR does it structurally satisfy
SupportsAgentRun as-is — confirmed directly: it's missing .id,
.create_session(), and .get_session() (isinstance() check fails without
them, even though .name, .description, and .run() are already present
with compatible signatures).

agent_framework itself ships FunctionalWorkflowAgent
(agent_framework._workflows._functional.FunctionalWorkflowAgent)
specifically to adapt a FunctionalWorkflow into something agent-shaped —
it supplies .id, delegates .name/.description, and wraps .run() with the
correct AgentResponse-returning overloads. It is STILL missing
create_session/get_session though (confirmed directly) so
CompleteFunctionalWorkflowAgent below adds just those two, verified via
isinstance(instance, SupportsAgentRun) == True with this addition and
nothing else.
"""

from __future__ import annotations

import os

from agent_framework import AgentSession
from agent_framework._workflows._functional import FunctionalWorkflowAgent
from agent_framework.ag_ui import add_agent_framework_fastapi_endpoint
from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential
from fastapi import FastAPI

from boardroom_orchestration import build_boardroom_workflow

# ── Configuration ────────────────────────────────────────────────────────

FOUNDRY_PROJECT_ENDPOINT = os.environ["FOUNDRY_PROJECT_ENDPOINT"]

# Each agent name build_boardroom_workflow()/boardroom_orchestration.py
# expects (founder-mvp, cfo-mvp, cmo-mvp — see SPECIALIST_ROUTES there for
# the CFO/CMO mapping) maps to a Foundry model deployment here. Adding a
# new specialist as the org grows: add its entry here, add its route in
# boardroom_orchestration.py's SPECIALIST_ROUTES, done.
AGENT_NAME_TO_FOUNDRY_DEPLOYMENT: dict[str, str] = {
    "founder-mvp": os.environ.get("FOUNDER_MODEL_DEPLOYMENT", os.environ["DEFAULT_MODEL_DEPLOYMENT"]),
    "cfo-mvp": os.environ.get("CFO_MODEL_DEPLOYMENT", os.environ["DEFAULT_MODEL_DEPLOYMENT"]),
    "cmo-mvp": os.environ.get("CMO_MODEL_DEPLOYMENT", os.environ["DEFAULT_MODEL_DEPLOYMENT"]),
}

# AG-UI CORS — restrict this to the actual frontend origin(s) in production.
AG_UI_ALLOW_ORIGINS = os.environ.get("AG_UI_ALLOW_ORIGINS", "*").split(",")


class CompleteFunctionalWorkflowAgent(FunctionalWorkflowAgent):
    """FunctionalWorkflowAgent + the two SupportsAgentRun members it's
    missing (create_session, get_session). Verified via isinstance check
    against SupportsAgentRun — see this module's docstring."""

    def create_session(self, *, session_id: str | None = None) -> AgentSession:
        return AgentSession(session_id=session_id)

    def get_session(self, service_session_id, *, session_id: str | None = None) -> AgentSession:
        return AgentSession(service_session_id=service_session_id, session_id=session_id)


def build_foundry_agents(credential: DefaultAzureCredential) -> dict[str, object]:
    """Build one real Foundry-backed Agent per named agent reference."""
    agents: dict[str, object] = {}
    for agent_name, deployment in AGENT_NAME_TO_FOUNDRY_DEPLOYMENT.items():
        chat_client = FoundryChatClient(
            project_endpoint=FOUNDRY_PROJECT_ENDPOINT,
            model=deployment,
            credential=credential,
        )
        agents[agent_name] = chat_client.as_agent(name=agent_name)
    return agents


def create_app() -> FastAPI:
    """Build the FastAPI app serving boardroom-mvp's AG-UI endpoint."""
    credential = DefaultAzureCredential()
    agents = build_foundry_agents(credential)

    functional_workflow = build_boardroom_workflow(agents)
    agent = CompleteFunctionalWorkflowAgent(functional_workflow)

    app = FastAPI(title="boardroom-mvp")
    add_agent_framework_fastapi_endpoint(
        app,
        agent,
        "/",
        allow_origins=AG_UI_ALLOW_ORIGINS,
    )
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
