from __future__ import annotations

import pytest

from app.api.auth import get_current_user
from app.api.main import app


# ---------------------------------------------------------------------------
# Test Authentication User
# ---------------------------------------------------------------------------

TEST_USER = {
    "uid": "test-recruiter-001",
    "email": "recruiter@test.com",
    "email_verified": True,
    "name": "Test Recruiter",
    "picture": None,
    "claims": {
        "uid": "test-recruiter-001",
        "email": "recruiter@test.com",
        "email_verified": True,
        "name": "Test Recruiter",
    },
}


# ---------------------------------------------------------------------------
# Fake Authentication Dependency
# ---------------------------------------------------------------------------

async def override_get_current_user() -> dict:
    """
    Return a fake authenticated Firebase user for tests.

    Production requests continue to use the real Firebase
    authentication dependency.

    Tests do not need a real Firebase ID token because authentication
    itself is not what these route/service tests are testing.
    """

    return TEST_USER.copy()


# ---------------------------------------------------------------------------
# Application Authentication Override
# ---------------------------------------------------------------------------

app.dependency_overrides[
    get_current_user
] = override_get_current_user


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def configure_test_authentication():
    """
    Keep Firebase authentication overridden for the complete test session.

    The override prevents route tests from requiring real Firebase
    credentials or real Firebase ID tokens.
    """

    app.dependency_overrides[
        get_current_user
    ] = override_get_current_user

    yield

    app.dependency_overrides.pop(
        get_current_user,
        None,
    )