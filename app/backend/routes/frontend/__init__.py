from fastapi import APIRouter

from app.backend.routes.frontend.dashboard import router as dashboard_router
from app.backend.routes.frontend.deliverables import router as deliverables_router
from app.backend.routes.frontend.marketing import router as marketing_router
from app.backend.routes.frontend.programme import router as programme_router
from app.backend.routes.frontend.programme_activities import (
    router as programme_activities_router,
)
from app.backend.routes.frontend.projects import router as projects_router
from app.backend.routes.frontend.work_packages import (
    router as work_packages_router,
)

router = APIRouter(
    include_in_schema=False,
)

router.include_router(marketing_router)
router.include_router(dashboard_router)
router.include_router(projects_router)
router.include_router(work_packages_router)
router.include_router(deliverables_router)
router.include_router(programme_router)
router.include_router(programme_activities_router)
