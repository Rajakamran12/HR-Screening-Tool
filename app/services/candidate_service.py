
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.audit_repository import (
    AuditRepository,
    AuditRepositoryError,
)
from app.core.candidate_repository import (
    CandidateRepository,
    CandidateRepositoryError,
)
from app.pipeline.screening_pipeline import (
    ScreeningPipeline,
    ScreeningPipelineError,
    ScreeningResult,
)
from app.schemas.categorization_schema import (
    CandidateCategory,
)
from app.schemas.job_schema import (
    JobCriterion,
    JobThresholds,
)
from app.schemas.scoring_schema import (
    ScreeningCriterion,
)


class CandidateServiceError(RuntimeError):
    """
    Raised when a candidate screening service operation fails.
    """


class CandidateService:
    """
    Application service responsible for candidate screening,
    persistence, human overrides, and candidate retrieval.

    Responsibilities:
        - Execute the existing ScreeningPipeline.
        - Persist completed screening results.
        - Retrieve persisted candidates.
        - Retrieve candidates belonging to a job.
        - Update candidate records.
        - Delete candidate records.
        - Apply explicit human category overrides.
        - Create an audit event for every human override.
        - Process individual candidates for bulk screening.

    This service does NOT:
        - Parse CV files directly.
        - Extract CV information directly.
        - Call the LLM directly.
        - Perform AI categorization directly.

    Those responsibilities remain inside their established
    components.
    """

    def __init__(
        self,
        pipeline: ScreeningPipeline | None = None,
        repository: CandidateRepository | None = None,
        audit_repository: AuditRepository | None = None,
    ) -> None:
        """
        Initialize the candidate service.

        Dependencies can be injected for testing and for sharing
        configured application instances.
        """

        self.pipeline = (
            pipeline
            or ScreeningPipeline()
        )

        self.repository = (
            repository
            or CandidateRepository()
        )

        self.audit_repository = (
            audit_repository
            or AuditRepository()
        )

    # ------------------------------------------------------------------
    # Screen And Persist Candidate
    # ------------------------------------------------------------------

    async def screen_candidate(
        self,
        *,
        candidate_id: str,
        job_id: str,
        cv_file: str | Path,
        filename: str,
        criteria: (
            list[dict[str, Any]]
            | list[JobCriterion]
            | list[ScreeningCriterion]
        ),
        thresholds: JobThresholds,
    ) -> dict[str, Any]:
        """
        Run the complete screening pipeline and persist the result.

        This is the primary single-candidate screening operation.
        """

        normalized_candidate_id = self._normalize_id(
            candidate_id,
            "Candidate ID",
        )

        normalized_job_id = self._normalize_id(
            job_id,
            "Job ID",
        )

        normalized_filename = self._normalize_filename(
            filename
        )

        self._validate_cv_file(
            cv_file
        )

        try:
            result = await self.pipeline.screen(
                cv_file=cv_file,
                criteria=criteria,
                thresholds=thresholds,
            )

        except ScreeningPipelineError as exc:
            raise CandidateServiceError(
                f"Candidate screening failed: {exc}"
            ) from exc

        except Exception as exc:
            raise CandidateServiceError(
                f"Unexpected candidate screening failure: {exc}"
            ) from exc

        if not isinstance(
            result,
            ScreeningResult,
        ):
            raise CandidateServiceError(
                "Screening pipeline returned an invalid "
                "ScreeningResult object."
            )

        candidate_data = result.candidate.model_dump(
            mode="json"
        )

        try:
            return self.repository.save(
                candidate_id=normalized_candidate_id,
                job_id=normalized_job_id,
                filename=normalized_filename,
                candidate_data=candidate_data,
                score=result.candidate_score,
                categorization=result.categorization,
            )

        except CandidateRepositoryError as exc:
            raise CandidateServiceError(
                f"Unable to persist screened candidate: {exc}"
            ) from exc

        except Exception as exc:
            raise CandidateServiceError(
                f"Unexpected candidate persistence failure: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Bulk Candidate Screening
    # ------------------------------------------------------------------

    async def screen_candidate_for_bulk(
        self,
        *,
        candidate_id: str,
        job_id: str,
        cv_file: str | Path,
        filename: str,
        criteria: (
            list[dict[str, Any]]
            | list[JobCriterion]
            | list[ScreeningCriterion]
        ),
        thresholds: JobThresholds,
    ) -> dict[str, Any]:
        """
        Screen one candidate as part of a bulk-processing operation.

        This method intentionally wraps the existing single-candidate
        screening operation instead of creating a second screening
        implementation.

        The important distinction is that bulk processing can call
        this method independently for every uploaded CV.

        Therefore, a failure for one candidate is converted into a
        structured failure result and does not need to terminate the
        entire batch.

        Returns:
            A structured result containing:

                candidate_id
                job_id
                filename
                status
                candidate

            or, when screening fails:

                candidate_id
                job_id
                filename
                status
                error
        """

        normalized_candidate_id = self._normalize_id(
            candidate_id,
            "Candidate ID",
        )

        normalized_job_id = self._normalize_id(
            job_id,
            "Job ID",
        )

        normalized_filename = self._normalize_filename(
            filename
        )

        try:
            result = await self.screen_candidate(
                candidate_id=normalized_candidate_id,
                job_id=normalized_job_id,
                cv_file=cv_file,
                filename=normalized_filename,
                criteria=criteria,
                thresholds=thresholds,
            )

            return {
                "candidate_id": normalized_candidate_id,
                "job_id": normalized_job_id,
                "filename": normalized_filename,
                "status": "completed",
                "candidate": result,
            }

        except CandidateServiceError as exc:
            return {
                "candidate_id": normalized_candidate_id,
                "job_id": normalized_job_id,
                "filename": normalized_filename,
                "status": "failed",
                "error": str(exc),
            }

        except Exception as exc:
            return {
                "candidate_id": normalized_candidate_id,
                "job_id": normalized_job_id,
                "filename": normalized_filename,
                "status": "failed",
                "error": (
                    "Unexpected bulk candidate processing failure: "
                    f"{exc}"
                ),
            }

    # ------------------------------------------------------------------
    # Human Override
    # ------------------------------------------------------------------

    def override_candidate(
        self,
        *,
        candidate_id: str,
        new_category: str | CandidateCategory,
        actor_id: str,
        reason: str,
    ) -> dict[str, Any]:
        """
        Override the AI-generated candidate category.

        This is the explicit human-in-the-loop decision point.

        The original AI score and categorization remain stored.
        The current category is updated, and an immutable audit
        event is created recording who made the change, when it
        happened, what changed, and why.
        """

        normalized_candidate_id = self._normalize_id(
            candidate_id,
            "Candidate ID",
        )

        normalized_actor_id = self._normalize_id(
            actor_id,
            "Actor ID",
        )

        normalized_reason = self._normalize_reason(
            reason
        )

        normalized_category = self._normalize_category(
            new_category
        )

        try:
            candidate = self.repository.get(
                normalized_candidate_id
            )

        except CandidateRepositoryError as exc:
            raise CandidateServiceError(
                f"Unable to retrieve candidate before override: {exc}"
            ) from exc

        current_category = self._extract_current_category(
            candidate
        )

        if current_category == normalized_category:
            raise CandidateServiceError(
                "Candidate is already in the requested category."
            )

        job_id = candidate.get(
            "job_id"
        )

        if not isinstance(
            job_id,
            str,
        ) or not job_id.strip():
            raise CandidateServiceError(
                "Candidate record does not contain a valid Job ID."
            )

        normalized_job_id = job_id.strip()

        update_data = {
            "category": normalized_category,
            "decision_source": "human_override",
            "override": {
                "actor_id": normalized_actor_id,
                "reason": normalized_reason,
                "previous_category": current_category,
                "new_category": normalized_category,
            },
        }

        try:
            updated_candidate = self.repository.update(
                normalized_candidate_id,
                update_data,
            )

        except CandidateRepositoryError as exc:
            raise CandidateServiceError(
                f"Unable to apply candidate override: {exc}"
            ) from exc

        try:
            self.audit_repository.create(
                candidate_id=normalized_candidate_id,
                job_id=normalized_job_id,
                action="candidate_category_override",
                actor_id=normalized_actor_id,
                previous_category=current_category,
                new_category=normalized_category,
                reason=normalized_reason,
                metadata={
                    "decision_source": "human_override",
                },
            )

        except AuditRepositoryError as exc:
            raise CandidateServiceError(
                "Candidate override was applied, but the audit "
                f"event could not be persisted: {exc}"
            ) from exc

        return updated_candidate

    # ------------------------------------------------------------------
    # Retrieve Candidate
    # ------------------------------------------------------------------

    def get_candidate(
        self,
        candidate_id: str,
    ) -> dict[str, Any]:
        """
        Retrieve one persisted candidate.
        """

        normalized_candidate_id = self._normalize_id(
            candidate_id,
            "Candidate ID",
        )

        try:
            return self.repository.get(
                normalized_candidate_id
            )

        except CandidateRepositoryError as exc:
            raise CandidateServiceError(
                f"Unable to retrieve candidate: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Check Candidate Exists
    # ------------------------------------------------------------------

    def candidate_exists(
        self,
        candidate_id: str,
    ) -> bool:
        """
        Return True when the candidate exists.
        """

        normalized_candidate_id = self._normalize_id(
            candidate_id,
            "Candidate ID",
        )

        try:
            return self.repository.exists(
                normalized_candidate_id
            )

        except CandidateRepositoryError as exc:
            raise CandidateServiceError(
                f"Unable to check candidate existence: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Retrieve All Candidates
    # ------------------------------------------------------------------

    def get_all_candidates(
        self,
    ) -> list[dict[str, Any]]:
        """
        Return all persisted candidates.
        """

        try:
            return self.repository.get_all()

        except CandidateRepositoryError as exc:
            raise CandidateServiceError(
                f"Unable to retrieve candidates: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Retrieve Candidates By Job
    # ------------------------------------------------------------------

    def get_candidates_by_job(
        self,
        job_id: str,
    ) -> list[dict[str, Any]]:
        """
        Return all candidates screened for a specific job.
        """

        normalized_job_id = self._normalize_id(
            job_id,
            "Job ID",
        )

        try:
            return self.repository.get_by_job(
                normalized_job_id
            )

        except CandidateRepositoryError as exc:
            raise CandidateServiceError(
                f"Unable to retrieve candidates for job "
                f"'{normalized_job_id}': {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Retrieve Candidate Audit History
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
            return self.audit_repository.get_by_candidate(
                normalized_candidate_id
            )

        except AuditRepositoryError as exc:
            raise CandidateServiceError(
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
        Return the audit history associated with a job.
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
            raise CandidateServiceError(
                f"Unable to retrieve job audit history: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Update Candidate
    # ------------------------------------------------------------------

    def update_candidate(
        self,
        candidate_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Update a persisted candidate record.

        Generic updates are retained for internal/application use.

        Category changes must use override_candidate() so that
        human decisions cannot bypass the audit trail.
        """

        normalized_candidate_id = self._normalize_id(
            candidate_id,
            "Candidate ID",
        )

        if not isinstance(
            updates,
            dict,
        ):
            raise CandidateServiceError(
                "Candidate updates must be provided as a dictionary."
            )

        if not updates:
            raise CandidateServiceError(
                "At least one candidate update is required."
            )

        if "category" in updates:
            raise CandidateServiceError(
                "Candidate category cannot be changed through the "
                "generic update operation. Use override_candidate() "
                "so the human decision is audited."
            )

        try:
            return self.repository.update(
                normalized_candidate_id,
                updates,
            )

        except CandidateRepositoryError as exc:
            raise CandidateServiceError(
                f"Unable to update candidate: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Delete Candidate
    # ------------------------------------------------------------------

    def delete_candidate(
        self,
        candidate_id: str,
    ) -> None:
        """
        Delete a persisted candidate.
        """

        normalized_candidate_id = self._normalize_id(
            candidate_id,
            "Candidate ID",
        )

        try:
            self.repository.delete(
                normalized_candidate_id
            )

        except CandidateRepositoryError as exc:
            raise CandidateServiceError(
                f"Unable to delete candidate: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Category Normalization
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_category(
        value: str | CandidateCategory,
    ) -> str:
        """
        Validate and normalize a candidate category.

        Only the three application categories are accepted.
        """

        if isinstance(
            value,
            CandidateCategory,
        ):
            return value.value

        if not isinstance(
            value,
            str,
        ):
            raise CandidateServiceError(
                "Candidate category must be a valid category string."
            )

        normalized = value.strip().lower()

        allowed_categories = {
            "shortlisted",
            "maybe",
            "rejected",
        }

        if normalized not in allowed_categories:
            raise CandidateServiceError(
                "Invalid candidate category. Allowed values are: "
                "Shortlisted, Maybe, Rejected."
            )

        return normalized

    @staticmethod
    def _extract_current_category(
        candidate: dict[str, Any],
    ) -> str:
        """
        Extract the candidate's currently active category.

        Human-overridden candidates use the top-level `category`.
        Original screening records use `categorization.category`.
        """

        category = candidate.get(
            "category"
        )

        if isinstance(
            category,
            str,
        ) and category.strip():
            return category.strip().lower()

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
            ) and category.strip():
                return category.strip().lower()

        raise CandidateServiceError(
            "Candidate record does not contain a valid current category."
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
            raise CandidateServiceError(
                f"{field_name} must be a non-empty string."
            )

        normalized = value.strip()

        if not normalized:
            raise CandidateServiceError(
                f"{field_name} must be a non-empty string."
            )

        return normalized

    @staticmethod
    def _normalize_filename(
        filename: str,
    ) -> str:
        """
        Validate and normalize the uploaded CV filename.
        """

        if not isinstance(
            filename,
            str,
        ):
            raise CandidateServiceError(
                "Filename must be a non-empty string."
            )

        normalized = filename.strip()

        if not normalized:
            raise CandidateServiceError(
                "Filename must be a non-empty string."
            )

        return normalized

    @staticmethod
    def _normalize_reason(
        reason: str,
    ) -> str:
        """
        Validate the mandatory human override reason.
        """

        if not isinstance(
            reason,
            str,
        ):
            raise CandidateServiceError(
                "Override reason must be a non-empty string."
            )

        normalized = reason.strip()

        if not normalized:
            raise CandidateServiceError(
                "Override reason must be a non-empty string."
            )

        if len(normalized) > 2000:
            raise CandidateServiceError(
                "Override reason cannot exceed 2000 characters."
            )

        return normalized

    @staticmethod
    def _validate_cv_file(
        cv_file: str | Path,
    ) -> None:
        """
        Validate that the supplied CV path exists and is a file.

        The actual CV format validation and parsing remain the
        responsibility of CVParser.
        """

        if not isinstance(
            cv_file,
            (str, Path),
        ):
            raise CandidateServiceError(
                "CV file must be a valid file path."
            )

        path = Path(
            cv_file
        )

        if not path.exists():
            raise CandidateServiceError(
                f"CV file does not exist: {path}"
            )

        if not path.is_file():
            raise CandidateServiceError(
                f"CV file path is not a file: {path}"
            )
