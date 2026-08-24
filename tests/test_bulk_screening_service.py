from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.services.bulk_screening_service import (
    BulkScreeningService,
    BulkScreeningServiceError,
)
from app.services.candidate_service import CandidateService, CandidateService, CandidateServiceError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def candidate_result(
    candidate_id: str = "candidate-001",
) -> dict:
    """
    Build a representative candidate screening result.
    """

    return {
        "candidate_id": candidate_id,
        "category": "shortlisted",
        "score": {
            "overall_score": 85,
        },
    }


def cv_file(
    filename: str = "candidate.pdf",
    content: bytes = b"Candidate CV content.",
    extension: str = ".pdf",
) -> dict:
    """
    Build a representative uploaded CV object.
    """

    return {
        "filename": filename,
        "content": content,
        "extension": extension,
    }


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------

def test_service_creates_default_candidate_service():
    service = BulkScreeningService()

    assert isinstance(
        service.candidate_service,
            CandidateService,
    )

    assert service.max_concurrency == 3


def test_service_accepts_custom_candidate_service():
    candidate_service = AsyncMock()

    service = BulkScreeningService(
        candidate_service=candidate_service,
        max_concurrency=5,
    )

    assert service.candidate_service is candidate_service
    assert service.max_concurrency == 5


def test_service_rejects_invalid_concurrency():
    with pytest.raises(
        ValueError,
        match="max_concurrency must be at least 1",
    ):
        BulkScreeningService(
            max_concurrency=0,
        )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_screen_candidates_rejects_empty_job_id():
    service = BulkScreeningService(
        candidate_service=AsyncMock(),
    )

    with pytest.raises(
        BulkScreeningServiceError,
        match="Job ID must be a non-empty string",
    ):
        await service.screen_candidates(
            job_id=" ",
            files=[
                cv_file(),
            ],
            actor_id="recruiter-001",
        )


@pytest.mark.asyncio
async def test_screen_candidates_rejects_empty_actor_id():
    service = BulkScreeningService(
        candidate_service=AsyncMock(),
    )

    with pytest.raises(
        BulkScreeningServiceError,
        match="Actor ID must be a non-empty string",
    ):
        await service.screen_candidates(
            job_id="job-001",
            files=[
                cv_file(),
            ],
            actor_id=" ",
        )


@pytest.mark.asyncio
async def test_screen_candidates_rejects_empty_file_list():
    service = BulkScreeningService(
        candidate_service=AsyncMock(),
    )

    with pytest.raises(
        BulkScreeningServiceError,
        match="At least one CV file is required",
    ):
        await service.screen_candidates(
            job_id="job-001",
            files=[],
            actor_id="recruiter-001",
        )


@pytest.mark.asyncio
async def test_screen_candidates_rejects_non_list_files():
    service = BulkScreeningService(
        candidate_service=AsyncMock(),
    )

    with pytest.raises(
        BulkScreeningServiceError,
        match="CV files must be provided as a list",
    ):
        await service.screen_candidates(
            job_id="job-001",
            files=None,
            actor_id="recruiter-001",
        )


@pytest.mark.asyncio
async def test_screen_candidates_rejects_invalid_file_object():
    service = BulkScreeningService(
        candidate_service=AsyncMock(),
    )

    with pytest.raises(
        BulkScreeningServiceError,
        match="Each CV file must be represented as an object",
    ):
        await service.screen_candidates(
            job_id="job-001",
            files=[
                "candidate.pdf",
            ],
            actor_id="recruiter-001",
        )


@pytest.mark.asyncio
async def test_screen_candidates_rejects_missing_filename():
    service = BulkScreeningService(
        candidate_service=AsyncMock(),
    )

    with pytest.raises(
        BulkScreeningServiceError,
        match="Every CV must have a non-empty filename",
    ):
        await service.screen_candidates(
            job_id="job-001",
            files=[
                {
                    "content": b"CV",
                    "extension": ".pdf",
                },
            ],
            actor_id="recruiter-001",
        )


@pytest.mark.asyncio
async def test_screen_candidates_rejects_non_bytes_content():
    service = BulkScreeningService(
        candidate_service=AsyncMock(),
    )

    with pytest.raises(
        BulkScreeningServiceError,
        match="must contain byte content",
    ):
        await service.screen_candidates(
            job_id="job-001",
            files=[
                {
                    "filename": "candidate.pdf",
                    "content": "CV content",
                    "extension": ".pdf",
                },
            ],
            actor_id="recruiter-001",
        )


