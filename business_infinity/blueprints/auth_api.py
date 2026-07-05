"""Auth API blueprint — issues a session token for the shared team password."""

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
    """Verify the team password and return a signed session token."""
    try:
        body = req.get_json()
    except ValueError:
        return json_response({"error": "Request body must be valid JSON"}, 400)

    password = body.get("password", "")
    if not password or password != TEAM_PASSWORD:
        return json_response({"error": "Invalid password"}, 401)

    payload = {
        "name": body.get("name", "team-member"),
        "exp": int(time.time()) + TOKEN_LIFETIME_SECONDS,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    return json_response({"token": token, "expires_in": TOKEN_LIFETIME_SECONDS})
