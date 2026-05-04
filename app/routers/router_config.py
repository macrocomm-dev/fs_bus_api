from app.routers.operationworkflow import operation_router
from app.routers.authentication import authentication_router


def register_routers(app):
    app.include_router(operation_router, prefix="/operation", tags=["operation"])
    app.include_router(
        authentication_router, prefix="/authentication", tags=["authentication"]
    )
