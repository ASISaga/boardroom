"""Auth blueprint — issues a session token for the shared team password."""

from __future__ import annotations

import os
import time
import jwt  # pip install pyjwt
import azure.functions as func

from business_infinity.blueprints._helpers import json_response

auth_blueprint = func.Blueprint()

JWT_SECRET = os.environ["JWT_SECRET"]
TEAM_PASSWORD = os.environ["TEAM_PASSWORD"]


@auth_blueprint.route(route="login", methods=["POST"])
def login(req: func.HttpRequest) -> func.HttpResponse:
    body = req.get_json()
    if body.get("password") != TEAM_PASSWORD:
        return json_response({"error": "Invalid password"}, 401)

    payload = {"name": body.get("name", "team-member"), "exp": int(time.time()) + 12 * 3600}
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return json_response({"token": token})