@pytest.mark.asyncio
async def test_screen_candidates_rejects_empty_content():
    service = BulkScreeningService(
        candidate_service=AsyncMock(),
    )

    with pytest.raises(
        BulkScreeningServiceError,
        match="uploaded CV 'candidate.pdf' is empty",
    ):
        await service.screen_candidates(
            job_id="job-001",
            files=[
                cv_file(
                    content=b"",
                ),
            ],
            actor_id="recruiter-001",
        )


# ---------------------------------------------------------------------------
# Successful Screening
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_screen_candidates_successfully_processes_all_files(
    tmp_path,
):
    candidate_service = AsyncMock()

    candidate_service.screen_candidate.side_effect = [
        candidate_result(
            "candidate-001",
        ),
        candidate_result(
            "candidate-002",
        ),
    ]

    service = BulkScreeningService(
        candidate_service=candidate_service,
        max_concurrency=2,
    )

    result = await service.screen_candidates(
        job_id=" job-001 ",
        files=[
            cv_file(
                filename="candidate-001.pdf",
            ),
            cv_file(
                filename="candidate-002.pdf",
            ),
        ],
        actor_id=" recruiter-001 ",
    )

    assert result["job_id"] == "job-001"
    assert result["status"] == "completed"
    assert result["total"] == 2
    assert result["successful"] == 2
    assert result["failed"] == 0

    assert len(
        result["results"],
    ) == 2

    assert all(
        item["success"] is True
        for item in result["results"]
    )

    assert candidate_service.screen_candidate.await_count == 2

    calls = (
        candidate_service.screen_candidate.await_args_list
    )

    assert calls[0].kwargs["job_id"] == "job-001"
    assert calls[0].kwargs["filename"] == "candidate-001.pdf"

    assert calls[1].kwargs["job_id"] == "job-001"
    assert calls[1].kwargs["filename"] == "candidate-002.pdf"

    for call in calls:
        assert isinstance(
            call.kwargs["cv_file"],
            Path,
        )

        assert not call.kwargs["cv_file"].exists()


# ---------------------------------------------------------------------------
# Partial Failure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_screen_candidates_continues_when_one_candidate_fails():
    candidate_service = AsyncMock()

    candidate_service.screen_candidate.side_effect = [
        candidate_result(
            "candidate-001",
        ),
        CandidateServiceError(
            "Candidate screening failed.",
        ),
        candidate_result(
            "candidate-003",
        ),
    ]

    service = BulkScreeningService(
        candidate_service=candidate_service,
        max_concurrency=1,
    )

    result = await service.screen_candidates(
        job_id="job-001",
        files=[
            cv_file(
                filename="candidate-001.pdf",
            ),
            cv_file(
                filename="candidate-002.pdf",
            ),
            cv_file(
                filename="candidate-003.pdf",
            ),
        ],
        actor_id="recruiter-001",
    )

    assert result["status"] == "completed"
    assert result["total"] == 3
    assert result["successful"] == 2
    assert result["failed"] == 1

    assert len(
        result["results"],
    ) == 3

    assert result["results"][0]["success"] is True

    assert result["results"][1]["success"] is False
    assert (
        result["results"][1]["error"]
        == "Candidate screening failed."
    )

    assert result["results"][2]["success"] is True

    assert candidate_service.screen_candidate.await_count == 3


@pytest.mark.asyncio
async def test_screen_candidates_converts_unexpected_candidate_error_to_result():
    candidate_service = AsyncMock()

    candidate_service.screen_candidate.side_effect = RuntimeError(
        "Unexpected failure.",
    )

    service = BulkScreeningService(
        candidate_service=candidate_service,
    )

    result = await service.screen_candidates(
        job_id="job-001",
        files=[
            cv_file(),
        ],
        actor_id="recruiter-001",
    )

    assert result["status"] == "completed"
    assert result["total"] == 1
    assert result["successful"] == 0
    assert result["failed"] == 1

    item = result["results"][0]

    assert item["success"] is False
    assert (
        "Unexpected error while screening candidate"
        in item["error"]
    )


