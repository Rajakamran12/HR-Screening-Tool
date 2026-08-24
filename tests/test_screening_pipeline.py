import asyncio

from app.parsing.cv_parser import ParsedCV
from app.pipeline.screening_pipeline import (
    ScreeningPipeline,
    ScreeningPipelineError,
    ScreeningResult,
)
from app.schemas.categorization_schema import (
    CandidateCategorization,
)
from app.schemas.cv_schema import (
    CVExtraction,
    CandidateProfile,
    CVEducation,
    CVExperience,
    CVSkill,
    EmploymentPeriod,
)
from app.schemas.job_schema import (
    JobCriterion,
    JobThresholds,
)
from app.schemas.scoring_schema import (
    CandidateScore,
    CriterionEvidence,
    CriterionScore,
)
from app.scoring.candidate_categorizer import (
    CandidateCategorizer,
)


# ---------------------------------------------------------------------------
# Test Doubles
# ---------------------------------------------------------------------------


class FakeParser:
    """
    Test double for CVParser.

    The pipeline tests verify orchestration without requiring
    a real PDF file or filesystem parsing.
    """

    def __init__(
        self,
        parsed_cv: ParsedCV,
    ) -> None:
        self.parsed_cv = parsed_cv
        self.received_file = None

    def parse(
        self,
        file_path,
    ) -> ParsedCV:
        self.received_file = file_path

        return self.parsed_cv


class FakeExtractor:
    """
    Test double for CVExtractor.
    """

    def __init__(
        self,
        candidate: CVExtraction,
    ) -> None:
        self.candidate = candidate
        self.received_text = None

    async def extract(
        self,
        cv_text: str,
    ) -> CVExtraction:
        self.received_text = cv_text

        return self.candidate


class FakeScorer:
    """
    Test double for CandidateScorer.
    """

    def __init__(
        self,
        candidate_score: CandidateScore,
    ) -> None:
        self.candidate_score = candidate_score
        self.received_candidate = None
        self.received_criteria = None

    async def score(
        self,
        candidate,
        criteria,
    ) -> CandidateScore:
        self.received_candidate = candidate
        self.received_criteria = criteria

        return self.candidate_score


class FakeCategorizer:
    """
    Test double for CandidateCategorizer.
    """

    def __init__(
        self,
        categorization: CandidateCategorization,
    ) -> None:
        self.categorization = categorization
        self.received_score = None
        self.received_thresholds = None

    def categorize(
        self,
        candidate_score,
        thresholds,
    ) -> CandidateCategorization:
        self.received_score = candidate_score
        self.received_thresholds = thresholds

        return self.categorization


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def build_candidate() -> CVExtraction:
    """
    Build a complete valid CVExtraction fixture using the
    application's finalized CV schema.
    """

    skill = CVSkill(
        name="Python",
        category="programming",
        evidence=(
            "Developed Python applications and automation scripts."
        ),
    )

    employment_period = EmploymentPeriod(
        start_date="2021",
        end_date="2024",
        is_current=False,
    )

    experience = CVExperience(
        job_title="Software Engineer",
        company="Example Technologies",
        period=employment_period,
        location="Islamabad",
        demonstrated_skills=[
            "Python",
        ],
        responsibilities=[
            "Developed backend applications using Python.",
            "Implemented application features and automation.",
        ],
        evidence=[
            "Developed backend applications using Python.",
            "Implemented application features and automation.",
        ],
    )

    education = CVEducation(
        degree="BS Computer Science",
        field_of_study="Computer Science",
        institution="Example University",
        start_date="2017",
        end_date="2021",
        evidence=(
            "BS Computer Science from Example University, "
            "2017 to 2021."
        ),
    )

    profile = CandidateProfile(
        name="Test Candidate",
        professional_summary=(
            "Software engineer with practical Python development "
            "experience."
        ),
        skills=[
            skill,
        ],
        experience=[
            experience,
        ],
        education=[
            education,
        ],
        certifications=[],
        projects=[
            "Python backend automation project.",
        ],
        languages=[
            "English",
        ],
    )

    return CVExtraction(
        candidate=profile,
        source_quality="high",
        source_quality_reason=(
            "The CV contains clear employment, skills, education, "
            "and project information."
        ),
        missing_information=[],
    )


