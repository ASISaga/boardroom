"""SEO API blueprint — taxonomy summary and category endpoints."""

from __future__ import annotations

import azure.functions as func

from business_infinity.blueprints._helpers import json_response, require_route_param
from business_infinity.seo import PainTaxonomy

seo_blueprint = func.Blueprint()


@seo_blueprint.route(route="seo/summary", methods=["GET"])
def seo_summary(req: func.HttpRequest) -> func.HttpResponse:
    """Return SEO taxonomy summary metrics."""
    return json_response(
        {
            "total_queries": PainTaxonomy.total_query_count(),
        }
    )


@seo_blueprint.route(route="seo/categories/{slug}", methods=["GET"])
def seo_category_details(req: func.HttpRequest) -> func.HttpResponse:
    """Return a single SEO taxonomy category by slug."""
    slug, error_response = require_route_param(req, "slug")
    if error_response:
        return error_response

    try:
        category = PainTaxonomy.get_by_slug(slug)
    except KeyError:
        return json_response({"error": f"Unknown category slug '{slug}'"}, 404)

    return json_response(
        {
            "slug": slug,
            "category": category,
        }
    )
