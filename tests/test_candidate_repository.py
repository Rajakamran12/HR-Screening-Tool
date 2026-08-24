from __future__ import annotations

from typing import Any

import pytest

from app.core.candidate_repository import (
    CandidateRepository,
    CandidateRepositoryError,
)
from app.schemas.categorization_schema import CandidateCategorization
from app.schemas.scoring_schema import (
    CandidateScore,
    CriterionEvidence,
    CriterionScore,
)


# ---------------------------------------------------------------------------
# Fake Firestore Objects
# ---------------------------------------------------------------------------


class FakeDocumentSnapshot:
    """
    Minimal Firestore document snapshot used by the tests.
    """

    def __init__(
        self,
        data: dict[str, Any] | None,
    ) -> None:
        self._data = data

    @property
    def exists(self) -> bool:
        return self._data is not None

    def to_dict(self) -> dict[str, Any] | None:
        if self._data is None:
            return None

        return dict(self._data)


class FakeDocumentReference:
    """
    Minimal Firestore document reference used by the tests.
    """

    def __init__(
        self,
        collection: "FakeCollection",
        document_id: str,
    ) -> None:
        self._collection = collection
        self.document_id = document_id

    def set(
        self,
        document: dict[str, Any],
    ) -> None:
        self._collection.documents[
            self.document_id
        ] = dict(document)

    def get(self) -> FakeDocumentSnapshot:
        return FakeDocumentSnapshot(
            self._collection.documents.get(
                self.document_id
            )
        )

    def update(
        self,
        updates: dict[str, Any],
    ) -> None:
        if self.document_id not in self._collection.documents:
            raise RuntimeError(
                "Document does not exist."
            )

        self._collection.documents[
            self.document_id
        ].update(
            updates
        )

    def delete(self) -> None:
        self._collection.documents.pop(
            self.document_id,
            None,
        )


class FakeQuery:
    """
    Minimal Firestore query implementation supporting equality
    filtering by job_id.
    """

    def __init__(
        self,
        collection: "FakeCollection",
        field_name: str,
        expected_value: Any,
    ) -> None:
        self._collection = collection
        self._field_name = field_name
        self._expected_value = expected_value

    def stream(self):
        for document in self._collection.documents.values():

            if (
                document.get(self._field_name)
                == self._expected_value
            ):
                yield FakeDocumentSnapshot(
                    document
                )


class FakeCollection:
    """
    Minimal Firestore collection implementation used by tests.
    """

    def __init__(self) -> None:
        self.documents: dict[str, dict[str, Any]] = {}

    def document(
        self,
        document_id: str,
    ) -> FakeDocumentReference:
        return FakeDocumentReference(
            self,
            document_id,
        )

    def stream(self):
        for document in self.documents.values():
            yield FakeDocumentSnapshot(
                document
            )

    def where(
        self,
        *,
        filter,
    ) -> FakeQuery:
        return FakeQuery(
            self,
            filter.field_path,
            filter.value,
        )


class FakeFirestoreClient:
    """
    Minimal Firestore client implementation used by tests.
    """

    def __init__(self) -> None:
        self.collections: dict[
            str,
            FakeCollection,
        ] = {}

    def collection(
        self,
        collection_name: str,
    ) -> FakeCollection:

        if collection_name not in self.collections:
            self.collections[
                collection_name
            ] = FakeCollection()

        return self.collections[
            collection_name
        ]


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def firestore_client() -> FakeFirestoreClient:
    """
    Provide an isolated fake Firestore client for each test.
    """

    return FakeFirestoreClient()


@pytest.fixture
def repository(
    firestore_client: FakeFirestoreClient,
) -> CandidateRepository:
    """
    Create a CandidateRepository using the fake Firestore client.
    """

    return CandidateRepository(
        client=firestore_client
    )


