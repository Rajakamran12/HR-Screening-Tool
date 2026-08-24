from __future__ import annotations

from typing import Iterable

from app.core.config import FIREBASE_CREDENTIALS_PATH
from app.core.firebase import get_firestore_client
from app.schemas.job_schema import Job, JobStatus


class JobRepositoryError(RuntimeError):
    """
    Raised when a job persistence operation cannot be completed.
    """


class JobRepository:
    """
    Repository for Job objects.

    The default repository is an isolated in-memory repository. This makes
    the repository deterministic and prevents state from leaking between
    service instances or unit tests.

    A Firestore-compatible client can be supplied explicitly through
    ``firestore_client`` when persistent storage is required.

    Responsibilities:
        - Store jobs.
        - Retrieve jobs.
        - List jobs.
        - Filter jobs by status.
        - Check job existence.
        - Update jobs.
        - Delete jobs.
        - Save multiple jobs.
        - Count jobs.
        - Clear jobs.

    Business validation remains in JobManager and Job schema validation
    remains in the Pydantic models.
    """

    COLLECTION_NAME = "jobs"

    VALID_STATUSES = {
        "draft",
        "active",
        "closed",
    }

    def __init__(
        self,
        jobs: dict[str, Job] | None = None,
        firestore_client=None,
    ) -> None:
        """
        Initialize the repository.

        Args:
            jobs:
                Optional initial jobs.

            firestore_client:
                Optional Firestore client.

                When supplied, persistence uses Firestore.

                When omitted, the repository uses isolated in-memory
                storage. This is intentional so that every repository
                instance starts clean and deterministic.
        """

        self._db = firestore_client

        self._jobs: dict[str, Job] = {}

        if jobs is not None:
            self._load_initial_jobs(
                jobs
            )

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def _load_initial_jobs(
        self,
        jobs: dict[str, Job],
    ) -> None:
        """
        Load initial jobs into the repository.

        The caller's dictionary is never retained directly.
        """

        if not isinstance(
            jobs,
            dict,
        ):
            raise JobRepositoryError(
                "Initial jobs must be provided as a dictionary."
            )

        for job_id, job in jobs.items():

            if not isinstance(
                job_id,
                str,
            ):
                raise JobRepositoryError(
                    "Every initial job ID must be a string."
                )

            if not isinstance(
                job,
                Job,
            ):
                raise JobRepositoryError(
                    "Every initial job must be a valid Job object."
                )

            if job.job_id != job_id:
                raise JobRepositoryError(
                    "Initial job dictionary key must match "
                    "the Job.job_id value."
                )

            self._jobs[job_id] = job

    # ------------------------------------------------------------------
    # Firestore Support
    # ------------------------------------------------------------------

    def _uses_firestore(self) -> bool:
        """
        Return whether this repository is configured for Firestore.
        """

        return self._db is not None

    def _collection(self):
        """
        Return the Firestore jobs collection reference.

        This method is only used when an explicit Firestore client
        has been supplied.
        """

        if not self._uses_firestore():
            raise JobRepositoryError(
                "Firestore client is not configured."
            )

        try:
            return self._db.collection(
                self.COLLECTION_NAME
            )

        except Exception as exc:
            raise JobRepositoryError(
                f"Unable to access jobs collection: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    @staticmethod
    def _job_to_document(
        job: Job,
    ) -> dict:
        """
        Convert a validated Job object into a dictionary.
        """

        if not isinstance(
            job,
            Job,
        ):
            raise JobRepositoryError(
                "Only valid Job objects can be stored."
            )

        try:
            return job.model_dump(
                mode="python"
            )

        except Exception as exc:
            raise JobRepositoryError(
                f"Unable to serialize job: {exc}"
            ) from exc

    @staticmethod
    def _document_to_job(
        document: dict,
    ) -> Job:
        """
        Convert stored dictionary data into a validated Job object.
        """

        if not isinstance(
            document,
            dict,
        ):
            raise JobRepositoryError(
                "Firestore job data must be a dictionary."
            )

        try:
            return Job.model_validate(
                document
            )

        except Exception as exc:
            raise JobRepositoryError(
                f"Stored job data is invalid: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save(
        self,
        job: Job,
    ) -> Job:
        """
        Create or replace a job.

        The exact Job instance supplied by the caller is returned.
        """

        if not isinstance(
            job,
            Job,
        ):
            raise JobRepositoryError(
                "Only valid Job objects can be stored."
            )

        if self._uses_firestore():

            try:
                document = self._job_to_document(
                    job
                )

                self._collection().document(
                    job.job_id
                ).set(
                    document
                )

            except JobRepositoryError:
                raise

            except Exception as exc:
                raise JobRepositoryError(
                    f"Unable to save job '{job.job_id}': {exc}"
                ) from exc

        else:
            self._jobs[job.job_id] = job

        return job

    # ------------------------------------------------------------------
    # Save All
    # ------------------------------------------------------------------

    def save_all(
        self,
        jobs: Iterable[Job],
    ) -> list[Job]:
        """
        Create or replace multiple jobs.

        Jobs are intentionally processed sequentially.

        This means that if an invalid job is encountered after one or
        more valid jobs have already been processed, those earlier valid
        jobs remain persisted.

        Example:

            save_all([
                valid_job,
                invalid_job,
            ])

        The valid job is stored first. The invalid job then raises
        JobRepositoryError.

        No rollback is performed.
        """

        if isinstance(
            jobs,
            (str, bytes),
        ):
            raise JobRepositoryError(
                "Jobs must be an iterable of Job objects."
            )

        try:
            iterator = iter(
                jobs
            )

        except TypeError as exc:
            raise JobRepositoryError(
                "Jobs must be an iterable of Job objects."
            ) from exc

        saved_jobs: list[Job] = []

        # IMPORTANT:
        # Do not pre-validate the complete iterable.
        #
        # The repository contract intentionally allows jobs that appear
        # before an invalid item to remain persisted.
        #
        # Therefore validation and saving happen one item at a time.

        for job in iterator:

            if not isinstance(
                job,
                Job,
            ):
                raise JobRepositoryError(
                    "Only valid Job objects can be stored."
                )

            saved_jobs.append(
                self.save(
                    job
                )
            )

        return saved_jobs

    # ------------------------------------------------------------------
    # Get
    # ------------------------------------------------------------------

    def get(
        self,
        job_id: str,
    ) -> Job:
        """
        Retrieve a job by ID.
        """

        normalized_job_id = self._normalize_job_id(
            job_id
        )

        if not self._uses_firestore():

            if normalized_job_id not in self._jobs:
                raise JobRepositoryError(
                    f"Job with ID '{normalized_job_id}' was not found."
                )

            return self._jobs[
                normalized_job_id
            ]

        try:
            snapshot = (
                self._collection()
                .document(
                    normalized_job_id
                )
                .get()
            )

        except Exception as exc:
            raise JobRepositoryError(
                f"Unable to retrieve job "
                f"'{normalized_job_id}': {exc}"
            ) from exc

        if not snapshot.exists:
            raise JobRepositoryError(
                f"Job with ID '{normalized_job_id}' was not found."
            )

        try:
            document = snapshot.to_dict()

            if document is None:
                raise JobRepositoryError(
                    f"Job with ID '{normalized_job_id}' was not found."
                )

            return self._document_to_job(
                document
            )

        except JobRepositoryError:
            raise

        except Exception as exc:
            raise JobRepositoryError(
                f"Unable to convert stored job "
                f"'{normalized_job_id}': {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Get All
    # ------------------------------------------------------------------

    def get_all(self) -> list[Job]:
        """
        Return all jobs.

        Jobs are returned in created_at order.
        """

        if not self._uses_firestore():

            jobs = list(
                self._jobs.values()
            )

            jobs.sort(
                key=lambda job: job.created_at
            )

            return jobs

        try:
            snapshots = self._collection().stream()

        except Exception as exc:
            raise JobRepositoryError(
                f"Unable to retrieve jobs: {exc}"
            ) from exc

        jobs: list[Job] = []

        try:

            for snapshot in snapshots:

                document = snapshot.to_dict()

                if document is None:
                    continue

                jobs.append(
                    self._document_to_job(
                        document
                    )
                )

        except JobRepositoryError:
            raise

        except Exception as exc:
            raise JobRepositoryError(
                f"Unable to process stored jobs: {exc}"
            ) from exc

        jobs.sort(
            key=lambda job: job.created_at
        )

        return jobs

    # ------------------------------------------------------------------
    # Find By Status
    # ------------------------------------------------------------------

    def find_by_status(
        self,
        status: JobStatus,
    ) -> list[Job]:
        """
        Return all jobs having the specified status.
        """

        self._validate_status(
            status
        )

        if not self._uses_firestore():

            jobs = [
                job
                for job in self._jobs.values()
                if job.status == status
            ]

            jobs.sort(
                key=lambda job: job.created_at
            )

            return jobs

        try:

            snapshots = (
                self._collection()
                .where(
                    filter=__import__(
                        "firebase_admin.firestore",
                        fromlist=["FieldFilter"],
                    ).FieldFilter(
                        "status",
                        "==",
                        status,
                    )
                )
                .stream()
            )

        except Exception as exc:
            raise JobRepositoryError(
                f"Unable to retrieve jobs with status "
                f"'{status}': {exc}"
            ) from exc

        jobs: list[Job] = []

        try:

            for snapshot in snapshots:

                document = snapshot.to_dict()

                if document is None:
                    continue

                jobs.append(
                    self._document_to_job(
                        document
                    )
                )

        except JobRepositoryError:
            raise

        except Exception as exc:
            raise JobRepositoryError(
                f"Unable to process jobs with status "
                f"'{status}': {exc}"
            ) from exc

        jobs.sort(
            key=lambda job: job.created_at
        )

        return jobs

    # ------------------------------------------------------------------
    # Exists
    # ------------------------------------------------------------------

    def exists(
        self,
        job_id: str,
    ) -> bool:
        """
        Return whether a job exists.
        """

        normalized_job_id = self._normalize_job_id(
            job_id
        )

        if not self._uses_firestore():
            return normalized_job_id in self._jobs

        try:

            snapshot = (
                self._collection()
                .document(
                    normalized_job_id
                )
                .get()
            )

            return snapshot.exists

        except Exception as exc:
            raise JobRepositoryError(
                f"Unable to check existence of job "
                f"'{normalized_job_id}': {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(
        self,
        job: Job,
    ) -> Job:
        """
        Replace an existing job.

        The supplied Job instance is returned unchanged.
        """

        if not isinstance(
            job,
            Job,
        ):
            raise JobRepositoryError(
                "Only valid Job objects can be stored."
            )

        if not self.exists(
            job.job_id
        ):
            raise JobRepositoryError(
                f"Job with ID '{job.job_id}' was not found."
            )

        return self.save(
            job
        )

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete(
        self,
        job_id: str,
    ) -> Job:
        """
        Delete an existing job and return it.
        """

        normalized_job_id = self._normalize_job_id(
            job_id
        )

        if not self._uses_firestore():

            if normalized_job_id not in self._jobs:
                raise JobRepositoryError(
                    f"Job with ID '{normalized_job_id}' was not found."
                )

            job = self._jobs.pop(
                normalized_job_id
            )

            return job

        try:

            document_reference = (
                self._collection()
                .document(
                    normalized_job_id
                )
            )

            snapshot = document_reference.get()

        except Exception as exc:
            raise JobRepositoryError(
                f"Unable to retrieve job "
                f"'{normalized_job_id}' before deletion: {exc}"
            ) from exc

        if not snapshot.exists:
            raise JobRepositoryError(
                f"Job with ID '{normalized_job_id}' was not found."
            )

        document = snapshot.to_dict()

        if document is None:
            raise JobRepositoryError(
                f"Job with ID '{normalized_job_id}' was not found."
            )

        try:

            job = self._document_to_job(
                document
            )

            document_reference.delete()

        except JobRepositoryError:
            raise

        except Exception as exc:
            raise JobRepositoryError(
                f"Unable to delete job "
                f"'{normalized_job_id}': {exc}"
            ) from exc

        return job

    # ------------------------------------------------------------------
    # Count
    # ------------------------------------------------------------------

    def count(self) -> int:
        """
        Return the number of stored jobs.
        """

        if not self._uses_firestore():
            return len(
                self._jobs
            )

        return len(
            self.get_all()
        )

    # ------------------------------------------------------------------
    # Clear
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """
        Remove all jobs from the repository.
        """

        if not self._uses_firestore():
            self._jobs.clear()
            return

        jobs = self.get_all()

        for job in jobs:

            try:

                self._collection().document(
                    job.job_id
                ).delete()

            except Exception as exc:
                raise JobRepositoryError(
                    f"Unable to clear job "
                    f"'{job.job_id}': {exc}"
                ) from exc

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

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
            raise JobRepositoryError(
                "Job ID must be a string."
            )

        normalized_job_id = job_id.strip()

        if not normalized_job_id:
            raise JobRepositoryError(
                "Job ID must be a non-empty string."
            )

        return normalized_job_id

    @classmethod
    def _validate_status(
        cls,
        status: JobStatus,
    ) -> None:
        """
        Validate a job status.

        JobStatus is a typing Literal, so it must NOT be passed to
        isinstance(). Runtime validation is performed against the
        concrete allowed string values instead.
        """

        if not isinstance(
            status,
            str,
        ):
            raise JobRepositoryError(
                "Invalid job status. "
                "Status must be one of: draft, active, closed."
            )

        if status not in cls.VALID_STATUSES:
            raise JobRepositoryError(
                "Invalid job status. "
                "Status must be one of: draft, active, closed."
            )


_application_job_repository: JobRepository | None = None


def get_application_job_repository() -> JobRepository:
    """Return the repository shared by the in-process API adapters."""

    global _application_job_repository

    if _application_job_repository is None:
        if FIREBASE_CREDENTIALS_PATH:
            _application_job_repository = JobRepository(
                firestore_client=get_firestore_client(),
            )
        else:
            _application_job_repository = JobRepository()

    return _application_job_repository
