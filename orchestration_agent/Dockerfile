# Foundry Hosted Agent container for boardroom-mvp.
#
# No .NET runtime needed. An earlier version of this project used
# agent_framework_declarative (PowerFx-based YAML workflows), which
# requires a real coreclr runtime. This version replaces that entirely
# with native Python orchestration (see boardroom_orchestration.py, using
# agent_framework's @workflow/@step functional API) — verified to have
# zero PowerFx/.NET dependency, and tested to run to full completion in a
# plain Python environment (see test_boardroom_orchestration.py and
# test_main_agui_endpoint.py).

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py boardroom_orchestration.py ./

# Foundry Hosted Agents inject configuration via environment variables at
# runtime — see main.py's os.environ reads for the exact variable names:
#   FOUNDRY_PROJECT_ENDPOINT, DEFAULT_MODEL_DEPLOYMENT,
#   FOUNDER_MODEL_DEPLOYMENT (optional), CFO_MODEL_DEPLOYMENT (optional),
#   CMO_MODEL_DEPLOYMENT (optional), AG_UI_ALLOW_ORIGINS (optional),
#   PORT (optional, default 8000)
# Do not hardcode these here.

CMD ["python", "main.py"]
