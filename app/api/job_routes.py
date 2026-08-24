from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.job_manager import (
    JobManager,
    JobManagerError,
)
from app.api.auth import get_current_user
from app.core.job_repository import get_application_job_repository
from app.schemas.job_schema import (
    JobCriterion,
    JobStatus,
    JobThresholds,
)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"],
)


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------


class CreateJobRequest(BaseModel):
    """
    Request body used to create a new job.
    """

    job_id: str = Field(
        ...,
        description="Unique identifier for the job.",
    )

    title: str = Field(
        ...,
        description="Job title.",
    )

    description: str = Field(
        ...,
        description="Job description.",
    )

    criteria: list[JobCriterion] = Field(
        ...,
        min_length=1,
        description="Weighted screening criteria.",
    )

    thresholds: JobThresholds = Field(
        ...,
        description=(
            "Deterministic candidate categorization thresholds."
        ),
    )

    created_by: str = Field(
        ...,
        description="Identifier of the recruiter who created the job.",
    )

    status: JobStatus = Field(
        default="draft",
        description=(
            "Job status. Allowed values: draft, active, closed."
        ),
    )


class UpdateJobRequest(BaseModel):
    """
    Request body used to update an existing job.

    Only supplied fields are changed.
    """

    title: str | None = Field(
        default=None,
        description="Updated job title.",
    )

    description: str | None = Field(
        default=None,
        description="Updated job description.",
    )

    criteria: list[JobCriterion] | None = Field(
        default=None,
        min_length=1,
        description="Updated screening criteria.",
    )

    thresholds: JobThresholds | None = Field(
        default=None,
        description="Updated categorization thresholds.",
    )

    created_by: str | None = Field(
        default=None,
        description="Updated recruiter identifier.",
    )

    status: JobStatus | None = Field(
        default=None,
        description=(
            "Updated job status. Allowed values: "
            "draft, active, closed."
        ),
    )


class UpdateJobStatusRequest(BaseModel):
    """
    Request body used to change only a job's status.
    """

    status: JobStatus = Field(
        ...,
        description=(
            "New job status. Allowed values: draft, active, closed."
        ),
    )


# ---------------------------------------------------------------------------
# Shared Manager
# ---------------------------------------------------------------------------


def _get_job_manager() -> JobManager:
    """
    Return the application's JobManager.

    The current JobManager uses the established repository layer.
    """

    return JobManager(
        repository=get_application_job_repository(),
    )


# ---------------------------------------------------------------------------
# Job Creation
# ---------------------------------------------------------------------------

