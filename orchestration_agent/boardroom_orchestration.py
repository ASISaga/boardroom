"""
boardroom_orchestration.py — boardroom-mvp's orchestration logic, rewritten
as native Python using agent_framework's @workflow/@step functional API.

This REPLACES the PowerFx-based declarative YAML entirely. No YAML, no
PowerFx, no .NET runtime dependency anywhere in this file — confirmed
directly: agent_framework's core @workflow/@step decorators
(agent_framework._workflows._functional) have zero dependency on the
`powerfx` package or a coreclr runtime; only agent_framework_declarative
(the Foundry-YAML-flavored loader) has that dependency, and this file does
not import or use that package at all.

WHY THIS REPLACES THE YAML, NOT JUST TRANSLATES IT
----------------------------------------------------
agent_framework_declarative's expression language IS PowerFx — confirmed
by reading its own module docstring ("PowerFx Expression Evaluation... The
.NET version uses RecalcEngine...") and its eval() method, which requires
a real coreclr runtime for anything beyond a single bare custom-function
call. There is no "PowerFx-free YAML dialect" within that specific loader
to migrate to. The only way to keep the same orchestration logic while
genuinely dropping the PowerFx/.NET dependency is to express the control
flow in actual Python — which is what this file does, using @workflow's
own real if/while/loop control flow instead of ConditionGroup/GotoAction
expression strings.

SAME LOGIC AS THE ORIGINAL YAML, VERIFIED EQUIVALENT STEP BY STEP
-------------------------------------------------------------------
  YAML                                          Python here
  ----------------------------------------       --------------------------------
  SetVariable Local.Purpose                       purpose = "..." (local variable)
  SetVariable Local.LatestMessage = Concat(...)   latest_message = f"{purpose} — {user_text}"
  InvokeAzureAgent founder-mvp                    await founder.run(latest_message)
  ConditionGroup routing_check (CFO/CMO)          if "[route:cfo]" in reply.lower(): ...
  SetVariable Local.TurnCount += 1                turn_count += 1
  ConditionGroup completion_check                 if "[complete]" in ...: break
                                                   if turn_count >= 6: ... break
  GotoAction back to founder_mvp_agent             (the enclosing while loop)

ORG-CHART-AS-DATA — HOW THIS STILL EVOLVES WITHOUT CODE CHANGES
-------------------------------------------------------------------
Dropping YAML means adding a new specialist is no longer literally a
"no Python changes" edit — but it's still a SINGLE, ISOLATED, additive
change: one more entry in SPECIALIST_ROUTES (name -> route tag) plus one
more branch in _route_to_specialist(). This is the honest tradeoff for
dropping PowerFx/.NET: slightly more than a pure-data edit, but still far
smaller than touching the loop/completion logic, which never changes when
adding participants. If the coordination PATTERN itself needs to change
(not just participants), that was always going to require a real logic
change in either format.
"""

from __future__ import annotations

from agent_framework import Agent, workflow

# ── Configuration ────────────────────────────────────────────────────────

MAX_TURNS = 6
COMPLETION_MARKER = "[complete]"

# Maps a specialist's route tag (as the founder is instructed to emit it,
# e.g. "[ROUTE:CFO]") to the specialist's registered agent name. Adding a
# new specialist as the org grows: add one entry here, and make sure the
# founder's own instructions (configured on the founder-mvp Foundry agent
# itself) know to emit the matching tag.
SPECIALIST_ROUTES: dict[str, str] = {
    "cfo": "cfo-mvp",
    "cmo": "cmo-mvp",
}


def _extract_route_tag(founder_reply: str) -> str | None:
    """Return the lowercased route tag (e.g. "cfo") if the founder's reply
    contains a [ROUTE:X] marker matching a known specialist, else None."""
    lower_reply = founder_reply.lower()
    for tag in SPECIALIST_ROUTES:
        if f"[route:{tag}]" in lower_reply:
            return tag
    return None


def build_boardroom_workflow(agents: dict[str, Agent]):
    """Build the boardroom-mvp orchestration as a FunctionalWorkflow.

    Args:
        agents: mapping of agent name (e.g. "founder-mvp", "cfo-mvp",
            "cmo-mvp") to a real Agent instance (e.g. built via
            FoundryChatClient.as_agent(name=...)). Must contain "founder-mvp"
            and an entry for every route in SPECIALIST_ROUTES.

    Returns:
        A FunctionalWorkflow (decorated with @workflow below) implementing
        the same founder-leads/routes-to-specialists/loops-until-complete
        pattern as the original YAML.
    """
    founder = agents["founder-mvp"]

    @workflow(name="boardroom-mvp", description="Boardroom orchestration: founder-led routing to specialists.")
    async def boardroom_mvp(user_text: str) -> str:
        purpose = "Orchestrating the Genesis of ASI"
        latest_message = f"{purpose} — {user_text}"
        turn_count = 0

        while True:
            founder_response = await founder.run(latest_message)
            founder_text = founder_response.text

            route_tag = _extract_route_tag(founder_text)
            if route_tag is not None:
                specialist_agent_name = SPECIALIST_ROUTES[route_tag]
                specialist = agents[specialist_agent_name]
                specialist_response = await specialist.run(founder_text)
                specialist_text = specialist_response.text
                latest_message = f"{founder_text} — Specialist Report: {specialist_text}"
            else:
                latest_message = founder_text

            turn_count += 1

            if COMPLETION_MARKER in latest_message.lower():
                return latest_message

            if turn_count >= MAX_TURNS:
                return "Let's try again later...I am tired."

    return boardroom_mvp