# ---------------------------------------------------------------------------
# Candidate ID Generation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_each_candidate_receives_unique_candidate_id():
    candidate_service = AsyncMock()

    candidate_service.screen_candidate.side_effect = [
        candidate_result(),
        candidate_result(),
    ]

    service = BulkScreeningService(
        candidate_service=candidate_service,
    )

    result = await service.screen_candidates(
        job_id="job-001",
        files=[
            cv_file(
                filename="one.pdf",
            ),
            cv_file(
                filename="two.pdf",
            ),
        ],
        actor_id="recruiter-001",
    )

    candidate_ids = [
        item["candidate_id"]
        for item in result["results"]
    ]

    assert len(
        candidate_ids,
    ) == 2

    assert len(
        set(candidate_ids),
    ) == 2


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_status_returns_latest_status_for_job():
    candidate_service = AsyncMock()

    candidate_service.screen_candidate.return_value = (
        candidate_result()
    )

    service = BulkScreeningService(
        candidate_service=candidate_service,
    )

    result = await service.screen_candidates(
        job_id="job-001",
        files=[
            cv_file(),
        ],
        actor_id="recruiter-001",
    )

    batch_id = result["batch_id"]

    status = service.get_status(
        "job-001",
    )

    assert status["batch_id"] == batch_id
    assert status["job_id"] == "job-001"
    assert status["status"] == "completed"
    assert status["total"] == 1
    assert status["processed"] == 1
    assert status["successful"] == 1
    assert status["failed"] == 0
    assert status["started_at"]
    assert status["completed_at"]


def test_get_status_rejects_empty_job_id():
    service = BulkScreeningService(
        candidate_service=AsyncMock(),
    )

    with pytest.raises(
        BulkScreeningServiceError,
        match="Job ID must be a non-empty string",
    ):
        service.get_status(
            " ",
        )


def test_get_status_raises_when_no_operation_exists():
    service = BulkScreeningService(
        candidate_service=AsyncMock(),
    )

    with pytest.raises(
        BulkScreeningServiceError,
        match="No bulk screening operation found",
    ):
        service.get_status(
            "job-without-screening",
        )


# ---------------------------------------------------------------------------
# Filename Normalization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_screen_candidates_normalizes_filename():
    candidate_service = AsyncMock()

    candidate_service.screen_candidate.return_value = (
        candidate_result()
    )

    service = BulkScreeningService(
        candidate_service=candidate_service,
    )

    result = await service.screen_candidates(
        job_id="job-001",
        files=[
            cv_file(
                filename="C:\\uploads\\candidate.pdf",
            ),
        ],
        actor_id="recruiter-001",
    )

    assert result["results"][0]["filename"] == (
        "candidate.pdf"
    )

    candidate_service.screen_candidate.assert_awaited_once()

    call = candidate_service.screen_candidate.await_args

    assert call.kwargs["filename"] == "candidate.pdf"


# ---------------------------------------------------------------------------
# Temporary File Cleanup
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_temporary_file_is_removed_after_successful_screening():
    candidate_service = AsyncMock()

    captured_path: Path | None = None

    async def fake_screen_candidate(
        *,
        candidate_id,
        job_id,
        filename,
        cv_file,
        criteria,
        thresholds,
    ):
        nonlocal captured_path

        captured_path = cv_file

        assert cv_file.exists()
        assert cv_file.read_bytes() == b"Candidate CV content."

        return candidate_result(
            candidate_id,
        )

    candidate_service.screen_candidate.side_effect = (
        fake_screen_candidate
    )

    service = BulkScreeningService(
        candidate_service=candidate_service,
    )

    await service.screen_candidates(
        job_id="job-001",
        files=[
            cv_file(),
        ],
        actor_id="recruiter-001",
    )

    assert captured_path is not None
    assert not captured_path.exists()


@pytest.mark.asyncio
async def test_temporary_file_is_removed_after_failed_screening():
    candidate_service = AsyncMock()

    captured_path: Path | None = None

    async def failing_screen_candidate(
        *,
        candidate_id,
        job_id,
        filename,
        cv_file,
        criteria,
        thresholds,
    ):
        nonlocal captured_path

        captured_path = cv_file

        assert cv_file.exists()

        raise CandidateServiceError(
            "Screening failed.",
        )

    candidate_service.screen_candidate.side_effect = (
        failing_screen_candidate
    )

    service = BulkScreeningService(
        candidate_service=candidate_service,
    )

    result = await service.screen_candidates(
        job_id="job-001",
        files=[
            cv_file(),
        ],
        actor_id="recruiter-001",
    )

    assert result["failed"] == 1

    assert captured_path is not None
    assert not captured_path.exists()