def build_candidate_score() -> CandidateScore:
    """
    Build a complete valid CandidateScore fixture using the
    application's finalized scoring schema.
    """

    criterion_score = CriterionScore(
        criterion_name="Python",
        score=85,
        expertise_level="advanced",
        relevant_years=3.0,
        recency_assessment=(
            "Python was demonstrated during the candidate's "
            "2021 to 2024 software engineering experience."
        ),
        seniority_assessment=(
            "The candidate demonstrated Python use in a "
            "Software Engineer role."
        ),
        depth_assessment=(
            "The CV describes practical backend development "
            "and automation work using Python."
        ),
        evidence=CriterionEvidence(
            evidence=[
                "Developed backend applications using Python.",
                "Implemented Python automation work.",
            ],
            evidence_location=[
                "Software Engineer experience",
                "Projects",
            ],
        ),
        reasoning=(
            "The candidate demonstrates practical Python usage "
            "through backend development and automation work."
        ),
        meets_requirement=True,
        confidence=0.9,
    )

    return CandidateScore(
        overall_score=85,
        criterion_scores=[
            criterion_score,
        ],
        strengths=[
            "Practical Python development experience.",
        ],
        gaps=[],
        overall_reasoning=(
            "The candidate demonstrates strong evidence of "
            "practical Python development experience."
        ),
        review_required=False,
        review_reason=None,
    )


def build_candidate_categorization(
    score: float = 85,
) -> CandidateCategorization:
    """
    Build a valid CandidateCategorization fixture.
    """

    return CandidateCategorization(
        category="shortlisted",
        score=score,
        shortlisted_threshold=80,
        maybe_threshold=60,
    )


def build_criterion() -> dict:
    """
    Build a valid job criterion fixture.

    The pipeline accepts dictionaries at its public boundary and
    normalizes them into the form required by the scorer.
    """

    return {
        "name": "Python",
        "description": (
            "Practical Python development experience."
        ),
        "required": True,
        "weight": 100.0,
        "minimum_years": 1.0,
    }


def build_thresholds() -> JobThresholds:
    """
    Build valid deterministic categorization thresholds.
    """

    return JobThresholds(
        shortlisted=80,
        maybe=60,
    )


def build_parsed_cv(
    tmp_path,
) -> ParsedCV:
    """
    Build a parsed CV fixture.
    """

    return ParsedCV(
        file_path=tmp_path / "candidate.pdf",
        text=(
            "Test Candidate\n"
            "Software Engineer\n"
            "Developed backend applications using Python."
        ),
        page_count=1,
    )


# ---------------------------------------------------------------------------
# Pipeline Tests
# ---------------------------------------------------------------------------


