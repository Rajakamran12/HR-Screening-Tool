from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import get_current_user
from app.api.candidate_routes import router
from app.services.candidate_service import (
    CandidateService,
    CandidateServiceError,
)


# ---------------------------------------------------------------------------
# Test Application
# ---------------------------------------------------------------------------

app = FastAPI()

app.include_router(router)


def fake_current_user() -> dict[str, str]:
    """
    Return a fake authenticated Firebase user for route tests.

    Production authentication remains enabled in candidate_routes.py.
    The test application overrides the Firebase authentication dependency
    so route behavior can be tested without requiring a real Firebase token.
    """

    return {
        "uid": "test-recruiter-001",
    }


app.dependency_overrides[get_current_user] = fake_current_user


client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def candidate_record(
    candidate_id: str = "candidate-001",
    job_id: str = "job-001",
    category: str = "shortlisted",
) -> dict:
    """
    Build a representative persisted candidate record.
    """

    return {
        "candidate_id": candidate_id,
        "job_id": job_id,
        "filename": "candidate.pdf",
        "candidate": {
            "candidate": {
                "name": "John Doe",
            },
            "source_quality": "high",
        },
        "score": {
            "overall_score": 85,
        },
        "categorization": {
            "category": category,
            "score": 85,
            "shortlisted_threshold": 80,
            "maybe_threshold": 60,
        },
        "category": category,
        "decision_source": "ai",
    }


# ---------------------------------------------------------------------------
# GET /candidates
# ---------------------------------------------------------------------------

