
from pathlib import Path

import pytest

from app.core.candidate_repository import (
    CandidateRepositoryError,
)
from app.pipeline.screening_pipeline import (
    ScreeningPipelineError,
    ScreeningResult,
)
from app.schemas.categorization_schema import (
    CandidateCategorization,
)
from app.schemas.cv_schema import (
    CVExtraction,
)
from app.schemas.job_schema import (
    JobThresholds,
)
from app.schemas.scoring_schema import (
    CandidateScore,
    CriterionEvidence,
    CriterionScore,
)
from app.services.candidate_service import (
    CandidateService,
    CandidateServiceError,
)


# ---------------------------------------------------------------------------
# Fake Screening Pipeline
# ---------------------------------------------------------------------------

class FakePipeline:
    """
    Test double for ScreeningPipeline.
    """

    def __init__(
        self,
        result: ScreeningResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error

        self.calls: list[dict] = []

    async def screen(
        self,
        *,
        cv_file,
        criteria,
        thresholds,
    ):
        self.calls.append(
            {
                "cv_file": cv_file,
                "criteria": criteria,
                "thresholds": thresholds,
            }
        )

        if self.error is not None:
            raise self.error

        return self.result


# ---------------------------------------------------------------------------
# Fake Candidate Repository
# ---------------------------------------------------------------------------

class FakeCandidateRepository:
    """
    Test double for CandidateRepository.
    """

    def __init__(self) -> None:
        self.saved_candidates: dict[str, dict] = {}
        self.updated_candidates: dict[str, dict] = {}

        self.save_calls: list[dict] = []
        self.get_calls: list[str] = []
        self.exists_calls: list[str] = []
        self.get_all_calls = 0
        self.get_by_job_calls: list[str] = []
        self.update_calls: list[dict] = []
        self.delete_calls: list[str] = []

        self.save_error: Exception | None = None
        self.get_error: Exception | None = None
        self.exists_error: Exception | None = None
        self.get_all_error: Exception | None = None
        self.get_by_job_error: Exception | None = None
        self.update_error: Exception | None = None
        self.delete_error: Exception | None = None

    def save(
        self,
        *,
        candidate_id,
        job_id,
        filename,
        candidate_data,
        score,
        categorization,
    ):
        self.save_calls.append(
            {
                "candidate_id": candidate_id,
                "job_id": job_id,
                "filename": filename,
                "candidate_data": candidate_data,
                "score": score,
                "categorization": categorization,
            }
        )

        if self.save_error is not None:
            raise self.save_error

        document = {
            "candidate_id": candidate_id,
            "job_id": job_id,
            "filename": filename,
            "candidate": candidate_data,
            "score": score.model_dump(),
            "categorization": categorization.model_dump(),
        }

        self.saved_candidates[candidate_id] = document

        return document

    def get(
        self,
        candidate_id,
    ):
        self.get_calls.append(
            candidate_id
        )

        if self.get_error is not None:
            raise self.get_error

        if candidate_id not in self.saved_candidates:
            raise CandidateRepositoryError(
                f"Candidate '{candidate_id}' does not exist."
            )

        return self.saved_candidates[candidate_id]

    def exists(
        self,
        candidate_id,
    ):
        self.exists_calls.append(
            candidate_id
        )

        if self.exists_error is not None:
            raise self.exists_error

        return candidate_id in self.saved_candidates

    def get_all(self):
        self.get_all_calls += 1

        if self.get_all_error is not None:
            raise self.get_all_error

        return list(
            self.saved_candidates.values()
        )

    def get_by_job(
        self,
        job_id,
    ):
        self.get_by_job_calls.append(
            job_id
        )

        if self.get_by_job_error is not None:
            raise self.get_by_job_error

        return [
            candidate
            for candidate in self.saved_candidates.values()
            if candidate["job_id"] == job_id
        ]

    def update(
        self,
        candidate_id,
        updates,
    ):
        self.update_calls.append(
            {
                "candidate_id": candidate_id,
                "updates": updates,
            }
        )

        if self.update_error is not None:
            raise self.update_error

        if candidate_id not in self.saved_candidates:
            raise CandidateRepositoryError(
                f"Candidate '{candidate_id}' does not exist."
            )

        self.saved_candidates[candidate_id].update(
            updates
        )

        return self.saved_candidates[candidate_id]

    def delete(
        self,
        candidate_id,
    ):
        self.delete_calls.append(
            candidate_id
        )

        if self.delete_error is not None:
            raise self.delete_error

        if candidate_id not in self.saved_candidates:
            raise CandidateRepositoryError(
                f"Candidate '{candidate_id}' does not exist."
            )

        del self.saved_candidates[
            candidate_id
        ]


# ---------------------------------------------------------------------------
# Test Data
# ---------------------------------------------------------------------------

def build_candidate_extraction() -> CVExtraction:
    """
    Build a valid CVExtraction object for service tests.

    The fixture follows the current evidence-oriented CV schema:
        CVExtraction
            -> CandidateProfile
                -> CVSkill
                -> CVExperience
                -> CVEducation
    """

    return CVExtraction.model_validate(
        {
            "candidate": {
                "name": "John Doe",
                "professional_summary": (
                    "Python developer with four years of "
                    "professional backend development experience."
                ),
                "skills": [
                    {
                        "name": "Python",
                        "category": "programming",
                        "evidence": (
                            "Developed backend applications using Python."
                        ),
                    },
                    {
                        "name": "FastAPI",
                        "category": "framework",
                        "evidence": (
                            "Built REST APIs using FastAPI."
                        ),
                    },
                ],
                "experience": [
                    {
                        "job_title": "Python Developer",
                        "company": "Example Technologies",
                        "period": {
                            "start_date": "2022",
                            "end_date": "2026",
                            "is_current": True,
                        },
                        "location": None,
                        "demonstrated_skills": [
                            "Python",
                            "FastAPI",
                        ],
                        "responsibilities": [
                            "Developed backend applications using Python.",
                            "Built REST APIs using FastAPI.",
                        ],
                        "evidence": [
                            (
                                "Developed backend applications using "
                                "Python for four years."
                            ),
                            (
                                "Built REST APIs using FastAPI as part "
                                "of backend development responsibilities."
                            ),
                        ],
                    },
                ],
                "education": [
                    {
                        "degree": "BS Computer Science",
                        "field_of_study": "Computer Science",
                        "institution": "Example University",
                        "start_date": "2018",
                        "end_date": "2022",
                        "evidence": (
                            "Bachelor of Science in Computer Science, "
                            "Example University."
                        ),
                    },
                ],
                "certifications": [],
                "projects": [
                    "Backend API development project using Python and FastAPI."
                ],
                "languages": [
                    "English",
                ],
            },
            "source_quality": "high",
            "source_quality_reason": (
                "The CV contains clear professional experience, "
                "skills, education, and supporting evidence."
            ),
            "missing_information": [],
        }
    )


def build_candidate_score() -> CandidateScore:
    """
    Build a valid CandidateScore object.
    """

    criterion_score = CriterionScore(
        criterion_name="Python",
        score=85,
        expertise_level="advanced",
        relevant_years=4,
        recency_assessment=(
            "Recent Python experience is demonstrated "
            "through professional projects."
        ),
        seniority_assessment=(
            "Python was used in professional development "
            "responsibilities."
        ),
        depth_assessment=(
            "The CV demonstrates practical Python usage "
            "rather than a simple skills-list mention."
        ),
        evidence=CriterionEvidence(
            evidence=[
                "Developed backend applications using Python."
            ],
            evidence_location=[
                "Professional Experience"
            ],
        ),
        reasoning=(
            "The candidate demonstrates substantial "
            "professional Python experience."
        ),
        meets_requirement=True,
        confidence=0.9,
    )

    return CandidateScore(
        overall_score=85,
        criterion_scores=[
            criterion_score
        ],
        strengths=[
            "Strong Python experience."
        ],
        gaps=[],
        overall_reasoning=(
            "The candidate demonstrates strong "
            "relevant experience."
        ),
        review_required=False,
        review_reason=None,
    )


def build_categorization() -> CandidateCategorization:
    """
    Build a valid deterministic categorization.
    """

    return CandidateCategorization(
        category="shortlisted",
        score=85,
        shortlisted_threshold=80,
        maybe_threshold=60,
    )


def build_screening_result() -> ScreeningResult:
    """
    Build a complete ScreeningResult.
    """

    candidate = build_candidate_extraction()
    score = build_candidate_score()
    categorization = build_categorization()

    parsed_cv = type(
        "FakeParsedCV",
        (),
        {
            "file_path": Path("sample_cv.pdf"),
            "page_count": 1,
            "text": (
                "Python developer with four years "
                "of experience."
            ),
        },
    )()

    return ScreeningResult(
        parsed_cv=parsed_cv,
        candidate=candidate,
        candidate_score=score,
        categorization=categorization,
    )


def build_thresholds() -> JobThresholds:
    """
    Build valid job categorization thresholds.
    """

    return JobThresholds(
        shortlisted=80,
        maybe=60,
    )


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def test_service_initializes_with_injected_dependencies():
    pipeline = FakePipeline(
        result=build_screening_result()
    )

    repository = FakeCandidateRepository()

    service = CandidateService(
        pipeline=pipeline,
        repository=repository,
    )

    assert service.pipeline is pipeline
    assert service.repository is repository


# ---------------------------------------------------------------------------
# Screen Candidate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_screen_candidate_runs_pipeline_and_persists_result(
    tmp_path,
):
    cv_file = tmp_path / "candidate.pdf"

    cv_file.write_text(
        "Python developer with four years of experience.",
        encoding="utf-8",
    )

    pipeline = FakePipeline(
        result=build_screening_result()
    )

    repository = FakeCandidateRepository()

    service = CandidateService(
        pipeline=pipeline,
        repository=repository,
    )

    thresholds = build_thresholds()

    result = await service.screen_candidate(
        candidate_id="candidate-001",
        job_id="job-001",
        cv_file=cv_file,
        filename="candidate.pdf",
        criteria=[
            {
                "name": "Python",
                "description": "Python experience",
                "required": True,
                "weight": 100,
                "minimum_years": 2,
            }
        ],
        thresholds=thresholds,
    )

    assert result["candidate_id"] == "candidate-001"
    assert result["job_id"] == "job-001"
    assert result["filename"] == "candidate.pdf"

    assert len(
        pipeline.calls
    ) == 1

    assert pipeline.calls[0]["cv_file"] == cv_file
    assert pipeline.calls[0]["thresholds"] is thresholds

    assert len(
        repository.save_calls
    ) == 1

    assert repository.save_calls[0][
        "candidate_id"
    ] == "candidate-001"

    assert repository.save_calls[0][
        "job_id"
    ] == "job-001"


