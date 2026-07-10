"""
test_main_agui_endpoint.py — full end-to-end test of main.py's actual
create_app(), with mock agents standing in for real FoundryChatClient
agents, hitting the real mounted AG-UI endpoint via FastAPI's TestClient.

Unlike the earlier YAML-based version of this test, this one runs to full,
genuine completion — no PowerFx, no .NET runtime dependency anywhere in
this call chain.
"""

import os

os.environ.setdefault("FOUNDRY_PROJECT_ENDPOINT", "https://fake.example.com")
os.environ.setdefault("DEFAULT_MODEL_DEPLOYMENT", "fake-model")

from agent_framework import AgentResponse, Message  # noqa: E402


class MockAgent:
    def __init__(self, name: str, reply_fn):
        self.name = name
        self._reply_fn = reply_fn
        self.call_count = 0

    async def run(self, messages=None, **kwargs):
        self.call_count += 1
        reply_text = self._reply_fn(messages, self.call_count)
        return AgentResponse(
            messages=[Message(role="assistant", contents=[reply_text])],
            response_id=f"{self.name}-{self.call_count}",
        )


def test_full_agui_http_roundtrip():
    import main as main_module

    # Replace real Foundry agent construction with mocks — this test
    # verifies the HTTP/AG-UI/orchestration wiring, not live Foundry
    # connectivity (see README for what still needs real credentials).
    def fake_build_foundry_agents(credential):
        def founder_reply(msgs, call_count):
            if call_count == 1:
                return "Let's check the numbers. [ROUTE:CFO]"
            return "Great, budget looks solid. [COMPLETE]"

        return {
            "founder-mvp": MockAgent("founder-mvp", founder_reply),
            "cfo-mvp": MockAgent("cfo-mvp", lambda m, c: "Q3 runway is 14 months."),
            "cmo-mvp": MockAgent("cmo-mvp", lambda m, c: "n/a"),
        }

    main_module.build_foundry_agents = fake_build_foundry_agents

    class FakeCredential:
        def get_token(self, *a, **kw):
            class T:
                token = "fake"
                expires_on = 9999999999

            return T()

    main_module.DefaultAzureCredential = FakeCredential

    app = main_module.create_app()

    from fastapi.testclient import TestClient

    client = TestClient(app)
    response = client.post(
        "/",
        json={
            "threadId": "test-thread-1",
            "runId": "test-run-1",
            "messages": [{"id": "m1", "role": "user", "content": "How are we doing financially?"}],
            "tools": [],
            "context": [],
            "state": {},
            "forwardedProps": {},
        },
    )
    print("HTTP status:", response.status_code)
    print("Response (first 3000 chars):")
    print(response.text[:3000])

    assert response.status_code == 200
    assert "RUN_STARTED" in response.text
    assert "RUN_FINISHED" in response.text
    assert "budget looks solid" in response.text
    print("\n✅ Full HTTP -> AG-UI -> FunctionalWorkflow round trip PASSED — no PowerFx, no .NET runtime involved")


if __name__ == "__main__":
    test_full_agui_http_roundtrip()
