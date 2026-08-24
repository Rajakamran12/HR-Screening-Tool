from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile

from app.api.auth import get_current_user
from app.services.bulk_screening_service import (
    BulkScreeningService,
    BulkScreeningServiceError,
)
from app.core.job_repository import get_application_job_repository


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/bulk-screening",
    tags=["Bulk Screening"],
)


# ---------------------------------------------------------------------------
# Application Limits
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
}

MAX_UPLOAD_SIZE = 10 * 1024 * 1024


# ---------------------------------------------------------------------------
# Shared Service Helper
# ---------------------------------------------------------------------------

def _get_bulk_screening_service() -> BulkScreeningService:
    """
    Return the application's bulk screening service.

    The service owns the actual bulk processing workflow. The API layer
    is responsible only for authentication, request validation, and
    HTTP response mapping.
    """

    return BulkScreeningService(
        job_repository=get_application_job_repository(),
        max_concurrency=1,
    )


# ---------------------------------------------------------------------------
# Authentication Helper
# ---------------------------------------------------------------------------

def _get_authenticated_uid(
    current_user: dict[str, Any],
) -> str:
    """
    Extract and validate the authenticated Firebase user's UID.

    Authentication itself is performed by get_current_user().
    """

    user_id = current_user.get(
        "uid",
    )

    if not isinstance(
        user_id,
        str,
    ) or not user_id.strip():
        raise HTTPException(
            status_code=401,
            detail="Authenticated user does not have a valid user ID.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    return user_id.strip()


# ---------------------------------------------------------------------------
# POST /bulk-screening
# ---------------------------------------------------------------------------

@router.post(
    "",
)
async def bulk_screen_candidates(
    job_id: str,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    current_user: dict[str, Any] = Depends(
        get_current_user,
    ),
) -> dict[str, Any]:
    """
    Upload and screen multiple CVs against an existing job.

    Authentication is required.

    Each uploaded CV is passed to the existing bulk screening service.
    The service is responsible for processing, screening, persistence,
    and result aggregation.
    """

    authenticated_uid = _get_authenticated_uid(
        current_user,
    )

    if not isinstance(
        job_id,
        str,
    ) or not job_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Job ID must be a non-empty string.",
        )

    normalized_job_id = job_id.strip()

    if not files:
        raise HTTPException(
            status_code=400,
            detail="At least one CV file must be provided.",
        )

    prepared_files: list[dict[str, Any]] = []

    for file in files:
        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="Every uploaded CV must have a filename.",
            )

        filename = file.filename

        extension = (
            filename.rsplit(
                ".",
                1,
            )[-1].lower()
            if "." in filename
            else ""
        )

        normalized_extension = (
            f".{extension}"
            if extension
            else ""
        )

        if normalized_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported CV file type for '{filename}'. "
                    "Supported formats are PDF, DOCX, and TXT."
                ),
            )

        try:
            content = await file.read()

        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unable to read uploaded CV '{filename}': "
                    f"{exc}"
                ),
            ) from exc

        if not content:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"The uploaded CV '{filename}' is empty."
                ),
            )

        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"The uploaded CV '{filename}' exceeds the "
                    "maximum allowed size of 10 MB."
                ),
            )

        prepared_files.append(
            {
                "filename": filename,
                "content": content,
                "extension": normalized_extension,
            }
        )

    service = _get_bulk_screening_service()
    batch_id = str(uuid.uuid4())
    service._status_store[batch_id] = {
        "batch_id": batch_id,
        "job_id": normalized_job_id,
        "status": "processing",
        "total": len(prepared_files),
        "processed": 0,
        "successful": 0,
        "failed": 0,
        "started_at": service._utc_now(),
        "completed_at": None,
    }

    async def process_batch() -> None:
        try:
            await service.screen_candidates(
                job_id=normalized_job_id,
                files=prepared_files,
                actor_id=authenticated_uid,
                batch_id=batch_id,
            )
        except Exception as exc:
            service._status_store[batch_id].update({
                "status": "failed",
                "error": str(exc),
                "completed_at": service._utc_now(),
            })

    background_tasks.add_task(process_batch)

    return {
        "success": True,
        "job_id": normalized_job_id,
        "uploaded_count": len(prepared_files),
        "result": {
            "batch_id": batch_id,
            "job_id": normalized_job_id,
            "status": "processing",
            "total": len(prepared_files),
            "processed": 0,
            "successful": 0,
            "failed": 0,
        },
    }


