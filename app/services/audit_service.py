
from __future__ import annotations

from typing import Any

from app.core.audit_repository import (
    AuditRepository,
    AuditRepositoryError,
)


class AuditServiceError(RuntimeError):
    """
    Raised when an audit service operation fails.
    """


class AuditService:
    """
    Application service responsible for audit-log operations.

    Responsibilities:
        - Create audit records.
        - Retrieve candidate audit history.
        - Retrieve job audit history.
        - Retrieve all audit records.

    This service does NOT:
        - Modify candidate records.
        - Perform candidate scoring.
        - Perform categorization.
        - Call the LLM.
        - Authenticate users.
    """

    def __init__(
        self,
        repository: AuditRepository | None = None,
    ) -> None:
        """
        Initialize the audit service.

        A repository can be injected for testing.
        """

        self.repository = (
            repository
            or AuditRepository()
        )

    # ------------------------------------------------------------------
    # Create Audit Event
    # ------------------------------------------------------------------

    def create_audit_event(
        self,
        *,
        candidate_id: str,
        job_id: str,
        actor_id: str,
        action: str,
        previous_category: str | None = None,
        new_category: str | None = None,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create and persist one audit event.
        """

        normalized_candidate_id = self._normalize_id(
            candidate_id,
            "Candidate ID",
        )

        normalized_job_id = self._normalize_id(
            job_id,
            "Job ID",
        )

        normalized_actor_id = self._normalize_id(
            actor_id,
            "Actor ID",
        )

        normalized_action = self._normalize_text(
            action,
            "Audit action",
        )

        if previous_category is not None:
            previous_category = self._normalize_text(
                previous_category,
                "Previous category",
            )

        if new_category is not None:
            new_category = self._normalize_text(
                new_category,
                "New category",
            )

        if reason is not None:
            reason = self._normalize_text(
                reason,
                "Reason",
            )

        if metadata is not None and not isinstance(
            metadata,
            dict,
        ):
            raise AuditServiceError(
                "Audit metadata must be a dictionary."
            )

        try:
            return self.repository.create(
                candidate_id=normalized_candidate_id,
                job_id=normalized_job_id,
                actor_id=normalized_actor_id,
                action=normalized_action,
                previous_category=previous_category,
                new_category=new_category,
                reason=reason,
                metadata=metadata,
            )

        except AuditRepositoryError as exc:
            raise AuditServiceError(
                f"Unable to create audit event: {exc}"
            ) from exc

        except Exception as exc:
            raise AuditServiceError(
                f"Unexpected audit creation failure: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Candidate Audit History
    # ------------------------------------------------------------------

    def get_candidate_audit_history(
        self,
        candidate_id: str,
    ) -> list[dict[str, Any]]:
        """
        Return the complete audit history for one candidate.
        """

        normalized_candidate_id = self._normalize_id(
            candidate_id,
            "Candidate ID",
        )

        try:
            return self.repository.get_by_candidate(
                normalized_candidate_id
            )

        except AuditRepositoryError as exc:
            raise AuditServiceError(
                "Unable to retrieve audit history for candidate "
                f"'{normalized_candidate_id}': {exc}"
            ) from exc

        except Exception as exc:
            raise AuditServiceError(
                "Unexpected candidate audit retrieval failure: "
                f"{exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Job Audit History
    # ------------------------------------------------------------------

    def get_job_audit_history(
        self,
        job_id: str,
    ) -> list[dict[str, Any]]:
        """
        Return all audit events associated with a job.
        """

        normalized_job_id = self._normalize_id(
            job_id,
            "Job ID",
        )

        try:
            return self.repository.get_by_job(
                normalized_job_id
            )

        except AuditRepositoryError as exc:
            raise AuditServiceError(
                f"Unable to retrieve audit history for job "
                f"'{normalized_job_id}': {exc}"
            ) from exc

        except Exception as exc:
            raise AuditServiceError(
                "Unexpected job audit retrieval failure: "
                f"{exc}"
            ) from exc

    # ------------------------------------------------------------------
    # All Audit History
    # ------------------------------------------------------------------

    def get_all_audit_events(
        self,
    ) -> list[dict[str, Any]]:
        """
        Return all audit events.

        Intended primarily for administrative and debugging
        purposes.
        """

        try:
            return self.repository.get_all()

        except AuditRepositoryError as exc:
            raise AuditServiceError(
                f"Unable to retrieve audit events: {exc}"
            ) from exc

        except Exception as exc:
            raise AuditServiceError(
                f"Unexpected audit retrieval failure: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_id(
        value: str,
        field_name: str,
    ) -> str:
        """
        Validate and normalize an identifier.
        """

        if not isinstance(
            value,
            str,
        ):
            raise AuditServiceError(
                f"{field_name} must be a non-empty string."
            )

        normalized = value.strip()

        if not normalized:
            raise AuditServiceError(
                f"{field_name} must be a non-empty string."
            )

        return normalized

    @staticmethod
    def _normalize_text(
        value: str,
        field_name: str,
    ) -> str:
        """
        Validate and normalize required text.
        """

        if not isinstance(
            value,
            str,
        ):
            raise AuditServiceError(
                f"{field_name} must be a non-empty string."
            )

        normalized = value.strip()

        if not normalized:
            raise AuditServiceError(
                f"{field_name} must be a non-empty string."
            )

        return normalized
