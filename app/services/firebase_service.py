
from __future__ import annotations

import json
from typing import Any

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore


class FirebaseServiceError(RuntimeError):
    """
    Raised when Firebase initialization or a Firebase operation fails.
    """


class FirebaseService:
    """
    Central Firebase service.

    Responsibilities:
    - Initialize Firebase Admin SDK once.
    - Provide access to Firestore.
    - Provide small, reusable Firestore operations.

    This service intentionally does not contain:
    - authentication business logic
    - CV parsing
    - candidate scoring
    - categorization
    - bulk screening orchestration

    Those responsibilities remain in their existing layers.
    """

    _app: firebase_admin.App | None = None
    _db: firestore.Client | None = None

    def __init__(
        self,
        credential_path: str | None = None,
        credential_dict: dict[str, Any] | None = None,
        project_id: str | None = None,
    ) -> None:
        """
        Initialize Firebase.

        Credential priority:

        1. Existing initialized Firebase application.
        2. Explicit credential_dict.
        3. Explicit credential_path.
        4. GOOGLE_APPLICATION_CREDENTIALS environment variable /
           Firebase Application Default Credentials.

        project_id is optional and can be used when initializing
        Firebase with Application Default Credentials.
        """

        self._initialize(
            credential_path=credential_path,
            credential_dict=credential_dict,
            project_id=project_id,
        )

        self._db = self._get_firestore()

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    @classmethod
    def _initialize(
        cls,
        credential_path: str | None = None,
        credential_dict: dict[str, Any] | None = None,
        project_id: str | None = None,
    ) -> None:
        """
        Initialize the Firebase Admin application exactly once.
        """

        if cls._app is not None:
            return

        try:
            existing_apps = firebase_admin._apps

            if existing_apps:
                cls._app = firebase_admin.get_app()
                return

            firebase_credential = None

            if credential_dict is not None:
                firebase_credential = credentials.Certificate(
                    credential_dict
                )

            elif credential_path:
                firebase_credential = credentials.Certificate(
                    credential_path
                )

            if firebase_credential is not None:
                options: dict[str, Any] = {}

                if project_id:
                    options["projectId"] = project_id

                cls._app = firebase_admin.initialize_app(
                    firebase_credential,
                    options or None,
                )

            else:
                options = {}

                if project_id:
                    options["projectId"] = project_id

                cls._app = firebase_admin.initialize_app(
                    options=options or None,
                )

        except Exception as exc:
            raise FirebaseServiceError(
                f"Failed to initialize Firebase: {exc}"
            ) from exc

    @classmethod
    def _get_firestore(
        cls,
    ) -> firestore.Client:
        """
        Get the Firestore client for the initialized Firebase app.
        """

        if cls._db is not None:
            return cls._db

        if cls._app is None:
            raise FirebaseServiceError(
                "Firebase has not been initialized."
            )

        try:
            cls._db = firestore.client(
                app=cls._app
            )

            return cls._db

        except Exception as exc:
            raise FirebaseServiceError(
                f"Failed to initialize Firestore client: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def db(self) -> firestore.Client:
        """
        Return the Firestore client.
        """

        if self._db is None:
            self._db = self._get_firestore()

        return self._db

    @property
    def app(self) -> firebase_admin.App:
        """
        Return the Firebase application.
        """

        if self._app is None:
            raise FirebaseServiceError(
                "Firebase application is not initialized."
            )

        return self._app

    # ------------------------------------------------------------------
    # Document Operations
    # ------------------------------------------------------------------

    def get_document(
        self,
        collection: str,
        document_id: str,
    ) -> dict[str, Any] | None:
        """
        Retrieve one Firestore document.

        Returns:
            Document dictionary including its ID, or None when the
            document does not exist.
        """

        collection = self._validate_collection(
            collection
        )

        document_id = self._validate_document_id(
            document_id
        )

        try:
            document = (
                self.db
                .collection(collection)
                .document(document_id)
                .get()
            )

            if not document.exists:
                return None

            data = document.to_dict()

            if data is None:
                return None

            return {
                "id": document.id,
                **data,
            }

        except Exception as exc:
            raise FirebaseServiceError(
                "Failed to retrieve Firestore document "
                f"{collection}/{document_id}: {exc}"
            ) from exc

    def create_document(
        self,
        collection: str,
        data: dict[str, Any],
        document_id: str | None = None,
    ) -> str:
        """
        Create a Firestore document.

        If document_id is supplied, that ID is used.
        Otherwise Firestore generates the document ID.

        Returns:
            The created document ID.
        """

        collection = self._validate_collection(
            collection
        )

        self._validate_data(
            data
        )

        try:
            if document_id is not None:
                document_id = self._validate_document_id(
                    document_id
                )

                reference = (
                    self.db
                    .collection(collection)
                    .document(document_id)
                )

                reference.create(
                    data
                )

                return reference.id

            reference = (
                self.db
                .collection(collection)
                .document()
            )

            reference.create(
                data
            )

            return reference.id

        except Exception as exc:
            raise FirebaseServiceError(
                f"Failed to create Firestore document in "
                f"{collection}: {exc}"
            ) from exc

    def set_document(
        self,
        collection: str,
        document_id: str,
        data: dict[str, Any],
        merge: bool = False,
    ) -> None:
        """
        Create or replace a Firestore document.

        merge=True updates only the supplied fields.
        merge=False replaces the document.
        """

        collection = self._validate_collection(
            collection
        )

        document_id = self._validate_document_id(
            document_id
        )

        self._validate_data(
            data
        )

        try:
            (
                self.db
                .collection(collection)
                .document(document_id)
                .set(
                    data,
                    merge=merge,
                )
            )

        except Exception as exc:
            raise FirebaseServiceError(
                f"Failed to write Firestore document "
                f"{collection}/{document_id}: {exc}"
            ) from exc

    def update_document(
        self,
        collection: str,
        document_id: str,
        data: dict[str, Any],
    ) -> None:
        """
        Update fields in an existing Firestore document.
        """

        collection = self._validate_collection(
            collection
        )

        document_id = self._validate_document_id(
            document_id
        )

        self._validate_data(
            data
        )

        try:
            (
                self.db
                .collection(collection)
                .document(document_id)
                .update(
                    data
                )
            )

        except Exception as exc:
            raise FirebaseServiceError(
                f"Failed to update Firestore document "
                f"{collection}/{document_id}: {exc}"
            ) from exc

    def delete_document(
        self,
        collection: str,
        document_id: str,
    ) -> None:
        """
        Delete a Firestore document.
        """

        collection = self._validate_collection(
            collection
        )

        document_id = self._validate_document_id(
            document_id
        )

        try:
            (
                self.db
                .collection(collection)
                .document(document_id)
                .delete()
            )

        except Exception as exc:
            raise FirebaseServiceError(
                f"Failed to delete Firestore document "
                f"{collection}/{document_id}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Collection Operations
    # ------------------------------------------------------------------

    def list_documents(
        self,
        collection: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve documents from a Firestore collection.
        """

        collection = self._validate_collection(
            collection
        )

        if limit is not None:
            if not isinstance(
                limit,
                int,
            ) or limit <= 0:
                raise FirebaseServiceError(
                    "Limit must be a positive integer."
                )

        try:
            query = self.db.collection(
                collection
            )

            if limit is not None:
                query = query.limit(
                    limit
                )

            documents = query.stream()

            results: list[dict[str, Any]] = []

            for document in documents:
                data = document.to_dict()

                if data is None:
                    data = {}

                results.append(
                    {
                        "id": document.id,
                        **data,
                    }
                )

            return results

        except Exception as exc:
            raise FirebaseServiceError(
                f"Failed to list Firestore collection "
                f"{collection}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Query Operations
    # ------------------------------------------------------------------

    def query_documents(
        self,
        collection: str,
        field: str,
        operator: str,
        value: Any,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Query a Firestore collection using a single condition.

        Example:

            query_documents(
                collection="jobs",
                field="created_by",
                operator="==",
                value="user123",
            )
        """

        collection = self._validate_collection(
            collection
        )

        field = self._validate_field(
            field
        )

        if not isinstance(
            operator,
            str,
        ) or not operator.strip():
            raise FirebaseServiceError(
                "Query operator must be a non-empty string."
            )

        if limit is not None:
            if not isinstance(
                limit,
                int,
            ) or limit <= 0:
                raise FirebaseServiceError(
                    "Limit must be a positive integer."
                )

        try:
            query = (
                self.db
                .collection(collection)
                .where(
                    filter=firestore.FieldFilter(
                        field,
                        operator,
                        value,
                    )
                )
            )

            if limit is not None:
                query = query.limit(
                    limit
                )

            documents = query.stream()

            results: list[dict[str, Any]] = []

            for document in documents:
                data = document.to_dict()

                if data is None:
                    data = {}

                results.append(
                    {
                        "id": document.id,
                        **data,
                    }
                )

            return results

        except Exception as exc:
            raise FirebaseServiceError(
                f"Failed to query Firestore collection "
                f"{collection}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def serialize_service_account(
        service_account: dict[str, Any],
    ) -> str:
        """
        Serialize a Firebase service-account dictionary to JSON.

        This helper exists for configuration/integration code that needs
        to pass the credential through an environment variable.

        It does NOT persist credentials anywhere.
        """

        if not isinstance(
            service_account,
            dict,
        ):
            raise FirebaseServiceError(
                "Firebase service account must be a dictionary."
            )

        try:
            return json.dumps(
                service_account
            )

        except (TypeError, ValueError) as exc:
            raise FirebaseServiceError(
                "Firebase service account could not be serialized."
            ) from exc

    # ------------------------------------------------------------------
    # Validation Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_collection(
        collection: str,
    ) -> str:
        """
        Validate a Firestore collection name.
        """

        if not isinstance(
            collection,
            str,
        ):
            raise FirebaseServiceError(
                "Collection name must be a string."
            )

        normalized = collection.strip()

        if not normalized:
            raise FirebaseServiceError(
                "Collection name must not be empty."
            )

        if "/" in normalized:
            raise FirebaseServiceError(
                "Collection name must contain only one collection "
                "path segment."
            )

        return normalized

    @staticmethod
    def _validate_document_id(
        document_id: str,
    ) -> str:
        """
        Validate a Firestore document ID.
        """

        if not isinstance(
            document_id,
            str,
        ):
            raise FirebaseServiceError(
                "Document ID must be a string."
            )

        normalized = document_id.strip()

        if not normalized:
            raise FirebaseServiceError(
                "Document ID must not be empty."
            )

        if "/" in normalized:
            raise FirebaseServiceError(
                "Document ID must not contain '/'."
            )

        return normalized

    @staticmethod
    def _validate_field(
        field: str,
    ) -> str:
        """
        Validate a Firestore field path.
        """

        if not isinstance(
            field,
            str,
        ):
            raise FirebaseServiceError(
                "Firestore field name must be a string."
            )

        normalized = field.strip()

        if not normalized:
            raise FirebaseServiceError(
                "Firestore field name must not be empty."
            )

        return normalized

    @staticmethod
    def _validate_data(
        data: dict[str, Any],
    ) -> None:
        """
        Validate Firestore document data.
        """

        if not isinstance(
            data,
            dict,
        ):
            raise FirebaseServiceError(
                "Firestore document data must be a dictionary."
            )