def test_pipeline_runs_all_stages(
    tmp_path,
):
    """
    Verify that the screening pipeline executes:

        parser
            ↓
        extractor
            ↓
        scorer
            ↓
        categorizer

    in the expected order and returns a ScreeningResult.
    """

    parsed_cv = build_parsed_cv(
        tmp_path
    )

    candidate = build_candidate()

    candidate_score = build_candidate_score()

    categorization = build_candidate_categorization()

    parser = FakeParser(
        parsed_cv=parsed_cv
    )

    extractor = FakeExtractor(
        candidate=candidate
    )

    scorer = FakeScorer(
        candidate_score=candidate_score
    )

    categorizer = FakeCategorizer(
        categorization=categorization
    )

    pipeline = ScreeningPipeline(
        parser=parser,
        extractor=extractor,
        scorer=scorer,
        categorizer=categorizer,
    )

    thresholds = build_thresholds()

    criteria = [
        build_criterion()
    ]

    result = asyncio.run(
        pipeline.screen(
            cv_file=tmp_path / "candidate.pdf",
            criteria=criteria,
            thresholds=thresholds,
        )
    )

    assert isinstance(
        result,
        ScreeningResult,
    )

    assert result.parsed_cv is parsed_cv

    assert result.candidate is candidate

    assert result.candidate_score is candidate_score

    assert result.categorization is categorization

    assert parser.received_file == (
        tmp_path / "candidate.pdf"
    )

    assert extractor.received_text == parsed_cv.text

    assert scorer.received_candidate is candidate

    assert scorer.received_criteria == [
        build_criterion()
    ]

    assert categorizer.received_score is candidate_score

    assert categorizer.received_thresholds is thresholds


def test_pipeline_passes_parsed_text_to_extractor(
    tmp_path,
):
    """
    Verify that the raw parsed CV text is passed to the extraction
    stage rather than the file path.
    """

    parsed_cv = build_parsed_cv(
        tmp_path
    )

    candidate = build_candidate()

    candidate_score = build_candidate_score()

    categorization = build_candidate_categorization()

    parser = FakeParser(
        parsed_cv=parsed_cv
    )

    extractor = FakeExtractor(
        candidate=candidate
    )

    scorer = FakeScorer(
        candidate_score=candidate_score
    )

    categorizer = FakeCategorizer(
        categorization=categorization
    )

    pipeline = ScreeningPipeline(
        parser=parser,
        extractor=extractor,
        scorer=scorer,
        categorizer=categorizer,
    )

    asyncio.run(
        pipeline.screen(
            cv_file=tmp_path / "candidate.pdf",
            criteria=[
                build_criterion()
            ],
            thresholds=build_thresholds(),
        )
    )

    assert extractor.received_text == parsed_cv.text

    assert extractor.received_text != str(
        tmp_path / "candidate.pdf"
    )


def test_pipeline_passes_extracted_candidate_to_scorer(
    tmp_path,
):
    """
    Verify that structured CV extraction is passed directly to
    the scoring stage.
    """

    parsed_cv = build_parsed_cv(
        tmp_path
    )

    candidate = build_candidate()

    candidate_score = build_candidate_score()

    categorization = build_candidate_categorization()

    parser = FakeParser(
        parsed_cv=parsed_cv
    )

    extractor = FakeExtractor(
        candidate=candidate
    )

    scorer = FakeScorer(
        candidate_score=candidate_score
    )

    categorizer = FakeCategorizer(
        categorization=categorization
    )

    pipeline = ScreeningPipeline(
        parser=parser,
        extractor=extractor,
        scorer=scorer,
        categorizer=categorizer,
    )

    asyncio.run(
        pipeline.screen(
            cv_file=tmp_path / "candidate.pdf",
            criteria=[
                build_criterion()
            ],
            thresholds=build_thresholds(),
        )
    )

    assert scorer.received_candidate is candidate

    assert scorer.received_candidate is not parsed_cv


def test_pipeline_passes_score_to_categorizer(
    tmp_path,
):
    """
    Verify that the AI-generated score is passed to deterministic
    categorization together with the configured thresholds.
    """

    parsed_cv = build_parsed_cv(
        tmp_path
    )

    candidate = build_candidate()

    candidate_score = build_candidate_score()

    categorization = build_candidate_categorization()

    parser = FakeParser(
        parsed_cv=parsed_cv
    )

    extractor = FakeExtractor(
        candidate=candidate
    )

    scorer = FakeScorer(
        candidate_score=candidate_score
    )

    categorizer = FakeCategorizer(
        categorization=categorization
    )

    pipeline = ScreeningPipeline(
        parser=parser,
        extractor=extractor,
        scorer=scorer,
        categorizer=categorizer,
    )

    thresholds = build_thresholds()

    asyncio.run(
        pipeline.screen(
            cv_file=tmp_path / "candidate.pdf",
            criteria=[
                build_criterion()
            ],
            thresholds=thresholds,
        )
    )

    assert categorizer.received_score is candidate_score

    assert categorizer.received_thresholds is thresholds


