"""Shared helpers for Azure Function blueprint endpoints."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, Tuple

import azure.functions as func
import jwt


def json_response(payload: Dict[str, Any], status_code: int = 200) -> func.HttpResponse:
    """Create a JSON HTTP response."""
    return func.HttpResponse(
        body=json.dumps(payload),
        status_code=status_code,
        mimetype="application/json",
    )


def require_route_param(
    req: func.HttpRequest, param_name: str
) -> Tuple[Optional[str], Optional[func.HttpResponse]]:
    """Return a required route parameter value or a 400 response."""
    value = req.route_params.get(param_name)
    if not value:
        return None, json_response(
            {"error": f"{param_name} route parameter is required"}, 400
        )
    return value, None


def require_auth(
    req: func.HttpRequest,
) -> Tuple[Optional[Dict[str, Any]], Optional[func.HttpResponse]]:
    """Verify the Bearer token from the Authorization header.

    Returns the decoded token payload on success, or a 401 response on failure.
    """
    auth_header = req.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, json_response({"error": "Missing or malformed token"}, 401)

    token = auth_header.removeprefix("Bearer ")
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None, json_response({"error": "Invalid or expired token"}, 401)

    return payload, None