@pytest.fixture
def candidate_score() -> CandidateScore:
    """
    Provide a valid CandidateScore matching the current schema.
    """

    criterion_score = CriterionScore(
        criterion_name="Python Experience",
        score=85.0,
        expertise_level="advanced",
        relevant_years=4.0,
        recency_assessment=(
            "Recent professional Python experience is demonstrated."
        ),
        seniority_assessment=(
            "Python was used in professional engineering responsibilities."
        ),
        depth_assessment=(
            "The CV demonstrates substantial practical Python usage."
        ),
        evidence=CriterionEvidence(
            evidence=[
                "Developed Python backend applications.",
                "Used Python professionally for four years.",
            ],
            evidence_location=[
                "Software Engineer experience",
                "Backend Developer experience",
            ],
        ),
        reasoning=(
            "The candidate demonstrates several years of professional "
            "Python development with meaningful practical depth."
        ),
        meets_requirement=True,
        confidence=0.9,
    )

    return CandidateScore(
        overall_score=85.0,
        criterion_scores=[
            criterion_score
        ],
        strengths=[
            "Strong Python experience."
        ],
        gaps=[
            "Limited evidence of leadership."
        ],
        overall_reasoning=(
            "The candidate demonstrates strong technical alignment "
            "with the screening requirements."
        ),
        review_required=False,
        review_reason=None,
    )


@pytest.fixture
def categorization() -> CandidateCategorization:
    """
    Provide a valid deterministic categorization result.
    """

    return CandidateCategorization(
        category="shortlisted",
        score=85.0,
        shortlisted_threshold=80.0,
        maybe_threshold=60.0,
    )


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


def test_repository_initializes_with_injected_client(
    firestore_client: FakeFirestoreClient,
) -> None:
    """
    The repository should initialize without contacting Firebase when
    a Firestore client is injected.
    """

    repository = CandidateRepository(
        client=firestore_client
    )

    assert repository is not None


# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------


def test_save_stores_complete_candidate_result(
    repository: CandidateRepository,
    candidate_score: CandidateScore,
    categorization: CandidateCategorization,
) -> None:
    """
    Saving a candidate should persist the complete screening result.
    """

    result = repository.save(
        candidate_id="candidate-001",
        job_id="job-001",
        filename="candidate.pdf",
        candidate_data={
            "name": "Test Candidate",
            "skills": [
                "Python",
                "FastAPI",
            ],
        },
        score=candidate_score,
        categorization=categorization,
    )

    assert result["candidate_id"] == "candidate-001"
    assert result["job_id"] == "job-001"
    assert result["filename"] == "candidate.pdf"

    assert result["candidate"] == {
        "name": "Test Candidate",
        "skills": [
            "Python",
            "FastAPI",
        ],
    }

    assert result["score"] == candidate_score.model_dump()
    assert (
        result["categorization"]
        == categorization.model_dump()
    )

    assert result["created_at"] is None
    assert result["updated_at"] is None


def test_save_normalizes_identifiers_and_filename(
    repository: CandidateRepository,
    candidate_score: CandidateScore,
    categorization: CandidateCategorization,
) -> None:
    """
    Candidate ID, job ID, and filename should be normalized.
    """

    result = repository.save(
        candidate_id="  candidate-002  ",
        job_id="  job-002  ",
        filename="  resume.pdf  ",
        candidate_data={
            "name": "Another Candidate"
        },
        score=candidate_score,
        categorization=categorization,
    )

    assert result["candidate_id"] == "candidate-002"
    assert result["job_id"] == "job-002"
    assert result["filename"] == "resume.pdf"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_save_rejects_empty_candidate_id(
    repository: CandidateRepository,
    candidate_score: CandidateScore,
    categorization: CandidateCategorization,
) -> None:
    with pytest.raises(
        CandidateRepositoryError,
        match="Candidate ID must be a non-empty string",
    ):
        repository.save(
            candidate_id="   ",
            job_id="job-001",
            filename="candidate.pdf",
            candidate_data={},
            score=candidate_score,
            categorization=categorization,
        )


