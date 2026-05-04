from app.routers.operationworkflow import operation_router
from app.routers.authentication import authentication_router
from app.routers.vehicle import vehicle_router
from app.routers.image import image_router
from app.routers.inspection import inspection_router


def register_routers(app):
    app.include_router(operation_router, prefix="/operation", tags=["operation"])

    app.include_router(vehicle_router, prefix="/vehicle", tags=["vehicle"])
    app.include_router(image_router, prefix="/image", tags=["image"])
    app.include_router(inspection_router, prefix="/inspection", tags=["inspection"])
    app.include_router(
        authentication_router, prefix="/authentication", tags=["authentication"]
    )
