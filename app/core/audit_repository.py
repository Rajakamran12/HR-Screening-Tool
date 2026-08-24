
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from firebase_admin import firestore

from app.core.firebase import initialize_firebase


class AuditRepositoryError(RuntimeError):
    """
    Raised when an audit-log persistence operation fails.
    """


class AuditRepository:
    """
    Firestore-backed repository for HR screening audit events.

    Responsibilities:
        - Store immutable audit events.
        - Retrieve audit events for a candidate.
        - Retrieve audit events for a job.

    This repository does NOT:
        - Decide candidate categories.
        - Perform candidate overrides.
        - Call the LLM.
        - Modify candidate records.
    """

    COLLECTION_NAME = "audit_logs"

    def __init__(
        self,
        client: Any | None = None,
    ) -> None:
        """
        Initialize the audit repository.

        Args:
            client:
                Optional Firestore client.

                Primarily useful for testing. When omitted,
                the application's Firebase initialization is used.
        """

        if client is not None:
            self._client = client

        else:
            try:
                initialize_firebase()
                self._client = firestore.client()

            except Exception as exc:
                raise AuditRepositoryError(
                    f"Unable to initialize Firestore: {exc}"
                ) from exc

        self._collection = self._client.collection(
            self.COLLECTION_NAME
        )

    # ------------------------------------------------------------------
    # Create Audit Event
    # ------------------------------------------------------------------

    def create(
        self,
        *,
        candidate_id: str,
        job_id: str,
        action: str,
        actor_id: str,
        previous_category: str | None = None,
        new_category: str | None = None,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Store one audit event.

        Audit events are append-only. Existing events are never
        modified by this repository.
        """

        normalized_candidate_id = self._normalize_required(
            candidate_id,
            "Candidate ID",
        )

        normalized_job_id = self._normalize_required(
            job_id,
            "Job ID",
        )

        normalized_action = self._normalize_required(
            action,
            "Audit action",
        )

        normalized_actor_id = self._normalize_required(
            actor_id,
            "Actor ID",
        )

        if previous_category is not None:
            previous_category = self._normalize_required(
                previous_category,
                "Previous category",
            )

        if new_category is not None:
            new_category = self._normalize_required(
                new_category,
                "New category",
            )

        if reason is not None:
            if not isinstance(reason, str):
                raise AuditRepositoryError(
                    "Audit reason must be a string."
                )

            reason = reason.strip()

            if not reason:
                raise AuditRepositoryError(
                    "Audit reason must not be empty."
                )

        if metadata is not None and not isinstance(
            metadata,
            dict,
        ):
            raise AuditRepositoryError(
                "Audit metadata must be a dictionary."
            )

        audit_reference = self._collection.document()

        document = {
            "audit_id": audit_reference.id,
            "candidate_id": normalized_candidate_id,
            "job_id": normalized_job_id,
            "action": normalized_action,
            "actor_id": normalized_actor_id,
            "previous_category": previous_category,
            "new_category": new_category,
            "reason": reason,
            "metadata": metadata or {},
            "created_at": firestore.SERVER_TIMESTAMP,
        }

        try:
            audit_reference.set(
                document
            )

        except Exception as exc:
            raise AuditRepositoryError(
                f"Unable to store audit event: {exc}"
            ) from exc

        # SERVER_TIMESTAMP has not necessarily been resolved in the
        # local object yet, therefore return a JSON-safe representation.
        return {
            **document,
            "created_at": None,
        }

    # ------------------------------------------------------------------
    # Retrieve Candidate Audit History
    # ------------------------------------------------------------------

    def get_by_candidate(
        self,
        candidate_id: str,
    ) -> list[dict[str, Any]]:
        """
        Return all audit events associated with a candidate.

        Events are returned oldest first so the complete decision
        history can be reconstructed chronologically.
        """

        normalized_candidate_id = self._normalize_required(
            candidate_id,
            "Candidate ID",
        )

        try:
            query = self._collection.where(
                filter=firestore.FieldFilter(
                    "candidate_id",
                    "==",
                    normalized_candidate_id,
                )
            )

            snapshots = query.stream()

            events: list[dict[str, Any]] = []

            for snapshot in snapshots:
                data = snapshot.to_dict()

                if isinstance(
                    data,
                    dict,
                ):
                    events.append(data)

            events.sort(
                key=self._audit_sort_key
            )

            return events

        except Exception as exc:
            raise AuditRepositoryError(
                "Unable to retrieve audit history for candidate "
                f"'{normalized_candidate_id}': {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Retrieve Job Audit History
    # ------------------------------------------------------------------

    def get_by_job(
        self,
        job_id: str,
    ) -> list[dict[str, Any]]:
        """
        Return all audit events associated with a job.
        """

        normalized_job_id = self._normalize_required(
            job_id,
            "Job ID",
        )

        try:
            query = self._collection.where(
                filter=firestore.FieldFilter(
                    "job_id",
                    "==",
                    normalized_job_id,
                )
            )

            snapshots = query.stream()

            events: list[dict[str, Any]] = []

            for snapshot in snapshots:
                data = snapshot.to_dict()

                if isinstance(
                    data,
                    dict,
                ):
                    events.append(data)

            events.sort(
                key=self._audit_sort_key
            )

            return events

        except Exception as exc:
            raise AuditRepositoryError(
                "Unable to retrieve audit history for job "
                f"'{normalized_job_id}': {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_required(
        value: str,
        field_name: str,
    ) -> str:
        """
        Validate and normalize a required string field.
        """

        if not isinstance(
            value,
            str,
        ):
            raise AuditRepositoryError(
                f"{field_name} must be a non-empty string."
            )

        normalized = value.strip()

        if not normalized:
            raise AuditRepositoryError(
                f"{field_name} must be a non-empty string."
            )

        return normalized

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------

    @staticmethod
    def _audit_sort_key(
        event: dict[str, Any],
    ) -> datetime:
        """
        Return a safe chronological sort key.

        Firestore timestamps are normally datetime objects.
        Missing or unexpected values are placed at the beginning.
        """

        value = event.get(
            "created_at"
        )

        if isinstance(
            value,
            datetime,
        ):
            return value

        return datetime.min.replace(
            tzinfo=timezone.utc
        )
