from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from app.core.job_repository import (
    JobRepository,
    JobRepositoryError,
)
from app.services.candidate_service import (
    CandidateService,
    CandidateServiceError,
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class BulkScreeningServiceError(Exception):
    """
    Raised when bulk candidate screening cannot be completed.
    """


# ---------------------------------------------------------------------------
# Internal File Representation
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class PreparedCV:
    """
    Internal representation of an uploaded CV.

    The API layer provides the filename, raw bytes, and extension.
    The bulk service converts those bytes into temporary files before
    passing them through the existing CandidateService screening pipeline.
    """

    filename: str
    content: bytes
    extension: str


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class BulkScreeningService:
    """
    Coordinates bulk CV screening.

    Responsibilities:

    - Validate bulk screening input.
    - Process multiple CVs.
    - Reuse CandidateService for the actual screening pipeline.
    - Preserve one failed candidate from stopping the remaining batch.
    - Aggregate batch results.
    - Track lightweight in-process job status.

    CandidateService remains the source of truth for:
        parsing
        extraction
        scoring
        categorization
        candidate persistence
    """

    _status_store: dict[str, dict[str, Any]] = {}
    CANDIDATE_TIMEOUT_SECONDS = 180.0

    def __init__(
        self,
        candidate_service: CandidateService | None = None,
        job_repository: JobRepository | None = None,
        max_concurrency: int = 3,
    ) -> None:
        if max_concurrency < 1:
            raise ValueError(
                "max_concurrency must be at least 1."
            )

        self.job_repository = job_repository

        self.candidate_service = (
            candidate_service
            if candidate_service is not None
            else CandidateService()
        )

        self.max_concurrency = max_concurrency

    # -----------------------------------------------------------------------
    # Public Bulk Screening
    # -----------------------------------------------------------------------

    async def screen_candidates(
        self,
        *,
        job_id: str,
        files: list[dict[str, Any]],
        actor_id: str,
        batch_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Screen all supplied CVs against one job.

        Each candidate receives an independent candidate ID.

        A failure for one CV is recorded in that CV's result and does not
        prevent the remaining CVs from being processed.
        """

        normalized_job_id = self._validate_job_id(
            job_id,
        )

        normalized_actor_id = self._validate_actor_id(
            actor_id,
        )

        prepared_files = self._normalize_files(
            files,
        )

        if not prepared_files:
            raise BulkScreeningServiceError(
                "At least one CV file is required."
            )

        criteria = None
        thresholds = None

        if self.job_repository is not None:
            try:
                job = self.job_repository.get(
                    normalized_job_id,
                )
            except JobRepositoryError as exc:
                raise BulkScreeningServiceError(
                    f"Unable to load job '{normalized_job_id}': {exc}"
                ) from exc

            criteria = job.criteria
            thresholds = job.thresholds

        batch_id = batch_id or str(uuid.uuid4())

        started_at = self._utc_now()

        self._status_store[batch_id] = {
            "batch_id": batch_id,
            "job_id": normalized_job_id,
            "status": "processing",
            "total": len(prepared_files),
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "started_at": started_at,
            "completed_at": None,
        }

        semaphore = asyncio.Semaphore(
            self.max_concurrency,
        )

        tasks = [
            self._screen_single_candidate(
                semaphore=semaphore,
                batch_id=batch_id,
                job_id=normalized_job_id,
                actor_id=normalized_actor_id,
                criteria=criteria,
                thresholds=thresholds,
                cv=cv,
            )
            for cv in prepared_files
        ]

        results = await asyncio.gather(
            *tasks,
        )

        successful = sum(
            1
            for result in results
            if result["success"] is True
        )

        failed = len(results) - successful

        completed_at = self._utc_now()

        self._status_store[batch_id] = {
            "batch_id": batch_id,
            "job_id": normalized_job_id,
            "status": "completed",
            "total": len(results),
            "processed": len(results),
            "successful": successful,
            "failed": failed,
            "started_at": started_at,
            "completed_at": completed_at,
            "results": results,
        }

        return {
            "batch_id": batch_id,
            "job_id": normalized_job_id,
            "status": "completed",
            "total": len(results),
            "successful": successful,
            "failed": failed,
            "results": results,
            "started_at": started_at,
            "completed_at": completed_at,
        }

    # -----------------------------------------------------------------------
    # Single Candidate Processing
    # -----------------------------------------------------------------------

    async def _screen_single_candidate(
        self,
        *,
        semaphore: asyncio.Semaphore,
        batch_id: str,
        job_id: str,
        actor_id: str,
        criteria: Any,
        thresholds: Any,
        cv: PreparedCV,
    ) -> dict[str, Any]:
        """
        Process one CV while respecting the configured concurrency limit.
        """

        candidate_id = str(
            uuid.uuid4(),
        )

        async with semaphore:
            temporary_path: Path | None = None

            try:
                temporary_path = self._create_temporary_file(
                    cv,
                )

                result = await asyncio.wait_for(
                    self.candidate_service.screen_candidate(
                        candidate_id=candidate_id,
                        job_id=job_id,
                        filename=cv.filename,
                        cv_file=temporary_path,
                        criteria=criteria,
                        thresholds=thresholds,
                    ),
                    timeout=self.CANDIDATE_TIMEOUT_SECONDS,
                )

                self._increment_status(
                    batch_id=batch_id,
                    successful=True,
                )

                return {
                    "success": True,
                    "candidate_id": candidate_id,
                    "job_id": job_id,
                    "filename": cv.filename,
                    "candidate": result,
                }

            except CandidateServiceError as exc:
                self._increment_status(
                    batch_id=batch_id,
                    successful=False,
                )

                return {
                    "success": False,
                    "candidate_id": candidate_id,
                    "job_id": job_id,
                    "filename": cv.filename,
                    "error": str(exc),
                }

            except asyncio.TimeoutError:
                self._increment_status(
                    batch_id=batch_id,
                    successful=False,
                )

                return {
                    "success": False,
                    "candidate_id": candidate_id,
                    "job_id": job_id,
                    "filename": cv.filename,
                    "error": (
                        "Candidate processing exceeded the 180-second "
                        "time limit and needs manual review."
                    ),
                }

            except Exception as exc:
                self._increment_status(
                    batch_id=batch_id,
                    successful=False,
                )

                return {
                    "success": False,
                    "candidate_id": candidate_id,
                    "job_id": job_id,
                    "filename": cv.filename,
                    "error": (
                        "Unexpected error while screening candidate: "
                        f"{exc}"
                    ),
                }

            finally:
                if temporary_path is not None:
                    try:
                        temporary_path.unlink(
                            missing_ok=True,
                        )
                    except Exception:
                        pass

    # -----------------------------------------------------------------------
    # Status
    # -----------------------------------------------------------------------

    def get_status(
        self,
        job_id: str,
    ) -> dict[str, Any]:
        """
        Return the latest known bulk screening status for a job.

        Since bulk processing is currently coordinated inside the API
        process, status is maintained in memory.
        """

        normalized_job_id = self._validate_job_id(
            job_id,
        )

        matching_statuses = [
            status
            for status in self._status_store.values()
            if status.get("job_id") == normalized_job_id
        ]

        if not matching_statuses:
            raise BulkScreeningServiceError(
                f"No bulk screening operation found for job "
                f"'{normalized_job_id}'."
            )

        latest_status = max(
            matching_statuses,
            key=lambda status: status.get(
                "started_at",
                "",
            ),
        )

        return dict(
            latest_status,
        )

    @classmethod
    def get_status_by_batch(
        cls,
        batch_id: str,
    ) -> dict[str, Any]:
        """Return the status for one exact batch operation."""

        if not isinstance(batch_id, str) or not batch_id.strip():
            raise BulkScreeningServiceError(
                "Batch ID must be a non-empty string."
            )

        status = cls._status_store.get(batch_id.strip())
        if status is None:
            raise BulkScreeningServiceError(
                f"No bulk screening operation found for batch "
                f"'{batch_id.strip()}'."
            )

        return dict(status)

    # -----------------------------------------------------------------------
    # Validation
    # -----------------------------------------------------------------------

    @staticmethod
    def _validate_job_id(
        job_id: str,
    ) -> str:
        if not isinstance(
            job_id,
            str,
        ) or not job_id.strip():
            raise BulkScreeningServiceError(
                "Job ID must be a non-empty string."
            )

        return job_id.strip()

    @staticmethod
    def _validate_actor_id(
        actor_id: str,
    ) -> str:
        if not isinstance(
            actor_id,
            str,
        ) or not actor_id.strip():
            raise BulkScreeningServiceError(
                "Actor ID must be a non-empty string."
            )

        return actor_id.strip()

    @staticmethod
    def _normalize_files(
        files: list[dict[str, Any]],
    ) -> list[PreparedCV]:
        if not isinstance(
            files,
            list,
        ):
            raise BulkScreeningServiceError(
                "CV files must be provided as a list."
            )

        prepared: list[PreparedCV] = []

        for item in files:
            if not isinstance(
                item,
                dict,
            ):
                raise BulkScreeningServiceError(
                    "Each CV file must be represented as an object."
                )

            filename = item.get(
                "filename",
            )

            content = item.get(
                "content",
            )

            extension = item.get(
                "extension",
            )

            if not isinstance(
                filename,
                str,
            ) or not filename.strip():
                raise BulkScreeningServiceError(
                    "Every CV must have a non-empty filename."
                )

            if not isinstance(
                content,
                bytes,
            ):
                raise BulkScreeningServiceError(
                    f"CV '{filename}' must contain byte content."
                )

            if not content:
                raise BulkScreeningServiceError(
                    f"The uploaded CV '{filename}' is empty."
                )

            if not isinstance(
                extension,
                str,
            ):
                extension = Path(
                    filename,
                ).suffix.lower()

            prepared.append(
                PreparedCV(
                    filename=Path(
                        filename,
                    ).name,
                    content=content,
                    extension=extension.lower(),
                )
            )

        return prepared

    # -----------------------------------------------------------------------
    # Temporary File Handling
    # -----------------------------------------------------------------------

    @staticmethod
    def _create_temporary_file(
        cv: PreparedCV,
    ) -> Path:
        suffix = cv.extension

        if not suffix:
            suffix = Path(
                cv.filename,
            ).suffix

        try:
            with NamedTemporaryFile(
                mode="wb",
                suffix=suffix,
                delete=False,
            ) as temporary_file:
                temporary_file.write(
                    cv.content,
                )

                return Path(
                    temporary_file.name,
                )

        except Exception as exc:
            raise BulkScreeningServiceError(
                f"Unable to create temporary CV file: {exc}"
            ) from exc

    # -----------------------------------------------------------------------
    # Status Helpers
    # -----------------------------------------------------------------------

    @classmethod
    def _increment_status(
        cls,
        *,
        batch_id: str,
        successful: bool,
    ) -> None:
        status = cls._status_store.get(
            batch_id,
        )

        if status is None:
            return

        status["processed"] = (
            int(
                status.get(
                    "processed",
                    0,
                )
            )
            + 1
        )

        if successful:
            status["successful"] = (
                int(
                    status.get(
                        "successful",
                        0,
                    )
                )
                + 1
            )
        else:
            status["failed"] = (
                int(
                    status.get(
                        "failed",
                        0,
                    )
                )
                + 1
            )

    # -----------------------------------------------------------------------
    # Date/Time
    # -----------------------------------------------------------------------

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(
            timezone.utc,
        ).isoformat()