from app.routers.operationworkflow import operation_router
from app.routers.vehicle import vehicle_router
from app.routers.image import image_router
from app.routers.inspection import inspection_router
from app.routers.monitors import monitor_router


def register_routers(app):
    """Attach all feature routers to the shared FastAPI application instance."""
    app.include_router(
        operation_router,
        prefix="/operation",
        tags=["operation"],
        include_in_schema=False,
    )

    app.include_router(vehicle_router, prefix="/vehicle", tags=["vehicle"])
    app.include_router(monitor_router, prefix="/shift", tags=["shifts"])
    app.include_router(image_router, prefix="/image", tags=["image"])
    app.include_router(inspection_router, prefix="/inspection", tags=["inspection"])
