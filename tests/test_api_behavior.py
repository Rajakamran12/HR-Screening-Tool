from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api.auth import get_current_user
from app.api.main import app
from app.core.firebase import FirebaseAuthenticationError


# ---------------------------------------------------------------------------
# Test Client
# ---------------------------------------------------------------------------

client = TestClient(app)


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    """
    Ensure one test's FastAPI dependency overrides never leak into
    another test.
    """

    app.dependency_overrides.clear()

    yield

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test Authentication User
# ---------------------------------------------------------------------------

TEST_USER = {
    "uid": "test-recruiter-001",
    "email": "recruiter@example.com",
    "email_verified": True,
    "name": "Test Recruiter",
    "picture": None,
    "claims": {},
}


def authenticate_test_user():
    """
    FastAPI dependency override used to simulate a successfully
    authenticated Firebase user.

    This intentionally bypasses Firebase itself. Firebase token
    verification is tested separately below.
    """

    return TEST_USER


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def test_health_endpoint_is_public():
    """
    /health must remain accessible without authentication.
    """

    response = client.get(
        "/health"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "healthy"
    assert data["service"] == "hr-screening-tool"


def test_root_endpoint_is_public():
    """
    The API root must remain accessible without authentication.
    """

    response = client.get(
        "/"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "HR Screening Tool API"
    assert data["version"] == "1.0.0"
    assert data["status"] == "running"
    assert data["docs"] == "/docs"
    assert data["health"] == "/health"


def test_openapi_endpoint_is_public():
    """
    FastAPI's OpenAPI schema must remain publicly accessible.

    The recruiter frontend can use the schema for API discovery,
    while actual protected operations still require authentication.
    """

    response = client.get(
        "/openapi.json"
    )

    assert response.status_code == 200

    data = response.json()

    assert "openapi" in data
    assert "paths" in data


def test_docs_endpoint_is_public():
    """
    Swagger UI should remain accessible without authentication.
    """

    response = client.get(
        "/docs"
    )

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Authentication - Missing Credentials
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/jobs/"),
        ("POST", "/jobs/"),
        ("GET", "/jobs/status/draft"),
        ("GET", "/jobs/job-001"),
        ("GET", "/jobs/job-001/exists"),
        ("PATCH", "/jobs/job-001"),
        ("PATCH", "/jobs/job-001/status"),
        ("DELETE", "/jobs/job-001"),
        ("GET", "/candidates"),
        ("GET", "/candidates/job/job-001"),
        ("GET", "/candidates/candidate-001"),
        ("POST", "/candidates/candidate-001/override"),
        ("GET", "/candidates/candidate-001/audit"),
        ("PATCH", "/candidates/candidate-001"),
        ("DELETE", "/candidates/candidate-001"),
        ("POST", "/candidates/screen"),
        ("POST", "/bulk-screening"),
        ("POST", "/bulk-screening/job-001"),
        ("GET", "/bulk-screening/job-001/status"),
    ],
)
def test_protected_endpoint_requires_authentication(
    method: str,
    path: str,
):
    """
    Every production recruiter endpoint must reject requests that
    do not contain a Firebase Bearer token.

    Authentication must happen before request-specific business
    validation, so these requests should return 401 even when the
    body/query parameters are otherwise incomplete.
    """

    response = client.request(
        method,
        path,
    )

    assert response.status_code == 401

    data = response.json()

    assert data["detail"] == (
        "Authentication credentials are required."
    )

    assert response.headers.get(
        "www-authenticate"
    ) == "Bearer"


# ---------------------------------------------------------------------------
# Authentication - Malformed Bearer Credentials
# ---------------------------------------------------------------------------

def test_auth_dependency_rejects_empty_bearer_token():
    """
    An Authorization header containing an empty Bearer token must
    return 401.
    """

    response = client.get(
        "/candidates",
        headers={
            "Authorization": "Bearer ",
        },
    )

    assert response.status_code == 401

    data = response.json()

    assert data["detail"] in {
        "Authentication credentials are required.",
        "Firebase ID token is required.",
    }


def test_auth_dependency_rejects_non_bearer_authentication_scheme():
    """
    Authentication must use the Bearer scheme.
    """

    response = client.get(
        "/candidates",
        headers={
            "Authorization": "Basic some-invalid-value",
        },
    )

    assert response.status_code == 401

    data = response.json()

    assert data["detail"] == (
        "Authentication scheme must be Bearer."
    )

    assert response.headers.get(
        "www-authenticate"
    ) == "Bearer"


# ---------------------------------------------------------------------------
# Authentication - Invalid Firebase Token
# ---------------------------------------------------------------------------

def test_auth_dependency_returns_401_when_firebase_token_is_invalid():
    """
    Firebase verification failures must be translated into HTTP 401.

    Firebase itself is mocked here so the test does not require a real
    Firebase project or production credential.
    """

    with patch(
        "app.api.auth.get_authenticated_user",
        side_effect=FirebaseAuthenticationError(
            "Invalid Firebase ID token."
        ),
    ):
        response = client.get(
            "/candidates",
            headers={
                "Authorization": "Bearer invalid-firebase-token",
            },
        )

    assert response.status_code == 401

    data = response.json()

    assert data["detail"] == (
        "Invalid Firebase ID token."
    )

    assert response.headers.get(
        "www-authenticate"
    ) == "Bearer"


# ---------------------------------------------------------------------------
# Authentication - Invalid Firebase User Data
# ---------------------------------------------------------------------------

