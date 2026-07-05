"""Auth API blueprint — issues a session token for the shared team password.

The same token is used for both:
- our own backend routes (verified via require_auth / JWT_SECRET), and
- the CopilotKit runtime client, which is expected to send it as a
  Bearer token / `copilotkit_token` on its own requests.

NOTE: this assumes the CopilotKit runtime at cloud.businessinfinity.asisaga.com
validates tokens signed with the same JWT_SECRET. If that runtime is a
separate service with its own auth scheme, this will need to be swapped
for whatever token format it actually expects.
"""

from __future__ import annotations

import os
import time

import azure.functions as func
import jwt

from business_infinity.blueprints._helpers import json_response

auth_blueprint = func.Blueprint()

JWT_SECRET = os.environ.get("JWT_SECRET", "")
TEAM_PASSWORD = os.environ.get("TEAM_PASSWORD", "")
TOKEN_LIFETIME_SECONDS = 12 * 60 * 60  # 12 hours


@auth_blueprint.route(route="login", methods=["POST"])
def login(req: func.HttpRequest) -> func.HttpResponse:
    """Verify the team password and return a signed session token.

    The token is returned under both `token` (used by our own backend
    fetches) and `copilotkit_token` (used by the CopilotKit client), so
    the frontend can wire either or both without extra requests.
    """
    try:
        body = req.get_json()
    except ValueError:
        return json_response({"error": "Request body must be valid JSON"}, 400)

    password = body.get("password", "")
    if not password or password != TEAM_PASSWORD:
        return json_response({"error": "Invalid password"}, 401)

    name = body.get("name", "team-member")
    payload = {
        "name": name,
        "exp": int(time.time()) + TOKEN_LIFETIME_SECONDS,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    return json_response(
        {
            "token": token,
            "copilotkit_token": token,
            "expires_in": TOKEN_LIFETIME_SECONDS,
        }
    )
