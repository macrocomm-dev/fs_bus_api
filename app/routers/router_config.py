from app.routers.operationworkflow import operation_router


def register_routers(app):
    app.include_router(operation_router, prefix="/operation", tags=["operation"])