# ---------------------------------------------------------------------------
# POST /bulk-screening/{job_id}
# ---------------------------------------------------------------------------

@router.post(
    "/{job_id}",
)
async def bulk_screen_candidates_for_job(
    job_id: str,
    files: list[UploadFile] = File(...),
    current_user: dict[str, Any] = Depends(
        get_current_user,
    ),
) -> dict[str, Any]:
    """
    Convenience endpoint for bulk screening where the job ID is part
    of the URL rather than a query parameter.

    This delegates to the same bulk screening implementation used by
    the primary endpoint.
    """

    authenticated_uid = _get_authenticated_uid(
        current_user,
    )

    if not isinstance(
        job_id,
        str,
    ) or not job_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Job ID must be a non-empty string.",
        )

    normalized_job_id = job_id.strip()

    if not files:
        raise HTTPException(
            status_code=400,
            detail="At least one CV file must be provided.",
        )

    prepared_files: list[dict[str, Any]] = []

    for file in files:
        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="Every uploaded CV must have a filename.",
            )

        filename = file.filename

        extension = (
            filename.rsplit(
                ".",
                1,
            )[-1].lower()
            if "." in filename
            else ""
        )

        normalized_extension = (
            f".{extension}"
            if extension
            else ""
        )

        if normalized_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported CV file type for '{filename}'. "
                    "Supported formats are PDF, DOCX, and TXT."
                ),
            )

        try:
            content = await file.read()

        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unable to read uploaded CV '{filename}': "
                    f"{exc}"
                ),
            ) from exc

        if not content:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"The uploaded CV '{filename}' is empty."
                ),
            )

        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"The uploaded CV '{filename}' exceeds the "
                    "maximum allowed size of 10 MB."
                ),
            )

        prepared_files.append(
            {
                "filename": filename,
                "content": content,
                "extension": normalized_extension,
            }
        )

    service = _get_bulk_screening_service()

    try:
        result = await service.screen_candidates(
            job_id=normalized_job_id,
            files=prepared_files,
            actor_id=authenticated_uid,
        )

    except BulkScreeningServiceError as exc:
        message = str(exc)
        lowered_message = message.lower()

        if (
            "job" in lowered_message
            and (
                "not found" in lowered_message
                or "does not exist" in lowered_message
            )
        ):
            raise HTTPException(
                status_code=404,
                detail=message,
            ) from exc

        if (
            "invalid" in lowered_message
            or "must be" in lowered_message
            or "required" in lowered_message
        ):
            raise HTTPException(
                status_code=400,
                detail=message,
            ) from exc

        raise HTTPException(
            status_code=422,
            detail=message,
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Unexpected error while processing bulk screening: "
                f"{exc}"
            ),
        ) from exc

    return {
        "success": True,
        "job_id": normalized_job_id,
        "uploaded_count": len(prepared_files),
        "result": result,
    }


# ---------------------------------------------------------------------------
# GET /bulk-screening/{job_id}/status
# ---------------------------------------------------------------------------

@router.get(
    "/{job_id}/status",
)
async def get_bulk_screening_status(
    job_id: str,
    current_user: dict[str, Any] = Depends(
        get_current_user,
    ),
) -> dict[str, Any]:
    """
    Return the current bulk screening status for a job.

    Authentication is required.
    """

    _get_authenticated_uid(
        current_user,
    )

    if not isinstance(
        job_id,
        str,
    ) or not job_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Job ID must be a non-empty string.",
        )

    normalized_job_id = job_id.strip()

    service = _get_bulk_screening_service()

    try:
        status = service.get_status(
            normalized_job_id,
        )

    except BulkScreeningServiceError as exc:
        message = str(exc)
        lowered_message = message.lower()

        if (
            "not found" in lowered_message
            or "does not exist" in lowered_message
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
        "status": status,
    }


@router.get(
    "/status/{batch_id}",
)
async def get_bulk_screening_batch_status(
    batch_id: str,
    current_user: dict[str, Any] = Depends(
        get_current_user,
    ),
) -> dict[str, Any]:
    """Return progress for one exact bulk screening batch."""

    _get_authenticated_uid(current_user)

    try:
        batch_status = BulkScreeningService.get_status_by_batch(
            batch_id,
        )
    except BulkScreeningServiceError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    return {
        "success": True,
        "batch_id": batch_id,
        "status": batch_status,
    }