def test_save_rejects_empty_job_id(
    repository: CandidateRepository,
    candidate_score: CandidateScore,
    categorization: CandidateCategorization,
) -> None:
    with pytest.raises(
        CandidateRepositoryError,
        match="Job ID must be a non-empty string",
    ):
        repository.save(
            candidate_id="candidate-001",
            job_id="   ",
            filename="candidate.pdf",
            candidate_data={},
            score=candidate_score,
            categorization=categorization,
        )


def test_save_rejects_empty_filename(
    repository: CandidateRepository,
    candidate_score: CandidateScore,
    categorization: CandidateCategorization,
) -> None:
    with pytest.raises(
        CandidateRepositoryError,
        match="Filename must be a non-empty string",
    ):
        repository.save(
            candidate_id="candidate-001",
            job_id="job-001",
            filename="   ",
            candidate_data={},
            score=candidate_score,
            categorization=categorization,
        )


def test_save_rejects_invalid_candidate_data(
    repository: CandidateRepository,
    candidate_score: CandidateScore,
    categorization: CandidateCategorization,
) -> None:
    with pytest.raises(
        CandidateRepositoryError,
        match="Candidate data must be a dictionary",
    ):
        repository.save(
            candidate_id="candidate-001",
            job_id="job-001",
            filename="candidate.pdf",
            candidate_data="invalid",  # type: ignore[arg-type]
            score=candidate_score,
            categorization=categorization,
        )


def test_save_rejects_invalid_score(
    repository: CandidateRepository,
    categorization: CandidateCategorization,
) -> None:
    with pytest.raises(
        CandidateRepositoryError,
        match="Score must be a valid CandidateScore object",
    ):
        repository.save(
            candidate_id="candidate-001",
            job_id="job-001",
            filename="candidate.pdf",
            candidate_data={},
            score={},  # type: ignore[arg-type]
            categorization=categorization,
        )