@pytest.mark.asyncio
async def test_screen_candidate_normalizes_identifiers_and_filename(
    tmp_path,
):
    cv_file = tmp_path / "candidate.pdf"

    cv_file.write_text(
        "Candidate CV",
        encoding="utf-8",
    )

    pipeline = FakePipeline(
        result=build_screening_result()
    )

    repository = FakeCandidateRepository()

    service = CandidateService(
        pipeline=pipeline,
        repository=repository,
    )

    await service.screen_candidate(
        candidate_id="  candidate-001  ",
        job_id="  job-001  ",
        cv_file=cv_file,
        filename="  candidate.pdf  ",
        criteria=[
            {
                "name": "Python",
                "description": "Python experience",
                "required": True,
                "weight": 100,
                "minimum_years": 2,
            }
        ],
        thresholds=build_thresholds(),
    )

    saved = repository.save_calls[0]

    assert saved["candidate_id"] == "candidate-001"
    assert saved["job_id"] == "job-001"
    assert saved["filename"] == "candidate.pdf"


@pytest.mark.asyncio
async def test_screen_candidate_rejects_missing_cv_file(
    tmp_path,
):
    missing_file = tmp_path / "missing.pdf"

    service = CandidateService(
        pipeline=FakePipeline(
            result=build_screening_result()
        ),
        repository=FakeCandidateRepository(),
    )

    with pytest.raises(
        CandidateServiceError,
        match="CV file does not exist",
    ):
        await service.screen_candidate(
            candidate_id="candidate-001",
            job_id="job-001",
            cv_file=missing_file,
            filename="candidate.pdf",
            criteria=[
                {
                    "name": "Python",
                    "description": "Python experience",
                    "required": True,
                    "weight": 100,
                    "minimum_years": 2,
                }
            ],
            thresholds=build_thresholds(),
        )


