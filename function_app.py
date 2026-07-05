import azure.functions as func

from business_infinity.blueprints import (
    auth_blueprint,
    boardroom_blueprint,
    health_blueprint,
    seo_blueprint,
)
# from business_infinity.workflows import aos_app

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# Register the AOS Blueprint
# bp = aos_app.get_blueprint()
# app.register_functions(bp)

app.register_functions(auth_blueprint)
app.register_functions(boardroom_blueprint)
app.register_functions(seo_blueprint)
app.register_functions(health_blueprint)