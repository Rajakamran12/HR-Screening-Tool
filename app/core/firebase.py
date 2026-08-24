
from pathlib import Path
from typing import Any

import firebase_admin
from firebase_admin import credentials, firestore, auth

from app.core.config import FIREBASE_CREDENTIALS_PATH


class FirebaseInitializationError(RuntimeError):
    """
    Raised when Firebase cannot be initialized successfully.
    """


class FirebaseAuthenticationError(RuntimeError):
    """
    Raised when a Firebase authentication token cannot be verified.
    """


_firebase_initialized = False
_firestore_client = None


def initialize_firebase():
    """
    Initialize Firebase Admin SDK and return the Firestore client.

    Initialization is performed only once for the application process.
    """

    global _firebase_initialized
    global _firestore_client

    if _firebase_initialized and _firestore_client is not None:
        return _firestore_client

    if not FIREBASE_CREDENTIALS_PATH:
        raise FirebaseInitializationError(
            "FIREBASE_CREDENTIALS_PATH is not configured."
        )

    credentials_path = Path(
        FIREBASE_CREDENTIALS_PATH
    )

    if not credentials_path.is_absolute():
        credentials_path = (
            Path(__file__).resolve().parents[2]
            / credentials_path
        )

    if not credentials_path.exists():
        raise FirebaseInitializationError(
            "Firebase credentials file does not exist: "
            f"{credentials_path}"
        )

    if not credentials_path.is_file():
        raise FirebaseInitializationError(
            "Firebase credentials path is not a file: "
            f"{credentials_path}"
        )

    try:
        if not firebase_admin._apps:
            firebase_credential = credentials.Certificate(
                str(credentials_path)
            )

            firebase_admin.initialize_app(
                firebase_credential
            )

        _firestore_client = firestore.client()
        _firebase_initialized = True

        return _firestore_client

    except Exception as exc:
        raise FirebaseInitializationError(
            f"Unable to initialize Firebase: {exc}"
        ) from exc


def get_firestore_client():
    """
    Return the initialized Firestore client.

    Firebase is initialized automatically if necessary.
    """

    if not _firebase_initialized or _firestore_client is None:
        return initialize_firebase()

    return _firestore_client


def verify_firebase_token(
    id_token: str,
) -> dict[str, Any]:
    """
    Verify a Firebase Authentication ID token.

    Args:
        id_token:
            Firebase ID token received from the authenticated frontend.

    Returns:
        Decoded Firebase token claims.

    Raises:
        FirebaseAuthenticationError:
            If the token is missing, invalid, expired, revoked,
            or Firebase authentication cannot be performed.

    The frontend never gets access to Firebase Admin credentials.
    Token verification happens exclusively on the backend.
    """

    if not isinstance(
        id_token,
        str,
    ):
        raise FirebaseAuthenticationError(
            "Firebase ID token must be a string."
        )

    normalized_token = id_token.strip()

    if not normalized_token:
        raise FirebaseAuthenticationError(
            "Firebase ID token is required."
        )

    try:
        # Firebase Admin SDK initializes the application only when
        # necessary. This also guarantees that the configured Firebase
        # credentials have been validated before token verification.
        initialize_firebase()

        decoded_token = auth.verify_id_token(
            normalized_token
        )

    except FirebaseAuthenticationError:
        raise

    except Exception as exc:
        raise FirebaseAuthenticationError(
            f"Unable to verify Firebase ID token: {exc}"
        ) from exc

    if not isinstance(
        decoded_token,
        dict,
    ):
        raise FirebaseAuthenticationError(
            "Firebase returned an invalid authentication payload."
        )

    return decoded_token


def get_authenticated_user(
    id_token: str,
) -> dict[str, Any]:
    """
    Verify a Firebase ID token and return the authenticated user data.

    This is a convenience wrapper used by API authentication layers.
    """

    decoded_token = verify_firebase_token(
        id_token
    )

    user_id = decoded_token.get(
        "uid"
    )

    if not user_id:
        raise FirebaseAuthenticationError(
            "Verified Firebase token does not contain a user ID."
        )

    return {
        "uid": user_id,
        "email": decoded_token.get(
            "email"
        ),
        "email_verified": bool(
            decoded_token.get(
                "email_verified",
                False,
            )
        ),
        "name": decoded_token.get(
            "name"
        ),
        "picture": decoded_token.get(
            "picture"
        ),
        "claims": decoded_token,
    }