def test_pipeline_rejects_empty_criteria(
    tmp_path,
):
    """
    The pipeline must not execute scoring when no job criteria are
    supplied.
    """

    parser = FakeParser(
        parsed_cv=ParsedCV(
            file_path=tmp_path / "candidate.pdf",
            text="Candidate CV text",
            page_count=1,
        )
    )

    pipeline = ScreeningPipeline(
        parser=parser,
        extractor=None,
        scorer=None,
        categorizer=CandidateCategorizer(),
    )

    thresholds = JobThresholds(
        shortlisted=80,
        maybe=60,
    )

    try:
        asyncio.run(
            pipeline.screen(
                cv_file=tmp_path / "candidate.pdf",
                criteria=[],
                thresholds=thresholds,
            )
        )

    except ScreeningPipelineError as exc:
        assert (
            "At least one job scoring criterion is required"
            in str(exc)
        )

    else:
        raise AssertionError(
            "ScreeningPipelineError was not raised."
        )


def test_pipeline_rejects_invalid_threshold_type(
    tmp_path,
):
    """
    The pipeline must require a valid JobThresholds object.
    """

    parser = FakeParser(
        parsed_cv=ParsedCV(
            file_path=tmp_path / "candidate.pdf",
            text="Candidate CV text",
            page_count=1,
        )
    )

    pipeline = ScreeningPipeline(
        parser=parser,
    )

    valid_criterion = build_criterion()

    try:
        asyncio.run(
            pipeline.screen(
                cv_file=tmp_path / "candidate.pdf",
                criteria=[
                    valid_criterion
                ],
                thresholds={
                    "shortlisted": 80,
                    "maybe": 60,
                },
            )
        )

    except ScreeningPipelineError as exc:
        assert (
            "Thresholds must be a valid JobThresholds object"
            in str(exc)
        )

    else:
        raise AssertionError(
            "ScreeningPipelineError was not raised."
        )


def test_candidate_categorizer_remains_deterministic():
    """
    Verify that candidate categorization remains purely deterministic
    and does not require an LLM.
    """

    score = CandidateScore(
        overall_score=85,
        criterion_scores=[
            CriterionScore(
                criterion_name="Python",
                score=85,
                expertise_level="advanced",
                relevant_years=3.0,
                recency_assessment=(
                    "Python experience is supported by the "
                    "candidate's recent software engineering work."
                ),
                seniority_assessment=(
                    "Python was demonstrated in a Software Engineer "
                    "role."
                ),
                depth_assessment=(
                    "The CV demonstrates practical Python backend "
                    "development."
                ),
                evidence=CriterionEvidence(
                    evidence=[
                        "Developed backend applications using Python."
                    ],
                    evidence_location=[
                        "Software Engineer experience"
                    ],
                ),
                reasoning=(
                    "The candidate demonstrates practical Python "
                    "development experience."
                ),
                meets_requirement=True,
                confidence=0.9,
            )
        ],
        strengths=[
            "Practical Python development experience."
        ],
        gaps=[],
        overall_reasoning=(
            "The candidate demonstrates strong practical "
            "Python experience."
        ),
        review_required=False,
        review_reason=None,
    )

    thresholds = JobThresholds(
        shortlisted=80,
        maybe=60,
    )

    categorizer = CandidateCategorizer()

    result = categorizer.categorize(
        candidate_score=score,
        thresholds=thresholds,
    )

    assert result.category == "shortlisted"

    assert result.score == 85

    assert result.shortlisted_threshold == 80

    assert result.maybe_threshold == 60