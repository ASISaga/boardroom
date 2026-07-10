"""
test_boardroom_orchestration.py — tests boardroom_orchestration.py's
FunctionalWorkflow-based routing logic with mock agents. No PowerFx, no
.NET runtime needed anywhere in this test — genuinely runs to full
completion in a plain Python environment.
"""

import asyncio

from agent_framework import AgentResponse, Message
from boardroom_orchestration import build_boardroom_workflow


class MockAgent:
    """Minimal Agent-compatible mock — only implements what
    boardroom_orchestration.py actually calls: run(text) -> AgentResponse
    with a .text property."""

    def __init__(self, name: str, reply_fn):
        self.name = name
        self._reply_fn = reply_fn
        self.call_count = 0
        self.last_input = None

    async def run(self, messages=None, **kwargs):
        self.call_count += 1
        self.last_input = messages
        reply_text = self._reply_fn(messages, self.call_count)
        return AgentResponse(messages=[Message(role="assistant", contents=[reply_text])], response_id=f"{self.name}-{self.call_count}")


async def test_routes_to_cfo_then_completes():
    def founder_reply(input_text, call_count):
        if call_count == 1:
            return "Let's check the numbers. [ROUTE:CFO]"
        return "Great, budget looks solid. [COMPLETE]"

    def cfo_reply(input_text, call_count):
        return "Q3 runway is 14 months at current burn."

    def cmo_reply(input_text, call_count):
        raise AssertionError("cmo-mvp should not be called in this test")

    agents = {
        "founder-mvp": MockAgent("founder-mvp", founder_reply),
        "cfo-mvp": MockAgent("cfo-mvp", cfo_reply),
        "cmo-mvp": MockAgent("cmo-mvp", cmo_reply),
    }

    workflow = build_boardroom_workflow(agents)
    result = await workflow.run("How are we doing financially?")
    outputs = result.get_outputs()

    print("Outputs:", outputs)
    assert len(outputs) == 1
    final_text = outputs[0]
    assert "budget looks solid" in final_text
    # NOTE: matches the original YAML's own behavior — the CFO's report is
    # folded into `latest_message` as CONTEXT for the founder's next call
    # (visible via founder's second call's input, asserted below), but the
    # founder's own reply text is what the workflow ultimately returns, not
    # a concatenation of the specialist's raw text. This mirrors the YAML's
    # extract_founder_text step, which overwrites Local.LatestMessage with
    # only the founder's own text after each of its turns.
    assert "Q3 runway is 14 months" in agents["founder-mvp"].last_input
    assert agents["founder-mvp"].call_count == 2
    assert agents["cfo-mvp"].call_count == 1
    assert agents["cmo-mvp"].call_count == 0
    print("✅ test_routes_to_cfo_then_completes PASSED")


async def test_routes_to_cmo():
    def founder_reply(input_text, call_count):
        if call_count == 1:
            return "Let's look at brand health. [ROUTE:CMO]"
        return "Marketing is on track. [COMPLETE]"

    def cmo_reply(input_text, call_count):
        return "Brand awareness up 12% this quarter."

    agents = {
        "founder-mvp": MockAgent("founder-mvp", founder_reply),
        "cfo-mvp": MockAgent("cfo-mvp", lambda i, c: (_ for _ in ()).throw(AssertionError("cfo-mvp should not be called"))),
        "cmo-mvp": MockAgent("cmo-mvp", cmo_reply),
    }

    workflow = build_boardroom_workflow(agents)
    result = await workflow.run("How's marketing?")
    outputs = result.get_outputs()

    assert "Marketing is on track" in outputs[0]
    assert "Brand awareness up 12%" in agents["founder-mvp"].last_input
    assert agents["cmo-mvp"].call_count == 1
    print("✅ test_routes_to_cmo PASSED")


async def test_turn_limit_exceeded():
    """Founder never says [COMPLETE] and never routes — should exit
    after MAX_TURNS with the 'tired' message, not loop forever."""

    def founder_reply(input_text, call_count):
        return f"Still thinking... (turn {call_count})"

    agents = {
        "founder-mvp": MockAgent("founder-mvp", founder_reply),
        "cfo-mvp": MockAgent("cfo-mvp", lambda i, c: "n/a"),
        "cmo-mvp": MockAgent("cmo-mvp", lambda i, c: "n/a"),
    }

    workflow = build_boardroom_workflow(agents)
    result = await workflow.run("Let's talk strategy")
    outputs = result.get_outputs()

    print("Outputs:", outputs)
    assert "tired" in outputs[0].lower()
    assert agents["founder-mvp"].call_count == 6  # MAX_TURNS
    print("✅ test_turn_limit_exceeded PASSED")


async def test_no_routing_still_completes():
    """Founder answers directly with [COMPLETE] on the very first turn,
    with no specialist routing at all — simplest possible path."""

    def founder_reply(input_text, call_count):
        return "This is a simple question, no specialist needed. [COMPLETE]"

    agents = {
        "founder-mvp": MockAgent("founder-mvp", founder_reply),
        "cfo-mvp": MockAgent("cfo-mvp", lambda i, c: "n/a"),
        "cmo-mvp": MockAgent("cmo-mvp", lambda i, c: "n/a"),
    }

    workflow = build_boardroom_workflow(agents)
    result = await workflow.run("What's the company name?")
    outputs = result.get_outputs()

    assert agents["founder-mvp"].call_count == 1
    assert agents["cfo-mvp"].call_count == 0
    assert agents["cmo-mvp"].call_count == 0
    print("✅ test_no_routing_still_completes PASSED")


async def main():
    await test_routes_to_cfo_then_completes()
    await test_routes_to_cmo()
    await test_turn_limit_exceeded()
    await test_no_routing_still_completes()
    print("\n🎉 ALL TESTS PASSED — pure Python, no PowerFx, no .NET runtime")


if __name__ == "__main__":
    asyncio.run(main())