def test_auth_dependency_rejects_non_dictionary_authenticated_user():
    """
    A successful Firebase verification must still produce valid
    normalized user data.
    """

    with patch(
        "app.api.auth.get_authenticated_user",
        return_value=None,
    ):
        response = client.get(
            "/candidates",
            headers={
                "Authorization": "Bearer valid-looking-token",
            },
        )

    assert response.status_code == 401

    data = response.json()

    assert data["detail"] == (
        "Firebase authentication returned invalid user data."
    )

    assert response.headers.get(
        "www-authenticate"
    ) == "Bearer"


def test_auth_dependency_rejects_authenticated_user_without_uid():
    """
    Firebase user data without a valid UID must never be accepted.
    """

    with patch(
        "app.api.auth.get_authenticated_user",
        return_value={
            "email": "recruiter@example.com",
            "email_verified": True,
        },
    ):
        response = client.get(
            "/candidates",
            headers={
                "Authorization": "Bearer valid-looking-token",
            },
        )

    assert response.status_code == 401

    data = response.json()

    assert data["detail"] == (
        "Authenticated Firebase user has no valid user ID."
    )

    assert response.headers.get(
        "www-authenticate"
    ) == "Bearer"


def test_auth_dependency_rejects_empty_uid():
    """
    A blank UID must be treated as an invalid authenticated identity.
    """

    with patch(
        "app.api.auth.get_authenticated_user",
        return_value={
            "uid": "   ",
            "email": "recruiter@example.com",
            "email_verified": True,
            "claims": {},
        },
    ):
        response = client.get(
            "/candidates",
            headers={
                "Authorization": "Bearer valid-looking-token",
            },
        )

    assert response.status_code == 401

    data = response.json()

    assert data["detail"] == (
        "Authenticated Firebase user has no valid user ID."
    )


# ---------------------------------------------------------------------------
# Authentication - Successful Authentication
# ---------------------------------------------------------------------------

def test_authenticated_user_can_access_candidates_endpoint():
    """
    A successfully authenticated recruiter must be allowed through
    the authentication dependency and into the candidate route.
    """

    app.dependency_overrides[
        get_current_user
    ] = authenticate_test_user

    with patch(
        "app.api.candidate_routes.CandidateService.get_all_candidates",
        return_value=[],
    ) as mocked_method:
        response = client.get(
            "/candidates"
        )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True
    assert data["count"] == 0
    assert data["candidates"] == []

    mocked_method.assert_called_once_with()


# ---------------------------------------------------------------------------
# Authentication - Authenticated UID Is Used
# ---------------------------------------------------------------------------

def test_authenticated_uid_is_used_for_candidate_override():
    """
    The override route must use the authenticated Firebase UID as
    the authoritative actor identity.

    The actor_id supplied by the client must not replace the
    authenticated identity.
    """

    app.dependency_overrides[
        get_current_user
    ] = authenticate_test_user

    candidate = {
        "candidate_id": "candidate-001",
        "job_id": "job-001",
        "category": "rejected",
    }

    payload = {
        "new_category": "Rejected",
        "actor_id": "attacker-supplied-user-id",
        "reason": "Manual recruiter review.",
    }

    with patch(
        "app.api.candidate_routes.CandidateService.override_candidate",
        return_value=candidate,
    ) as mocked_method:
        response = client.post(
            "/candidates/candidate-001/override",
            json=payload,
        )

    assert response.status_code == 200

    mocked_method.assert_called_once_with(
        candidate_id="candidate-001",
        new_category="Rejected",
        actor_id="test-recruiter-001",
        reason="Manual recruiter review.",
    )


# ---------------------------------------------------------------------------
# Protected Endpoint Inventory
# ---------------------------------------------------------------------------

def test_production_api_routes_are_present():
    """
    Verify that the complete production API surface is still registered.

    This catches accidental router removal or incorrect mounting while
    keeping the test independent of individual service implementations.
    """

    schema = app.openapi()

    paths = schema["paths"]

    expected_routes = {
        "/jobs/": {"get", "post"},
        "/jobs/status/{status}": {"get"},
        "/jobs/{job_id}": {"get", "patch", "delete"},
        "/jobs/{job_id}/exists": {"get"},
        "/jobs/{job_id}/status": {"patch"},
        "/candidates": {"get"},
        "/candidates/job/{job_id}": {"get"},
        "/candidates/{candidate_id}": {"get", "patch", "delete"},
        "/candidates/{candidate_id}/override": {"post"},
        "/candidates/{candidate_id}/audit": {"get"},
        "/candidates/screen": {"post"},
        "/bulk-screening": {"post"},
        "/bulk-screening/{job_id}": {"post"},
        "/bulk-screening/{job_id}/status": {"get"},
    }

    for path, expected_methods in expected_routes.items():
        assert path in paths, (
            f"Expected API route is missing: {path}"
        )

        actual_methods = set(
            paths[path].keys()
        )

        assert expected_methods.issubset(
            actual_methods
        ), (
            f"Route {path} is missing methods. "
            f"Expected {expected_methods}, "
            f"found {actual_methods}."
        )


# ---------------------------------------------------------------------------
# Legacy Endpoint Behavior
# ---------------------------------------------------------------------------

def test_legacy_screen_endpoint_remains_public():
    """
    The original Step 0 /screen endpoint intentionally remains
    outside Firebase authentication because it is a legacy endpoint
    retained for existing tests and compatibility.
    """

    response = client.post(
        "/screen",
        files={
            "file": (
                "candidate.txt",
                b"not a pdf",
                "text/plain",
            )
        },
    )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "Unsupported file type. "
        "Only PDF CV files are currently supported "
        "by the legacy /screen endpoint."
    )