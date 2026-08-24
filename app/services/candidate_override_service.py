from __future__ import annotations

import uuid
from typing import Any

from app.core.audit_repository import (
    AuditRepository,
    AuditRepositoryError,
)
from app.core.candidate_repository import (
    CandidateRepository,
    CandidateRepositoryError,
)
from app.schemas.audit_schema import (
    AuditAction,
    CandidateAuditRecord,
    CandidateCategory,
    CandidateOverrideRequest,
)


class CandidateOverrideServiceError(RuntimeError):
    """
    Raised when a candidate override operation fails.
    """


class CandidateOverrideService:
    """
    Service responsible for human candidate categorization overrides.

    Core principle:

        AI recommendation
                ↓
        Human review
                ↓
        Optional override
                ↓
        Audit record

    The AI-generated score and original categorization are never
    silently replaced. The human decision is stored separately.
    """

    def __init__(
        self,
        candidate_repository: CandidateRepository | None = None,
        audit_repository: AuditRepository | None = None,
    ) -> None:
        """
        Initialize the override service.
        """

        self.candidate_repository = (
            candidate_repository
            or CandidateRepository()
        )

        self.audit_repository = (
            audit_repository
            or AuditRepository()
        )

    # ------------------------------------------------------------------
    # Override Candidate
    # ------------------------------------------------------------------

    def override_candidate(
        self,
        *,
        candidate_id: str,
        request: CandidateOverrideRequest,
        performed_by: str,
    ) -> dict[str, Any]:
        """
        Manually override a candidate's category.

        The operation:

            1. Validates the candidate.
            2. Reads the existing candidate.
            3. Determines the current effective category.
            4. Validates the requested category.
            5. Updates the human override fields.
            6. Creates an immutable audit record.
            7. Returns the updated candidate.

        Args:
            candidate_id:
                Candidate being overridden.

            request:
                Requested category and mandatory reason.

            performed_by:
                Recruiter/user identifier responsible for
                the decision.
        """

        normalized_candidate_id = self._normalize_id(
            candidate_id,
            "Candidate ID",
        )

        normalized_performed_by = self._normalize_id(
            performed_by,
            "Performed by",
        )

        if not isinstance(
            request,
            CandidateOverrideRequest,
        ):
            raise CandidateOverrideServiceError(
                "Override request must be a valid "
                "CandidateOverrideRequest object."
            )

        reason = request.reason.strip()

        if not reason:
            raise CandidateOverrideServiceError(
                "An override reason is required."
            )

        # --------------------------------------------------------------
        # Retrieve candidate
        # --------------------------------------------------------------

        try:
            candidate = self.candidate_repository.get(
                normalized_candidate_id
            )

        except CandidateRepositoryError as exc:
            raise CandidateOverrideServiceError(
                f"Unable to retrieve candidate: {exc}"
            ) from exc

        if not isinstance(
            candidate,
            dict,
        ):
            raise CandidateOverrideServiceError(
                "Stored candidate data is invalid."
            )

        # --------------------------------------------------------------
        # Retrieve job ID
        # --------------------------------------------------------------

        job_id = candidate.get(
            "job_id"
        )

        if not isinstance(
            job_id,
            str,
        ) or not job_id.strip():
            raise CandidateOverrideServiceError(
                "Candidate does not contain a valid Job ID."
            )

        normalized_job_id = job_id.strip()

        # --------------------------------------------------------------
        # Determine current category
        # --------------------------------------------------------------

        current_category = self._extract_current_category(
            candidate
        )

        new_category = request.category

        # --------------------------------------------------------------
        # Prevent meaningless override
        # --------------------------------------------------------------

        if current_category == new_category:
            raise CandidateOverrideServiceError(
                "The requested category is already the candidate's "
                "current effective category."
            )

        # --------------------------------------------------------------
        # Update candidate
        # --------------------------------------------------------------

        update_data = {
            "human_override": {
                "category": new_category.value,
                "reason": reason,
                "performed_by": normalized_performed_by,
            },
            "effective_category": new_category.value,
        }

        try:
            updated_candidate = (
                self.candidate_repository.update(
                    normalized_candidate_id,
                    update_data,
                )
            )

        except CandidateRepositoryError as exc:
            raise CandidateOverrideServiceError(
                f"Unable to apply candidate override: {exc}"
            ) from exc

        # --------------------------------------------------------------
        # Create audit record
        # --------------------------------------------------------------

        audit_record = CandidateAuditRecord(
            audit_id=str(
                uuid.uuid4()
            ),
            candidate_id=normalized_candidate_id,
            job_id=normalized_job_id,
            action=AuditAction.CATEGORIZATION_OVERRIDE,
            previous_category=current_category,
            new_category=new_category,
            reason=reason,
            performed_by=normalized_performed_by,
        )

        try:
            self.audit_repository.save(
                audit_record
            )

        except AuditRepositoryError as exc:
            # Do not silently report success when the audit trail
            # could not be persisted.
            raise CandidateOverrideServiceError(
                "Candidate override was applied, but the required "
                f"audit record could not be stored: {exc}"
            ) from exc

        return updated_candidate

    # ------------------------------------------------------------------
    # Retrieve Candidate Audit History
    # ------------------------------------------------------------------

    def get_candidate_audit_history(
        self,
        candidate_id: str,
    ) -> list[dict[str, Any]]:
        """
        Return the complete audit history for a candidate.
        """

        normalized_candidate_id = self._normalize_id(
            candidate_id,
            "Candidate ID",
        )

        try:
            return self.audit_repository.get_by_candidate(
                normalized_candidate_id
            )

        except AuditRepositoryError as exc:
            raise CandidateOverrideServiceError(
                f"Unable to retrieve candidate audit history: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Retrieve Job Audit History
    # ------------------------------------------------------------------

    def get_job_audit_history(
        self,
        job_id: str,
    ) -> list[dict[str, Any]]:
        """
        Return all audit records belonging to a job.
        """

        normalized_job_id = self._normalize_id(
            job_id,
            "Job ID",
        )

        try:
            return self.audit_repository.get_by_job(
                normalized_job_id
            )

        except AuditRepositoryError as exc:
            raise CandidateOverrideServiceError(
                f"Unable to retrieve job audit history: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Current Category
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_current_category(
        candidate: dict[str, Any],
    ) -> CandidateCategory:
        """
        Determine the candidate's current effective category.

        Human override takes precedence over the original
        deterministic categorization.
        """

        effective_category = candidate.get(
            "effective_category"
        )

        if isinstance(
            effective_category,
            str,
        ):
            try:
                return CandidateCategory(
                    effective_category
                )
            except ValueError:
                pass

        human_override = candidate.get(
            "human_override"
        )

        if isinstance(
            human_override,
            dict,
        ):
            override_category = human_override.get(
                "category"
            )

            if isinstance(
                override_category,
                str,
            ):
                try:
                    return CandidateCategory(
                        override_category
                    )
                except ValueError:
                    pass

        categorization = candidate.get(
            "categorization"
        )

        if isinstance(
            categorization,
            dict,
        ):
            category = categorization.get(
                "category"
            )

            if isinstance(
                category,
                str,
            ):
                try:
                    return CandidateCategory(
                        category
                    )
                except ValueError:
                    pass

        raise CandidateOverrideServiceError(
            "Candidate does not contain a valid current category."
        )

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
            raise CandidateOverrideServiceError(
                f"{field_name} must be a non-empty string."
            )

        normalized = value.strip()

        if not normalized:
            raise CandidateOverrideServiceError(
                f"{field_name} must be a non-empty string."
            )

        return normalized
    