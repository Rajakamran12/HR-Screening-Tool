from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.api.auth import get_current_user
from app.api.bulk_screening_routes import (
    router as bulk_screening_router,
)
from app.api.candidate_routes import (
    router as candidate_router,
)
from app.api.job_routes import (
    router as job_router,
)
from app.pipeline.screening_pipeline import (
    ScreeningPipeline,
    ScreeningPipelineError,
)
from app.schemas.job_schema import (
    JobCriterion,
    JobThresholds,
)
from app.core.config import FIREBASE_WEB_CONFIG


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="HR Screening Tool API",
    description=(
        "AI-assisted HR screening API for evidence-grounded candidate "
        "evaluation, deterministic categorization, human review, "
        "and auditable recruiter decisions."
    ),
    version="1.0.0",
)

FRONTEND_PATH = Path(__file__).resolve().parents[2] / "frontend" / "dashboard.html"


# ---------------------------------------------------------------------------
# Production API Routers
# ---------------------------------------------------------------------------
#
# Production recruiter endpoints require Firebase authentication.
#
# Authentication is attached at router-registration level rather than
# application level so that the following public endpoints remain public:
#
#     /
#     /health
#     /docs
#     /openapi.json
#     /screen
#
# The authentication dependency is the existing get_current_user()
# dependency. FastAPI dependency overrides used by the test suite therefore
# continue to work normally.
#
# Authentication is evaluated before the actual route handler, which means
# unauthenticated requests receive HTTP 401 before business validation,
# request-body validation, or service execution.
#
# ---------------------------------------------------------------------------

app.include_router(
    job_router,
    dependencies=[
        Depends(get_current_user),
    ],
)

app.include_router(
    candidate_router,
    dependencies=[
        Depends(get_current_user),
    ],
)

app.include_router(
    bulk_screening_router,
    dependencies=[
        Depends(get_current_user),
    ],
)


# ---------------------------------------------------------------------------
# Legacy Step 0 Screening Criteria
# ---------------------------------------------------------------------------
#
# These criteria are retained only for the original /screen endpoint.
#
# Production candidate screening uses persisted jobs and their configured
# criteria through the candidate API.
#
# ---------------------------------------------------------------------------

SCREENING_CRITERIA = [
    JobCriterion(
        name="Python Development",
        description=(
            "Professional experience developing software using Python, "
            "with evidence of practical implementation rather than only "
            "listing Python as a skill."
        ),
        required=True,
        weight=40.0,
        minimum_years=2.0,
    ),
    JobCriterion(
        name="Machine Learning",
        description=(
            "Practical experience applying machine learning techniques "
            "in professional, academic, research, or project work, "
            "with evidence of actual implementation."
        ),
        required=True,
        weight=35.0,
        minimum_years=1.0,
    ),
    JobCriterion(
        name="SQL and Database Experience",
        description=(
            "Practical experience working with SQL or relational "
            "databases, including evidence of actual database usage."
        ),
        required=False,
        weight=25.0,
        minimum_years=1.0,
    ),
]


# ---------------------------------------------------------------------------
# Legacy Step 0 Categorization Thresholds
# ---------------------------------------------------------------------------

SCREENING_THRESHOLDS = JobThresholds(
    shortlisted=80.0,
    maybe=60.0,
)


# ---------------------------------------------------------------------------
# Legacy Upload Configuration
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS = {
    ".pdf",
}

MAX_UPLOAD_SIZE = 10 * 1024 * 1024


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    tags=["System"],
)
async def health_check() -> dict[str, str]:
    """
    Confirm that the API is running.
    """

    return {
        "status": "healthy",
        "service": "hr-screening-tool",
    }


# ---------------------------------------------------------------------------
# Root Endpoint
# ---------------------------------------------------------------------------

@app.get(
    "/",
    tags=["System"],
)
async def root() -> dict[str, str]:
    """
    Return basic API information.
    """

    return {
        "name": "HR Screening Tool API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
    }


@app.get(
    "/ui",
    include_in_schema=False,
)
async def recruiter_dashboard() -> FileResponse:
    """Serve the recruiter dashboard."""

    return FileResponse(FRONTEND_PATH)


@app.get(
    "/ui-config",
    include_in_schema=False,
)
async def ui_config() -> dict[str, object]:
    """Return public Firebase Web SDK configuration only."""

    return {
        "firebase": FIREBASE_WEB_CONFIG,
    }


# ---------------------------------------------------------------------------
# Legacy Single-CV Screening Endpoint
# ---------------------------------------------------------------------------

@app.post(
    "/screen",
    tags=["Screening"],
)
async def screen_cv(
    file: UploadFile = File(...),
) -> JSONResponse:
    """
    Legacy single-CV screening endpoint.

    This endpoint remains available for the original Step 0 workflow
    and existing tests.

    Production job-based screening should use the candidate routes,
    where the candidate is associated with a persisted job and its
    configured criteria and thresholds.
    """

    # -----------------------------------------------------------------------
    # Validate filename
    # -----------------------------------------------------------------------

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="A CV file must be provided.",
        )

    original_filename = Path(
        file.filename
    ).name

    extension = Path(
        original_filename
    ).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                "Unsupported file type. "
                "Only PDF CV files are currently supported "
                "by the legacy /screen endpoint."
            ),
        )

    # -----------------------------------------------------------------------
    # Read uploaded file
    # -----------------------------------------------------------------------

    try:
        file_content = await file.read()

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to read uploaded CV: {exc}",
        ) from exc

    # -----------------------------------------------------------------------
    # Validate file content
    # -----------------------------------------------------------------------

    if not file_content:
        raise HTTPException(
            status_code=400,
            detail="The uploaded CV is empty.",
        )

    # -----------------------------------------------------------------------
    # Validate file size
    # -----------------------------------------------------------------------

    if len(file_content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=(
                "The uploaded CV exceeds the maximum allowed size "
                "of 10 MB."
            ),
        )

    # -----------------------------------------------------------------------
    # Create temporary CV file
    # -----------------------------------------------------------------------

    temporary_path: Path | None = None

    try:
        with NamedTemporaryFile(
            mode="wb",
            suffix=".pdf",
            delete=False,
        ) as temporary_file:

            temporary_file.write(
                file_content
            )

            temporary_path = Path(
                temporary_file.name
            )

        # -------------------------------------------------------------------
        # Initialize screening pipeline
        # -------------------------------------------------------------------

        pipeline = ScreeningPipeline()

        # -------------------------------------------------------------------
        # Execute parse -> extract -> score -> categorize pipeline
        # -------------------------------------------------------------------

        result = await pipeline.screen(
            cv_file=temporary_path,
            criteria=SCREENING_CRITERIA,
            thresholds=SCREENING_THRESHOLDS,
        )

        # -------------------------------------------------------------------
        # Return complete screening result
        # -------------------------------------------------------------------

        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "filename": original_filename,
                "result": result.model_dump(),
            },
        )

    except ScreeningPipelineError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "An unexpected error occurred while screening "
                f"the CV: {exc}"
            ),
        ) from exc

    finally:
        # -------------------------------------------------------------------
        # Remove temporary file
        # -------------------------------------------------------------------

        if temporary_path is not None:
            try:
                temporary_path.unlink(
                    missing_ok=True
                )

            except Exception:
                pass