def test_get_candidates_returns_all_candidates():
    candidates = [
        candidate_record(
            candidate_id="candidate-001",
        ),
        candidate_record(
            candidate_id="candidate-002",
            category="maybe",
        ),
    ]

    with patch(
        "app.api.candidate_routes.CandidateService.get_all_candidates",
        return_value=candidates,
    ):
        response = client.get(
            "/candidates"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["count"] == 2
    assert data["candidates"] == candidates


def test_get_candidates_returns_500_on_service_error():
    with patch(
        "app.api.candidate_routes.CandidateService.get_all_candidates",
        side_effect=CandidateServiceError(
            "Unable to retrieve candidates."
        ),
    ):
        response = client.get(
            "/candidates"
        )

    assert response.status_code == 500

    data = response.json()

    assert data["detail"] == (
        "Unable to retrieve candidates."
    )


# ---------------------------------------------------------------------------
# GET /candidates/job/{job_id}
# ---------------------------------------------------------------------------

def test_get_candidates_by_job_returns_matching_candidates():
    candidates = [
        candidate_record(
            candidate_id="candidate-001",
            job_id="job-001",
        ),
        candidate_record(
            candidate_id="candidate-002",
            job_id="job-001",
            category="maybe",
        ),
    ]

    with patch(
        "app.api.candidate_routes.CandidateService.get_candidates_by_job",
        return_value=candidates,
    ) as mocked_method:
        response = client.get(
            "/candidates/job/job-001"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["job_id"] == "job-001"
    assert data["count"] == 2
    assert data["candidates"] == candidates

    mocked_method.assert_called_once_with(
        "job-001"
    )


def test_get_candidates_by_job_strips_job_id():
    candidates = []

    with patch(
        "app.api.candidate_routes.CandidateService.get_candidates_by_job",
        return_value=candidates,
    ) as mocked_method:
        response = client.get(
            "/candidates/job/%20job-001%20"
        )

    assert response.status_code == 200

    mocked_method.assert_called_once_with(
        "job-001"
    )


def test_get_candidates_by_job_returns_400_for_empty_job_id():
    response = client.get(
        "/candidates/job/%20"
    )

    assert response.status_code == 400

    data = response.json()

    assert data["detail"] == (
        "Job ID must be a non-empty string."
    )


def test_get_candidates_by_job_returns_500_on_service_error():
    with patch(
        "app.api.candidate_routes.CandidateService.get_candidates_by_job",
        side_effect=CandidateServiceError(
            "Unable to retrieve candidates for job."
        ),
    ):
        response = client.get(
            "/candidates/job/job-001"
        )

    assert response.status_code == 500

    assert response.json()["detail"] == (
        "Unable to retrieve candidates for job."
    )


# ---------------------------------------------------------------------------
# GET /candidates/{candidate_id}
# ---------------------------------------------------------------------------

def test_get_candidate_returns_candidate():
    candidate = candidate_record()

    with patch(
        "app.api.candidate_routes.CandidateService.get_candidate",
        return_value=candidate,
    ) as mocked_method:
        response = client.get(
            "/candidates/candidate-001"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["candidate"] == candidate

    mocked_method.assert_called_once_with(
        "candidate-001"
    )


def test_get_candidate_strips_candidate_id():
    candidate = candidate_record()

    with patch(
        "app.api.candidate_routes.CandidateService.get_candidate",
        return_value=candidate,
    ) as mocked_method:
        response = client.get(
            "/candidates/%20candidate-001%20"
        )

    assert response.status_code == 200

    mocked_method.assert_called_once_with(
        "candidate-001"
    )


def test_get_candidate_returns_400_for_empty_candidate_id():
    response = client.get(
        "/candidates/%20"
    )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "Candidate ID must be a non-empty string."
    )


def test_get_candidate_returns_404_when_candidate_not_found():
    with patch(
        "app.api.candidate_routes.CandidateService.get_candidate",
        side_effect=CandidateServiceError(
            "Candidate 'candidate-001' does not exist."
        ),
    ):
        response = client.get(
            "/candidates/candidate-001"
        )

    assert response.status_code == 404

    assert response.json()["detail"] == (
        "Candidate 'candidate-001' does not exist."
    )


def test_get_candidate_returns_500_for_unexpected_service_error():
    with patch(
        "app.api.candidate_routes.CandidateService.get_candidate",
        side_effect=CandidateServiceError(
            "Database unavailable."
        ),
    ):
        response = client.get(
            "/candidates/candidate-001"
        )

    assert response.status_code == 500

    assert response.json()["detail"] == (
        "Database unavailable."
    )


# ---------------------------------------------------------------------------
# POST /candidates/{candidate_id}/override
# ---------------------------------------------------------------------------

def test_override_candidate_applies_human_override():
    updated_candidate = candidate_record(
        category="rejected"
    )

    payload = {
        "new_category": "Rejected",
        "actor_id": "recruiter-001",
        "reason": "Candidate does not meet the required seniority.",
    }

    with patch(
        "app.api.candidate_routes.CandidateService.override_candidate",
        return_value=updated_candidate,
    ) as mocked_method:
        response = client.post(
            "/candidates/candidate-001/override",
            json=payload,
        )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["candidate_id"] == "candidate-001"
    assert data["override_applied"] is True
    assert data["candidate"] == updated_candidate

    mocked_method.assert_called_once_with(
        candidate_id="candidate-001",
        new_category="Rejected",
        actor_id="test-recruiter-001",
        reason=(
            "Candidate does not meet the required seniority."
        ),
    )


def test_override_candidate_returns_400_for_empty_candidate_id():
    payload = {
        "new_category": "Rejected",
        "actor_id": "recruiter-001",
        "reason": "Changed after recruiter review.",
    }

    response = client.post(
        "/candidates/%20/override",
        json=payload,
    )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "Candidate ID must be a non-empty string."
    )


def test_override_candidate_returns_404_when_candidate_not_found():
    payload = {
        "new_category": "Rejected",
        "actor_id": "recruiter-001",
        "reason": "Candidate does not satisfy requirements.",
    }

    with patch(
        "app.api.candidate_routes.CandidateService.override_candidate",
        side_effect=CandidateServiceError(
            "Candidate 'candidate-001' does not exist."
        ),
    ):
        response = client.post(
            "/candidates/candidate-001/override",
            json=payload,
        )

    assert response.status_code == 404


def test_override_candidate_returns_409_when_category_is_unchanged():
    payload = {
        "new_category": "Shortlisted",
        "actor_id": "recruiter-001",
        "reason": "Reviewed candidate again.",
    }

    with patch(
        "app.api.candidate_routes.CandidateService.override_candidate",
        side_effect=CandidateServiceError(
            "Candidate is already in the requested category."
        ),
    ):
        response = client.post(
            "/candidates/candidate-001/override",
            json=payload,
        )

    assert response.status_code == 409


def test_override_candidate_returns_400_for_invalid_category():
    payload = {
        "new_category": "Unknown",
        "actor_id": "recruiter-001",
        "reason": "Manual decision.",
    }

    with patch(
        "app.api.candidate_routes.CandidateService.override_candidate",
        side_effect=CandidateServiceError(
            "Invalid candidate category. Allowed values are: "
            "Shortlisted, Maybe, Rejected."
        ),
    ):
        response = client.post(
            "/candidates/candidate-001/override",
            json=payload,
        )

    assert response.status_code == 400


def test_override_candidate_returns_500_for_unexpected_service_error():
    payload = {
        "new_category": "Maybe",
        "actor_id": "recruiter-001",
        "reason": "Manual review decision.",
    }

    with patch(
        "app.api.candidate_routes.CandidateService.override_candidate",
        side_effect=CandidateServiceError(
            "Audit persistence failed."
        ),
    ):
        response = client.post(
            "/candidates/candidate-001/override",
            json=payload,
        )

    assert response.status_code == 500


def test_override_candidate_requires_reason():
    payload = {
        "new_category": "Rejected",
        "actor_id": "recruiter-001",
    }

    response = client.post(
        "/candidates/candidate-001/override",
        json=payload,
    )

    assert response.status_code == 422


def test_override_candidate_requires_actor_id():
    payload = {
        "new_category": "Rejected",
        "reason": "Manual review decision.",
    }

    response = client.post(
        "/candidates/candidate-001/override",
        json=payload,
    )

    assert response.status_code == 422


def test_override_candidate_requires_new_category():
    payload = {
        "actor_id": "recruiter-001",
        "reason": "Manual review decision.",
    }

    response = client.post(
        "/candidates/candidate-001/override",
        json=payload,
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /candidates/{candidate_id}/audit
# ---------------------------------------------------------------------------

def test_get_candidate_audit_history_returns_events():
    events = [
        {
            "candidate_id": "candidate-001",
            "job_id": "job-001",
            "action": "candidate_category_override",
            "actor_id": "recruiter-001",
            "previous_category": "maybe",
            "new_category": "shortlisted",
            "reason": "Strong interview performance.",
        }
    ]

    with patch(
        "app.api.candidate_routes.CandidateService.get_candidate_audit_history",
        return_value=events,
    ) as mocked_method:
        response = client.get(
            "/candidates/candidate-001/audit"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["candidate_id"] == "candidate-001"
    assert data["count"] == 1
    assert data["audit_events"] == events

    mocked_method.assert_called_once_with(
        "candidate-001"
    )


def test_get_candidate_audit_history_returns_400_for_empty_id():
    response = client.get(
        "/candidates/%20/audit"
    )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "Candidate ID must be a non-empty string."
    )


def test_get_candidate_audit_history_returns_500_on_service_error():
    with patch(
        "app.api.candidate_routes.CandidateService.get_candidate_audit_history",
        side_effect=CandidateServiceError(
            "Unable to retrieve candidate audit history."
        ),
    ):
        response = client.get(
            "/candidates/candidate-001/audit"
        )

    assert response.status_code == 500

    assert response.json()["detail"] == (
        "Unable to retrieve candidate audit history."
    )


# ---------------------------------------------------------------------------
# PATCH /candidates/{candidate_id}
# ---------------------------------------------------------------------------

def test_update_candidate_updates_non_category_fields():
    updated_candidate = candidate_record()

    payload = {
        "status": "reviewed",
        "notes": "Recruiter reviewed the CV.",
    }

    with patch(
        "app.api.candidate_routes.CandidateService.update_candidate",
        return_value=updated_candidate,
    ) as mocked_method:
        response = client.patch(
            "/candidates/candidate-001",
            json=payload,
        )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["candidate"] == updated_candidate

    mocked_method.assert_called_once_with(
        candidate_id="candidate-001",
        updates=payload,
    )


def test_update_candidate_rejects_category_update():
    with patch(
        "app.api.candidate_routes.CandidateService.update_candidate",
        side_effect=CandidateServiceError(
            "Candidate category cannot be changed through the "
            "generic update operation. Use override_candidate() "
            "so the human decision is audited."
        ),
    ):
        response = client.patch(
            "/candidates/candidate-001",
            json={
                "category": "rejected",
            },
        )

    assert response.status_code == 400

    assert "category cannot be changed" in (
        response.json()["detail"].lower()
    )


def test_update_candidate_returns_404_when_candidate_not_found():
    with patch(
        "app.api.candidate_routes.CandidateService.update_candidate",
        side_effect=CandidateServiceError(
            "Candidate 'candidate-001' does not exist."
        ),
    ):
        response = client.patch(
            "/candidates/candidate-001",
            json={
                "status": "reviewed",
            },
        )

    assert response.status_code == 404


def test_update_candidate_returns_400_for_invalid_update():
    with patch(
        "app.api.candidate_routes.CandidateService.update_candidate",
        side_effect=CandidateServiceError(
            "At least one candidate update is required."
        ),
    ):
        response = client.patch(
            "/candidates/candidate-001",
            json={},
        )

    assert response.status_code == 400


def test_update_candidate_returns_422_for_invalid_json_body():
    response = client.patch(
        "/candidates/candidate-001",
        json=[],
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /candidates/{candidate_id}
# ---------------------------------------------------------------------------

def test_delete_candidate_deletes_candidate():
    with patch(
        "app.api.candidate_routes.CandidateService.delete_candidate",
        return_value=None,
    ) as mocked_method:
        response = client.delete(
            "/candidates/candidate-001"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["candidate_id"] == "candidate-001"
    assert data["deleted"] is True

    mocked_method.assert_called_once_with(
        "candidate-001"
    )


def test_delete_candidate_returns_404_when_candidate_not_found():
    with patch(
        "app.api.candidate_routes.CandidateService.delete_candidate",
        side_effect=CandidateServiceError(
            "Candidate 'candidate-001' does not exist."
        ),
    ):
        response = client.delete(
            "/candidates/candidate-001"
        )

    assert response.status_code == 404


def test_delete_candidate_returns_500_on_service_error():
    with patch(
        "app.api.candidate_routes.CandidateService.delete_candidate",
        side_effect=CandidateServiceError(
            "Firestore unavailable."
        ),
    ):
        response = client.delete(
            "/candidates/candidate-001"
        )

    assert response.status_code == 500


# ---------------------------------------------------------------------------
# POST /candidates/screen
# ---------------------------------------------------------------------------

def test_screen_candidate_rejects_unsupported_file_type():
    response = client.post(
        "/candidates/screen",
        params={
            "job_id": "job-001",
        },
        files={
            "file": (
                "candidate.jpg",
                b"fake image content",
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "Unsupported CV file type. "
        "Supported formats are PDF, DOCX, and TXT."
    )


def test_screen_candidate_rejects_missing_filename():
    response = client.post(
        "/candidates/screen",
        params={
            "job_id": "job-001",
        },
        files={
            "file": (
                "",
                b"candidate content",
                "text/plain",
            )
        },
    )

    assert response.status_code in {
        400,
        422,
    }


def test_screen_candidate_rejects_empty_file():
    mock_job = type(
        "FakeJob",
        (),
        {
            "job_id": "job-001",
            "criteria": [],
            "thresholds": None,
        },
    )()

    with patch(
        "app.api.candidate_routes.JobRepository.get",
        return_value=mock_job,
    ):
        response = client.post(
            "/candidates/screen",
            params={
                "job_id": "job-001",
            },
            files={
                "file": (
                    "candidate.txt",
                    b"",
                    "text/plain",
                )
            },
        )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "The uploaded CV is empty."
    )


def test_screen_candidate_rejects_empty_job_id():
    response = client.post(
        "/candidates/screen",
        params={
            "job_id": " ",
        },
        files={
            "file": (
                "candidate.txt",
                b"Candidate CV",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "Job ID must be a non-empty string."
    )


def test_screen_candidate_returns_404_when_job_does_not_exist():
    from app.core.job_repository import JobRepositoryError

    with patch(
        "app.api.candidate_routes.JobRepository.get",
        side_effect=JobRepositoryError(
            "Job 'job-001' does not exist."
        ),
    ):
        response = client.post(
            "/candidates/screen",
            params={
                "job_id": "job-001",
            },
            files={
                "file": (
                    "candidate.txt",
                    b"Candidate CV",
                    "text/plain",
                )
            },
        )

    assert response.status_code == 404


def test_screen_candidate_returns_500_when_job_repository_fails():
    from app.core.job_repository import JobRepositoryError

    with patch(
        "app.api.candidate_routes.JobRepository.get",
        side_effect=JobRepositoryError(
            "Firestore unavailable."
        ),
    ):
        response = client.post(
            "/candidates/screen",
            params={
                "job_id": "job-001",
            },
            files={
                "file": (
                    "candidate.txt",
                    b"Candidate CV",
                    "text/plain",
                )
            },
        )

    assert response.status_code == 500


def test_screen_candidate_successfully_screens_txt_file(
    tmp_path,
):
    candidate_result = candidate_record()

    mock_job = type(
        "FakeJob",
        (),
        {
            "job_id": "job-001",
            "criteria": [],
            "thresholds": None,
        },
    )()

    async def fake_screen_candidate(
        self,
        *,
        candidate_id,
        job_id,
        filename,
        cv_file,
        criteria,
        thresholds,
    ):
        assert job_id == "job-001"
        assert filename == "candidate.txt"
        assert Path(cv_file).exists()
        assert criteria == []
        assert thresholds is None

        return candidate_result

    with patch(
        "app.api.candidate_routes.JobRepository.get",
        return_value=mock_job,
    ), patch.object(
        CandidateService,
        "screen_candidate",
        new=fake_screen_candidate,
    ):
        response = client.post(
            "/candidates/screen",
            params={
                "job_id": "job-001",
            },
            files={
                "file": (
                    "candidate.txt",
                    b"Python developer with four years of experience.",
                    "text/plain",
                )
            },
        )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["job_id"] == "job-001"
    assert data["filename"] == "candidate.txt"
    assert data["candidate"] == candidate_result
    assert isinstance(
        data["candidate_id"],
        str,
    )
    assert data["candidate_id"]


def test_screen_candidate_returns_422_for_service_error():
    mock_job = type(
        "FakeJob",
        (),
        {
            "job_id": "job-001",
            "criteria": [],
            "thresholds": None,
        },
    )()

    async def failing_screen_candidate(
        self,
        *,
        candidate_id,
        job_id,
        filename,
        cv_file,
        criteria,
        thresholds,
    ):
        raise CandidateServiceError(
            "Candidate screening failed."
        )

    with patch(
        "app.api.candidate_routes.JobRepository.get",
        return_value=mock_job,
    ), patch.object(
        CandidateService,
        "screen_candidate",
        new=failing_screen_candidate,
    ):
        response = client.post(
            "/candidates/screen",
            params={
                "job_id": "job-001",
            },
            files={
                "file": (
                    "candidate.txt",
                    b"Candidate CV",
                    "text/plain",
                )
            },
        )

    assert response.status_code == 422

    assert response.json()["detail"] == (
        "Candidate screening failed."
    )


def test_screen_candidate_returns_500_for_unexpected_error():
    mock_job = type(
        "FakeJob",
        (),
        {
            "job_id": "job-001",
            "criteria": [],
            "thresholds": None,
        },
    )()

    async def failing_screen_candidate(
        self,
        *,
        candidate_id,
        job_id,
        filename,
        cv_file,
        criteria,
        thresholds,
    ):
        raise RuntimeError(
            "Unexpected failure."
        )

    with patch(
        "app.api.candidate_routes.JobRepository.get",
        return_value=mock_job,
    ), patch.object(
        CandidateService,
        "screen_candidate",
        new=failing_screen_candidate,
    ):
        response = client.post(
            "/candidates/screen",
            params={
                "job_id": "job-001",
            },
            files={
                "file": (
                    "candidate.txt",
                    b"Candidate CV",
                    "text/plain",
                )
            },
        )

    assert response.status_code == 500

    assert "Unexpected error while screening candidate" in (
        response.json()["detail"]
    )