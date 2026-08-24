from __future__ import annotations

from typing import Any

from firebase_admin import firestore

from app.core.firebase import initialize_firebase
from app.schemas.categorization_schema import CandidateCategorization
from app.schemas.scoring_schema import CandidateScore


class CandidateRepositoryError(RuntimeError):
    """
    Raised when a candidate persistence operation fails.
    """


class CandidateRepository:
    """
    Firestore-backed repository for screened candidates.

    Responsibilities:
        - Store candidate screening results.
        - Retrieve candidates.
        - Retrieve candidates belonging to a job.
        - Update candidate records.
        - Delete candidates.

    This repository does NOT:
        - Parse CVs.
        - Extract candidate information.
        - Score candidates.
        - Categorize candidates.
        - Call an LLM.
    """

    COLLECTION_NAME = "candidates"

    def __init__(
        self,
        client: Any | None = None,
    ) -> None:
        """
        Initialize the candidate repository.

        Args:
            client:
                Optional Firestore client.

                If omitted, the application's Firebase
                initialization is performed and the default
                Firestore client is obtained from Firebase Admin.
        """

        if client is not None:
            self._client = client
        else:
            try:
                initialize_firebase()
                self._client = firestore.client()

            except Exception as exc:
                raise CandidateRepositoryError(
                    f"Unable to initialize Firestore: {exc}"
                ) from exc

        self._collection = self._client.collection(
            self.COLLECTION_NAME
        )

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def save(
        self,
        *,
        candidate_id: str,
        job_id: str,
        filename: str,
        candidate_data: dict[str, Any],
        score: CandidateScore,
        categorization: CandidateCategorization,
    ) -> dict[str, Any]:
        """
        Store a complete candidate screening result.
        """

        normalized_candidate_id = self._normalize_id(
            candidate_id,
            "Candidate ID",
        )

        normalized_job_id = self._normalize_id(
            job_id,
            "Job ID",
        )

        if not isinstance(
            filename,
            str,
        ) or not filename.strip():
            raise CandidateRepositoryError(
                "Filename must be a non-empty string."
            )

        if not isinstance(
            candidate_data,
            dict,
        ):
            raise CandidateRepositoryError(
                "Candidate data must be a dictionary."
            )

        if not isinstance(
            score,
            CandidateScore,
        ):
            raise CandidateRepositoryError(
                "Score must be a valid CandidateScore object."
            )

        if not isinstance(
            categorization,
            CandidateCategorization,
        ):
            raise CandidateRepositoryError(
                "Categorization must be a valid "
                "CandidateCategorization object."
            )

        document = {
            "candidate_id": normalized_candidate_id,
            "job_id": normalized_job_id,
            "filename": filename.strip(),
            "candidate": candidate_data,
            "score": score.model_dump(),
            "categorization": categorization.model_dump(),
            "created_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        try:
            self._collection.document(
                normalized_candidate_id
            ).set(
                document
            )

        except Exception as exc:
            raise CandidateRepositoryError(
                f"Unable to store candidate: {exc}"
            ) from exc

        return {
            **document,
            "created_at": None,
            "updated_at": None,
        }

    # ------------------------------------------------------------------
    # Retrieve
    # ------------------------------------------------------------------

    def get(
        self,
        candidate_id: str,
    ) -> dict[str, Any]:
        """
        Retrieve a candidate by ID.
        """

        normalized_candidate_id = self._normalize_id(
            candidate_id,
            "Candidate ID",
        )

        try:
            snapshot = self._collection.document(
                normalized_candidate_id
            ).get()

        except Exception as exc:
            raise CandidateRepositoryError(
                f"Unable to retrieve candidate: {exc}"
            ) from exc

        if not snapshot.exists:
            raise CandidateRepositoryError(
                f"Candidate '{normalized_candidate_id}' does not exist."
            )

        data = snapshot.to_dict()

        if not isinstance(
            data,
            dict,
        ):
            raise CandidateRepositoryError(
                f"Candidate '{normalized_candidate_id}' "
                "contains invalid stored data."
            )

        return data

    # ------------------------------------------------------------------
    # Existence
    # ------------------------------------------------------------------

    def exists(
        self,
        candidate_id: str,
    ) -> bool:
        """
        Return True when a candidate exists.
        """

        normalized_candidate_id = self._normalize_id(
            candidate_id,
            "Candidate ID",
        )

        try:
            snapshot = self._collection.document(
                normalized_candidate_id
            ).get()

        except Exception as exc:
            raise CandidateRepositoryError(
                f"Unable to check candidate existence: {exc}"
            ) from exc

        return snapshot.exists

    # ------------------------------------------------------------------
    # Retrieve All
    # ------------------------------------------------------------------

    def get_all(self) -> list[dict[str, Any]]:
        """
        Return all stored candidates.
        """

        try:
            snapshots = self._collection.stream()

            candidates: list[dict[str, Any]] = []

            for snapshot in snapshots:
                data = snapshot.to_dict()

                if isinstance(
                    data,
                    dict,
                ):
                    candidates.append(data)

            return candidates

        except Exception as exc:
            raise CandidateRepositoryError(
                f"Unable to retrieve stored candidates: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Retrieve By Job
    # ------------------------------------------------------------------

    def get_by_job(
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
            query = self._collection.where(
                filter=firestore.FieldFilter(
                    "job_id",
                    "==",
                    normalized_job_id,
                )
            )

            snapshots = query.stream()

            candidates: list[dict[str, Any]] = []

            for snapshot in snapshots:
                data = snapshot.to_dict()

                if isinstance(
                    data,
                    dict,
                ):
                    candidates.append(data)

            return candidates

        except Exception as exc:
            raise CandidateRepositoryError(
                f"Unable to retrieve candidates for job "
                f"'{normalized_job_id}': {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(
        self,
        candidate_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Update selected candidate fields.
        """

        normalized_candidate_id = self._normalize_id(
            candidate_id,
            "Candidate ID",
        )

        if not isinstance(
            updates,
            dict,
        ):
            raise CandidateRepositoryError(
                "Candidate updates must be a dictionary."
            )

        if not updates:
            raise CandidateRepositoryError(
                "At least one candidate update is required."
            )

        update_data = {
            **updates,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

        try:
            reference = self._collection.document(
                normalized_candidate_id
            )

            snapshot = reference.get()

            if not snapshot.exists:
                raise CandidateRepositoryError(
                    f"Candidate '{normalized_candidate_id}' "
                    "does not exist."
                )

            reference.update(
                update_data
            )

            updated_snapshot = reference.get()

        except CandidateRepositoryError:
            raise

        except Exception as exc:
            raise CandidateRepositoryError(
                f"Unable to update candidate: {exc}"
            ) from exc

        data = updated_snapshot.to_dict()

        if not isinstance(
            data,
            dict,
        ):
            raise CandidateRepositoryError(
                f"Candidate '{normalized_candidate_id}' "
                "contains invalid stored data."
            )

        return data

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete(
        self,
        candidate_id: str,
    ) -> None:
        """
        Delete a candidate by ID.
        """

        normalized_candidate_id = self._normalize_id(
            candidate_id,
            "Candidate ID",
        )

        try:
            reference = self._collection.document(
                normalized_candidate_id
            )

            snapshot = reference.get()

            if not snapshot.exists:
                raise CandidateRepositoryError(
                    f"Candidate '{normalized_candidate_id}' "
                    "does not exist."
                )

            reference.delete()

        except CandidateRepositoryError:
            raise

        except Exception as exc:
            raise CandidateRepositoryError(
                f"Unable to delete candidate: {exc}"
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
            raise CandidateRepositoryError(
                f"{field_name} must be a non-empty string."
            )

        normalized = value.strip()

        if not normalized:
            raise CandidateRepositoryError(
                f"{field_name} must be a non-empty string."
            )

        return normalized