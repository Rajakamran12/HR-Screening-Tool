from __future__ import annotations

import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.api.auth import get_current_user
from app.core.candidate_repository import (
    CandidateRepository,
)
from app.core.job_repository import (
    JobRepository,
    JobRepositoryError,
    get_application_job_repository,
)
from app.services.candidate_service import (
    CandidateService,
    CandidateServiceError,
)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/candidates",
    tags=["Candidates"],
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
# Request Schemas
# ---------------------------------------------------------------------------

class CandidateOverrideRequest(BaseModel):
    """
    Request body used when a recruiter manually overrides
    an AI-generated candidate category.
    """

    new_category: str = Field(
        ...,
        description=(
            "New candidate category. Allowed values: "
            "Shortlisted, Maybe, Rejected."
        ),
    )

    actor_id: str = Field(
        ...,
        description=(
            "Legacy field retained for request compatibility. "
            "The authenticated Firebase user's UID is used by "
            "the backend as the authoritative actor identity."
        ),
    )

    reason: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description=(
            "Mandatory explanation for why the human "
            "decision differs from the current category."
        ),
    )


# ---------------------------------------------------------------------------
# Shared Service Helpers
# ---------------------------------------------------------------------------

def _get_candidate_service() -> CandidateService:
    """
    Return a CandidateService using the application's repositories.

    CandidateService internally creates its AuditRepository when one
    is not explicitly supplied.
    """

    return CandidateService(
        repository=CandidateRepository(),
    )


def _get_job_repository() -> JobRepository:
    """
    Return a JobRepository instance.
    """

    return get_application_job_repository()


# ---------------------------------------------------------------------------
# Authentication Helper
# ---------------------------------------------------------------------------

def _get_authenticated_uid(
    current_user: dict[str, Any],
) -> str:
    """
    Extract and validate the authenticated Firebase user's UID.

    Authentication itself is performed by get_current_user().
    This helper guarantees that route logic receives a valid UID.
    """

    user_id = current_user.get(
        "uid"
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
# Candidate Retrieval
# ---------------------------------------------------------------------------

@router.get(
    "",
)
async def get_candidates(
    current_user: dict[str, Any] = Depends(
        get_current_user
    ),
) -> dict[str, Any]:
    """
    Return all persisted candidates.

    Authentication is required.
    """

    _get_authenticated_uid(
        current_user
    )

    service = _get_candidate_service()

    try:
        candidates = service.get_all_candidates()

    except CandidateServiceError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    return {
        "success": True,
        "count": len(candidates),
        "candidates": candidates,
    }


# ---------------------------------------------------------------------------
# Candidate Retrieval By Job
# ---------------------------------------------------------------------------

@router.get(
    "/job/{job_id}",
)
async def get_candidates_by_job(
    job_id: str,
    current_user: dict[str, Any] = Depends(
        get_current_user
    ),
) -> dict[str, Any]:
    """
    Return all candidates associated with a specific job.

    Authentication is required.
    """

    _get_authenticated_uid(
        current_user
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

    service = _get_candidate_service()

    try:
        candidates = service.get_candidates_by_job(
            normalized_job_id,
        )

    except CandidateServiceError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    return {
        "success": True,
        "job_id": normalized_job_id,
        "count": len(candidates),
        "candidates": candidates,
    }


# ---------------------------------------------------------------------------
# Human Category Override
# ---------------------------------------------------------------------------

@router.post(
    "/{candidate_id}/override",
)
async def override_candidate(
    candidate_id: str,
    request: CandidateOverrideRequest,
    current_user: dict[str, Any] = Depends(
        get_current_user
    ),
) -> dict[str, Any]:
    """
    Apply an explicit human override to a candidate's category.

    Authentication is required.

    The authenticated Firebase user's UID is used as the authoritative
    audit actor instead of trusting the actor_id supplied by the client.

    Every successful override is recorded in the audit trail.
    """

    authenticated_uid = _get_authenticated_uid(
        current_user
    )

    if not isinstance(
        candidate_id,
        str,
    ) or not candidate_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Candidate ID must be a non-empty string.",
        )

    normalized_candidate_id = candidate_id.strip()

    service = _get_candidate_service()

    try:
        candidate = service.override_candidate(
            candidate_id=normalized_candidate_id,
            new_category=request.new_category,
            actor_id=authenticated_uid,
            reason=request.reason,
        )

    except CandidateServiceError as exc:
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

        if (
            "already in the requested category"
            in lowered_message
        ):
            raise HTTPException(
                status_code=409,
                detail=message,
            ) from exc

        if (
            "must be" in lowered_message
            or "invalid" in lowered_message
            or "cannot" in lowered_message
        ):
            raise HTTPException(
                status_code=400,
                detail=message,
            ) from exc

        raise HTTPException(
            status_code=500,
            detail=message,
        ) from exc

    return {
        "success": True,
        "candidate_id": normalized_candidate_id,
        "override_applied": True,
        "candidate": candidate,
    }


# ---------------------------------------------------------------------------
# Candidate Audit History
# ---------------------------------------------------------------------------

@router.get(
    "/{candidate_id}/audit",
)
async def get_candidate_audit_history(
    candidate_id: str,
    current_user: dict[str, Any] = Depends(
        get_current_user
    ),
) -> dict[str, Any]:
    """
    Return the complete audit history for one candidate.

    Authentication is required.

    This allows the recruiter dashboard to display the history
    of human decisions made against the candidate.
    """

    _get_authenticated_uid(
        current_user
    )

    if not isinstance(
        candidate_id,
        str,
    ) or not candidate_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Candidate ID must be a non-empty string.",
        )

    normalized_candidate_id = candidate_id.strip()

    service = _get_candidate_service()

    try:
        events = service.get_candidate_audit_history(
            normalized_candidate_id,
        )

    except CandidateServiceError as exc:
        message = str(exc)

        if (
            "not found" in message.lower()
            or "does not exist" in message.lower()
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
        "candidate_id": normalized_candidate_id,
        "count": len(events),
        "audit_events": events,
    }


