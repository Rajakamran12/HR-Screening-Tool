from __future__ import annotations

from typing import Any

from fastapi import Depends, Header, HTTPException, status

from app.core.firebase import (
    FirebaseAuthenticationError,
    get_authenticated_user,
)


# ---------------------------------------------------------------------------
# Authentication Dependency
# ---------------------------------------------------------------------------

async def get_current_user(
    authorization: str | None = Header(
        default=None,
        alias="Authorization",
    ),
) -> dict[str, Any]:
    """
    Authenticate the current API request using a Firebase ID token.

    The frontend must send:

        Authorization: Bearer <firebase-id-token>

    Firebase Admin verifies the token server-side.

    Returns:
        A normalized authenticated-user dictionary containing:

            uid
            email
            email_verified
            name
            picture
            claims

    Raises:
        HTTPException:
            401 when the authorization header is missing,
            malformed, uses a non-Bearer authentication scheme,
            or the Firebase token cannot be verified.
    """

    # -----------------------------------------------------------------------
    # Missing Authorization Header
    # -----------------------------------------------------------------------

    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials are required.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    # -----------------------------------------------------------------------
    # Parse Authorization Header
    # -----------------------------------------------------------------------

    authorization_value = authorization.strip()

    if not authorization_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials are required.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    parts = authorization_value.split(
        " ",
        1,
    )

    scheme = parts[0]

    # -----------------------------------------------------------------------
    # Validate Authentication Scheme
    # -----------------------------------------------------------------------

    if scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication scheme must be Bearer.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    # -----------------------------------------------------------------------
    # Extract Bearer Token
    # -----------------------------------------------------------------------

    if len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase ID token is required.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    token = parts[1].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase ID token is required.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    # -----------------------------------------------------------------------
    # Verify Firebase Authentication
    # -----------------------------------------------------------------------

    try:
        user = get_authenticated_user(
            token
        )

    except FirebaseAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={
                "WWW-Authenticate": "Bearer",
            },
        ) from exc

    # -----------------------------------------------------------------------
    # Validate Normalized Firebase User
    # -----------------------------------------------------------------------

    if not isinstance(
        user,
        dict,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase authentication returned invalid user data.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    user_id = user.get(
        "uid"
    )

    if not isinstance(
        user_id,
        str,
    ) or not user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated Firebase user has no valid user ID.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    return user


# ---------------------------------------------------------------------------
# Convenience Dependency
# ---------------------------------------------------------------------------

CurrentUser = Depends(
    get_current_user
)