import pytest

from app.schemas.cv_schema import (
    CVExtraction,
    CandidateProfile,
    CVSkill,
)
from app.schemas.scoring_schema import CandidateScore
from app.scoring.candidate_scorer import (
    CandidateScorer,
    CandidateScoringError,
)


class FakeGroqService:
    """
    Fake Groq service used to test CandidateScorer without
    making real API calls.
    """

    def __init__(
        self,
        response=None,
        error=None,
    ):
        self.response = response
        self.error = error
        self.calls = []

    async def generate_structured(
        self,
        messages,
        schema,
        schema_name,
        max_tokens,
    ):
        self.calls.append(
            {
                "messages": messages,
                "schema": schema,
                "schema_name": schema_name,
                "max_tokens": max_tokens,
            }
        )

        if self.error is not None:
            raise self.error

        return self.response


def create_candidate() -> CVExtraction:
    return CVExtraction(
        candidate=CandidateProfile(
            name="John Doe",
            professional_summary=(
                "Python developer with professional "
                "backend experience."
            ),
            skills=[
                CVSkill(
                    name="Python",
                    category="programming",
                    evidence=(
                        "Professional backend development "
                        "experience using Python."
                    ),
                ),
                CVSkill(
                    name="FastAPI",
                    category="framework",
                    evidence=(
                        "Professional backend development "
                        "using FastAPI."
                    ),
                ),
                CVSkill(
                    name="SQL",
                    category="database",
                    evidence=(
                        "Professional backend development "
                        "involving SQL."
                    ),
                ),
            ],
            experience=[],
            education=[],
            certifications=[],
            projects=[],
            languages=[],
        ),
        source_quality="high",
        source_quality_reason=(
            "The CV contains sufficient structured information "
            "for candidate evaluation."
        ),
        missing_information=[],
    )


def create_criterion() -> dict:
    return {
        "name": "Python Development",
        "description": (
            "Professional Python development experience."
        ),
        "minimum_years": 2,
        "required": True,
    }


def create_candidate_score_data() -> dict:
    return {
        "overall_score": 80.0,
        "criterion_scores": [
            {
                "criterion_name": "Python Development",
                "score": 80.0,
                "expertise_level": "advanced",
                "relevant_years": 3.0,
                "recency_assessment": (
                    "Recent professional use."
                ),
                "seniority_assessment": (
                    "Demonstrated professional responsibility."
                ),
                "depth_assessment": (
                    "Strong practical Python experience."
                ),
                "evidence": {
                    "evidence": [
                        (
                            "Candidate demonstrates professional "
                            "Python development experience."
                        )
                    ],
                    "evidence_location": [
                        "Professional experience"
                    ],
                },
                "reasoning": (
                    "The candidate demonstrates strong practical "
                    "Python experience."
                ),
                "meets_requirement": True,
                "confidence": 0.90,
            }
        ],
        "strengths": [
            "Strong Python experience."
        ],
        "gaps": [
            "Limited evidence of senior architecture ownership."
        ],
        "overall_reasoning": (
            "Candidate demonstrates strong Python development "
            "capability."
        ),
        "review_required": False,
        "review_reason": "",
    }


def test_candidate_scorer_rejects_invalid_candidate():
    scorer = CandidateScorer(
        llm_service=FakeGroqService()
    )

    with pytest.raises(
        CandidateScoringError,
        match="Candidate must be a valid CVExtraction object",
    ):
        import asyncio

        asyncio.run(
            scorer.score(
                candidate="invalid candidate",
                criteria=[create_criterion()],
            )
        )


@pytest.mark.anyio
async def test_candidate_scorer_rejects_empty_criteria():
    scorer = CandidateScorer(
        llm_service=FakeGroqService()
    )

    with pytest.raises(
        CandidateScoringError,
        match="At least one scoring criterion is required",
    ):
        await scorer.score(
            candidate=create_candidate(),
            criteria=[],
        )


@pytest.mark.anyio
async def test_candidate_scorer_returns_valid_candidate_score():
    fake_service = FakeGroqService(
        response=create_candidate_score_data()
    )

    scorer = CandidateScorer(
        llm_service=fake_service
    )

    result = await scorer.score(
        candidate=create_candidate(),
        criteria=[create_criterion()],
    )

    assert isinstance(
        result,
        CandidateScore,
    )

    assert result.overall_score == 80.0

    assert len(
        result.criterion_scores
    ) == 1

    assert (
        result.criterion_scores[0].criterion_name
        == "Python Development"
    )


