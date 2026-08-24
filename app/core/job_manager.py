from datetime import datetime, timezone
from typing import Iterable

from pydantic import ValidationError

from app.core.job_repository import (
    JobRepository,
    JobRepositoryError,
)
from app.schemas.job_schema import (
    Job,
    JobCriterion,
    JobStatus,
    JobThresholds,
)


class JobManagerError(RuntimeError):
    """
    Raised when a job management operation cannot be completed.
    """


class JobManager:
    """
    Deterministic job management service.

    Responsibilities:
        - Create validated Job objects.
        - Retrieve jobs.
        - Update jobs.
        - Change job status.
        - Delete jobs.
        - Validate criteria and thresholds through Job schemas.
        - Delegate job storage to JobRepository.

    This class does NOT:
        - Call an LLM.
        - Score candidates.
        - Parse CVs.
        - Extract candidate information.
        - Categorize candidates.

    Business logic remains in JobManager while persistence is
    delegated to JobRepository.
    """

    def __init__(
        self,
        jobs: dict[str, Job] | None = None,
        repository: JobRepository | None = None,
    ) -> None:
        """
        Initialize the job manager.

        Args:
            jobs:
                Optional initial jobs.

                This argument is retained for backwards compatibility
                with the existing JobManager interface.

            repository:
                Optional JobRepository instance.

                If supplied, the manager uses that repository.
                Otherwise a new in-memory repository is created.

        Raises:
            JobManagerError:
                If both jobs and a repository are supplied.
        """

        if jobs is not None and repository is not None:
            raise JobManagerError(
                "Provide either initial jobs or a repository, "
                "not both."
            )

        if repository is not None:
            if not isinstance(
                repository,
                JobRepository,
            ):
                raise JobManagerError(
                    "Repository must be a valid JobRepository object."
                )

            self._repository = repository

        else:
            self._repository = JobRepository(
                jobs
            )

    # ------------------------------------------------------------------
    # Job Creation
    # ------------------------------------------------------------------

    def create_job(
        self,
        *,
        job_id: str,
        title: str,
        description: str,
        criteria: Iterable[JobCriterion],
        thresholds: JobThresholds,
        created_by: str,
        status: JobStatus = "draft",
    ) -> Job:
        """
        Create and register a new validated Job.

        Raises:
            JobManagerError:
                If the job ID already exists or the supplied job data
                is invalid.
        """

        if not isinstance(
            job_id,
            str,
        ) or not job_id.strip():
            raise JobManagerError(
                "Job ID must be a non-empty string."
            )

        normalized_job_id = job_id.strip()

        if self.job_exists(
            normalized_job_id
        ):
            raise JobManagerError(
                f"A job with ID '{normalized_job_id}' already exists."
            )

        criteria_list = self._validate_criteria(
            criteria
        )

        validated_thresholds = self._validate_thresholds(
            thresholds
        )

        self._validate_status(
            status
        )

        timestamp = self._current_timestamp()

        try:
            job = Job(
                job_id=normalized_job_id,
                title=title,
                description=description,
                criteria=criteria_list,
                thresholds=validated_thresholds,
                created_by=created_by,
                created_at=timestamp,
                updated_at=timestamp,
                status=status,
            )

        except ValidationError as exc:
            raise JobManagerError(
                f"Invalid job configuration: {exc}"
            ) from exc

        try:
            self._repository.save(
                job
            )

        except JobRepositoryError as exc:
            raise JobManagerError(
                f"Unable to store job: {exc}"
            ) from exc

        return job

    # ------------------------------------------------------------------
    # Job Retrieval
    # ------------------------------------------------------------------

    def get_job(
        self,
        job_id: str,
    ) -> Job:
        """
        Retrieve a job by ID.

        Raises:
            JobManagerError:
                If the job does not exist.
        """

        normalized_job_id = self._normalize_job_id(
            job_id
        )

        try:
            return self._repository.get(
                normalized_job_id
            )

        except JobRepositoryError as exc:
            raise JobManagerError(
                str(exc)
            ) from exc

    def get_all_jobs(self) -> list[Job]:
        """
        Return all registered jobs.

        Jobs are returned in repository insertion order.
        """

        return self._repository.get_all()

    def get_jobs_by_status(
        self,
        status: JobStatus,
    ) -> list[Job]:
        """
        Return all jobs having the requested status.
        """

        self._validate_status(
            status
        )

        return self._repository.find_by_status(
            status
        )

    # ------------------------------------------------------------------
    # Job Existence
    # ------------------------------------------------------------------

    def job_exists(
        self,
        job_id: str,
    ) -> bool:
        """
        Return True if a job with the supplied ID exists.
        """

        normalized_job_id = self._normalize_job_id(
            job_id
        )

        return self._repository.exists(
            normalized_job_id
        )

    # ------------------------------------------------------------------
    # Job Update
    # ------------------------------------------------------------------

    def update_job(
        self,
        job_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        criteria: Iterable[JobCriterion] | None = None,
        thresholds: JobThresholds | None = None,
        created_by: str | None = None,
        status: JobStatus | None = None,
    ) -> Job:
        """
        Update supplied fields of an existing job.

        Fields that are not supplied remain unchanged.

        All supplied values are validated before the updated Job is
        stored.
        """

        existing_job = self.get_job(
            job_id
        )

        updated_title = (
            existing_job.title
            if title is None
            else title
        )

        updated_description = (
            existing_job.description
            if description is None
            else description
        )

        if criteria is None:
            updated_criteria = list(
                existing_job.criteria
            )
        else:
            try:
                updated_criteria = self._validate_criteria(
                    criteria
                )

            except JobManagerError as exc:
                raise JobManagerError(
                    f"Invalid updated job configuration: {exc}"
                ) from exc

        if thresholds is None:
            updated_thresholds = existing_job.thresholds
        else:
            try:
                updated_thresholds = self._validate_thresholds(
                    thresholds
                )

            except JobManagerError as exc:
                raise JobManagerError(
                    f"Invalid updated job configuration: {exc}"
                ) from exc

        updated_created_by = (
            existing_job.created_by
            if created_by is None
            else created_by
        )

        updated_status = (
            existing_job.status
            if status is None
            else status
        )

        try:
            self._validate_status(
                updated_status
            )

        except JobManagerError as exc:
            raise JobManagerError(
                f"Invalid updated job configuration: {exc}"
            ) from exc

        timestamp = self._current_timestamp()

        try:
            updated_job = Job(
                job_id=existing_job.job_id,
                title=updated_title,
                description=updated_description,
                criteria=updated_criteria,
                thresholds=updated_thresholds,
                created_by=updated_created_by,
                created_at=existing_job.created_at,
                updated_at=timestamp,
                status=updated_status,
            )

        except ValidationError as exc:
            raise JobManagerError(
                f"Invalid updated job configuration: {exc}"
            ) from exc

        try:
            self._repository.save(
                updated_job
            )

        except JobRepositoryError as exc:
            raise JobManagerError(
                f"Unable to update job: {exc}"
            ) from exc

        return updated_job

    # ------------------------------------------------------------------
    # Job Status
    # ------------------------------------------------------------------

    def set_status(
        self,
        job_id: str,
        status: JobStatus,
    ) -> Job:
        """
        Change the status of an existing job.
        """

        self._validate_status(
            status
        )

        return self.update_job(
            job_id,
            status=status,
        )

    # ------------------------------------------------------------------
    # Job Deletion
    # ------------------------------------------------------------------

    def delete_job(
        self,
        job_id: str,
    ) -> Job:
        """
        Delete an existing job.

        Returns:
            The deleted Job object.

        Raises:
            JobManagerError:
                If the job does not exist or deletion fails.
        """

        normalized_job_id = self._normalize_job_id(
            job_id
        )

        try:
            job = self._repository.get(
                normalized_job_id
            )

        except JobRepositoryError as exc:
            raise JobManagerError(
                str(exc)
            ) from exc

        try:
            self._repository.delete(
                normalized_job_id
            )

        except JobRepositoryError as exc:
            raise JobManagerError(
                f"Unable to delete job: {exc}"
            ) from exc

        return job

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_criteria(
        criteria: Iterable[JobCriterion],
    ) -> list[JobCriterion]:
        """
        Validate and materialize job criteria.
        """

        if isinstance(
            criteria,
            (str, bytes),
        ):
            raise JobManagerError(
                "Every job criterion must be a valid JobCriterion object."
            )

        try:
            criteria_list = list(
                criteria
            )

        except TypeError as exc:
            raise JobManagerError(
                "Every job criterion must be a valid JobCriterion object."
            ) from exc

        if not criteria_list:
            raise JobManagerError(
                "At least one job criterion is required."
            )

        if not all(
            isinstance(
                criterion,
                JobCriterion,
            )
            for criterion in criteria_list
        ):
            raise JobManagerError(
                "Every job criterion must be a valid JobCriterion object."
            )

        try:
            Job(
                job_id="validation-job",
                title="Validation Job",
                description="Validation Job",
                criteria=criteria_list,
                thresholds=JobThresholds(
                    shortlisted=80.0,
                    maybe=60.0,
                ),
                created_by="validation",
                created_at=JobManager._current_timestamp(),
                updated_at=JobManager._current_timestamp(),
                status="draft",
            )

        except ValidationError as exc:
            raise JobManagerError(
                f"Invalid job criteria: {exc}"
            ) from exc

        return criteria_list

    @staticmethod
    def _validate_thresholds(
        thresholds: JobThresholds,
    ) -> JobThresholds:
        """
        Validate job thresholds.
        """

        if not isinstance(
            thresholds,
            JobThresholds,
        ):
            raise JobManagerError(
                "Thresholds must be a valid JobThresholds object."
            )

        try:
            JobThresholds(
                shortlisted=thresholds.shortlisted,
                maybe=thresholds.maybe,
            )

        except ValidationError as exc:
            raise JobManagerError(
                f"Invalid job thresholds: {exc}"
            ) from exc

        return thresholds

    @staticmethod
    def _validate_status(
        status: JobStatus,
    ) -> None:
        """
        Validate a job status.
        """

        valid_statuses = {
            "draft",
            "active",
            "closed",
        }

        if status not in valid_statuses:
            raise JobManagerError(
                "Invalid job status. "
                "Status must be one of: draft, active, closed."
            )

    @staticmethod
    def _normalize_job_id(
        job_id: str,
    ) -> str:
        """
        Validate and normalize a job ID.
        """

        if not isinstance(
            job_id,
            str,
        ):
            raise JobManagerError(
                "Job ID must be a non-empty string."
            )

        normalized_job_id = job_id.strip()

        if not normalized_job_id:
            raise JobManagerError(
                "Job ID must be a non-empty string."
            )

        return normalized_job_id

    @staticmethod
    def _current_timestamp() -> str:
        """
        Return the current UTC timestamp as an ISO-8601 string.

        Job.created_at and Job.updated_at are defined as strings in
        the Job schema, so this method must return a string rather
        than a datetime object.
        """

        return datetime.now(
            timezone.utc
        ).isoformat()