@pytest.mark.asyncio
async def test_screen_candidate_rejects_empty_candidate_id(
    tmp_path,
):
    cv_file = tmp_path / "candidate.pdf"

    cv_file.write_text(
        "Candidate CV",
        encoding="utf-8",
    )

    service = CandidateService(
        pipeline=FakePipeline(
            result=build_screening_result()
        ),
        repository=FakeCandidateRepository(),
    )

    with pytest.raises(
        CandidateServiceError,
        match="Candidate ID must be a non-empty string",
    ):
        await service.screen_candidate(
            candidate_id="   ",
            job_id="job-001",
            cv_file=cv_file,
            filename="candidate.pdf",
            criteria=[
                {
                    "name": "Python",
                    "description": "Python experience",
                    "required": True,
                    "weight": 100,
                    "minimum_years": 2,
                }
            ],
            thresholds=build_thresholds(),
        )


@pytest.mark.asyncio
async def test_screen_candidate_rejects_empty_filename(
    tmp_path,
):
    cv_file = tmp_path / "candidate.pdf"

    cv_file.write_text(
        "Candidate CV",
        encoding="utf-8",
    )

    service = CandidateService(
        pipeline=FakePipeline(
            result=build_screening_result()
        ),
        repository=FakeCandidateRepository(),
    )

    with pytest.raises(
        CandidateServiceError,
        match="Filename must be a non-empty string",
    ):
        await service.screen_candidate(
            candidate_id="candidate-001",
            job_id="job-001",
            cv_file=cv_file,
            filename="   ",
            criteria=[
                {
                    "name": "Python",
                    "description": "Python experience",
                    "required": True,
                    "weight": 100,
                    "minimum_years": 2,
                }
            ],
            thresholds=build_thresholds(),
        )