# ---------------------------------------------------------------------------
# Candidate Retrieval
# ---------------------------------------------------------------------------

@router.get(
    "/{candidate_id}",
)
async def get_candidate(
    candidate_id: str,
    current_user: dict[str, Any] = Depends(
        get_current_user
    ),
) -> dict[str, Any]:
    """
    Return a single persisted candidate.

    Authentication is required.
    """

    _get_authenticated_uid(
        current_user
    )

    if not isinstance(
        candidate_id,
        str,
    ) or not candidate_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Candidate ID must be a non-empty string.",
        )

    normalized_candidate_id = candidate_id.strip()

    service = _get_candidate_service()

    try:
        candidate = service.get_candidate(
            normalized_candidate_id,
        )

    except CandidateServiceError as exc:
        message = str(exc)

        if (
            "not found" in message.lower()
            or "does not exist" in message.lower()
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
        "candidate": candidate,
    }


# ---------------------------------------------------------------------------
# Candidate Upload And Screening
# ---------------------------------------------------------------------------

@router.post(
    "/screen",
)
async def screen_candidate(
    job_id: str,
    file: UploadFile = File(...),
    current_user: dict[str, Any] = Depends(
        get_current_user
    ),
) -> dict[str, Any]:
    """
    Upload and screen one CV against an existing job.

    Authentication is required.

    The CV is processed through the existing screening pipeline
    using the criteria and thresholds stored on the job.

    The resulting candidate is persisted by CandidateService.
    """

    _get_authenticated_uid(
        current_user
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

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="A CV file must be provided.",
        )

    original_filename = Path(
        file.filename,
    ).name

    extension = Path(
        original_filename,
    ).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported CV file type. "
                "Supported formats are PDF, DOCX, and TXT."
            ),
        )

    # -----------------------------------------------------------------------
    # Verify Job Exists
    # -----------------------------------------------------------------------

    job_repository = _get_job_repository()

    try:
        job = job_repository.get(
            normalized_job_id,
        )

    except JobRepositoryError as exc:
        message = str(exc)

        if (
            "not found" in message.lower()
            or "does not exist" in message.lower()
        ):
            raise HTTPException(
                status_code=404,
                detail=message,
            ) from exc

        raise HTTPException(
            status_code=500,
            detail=message,
        ) from exc

    # -----------------------------------------------------------------------
    # Read Uploaded File
    # -----------------------------------------------------------------------

    try:
        file_content = await file.read()

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to read uploaded CV: {exc}",
        ) from exc

    if not file_content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded CV is empty.",
        )

    # -----------------------------------------------------------------------
    # Validate Upload Size
    # -----------------------------------------------------------------------

    if len(file_content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=(
                "The uploaded CV exceeds the maximum allowed size "
                "of 10 MB."
            ),
        )

    candidate_id = str(
        uuid.uuid4(),
    )

    temporary_path: Path | None = None

    try:
        # -------------------------------------------------------------------
        # Create Temporary CV File
        # -------------------------------------------------------------------

        with NamedTemporaryFile(
            mode="wb",
            suffix=extension,
            delete=False,
        ) as temporary_file:

            temporary_file.write(
                file_content,
            )

            temporary_path = Path(
                temporary_file.name,
            )

        # -------------------------------------------------------------------
        # Screen And Persist Candidate
        # -------------------------------------------------------------------

        service = _get_candidate_service()

        result = await service.screen_candidate(
            candidate_id=candidate_id,
            job_id=job.job_id,
            filename=original_filename,
            cv_file=temporary_path,
            criteria=list(job.criteria),
            thresholds=job.thresholds,
        )

        return {
            "success": True,
            "candidate_id": candidate_id,
            "job_id": normalized_job_id,
            "filename": original_filename,
            "candidate": result,
        }

    except CandidateServiceError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Unexpected error while screening candidate: "
                f"{exc}"
            ),
        ) from exc

    finally:
        # -------------------------------------------------------------------
        # Remove Temporary File
        # -------------------------------------------------------------------

        if temporary_path is not None:
            try:
                temporary_path.unlink(
                    missing_ok=True,
                )

            except Exception:
                pass


