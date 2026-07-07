"""Health check blueprint — liveness probe for the Azure Functions host."""

from __future__ import annotations

import azure.functions as func

health_blueprint = func.Blueprint()


@health_blueprint.route(route="ping", methods=["GET"])
def ping(req: func.HttpRequest) -> func.HttpResponse:
    """Lightweight liveness probe confirming the host is active."""
    return func.HttpResponse("BusinessInfinity Host Active", status_code=200)