@pytest.mark.asyncio
async def test_screen_candidate_wraps_pipeline_errors(
    tmp_path,
):
    cv_file = tmp_path / "candidate.pdf"

    cv_file.write_text(
        "Candidate CV",
        encoding="utf-8",
    )

    pipeline = FakePipeline(
        error=ScreeningPipelineError(
            "CV parsing failed."
        )
    )

    repository = FakeCandidateRepository()

    service = CandidateService(
        pipeline=pipeline,
        repository=repository,
    )

    with pytest.raises(
        CandidateServiceError,
        match="Candidate screening failed",
    ):
        await service.screen_candidate(
            candidate_id="candidate-001",
            job_id="job-001",
            cv_file=cv_file,
            filename="candidate.pdf",
            criteria=[
                {
                    "name": "Python",
                    "description": "Python experience",
                    "required": True,
                    "weight": 100,
                    "minimum_years": 2,
                }
            ],
            thresholds=build_thresholds(),
        )

    assert repository.save_calls == []


@pytest.mark.asyncio
async def test_screen_candidate_wraps_repository_errors(
    tmp_path,
):
    cv_file = tmp_path / "candidate.pdf"

    cv_file.write_text(
        "Candidate CV",
        encoding="utf-8",
    )

    pipeline = FakePipeline(
        result=build_screening_result()
    )

    repository = FakeCandidateRepository()

    repository.save_error = CandidateRepositoryError(
        "Firestore unavailable."
    )

    service = CandidateService(
        pipeline=pipeline,
        repository=repository,
    )

    with pytest.raises(
        CandidateServiceError,
        match="Unable to persist screened candidate",
    ):
        await service.screen_candidate(
            candidate_id="candidate-001",
            job_id="job-001",
            cv_file=cv_file,
            filename="candidate.pdf",
            criteria=[
                {
                    "name": "Python",
                    "description": "Python experience",
                    "required": True,
                    "weight": 100,
                    "minimum_years": 2,
                }
            ],
            thresholds=build_thresholds(),
        )


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def test_get_candidate_delegates_to_repository():
    repository = FakeCandidateRepository()

    repository.saved_candidates["candidate-001"] = {
        "candidate_id": "candidate-001",
        "job_id": "job-001",
    }

    service = CandidateService(
        pipeline=FakePipeline(),
        repository=repository,
    )

    result = service.get_candidate(
        "  candidate-001  "
    )

    assert result["candidate_id"] == "candidate-001"
    assert repository.get_calls == [
        "candidate-001"
    ]


def test_candidate_exists_delegates_to_repository():
    repository = FakeCandidateRepository()

    repository.saved_candidates["candidate-001"] = {
        "candidate_id": "candidate-001",
    }

    service = CandidateService(
        pipeline=FakePipeline(),
        repository=repository,
    )

    assert service.candidate_exists(
        "candidate-001"
    ) is True

    assert service.candidate_exists(
        "candidate-999"
    ) is False


def test_get_all_candidates_delegates_to_repository():
    repository = FakeCandidateRepository()

    repository.saved_candidates = {
        "candidate-001": {
            "candidate_id": "candidate-001"
        },
        "candidate-002": {
            "candidate_id": "candidate-002"
        },
    }

    service = CandidateService(
        pipeline=FakePipeline(),
        repository=repository,
    )

    result = service.get_all_candidates()

    assert len(result) == 2
    assert repository.get_all_calls == 1


