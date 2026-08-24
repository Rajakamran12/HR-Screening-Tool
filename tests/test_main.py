import asyncio
from pathlib import Path

import pytest

import main
from app.pipeline.screening_pipeline import (
    ScreeningPipelineError,
)


class FakeScreeningPipeline:
    """
    Test double for ScreeningPipeline.

    The test verifies that main.py delegates the complete screening
    operation to ScreeningPipeline rather than manually executing
    individual pipeline stages.
    """

    def __init__(self) -> None:
        self.received_cv_file = None
        self.received_criteria = None
        self.received_thresholds = None

    async def screen(
        self,
        cv_file,
        criteria,
        thresholds,
    ):
        self.received_cv_file = cv_file
        self.received_criteria = criteria
        self.received_thresholds = thresholds

        return FakeScreeningResult()


class FakeExtraction:
    """
    Minimal extraction result used by the console output test.
    """

    class Candidate:
        name = "Test Candidate"
        skills = []
        experience = []
        education = []
        certifications = []
        projects = []
        languages = []

    candidate = Candidate()

    source_quality = "high"
    source_quality_reason = "Test source quality."
    missing_information = []


class FakeCriterionEvidence:
    """
    Minimal criterion evidence object.
    """

    evidence = []
    evidence_location = []


class FakeCriterionScore:
    """
    Minimal criterion score object.
    """

    criterion_name = "Python Development"
    score = 85.0
    expertise_level = "advanced"
    relevant_years = 3.0
    recency_assessment = "Recent."
    seniority_assessment = "Appropriate."
    depth_assessment = "Demonstrated."
    evidence = FakeCriterionEvidence()
    reasoning = "Strong demonstrated experience."
    meets_requirement = True
    confidence = 0.95


class FakeCandidateScore:
    """
    Minimal candidate score object.
    """

    overall_score = 85.0
    criterion_scores = [
        FakeCriterionScore()
    ]
    strengths = [
        "Strong Python experience."
    ]
    gaps = []
    overall_reasoning = (
        "Candidate demonstrates strong relevant experience."
    )
    review_required = False
    review_reason = None


class FakeCategorization:
    """
    Minimal deterministic categorization result.
    """

    category = "shortlisted"
    score = 85.0
    shortlisted_threshold = 80.0
    maybe_threshold = 60.0


class FakeScreeningResult:
    """
    Minimal ScreeningResult replacement.
    """

    extraction = FakeExtraction()
    candidate_score = FakeCandidateScore()
    categorization = FakeCategorization()


def test_step0_criteria_are_valid():
    """
    Verify the Step 0 criteria configuration is valid and its weights
    total 100 percent when represented as percentages.
    """

    assert len(main.STEP0_CRITERIA) == 3

    total_weight = sum(
        criterion.weight
        for criterion in main.STEP0_CRITERIA
    )

    assert total_weight == pytest.approx(1.0)


def test_step0_thresholds_are_valid():
    """
    Verify the configured Step 0 thresholds are valid and ordered
    correctly.
    """

    assert (
        main.STEP0_THRESHOLDS.shortlisted
        == 80.0
    )

    assert (
        main.STEP0_THRESHOLDS.maybe
        == 60.0
    )

    assert (
        main.STEP0_THRESHOLDS.maybe
        <= main.STEP0_THRESHOLDS.shortlisted
    )


def test_get_cv_path_requires_exactly_one_argument(
    monkeypatch,
):
    """
    Verify that the CLI requires exactly one CV path argument.
    """

    monkeypatch.setattr(
        main.sys,
        "argv",
        ["main.py"],
    )

    with pytest.raises(
        ValueError,
        match="Usage: python main.py <path-to-cv.pdf>",
    ):
        main.get_cv_path()


def test_get_cv_path_returns_resolved_path(
    monkeypatch,
    tmp_path,
):
    """
    Verify that the supplied CV path is expanded and resolved.
    """

    cv_file = (
        tmp_path / "candidate.pdf"
    )

    monkeypatch.setattr(
        main.sys,
        "argv",
        [
            "main.py",
            str(cv_file),
        ],
    )

    result = main.get_cv_path()

    assert isinstance(
        result,
        Path,
    )

    assert result == cv_file.resolve()


def test_run_step0_delegates_to_screening_pipeline(
    monkeypatch,
    tmp_path,
):
    """
    Verify that run_step0 delegates the complete operation to
    ScreeningPipeline.
    """

    fake_pipeline = FakeScreeningPipeline()

    def fake_pipeline_constructor():
        return fake_pipeline

    monkeypatch.setattr(
        main,
        "ScreeningPipeline",
        fake_pipeline_constructor,
    )

    monkeypatch.setattr(
        main,
        "initialize_directories",
        lambda: None,
    )

    cv_file = (
        tmp_path / "candidate.pdf"
    )

    asyncio.run(
        main.run_step0(
            cv_file
        )
    )

    assert (
        fake_pipeline.received_cv_file
        == cv_file
    )

    assert (
        fake_pipeline.received_criteria
        == main.STEP0_CRITERIA
    )

    assert (
        fake_pipeline.received_thresholds
        == main.STEP0_THRESHOLDS
    )


def test_run_step0_propagates_pipeline_error(
    monkeypatch,
    tmp_path,
):
    """
    Verify that pipeline failures are not silently swallowed by
    run_step0.
    """

    class FailingPipeline:
        async def screen(
            self,
            cv_file,
            criteria,
            thresholds,
        ):
            raise ScreeningPipelineError(
                "Test pipeline failure."
            )

    monkeypatch.setattr(
        main,
        "ScreeningPipeline",
        FailingPipeline,
    )

    monkeypatch.setattr(
        main,
        "initialize_directories",
        lambda: None,
    )

    cv_file = (
        tmp_path / "candidate.pdf"
    )

    with pytest.raises(
        ScreeningPipelineError,
        match="Test pipeline failure",
    ):
        asyncio.run(
            main.run_step0(
                cv_file
            )
        )


def test_print_screening_result_displays_complete_result(
    capsys,
):
    """
    Verify that the console presentation layer displays extraction,
    scoring, and deterministic categorization results.
    """

    result = FakeScreeningResult()

    main.print_screening_result(
        result
    )

    captured = capsys.readouterr()

    output = captured.out

    assert (
        "STRUCTURED CV EXTRACTION"
        in output
    )

    assert (
        "CANDIDATE SCORING"
        in output
    )

    assert (
        "CANDIDATE CATEGORIZATION"
        in output
    )

    assert (
        "Test Candidate"
        in output
    )

    assert (
        "85.00/100"
        in output
    )

    assert (
        "SHORTLISTED"
        in output
    )

    assert (
        "80.00"
        in output
    )

    assert (
        "60.00"
        in output
    )