from app.schemas.categorization_schema import CandidateCategorization
from app.schemas.job_schema import JobThresholds
from app.schemas.scoring_schema import (
    CandidateScore,
    CriterionEvidence,
    CriterionScore,
)
from app.scoring.candidate_categorizer import CandidateCategorizer


def create_criterion_score() -> CriterionScore:
    return CriterionScore(
        criterion_name="Python Development",
        score=50.0,
        expertise_level="intermediate",
        relevant_years=1.0,
        recency_assessment="Recent demonstrated use.",
        seniority_assessment="Demonstrated professional use.",
        depth_assessment="Some practical depth demonstrated.",
        evidence=CriterionEvidence(
            evidence=[
                "Python was used in professional and project work."
            ],
            evidence_location=[
                "Professional experience and projects."
            ],
        ),
        reasoning="Test criterion assessment.",
        meets_requirement=False,
        confidence=0.80,
    )


def create_candidate_score(score: float) -> CandidateScore:
    return CandidateScore(
        overall_score=score,
        criterion_scores=[
            create_criterion_score(),
        ],
        strengths=[
            "Strong Python experience."
        ],
        gaps=[
            "Limited senior-level experience."
        ],
        overall_reasoning="Test scoring result.",
        review_required=False,
        review_reason="",
    )


def create_thresholds(
    shortlisted: float = 75.0,
    maybe: float = 50.0,
) -> JobThresholds:
    return JobThresholds(
        shortlisted=shortlisted,
        maybe=maybe,
    )


def test_score_above_shortlisted_threshold_is_shortlisted():
    categorizer = CandidateCategorizer()

    candidate_score = create_candidate_score(90.0)
    thresholds = create_thresholds()

    result = categorizer.categorize(
        candidate_score=candidate_score,
        thresholds=thresholds,
    )

    assert isinstance(result, CandidateCategorization)
    assert result.category == "shortlisted"
    assert result.score == 90.0


def test_score_exactly_at_shortlisted_threshold_is_shortlisted():
    categorizer = CandidateCategorizer()

    candidate_score = create_candidate_score(75.0)
    thresholds = create_thresholds()

    result = categorizer.categorize(
        candidate_score=candidate_score,
        thresholds=thresholds,
    )

    assert result.category == "shortlisted"
    assert result.score == 75.0


def test_score_between_thresholds_is_maybe():
    categorizer = CandidateCategorizer()

    candidate_score = create_candidate_score(60.0)
    thresholds = create_thresholds()

    result = categorizer.categorize(
        candidate_score=candidate_score,
        thresholds=thresholds,
    )

    assert result.category == "maybe"
    assert result.score == 60.0


def test_score_exactly_at_maybe_threshold_is_maybe():
    categorizer = CandidateCategorizer()

    candidate_score = create_candidate_score(50.0)
    thresholds = create_thresholds()

    result = categorizer.categorize(
        candidate_score=candidate_score,
        thresholds=thresholds,
    )

    assert result.category == "maybe"
    assert result.score == 50.0


def test_score_below_maybe_threshold_is_rejected():
    categorizer = CandidateCategorizer()

    candidate_score = create_candidate_score(49.99)
    thresholds = create_thresholds()

    result = categorizer.categorize(
        candidate_score=candidate_score,
        thresholds=thresholds,
    )

    assert result.category == "rejected"
    assert result.score == 49.99


def test_zero_score_is_rejected():
    categorizer = CandidateCategorizer()

    candidate_score = create_candidate_score(0.0)
    thresholds = create_thresholds()

    result = categorizer.categorize(
        candidate_score=candidate_score,
        thresholds=thresholds,
    )

    assert result.category == "rejected"
    assert result.score == 0.0


def test_maximum_score_is_shortlisted():
    categorizer = CandidateCategorizer()

    candidate_score = create_candidate_score(100.0)
    thresholds = create_thresholds()

    result = categorizer.categorize(
        candidate_score=candidate_score,
        thresholds=thresholds,
    )

    assert result.category == "shortlisted"
    assert result.score == 100.0


def test_thresholds_are_preserved_in_result():
    categorizer = CandidateCategorizer()

    candidate_score = create_candidate_score(65.0)
    thresholds = create_thresholds(
        shortlisted=80.0,
        maybe=55.0,
    )

    result = categorizer.categorize(
        candidate_score=candidate_score,
        thresholds=thresholds,
    )

    assert result.category == "maybe"
    assert result.score == 65.0
    assert result.shortlisted_threshold == 80.0
    assert result.maybe_threshold == 55.0


def test_convenience_function_produces_same_result():
    from app.scoring.candidate_categorizer import categorize_candidate

    candidate_score = create_candidate_score(80.0)
    thresholds = create_thresholds()

    result = categorize_candidate(
        candidate_score=candidate_score,
        thresholds=thresholds,
    )

    assert isinstance(result, CandidateCategorization)
    assert result.category == "shortlisted"
    assert result.score == 80.0
    assert result.shortlisted_threshold == 75.0
    assert result.maybe_threshold == 50.0