def test_get_candidates_by_job_delegates_to_repository():
    repository = FakeCandidateRepository()

    repository.saved_candidates = {
        "candidate-001": {
            "candidate_id": "candidate-001",
            "job_id": "job-001",
        },
        "candidate-002": {
            "candidate_id": "candidate-002",
            "job_id": "job-002",
        },
    }

    service = CandidateService(
        pipeline=FakePipeline(),
        repository=repository,
    )

    result = service.get_candidates_by_job(
        "  job-001  "
    )

    assert len(result) == 1
    assert result[0]["candidate_id"] == "candidate-001"
    assert repository.get_by_job_calls == [
        "job-001"
    ]


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

def test_update_candidate_delegates_to_repository():
    repository = FakeCandidateRepository()

    repository.saved_candidates["candidate-001"] = {
        "candidate_id": "candidate-001",
        "status": "active",
    }

    service = CandidateService(
        pipeline=FakePipeline(),
        repository=repository,
    )

    result = service.update_candidate(
        "  candidate-001  ",
        {
            "status": "reviewed"
        },
    )

    assert result["status"] == "reviewed"

    assert repository.update_calls == [
        {
            "candidate_id": "candidate-001",
            "updates": {
                "status": "reviewed"
            },
        }
    ]


def test_update_candidate_rejects_empty_updates():
    service = CandidateService(
        pipeline=FakePipeline(),
        repository=FakeCandidateRepository(),
    )

    with pytest.raises(
        CandidateServiceError,
        match="At least one candidate update is required",
    ):
        service.update_candidate(
            "candidate-001",
            {},
        )


def test_update_candidate_rejects_category_updates():
    service = CandidateService(
        pipeline=FakePipeline(),
        repository=FakeCandidateRepository(),
    )

    with pytest.raises(
        CandidateServiceError,
        match="Candidate category cannot be changed",
    ):
        service.update_candidate(
            "candidate-001",
            {
                "category": "shortlisted"
            },
        )


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def test_delete_candidate_delegates_to_repository():
    repository = FakeCandidateRepository()

    repository.saved_candidates["candidate-001"] = {
        "candidate_id": "candidate-001",
    }

    service = CandidateService(
        pipeline=FakePipeline(),
        repository=repository,
    )

    service.delete_candidate(
        "  candidate-001  "
    )

    assert repository.delete_calls == [
        "candidate-001"
    ]

    assert "candidate-001" not in (
        repository.saved_candidates
    )


# ---------------------------------------------------------------------------
# Repository Error Translation
# ---------------------------------------------------------------------------

def test_get_candidate_wraps_repository_error():
    repository = FakeCandidateRepository()

    repository.get_error = CandidateRepositoryError(
        "Firestore unavailable."
    )

    service = CandidateService(
        pipeline=FakePipeline(),
        repository=repository,
    )

    with pytest.raises(
        CandidateServiceError,
        match="Unable to retrieve candidate",
    ):
        service.get_candidate(
            "candidate-001"
        )


def test_get_all_candidates_wraps_repository_error():
    repository = FakeCandidateRepository()

    repository.get_all_error = CandidateRepositoryError(
        "Firestore unavailable."
    )

    service = CandidateService(
        pipeline=FakePipeline(),
        repository=repository,
    )

    with pytest.raises(
        CandidateServiceError,
        match="Unable to retrieve candidates",
    ):
        service.get_all_candidates()


def test_get_candidates_by_job_wraps_repository_error():
    repository = FakeCandidateRepository()

    repository.get_by_job_error = CandidateRepositoryError(
        "Firestore unavailable."
    )

    service = CandidateService(
        pipeline=FakePipeline(),
        repository=repository,
    )

    with pytest.raises(
        CandidateServiceError,
        match="Unable to retrieve candidates for job",
    ):
        service.get_candidates_by_job(
            "job-001"
        )


def test_update_candidate_wraps_repository_error():
    repository = FakeCandidateRepository()

    repository.update_error = CandidateRepositoryError(
        "Firestore unavailable."
    )

    service = CandidateService(
        pipeline=FakePipeline(),
        repository=repository,
    )

    with pytest.raises(
        CandidateServiceError,
        match="Unable to update candidate",
    ):
        service.update_candidate(
            "candidate-001",
            {
                "status": "reviewed"
            },
        )


def test_delete_candidate_wraps_repository_error():
    repository = FakeCandidateRepository()

    repository.delete_error = CandidateRepositoryError(
        "Firestore unavailable."
    )

    service = CandidateService(
        pipeline=FakePipeline(),
        repository=repository,
    )

    with pytest.raises(
        CandidateServiceError,
        match="Unable to delete candidate",
    ):
        service.delete_candidate(
            "candidate-001"
        )