@pytest.mark.anyio
async def test_candidate_scorer_calls_llm_service():
    fake_service = FakeGroqService(
        response=create_candidate_score_data()
    )

    scorer = CandidateScorer(
        llm_service=fake_service
    )

    await scorer.score(
        candidate=create_candidate(),
        criteria=[create_criterion()],
    )

    assert len(
        fake_service.calls
    ) == 1


@pytest.mark.anyio
async def test_candidate_scorer_uses_correct_schema_name():
    fake_service = FakeGroqService(
        response=create_candidate_score_data()
    )

    scorer = CandidateScorer(
        llm_service=fake_service
    )

    await scorer.score(
        candidate=create_candidate(),
        criteria=[create_criterion()],
    )

    call = fake_service.calls[0]

    assert (
        call["schema_name"]
        == "candidate_score"
    )


@pytest.mark.anyio
async def test_candidate_scorer_uses_candidate_score_schema():
    fake_service = FakeGroqService(
        response=create_candidate_score_data()
    )

    scorer = CandidateScorer(
        llm_service=fake_service
    )

    await scorer.score(
        candidate=create_candidate(),
        criteria=[create_criterion()],
    )

    call = fake_service.calls[0]

    assert (
        call["schema"]
        == CandidateScore.model_json_schema()
    )


@pytest.mark.anyio
async def test_candidate_scorer_sends_candidate_and_criteria_to_llm():
    fake_service = FakeGroqService(
        response=create_candidate_score_data()
    )

    scorer = CandidateScorer(
        llm_service=fake_service
    )

    candidate = create_candidate()
    criterion = create_criterion()

    await scorer.score(
        candidate=candidate,
        criteria=[criterion],
    )

    call = fake_service.calls[0]

    messages = call["messages"]

    assert len(messages) == 2

    user_message = messages[1]["content"]

    assert "STRUCTURED CV:" in user_message
    assert "JOB CRITERIA:" in user_message
    assert "Python Development" in user_message


@pytest.mark.anyio
async def test_candidate_scorer_retries_after_runtime_error():
    class RetryFakeGroqService:
        def __init__(self):
            self.calls = 0

        async def generate_structured(
            self,
            messages,
            schema,
            schema_name,
            max_tokens,
        ):
            self.calls += 1

            if self.calls == 1:
                raise RuntimeError(
                    "Temporary Groq failure"
                )

            return create_candidate_score_data()

    fake_service = RetryFakeGroqService()

    scorer = CandidateScorer(
        llm_service=fake_service
    )

    result = await scorer.score(
        candidate=create_candidate(),
        criteria=[create_criterion()],
    )

    assert isinstance(
        result,
        CandidateScore,
    )

    assert result.overall_score == 80.0

    assert fake_service.calls == 2


@pytest.mark.anyio
async def test_candidate_scorer_raises_error_after_retries():
    class AlwaysFailingGroqService:
        def __init__(self):
            self.calls = 0

        async def generate_structured(
            self,
            messages,
            schema,
            schema_name,
            max_tokens,
        ):
            self.calls += 1

            raise RuntimeError(
                "Groq service unavailable"
            )

    fake_service = AlwaysFailingGroqService()

    scorer = CandidateScorer(
        llm_service=fake_service
    )

    with pytest.raises(
        CandidateScoringError,
        match="Candidate scoring failed after",
    ):
        await scorer.score(
            candidate=create_candidate(),
            criteria=[create_criterion()],
        )


def test_validate_score_accepts_valid_data():
    data = create_candidate_score_data()

    result = CandidateScorer._validate_score(
        data
    )

    assert isinstance(
        result,
        CandidateScore,
    )

    assert result.overall_score == 80.0


def test_validate_score_rejects_non_dictionary():
    with pytest.raises(
        CandidateScoringError,
        match="Groq scoring response must be a JSON object",
    ):
        CandidateScorer._validate_score(
            ["invalid"]
        )


def test_validate_score_rejects_invalid_schema():
    invalid_data = {
        "overall_score": 80.0,
        "criterion_scores": [],
        "strengths": [],
        "gaps": [],
        "overall_reasoning": "Invalid test result.",
        "review_required": False,
        "review_reason": "",
    }

    with pytest.raises(
        CandidateScoringError,
        match="does not satisfy the CandidateScore schema",
    ):
        CandidateScorer._validate_score(
            invalid_data
        )