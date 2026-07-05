"""Boardroom API blueprint — workflow listing, details, and chat endpoints."""

from __future__ import annotations

import os

import azure.functions as func
import requests
from azure.identity import ClientSecretCredential, ManagedIdentityCredential

from business_infinity.boardroom import WorkflowRegistryManager
from business_infinity.blueprints._helpers import (
    json_response,
    require_auth,
    require_route_param,
)

boardroom_blueprint = func.Blueprint()

AGENT_ENDPOINT = os.environ.get("AGENT_ENDPOINT", "")
AZURE_TENANT_ID = os.environ.get("AZURE_TENANT_ID", "")
AZURE_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID", "")


def _get_credential():
    """Prefer Managed Identity; fall back to a client secret for local dev."""
    client_secret = os.environ.get("AZURE_CLIENT_SECRET")
    if client_secret:
        return ClientSecretCredential(AZURE_TENANT_ID, AZURE_CLIENT_ID, client_secret)
    return ManagedIdentityCredential(client_id=AZURE_CLIENT_ID)


@boardroom_blueprint.route(route="boardroom/workflows", methods=["GET"])
def boardroom_workflows(_req: func.HttpRequest) -> func.HttpResponse:
    """Return all registered boardroom workflows."""
    workflows = WorkflowRegistryManager.list_all()
    return json_response(
        {
            "count": len(workflows),
            "workflows": workflows,
        }
    )


@boardroom_blueprint.route(route="boardroom/workflows/{workflow_id}", methods=["GET"])
def boardroom_workflow_details(req: func.HttpRequest) -> func.HttpResponse:
    """Return metadata and step IDs for a single workflow."""
    workflow_id, error_response = require_route_param(req, "workflow_id")
    if error_response:
        return error_response

    try:
        metadata = WorkflowRegistryManager.get_metadata(workflow_id)
    except KeyError:
        return json_response({"error": f"Unknown workflow_id '{workflow_id}'"}, 404)

    try:
        step_ids = WorkflowRegistryManager.get_step_ids(workflow_id)
    except NotImplementedError:
        step_ids = []

    return json_response(
        {
            "workflow_id": workflow_id,
            "metadata": metadata,
            "step_ids": step_ids,
        }
    )


@boardroom_blueprint.route(route="boardroom/chat", methods=["POST"])
def boardroom_chat(req: func.HttpRequest) -> func.HttpResponse:
    """Forward a chat message to the Azure AI Foundry boardroom-mvp agent."""
    _user, auth_error = require_auth(req)
    if auth_error:
        return auth_error

    try:
        body = req.get_json()
    except ValueError:
        return json_response({"error": "Request body must be valid JSON"}, 400)

    credential = _get_credential()
    token = credential.get_token("https://ai.azure.com/.default").token

    try:
        upstream = requests.post(
            AGENT_ENDPOINT,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=30,
        )
    except requests.RequestException as exc:
        return json_response({"error": f"Agent request failed: {exc}"}, 502)

    try:
        upstream_body = upstream.json()
    except ValueError:
        upstream_body = {"raw": upstream.text}

    return json_response(upstream_body, upstream.status_code)