def test_save_rejects_invalid_categorization(
    repository: CandidateRepository,
    candidate_score: CandidateScore,
) -> None:
    with pytest.raises(
        CandidateRepositoryError,
        match="Categorization must be a valid CandidateCategorization object",
    ):
        repository.save(
            candidate_id="candidate-001",
            job_id="job-001",
            filename="candidate.pdf",
            candidate_data={},
            score=candidate_score,
            categorization={},  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


def test_get_returns_saved_candidate(
    repository: CandidateRepository,
    candidate_score: CandidateScore,
    categorization: CandidateCategorization,
) -> None:
    repository.save(
        candidate_id="candidate-003",
        job_id="job-001",
        filename="candidate.pdf",
        candidate_data={
            "name": "Saved Candidate"
        },
        score=candidate_score,
        categorization=categorization,
    )

    result = repository.get(
        "candidate-003"
    )

    assert result["candidate_id"] == "candidate-003"
    assert result["job_id"] == "job-001"
    assert result["filename"] == "candidate.pdf"
    assert result["candidate"]["name"] == "Saved Candidate"


def test_get_rejects_missing_candidate(
    repository: CandidateRepository,
) -> None:
    with pytest.raises(
        CandidateRepositoryError,
        match="does not exist",
    ):
        repository.get(
            "missing-candidate"
        )


# ---------------------------------------------------------------------------
# Exists
# ---------------------------------------------------------------------------


def test_exists_returns_true_for_existing_candidate(
    repository: CandidateRepository,
    candidate_score: CandidateScore,
    categorization: CandidateCategorization,
) -> None:
    repository.save(
        candidate_id="candidate-004",
        job_id="job-001",
        filename="candidate.pdf",
        candidate_data={},
        score=candidate_score,
        categorization=categorization,
    )

    assert repository.exists(
        "candidate-004"
    ) is True


def test_exists_returns_false_for_missing_candidate(
    repository: CandidateRepository,
) -> None:
    assert repository.exists(
        "missing-candidate"
    ) is False


# ---------------------------------------------------------------------------
# Get All
# ---------------------------------------------------------------------------


def test_get_all_returns_all_candidates(
    repository: CandidateRepository,
    candidate_score: CandidateScore,
    categorization: CandidateCategorization,
) -> None:
    repository.save(
        candidate_id="candidate-005",
        job_id="job-001",
        filename="candidate1.pdf",
        candidate_data={},
        score=candidate_score,
        categorization=categorization,
    )

    repository.save(
        candidate_id="candidate-006",
        job_id="job-002",
        filename="candidate2.pdf",
        candidate_data={},
        score=candidate_score,
        categorization=categorization,
    )

    candidates = repository.get_all()

    assert len(candidates) == 2

    candidate_ids = {
        candidate["candidate_id"]
        for candidate in candidates
    }

    assert candidate_ids == {
        "candidate-005",
        "candidate-006",
    }


# ---------------------------------------------------------------------------
# Get By Job
# ---------------------------------------------------------------------------


def test_get_by_job_returns_only_candidates_for_requested_job(
    repository: CandidateRepository,
    candidate_score: CandidateScore,
    categorization: CandidateCategorization,
) -> None:
    repository.save(
        candidate_id="candidate-007",
        job_id="job-a",
        filename="candidate1.pdf",
        candidate_data={},
        score=candidate_score,
        categorization=categorization,
    )

    repository.save(
        candidate_id="candidate-008",
        job_id="job-a",
        filename="candidate2.pdf",
        candidate_data={},
        score=candidate_score,
        categorization=categorization,
    )

    repository.save(
        candidate_id="candidate-009",
        job_id="job-b",
        filename="candidate3.pdf",
        candidate_data={},
        score=candidate_score,
        categorization=categorization,
    )

    candidates = repository.get_by_job(
        "job-a"
    )

    assert len(candidates) == 2

    candidate_ids = {
        candidate["candidate_id"]
        for candidate in candidates
    }

    assert candidate_ids == {
        "candidate-007",
        "candidate-008",
    }


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def test_update_changes_candidate_fields(
    repository: CandidateRepository,
    candidate_score: CandidateScore,
    categorization: CandidateCategorization,
) -> None:
    repository.save(
        candidate_id="candidate-010",
        job_id="job-001",
        filename="candidate.pdf",
        candidate_data={
            "name": "Original Name"
        },
        score=candidate_score,
        categorization=categorization,
    )

    result = repository.update(
        "candidate-010",
        {
            "filename": "updated.pdf",
            "candidate": {
                "name": "Updated Name"
            },
        },
    )

    assert result["filename"] == "updated.pdf"
    assert result["candidate"]["name"] == "Updated Name"


def test_update_rejects_empty_updates(
    repository: CandidateRepository,
) -> None:
    with pytest.raises(
        CandidateRepositoryError,
        match="At least one candidate update is required",
    ):
        repository.update(
            "candidate-010",
            {},
        )


def test_update_rejects_missing_candidate(
    repository: CandidateRepository,
) -> None:
    with pytest.raises(
        CandidateRepositoryError,
        match="does not exist",
    ):
        repository.update(
            "missing-candidate",
            {
                "filename": "updated.pdf"
            },
        )


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def test_delete_removes_existing_candidate(
    repository: CandidateRepository,
    candidate_score: CandidateScore,
    categorization: CandidateCategorization,
) -> None:
    repository.save(
        candidate_id="candidate-011",
        job_id="job-001",
        filename="candidate.pdf",
        candidate_data={},
        score=candidate_score,
        categorization=categorization,
    )

    assert repository.exists(
        "candidate-011"
    ) is True

    repository.delete(
        "candidate-011"
    )

    assert repository.exists(
        "candidate-011"
    ) is False


def test_delete_rejects_missing_candidate(
    repository: CandidateRepository,
) -> None:
    with pytest.raises(
        CandidateRepositoryError,
        match="does not exist",
    ):
        repository.delete(
            "missing-candidate"
        )