# ---------------------------------------------------------------------------
# Candidate Update
# ---------------------------------------------------------------------------

@router.patch(
    "/{candidate_id}",
)
async def update_candidate(
    candidate_id: str,
    updates: dict[str, Any],
    current_user: dict[str, Any] = Depends(
        get_current_user
    ),
) -> dict[str, Any]:
    """
    Update non-category candidate fields.

    Authentication is required.

    Category changes are deliberately rejected by CandidateService.
    Recruiter category changes must use the dedicated override
    endpoint so the decision is always recorded in the audit trail.
    """

    _get_authenticated_uid(
        current_user
    )

    if not isinstance(
        candidate_id,
        str,
    ) or not candidate_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Candidate ID must be a non-empty string.",
        )

    if not isinstance(
        updates,
        dict,
    ):
        raise HTTPException(
            status_code=400,
            detail="Candidate updates must be provided as an object.",
        )

    service = _get_candidate_service()

    try:
        candidate = service.update_candidate(
            candidate_id=candidate_id.strip(),
            updates=updates,
        )

    except CandidateServiceError as exc:
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
            status_code=400,
            detail=message,
        ) from exc

    return {
        "success": True,
        "candidate": candidate,
    }


# ---------------------------------------------------------------------------
# Candidate Delete
# ---------------------------------------------------------------------------

@router.delete(
    "/{candidate_id}",
)
async def delete_candidate(
    candidate_id: str,
    current_user: dict[str, Any] = Depends(
        get_current_user
    ),
) -> dict[str, Any]:
    """
    Delete a persisted candidate.

    Authentication is required.
    """

    _get_authenticated_uid(
        current_user
    )

    if not isinstance(
        candidate_id,
        str,
    ) or not candidate_id.strip():
        raise HTTPException(
            status_code=400,
            detail="Candidate ID must be a non-empty string.",
        )

    normalized_candidate_id = candidate_id.strip()

    service = _get_candidate_service()

    try:
        service.delete_candidate(
            normalized_candidate_id,
        )

    except CandidateServiceError as exc:
        message = str(exc)

        if (
            "not found" in message.lower()
            or "does not exist" in message.lower()
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
        "candidate_id": normalized_candidate_id,
        "deleted": True,
    }