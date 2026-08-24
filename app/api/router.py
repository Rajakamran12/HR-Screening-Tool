from __future__ import annotations

from fastapi import APIRouter

from app.api.bulk_screening_routes import router as bulk_screening_router
from app.api.candidate_routes import router as candidate_router
from app.api.job_routes import router as job_router


# ---------------------------------------------------------------------------
# Central API Router
# ---------------------------------------------------------------------------
#
# This router aggregates the application's production API routers.
#
# IMPORTANT:
#
# job_routes.py already defines:
#
#     prefix="/jobs"
#
# candidate_routes.py already defines:
#
#     prefix="/candidates"
#
# bulk_screening_routes.py already defines its production paths.
#
# Therefore this central router MUST NOT add another /jobs,
# /candidates, or /bulk-screening prefix.
#
# The central router is intentionally prefix-free.
#
# ---------------------------------------------------------------------------

router = APIRouter(
    tags=["API"],
)


# ---------------------------------------------------------------------------
# Job Routes
# ---------------------------------------------------------------------------
#
# job_routes.py already owns the /jobs prefix.
#
# Resulting endpoints:
#
#     POST   /jobs/
#     GET    /jobs/
#     GET    /jobs/status/{status}
#     GET    /jobs/{job_id}
#     GET    /jobs/{job_id}/exists
#     PATCH  /jobs/{job_id}
#     PATCH  /jobs/{job_id}/status
#     DELETE /jobs/{job_id}
#
# Do NOT supply prefix="/jobs" here.
#
# ---------------------------------------------------------------------------

router.include_router(
    job_router,
)


# ---------------------------------------------------------------------------
# Candidate Routes
# ---------------------------------------------------------------------------
#
# candidate_routes.py already owns the /candidates prefix.
#
# Resulting endpoints:
#
#     GET    /candidates
#     GET    /candidates/job/{job_id}
#     GET    /candidates/{candidate_id}
#     POST   /candidates/{candidate_id}/override
#     GET    /candidates/{candidate_id}/audit
#     POST   /candidates/screen
#     PATCH  /candidates/{candidate_id}
#     DELETE /candidates/{candidate_id}
#
# ---------------------------------------------------------------------------

router.include_router(
    candidate_router,
)


# ---------------------------------------------------------------------------
# Bulk Screening Routes
# ---------------------------------------------------------------------------
#
# bulk_screening_routes.py already owns its production paths.
#
# Resulting endpoints:
#
#     POST /bulk-screening
#     POST /bulk-screening/{job_id}
#     GET  /bulk-screening/{job_id}/status
#
# ---------------------------------------------------------------------------

router.include_router(
    bulk_screening_router,
)