@router.post(
    "/",
    status_code=201,
)
async def create_job(
    request: CreateJobRequest,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Create and persist a new validated job.
    """

    manager = _get_job_manager()

    try:
        job = manager.create_job(
            job_id=request.job_id,
            title=request.title,
            description=request.description,
            criteria=request.criteria,
            thresholds=request.thresholds,
            created_by=current_user["uid"],
            status=request.status,
        )

    except JobManagerError as exc:
        message = str(exc)
        lowered_message = message.lower()

        if (
            "already exists" in lowered_message
            or "already" in lowered_message
        ):
            raise HTTPException(
                status_code=409,
                detail=message,
            ) from exc

        raise HTTPException(
            status_code=400,
            detail=message,
        ) from exc

    return {
        "success": True,
        "job": job.model_dump(
            mode="json"
        ),
    }


# ---------------------------------------------------------------------------
# Job Retrieval
# ---------------------------------------------------------------------------

@router.get(
    "/",
)
async def get_jobs() -> dict[str, Any]:
    """
    Return all jobs.
    """

    manager = _get_job_manager()

    try:
        jobs = manager.get_all_jobs()

    except JobManagerError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    return {
        "success": True,
        "count": len(jobs),
        "jobs": [
            job.model_dump(
                mode="json"
            )
            for job in jobs
        ],
    }


# ---------------------------------------------------------------------------
# Jobs By Status
# ---------------------------------------------------------------------------

@router.get(
    "/status/{status}",
)
async def get_jobs_by_status(
    status: JobStatus,
) -> dict[str, Any]:
    """
    Return all jobs having the requested status.
    """

    manager = _get_job_manager()

    try:
        jobs = manager.get_jobs_by_status(
            status
        )

    except JobManagerError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "success": True,
        "status": status,
        "count": len(jobs),
        "jobs": [
            job.model_dump(
                mode="json"
            )
            for job in jobs
        ],
    }


# ---------------------------------------------------------------------------
# Job Retrieval
# ---------------------------------------------------------------------------

@router.get(
    "/{job_id}",
)
async def get_job(
    job_id: str,
) -> dict[str, Any]:
    """
    Return one job by ID.
    """

    if not isinstance(
        job_id,
        str,
    ) or not job_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Job ID must be a non-empty string.",
        )

    normalized_job_id = job_id.strip()

    manager = _get_job_manager()

    try:
        job = manager.get_job(
            normalized_job_id
        )

    except JobManagerError as exc:
        message = str(exc)
        lowered_message = message.lower()

        if (
            "does not exist" in lowered_message
            or "not found" in lowered_message
        ):
            raise HTTPException(
                status_code=404,
                detail=message,
            ) from exc

        raise HTTPException(
            status_code=500,
            detail=message,
        ) from exc

    return {
        "success": True,
        "job": job.model_dump(
            mode="json"
        ),
    }


# ---------------------------------------------------------------------------
# Job Existence
# ---------------------------------------------------------------------------

@router.get(
    "/{job_id}/exists",
)
async def job_exists(
    job_id: str,
) -> dict[str, Any]:
    """
    Check whether a job exists.
    """

    if not isinstance(
        job_id,
        str,
    ) or not job_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Job ID must be a non-empty string.",
        )

    normalized_job_id = job_id.strip()

    manager = _get_job_manager()

    try:
        exists = manager.job_exists(
            normalized_job_id
        )

    except JobManagerError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "success": True,
        "job_id": normalized_job_id,
        "exists": exists,
    }


# ---------------------------------------------------------------------------
# Job Update
# ---------------------------------------------------------------------------

@router.patch(
    "/{job_id}",
)
async def update_job(
    job_id: str,
    request: UpdateJobRequest,
) -> dict[str, Any]:
    """
    Update supplied fields of an existing job.
    """

    if not isinstance(
        job_id,
        str,
    ) or not job_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Job ID must be a non-empty string.",
        )

    normalized_job_id = job_id.strip()

    manager = _get_job_manager()

    try:
        job = manager.update_job(
            normalized_job_id,
            title=request.title,
            description=request.description,
            criteria=request.criteria,
            thresholds=request.thresholds,
            created_by=request.created_by,
            status=request.status,
        )

    except JobManagerError as exc:
        message = str(exc)
        lowered_message = message.lower()

        if (
            "does not exist" in lowered_message
            or "not found" in lowered_message
        ):
            raise HTTPException(
                status_code=404,
                detail=message,
            ) from exc

        raise HTTPException(
            status_code=400,
            detail=message,
        ) from exc

    return {
        "success": True,
        "job": job.model_dump(
            mode="json"
        ),
    }


# ---------------------------------------------------------------------------
# Job Status
# ---------------------------------------------------------------------------

@router.patch(
    "/{job_id}/status",
)
async def update_job_status(
    job_id: str,
    request: UpdateJobStatusRequest,
) -> dict[str, Any]:
    """
    Change the status of an existing job.
    """

    if not isinstance(
        job_id,
        str,
    ) or not job_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Job ID must be a non-empty string.",
        )

    normalized_job_id = job_id.strip()

    manager = _get_job_manager()

    try:
        job = manager.set_status(
            normalized_job_id,
            request.status,
        )

    except JobManagerError as exc:
        message = str(exc)
        lowered_message = message.lower()

        if (
            "does not exist" in lowered_message
            or "not found" in lowered_message
        ):
            raise HTTPException(
                status_code=404,
                detail=message,
            ) from exc

        raise HTTPException(
            status_code=400,
            detail=message,
        ) from exc

    return {
        "success": True,
        "job": job.model_dump(
            mode="json"
        ),
    }


# ---------------------------------------------------------------------------
# Job Delete
# ---------------------------------------------------------------------------

@router.delete(
    "/{job_id}",
)
async def delete_job(
    job_id: str,
) -> dict[str, Any]:
    """
    Delete an existing job.
    """

    if not isinstance(
        job_id,
        str,
    ) or not job_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Job ID must be a non-empty string.",
        )

    normalized_job_id = job_id.strip()

    manager = _get_job_manager()

    try:
        deleted_job = manager.delete_job(
            normalized_job_id
        )

    except JobManagerError as exc:
        message = str(exc)
        lowered_message = message.lower()

        if (
            "does not exist" in lowered_message
            or "not found" in lowered_message
        ):
            raise HTTPException(
                status_code=404,
                detail=message,
            ) from exc

        raise HTTPException(
            status_code=500,
            detail=message,
        ) from exc

    return {
        "success": True,
        "job_id": normalized_job_id,
        "deleted": True,
        "job": deleted_job.model_dump(
            mode="json"
        ),
    }