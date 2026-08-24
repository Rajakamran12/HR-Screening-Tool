import pytest
from pydantic import ValidationError

from app.schemas.job_schema import (
    Job,
    JobCriterion,
    JobThresholds,
)


def create_valid_criterion(
    name: str,
    weight: float,
    required: bool = True,
    minimum_years: float = 0.0,
) -> JobCriterion:
    return JobCriterion(
        name=name,
        description=f"Experience with {name}.",
        required=required,
        weight=weight,
        minimum_years=minimum_years,
    )


def create_valid_thresholds() -> JobThresholds:
    return JobThresholds(
        shortlisted=75.0,
        maybe=50.0,
    )


def create_valid_job() -> Job:
    return Job(
        job_id="job-001",
        title="AI Engineer",
        description=(
            "AI Engineer responsible for developing and deploying "
            "machine learning systems."
        ),
        criteria=[
            create_valid_criterion(
                name="Python Development",
                weight=50.0,
                required=True,
                minimum_years=2.0,
            ),
            create_valid_criterion(
                name="Machine Learning",
                weight=30.0,
                required=True,
                minimum_years=1.0,
            ),
            create_valid_criterion(
                name="React",
                weight=20.0,
                required=False,
                minimum_years=1.0,
            ),
        ],
        thresholds=create_valid_thresholds(),
        created_by="recruiter-001",
        created_at="2026-08-17T10:00:00Z",
        updated_at="2026-08-17T10:00:00Z",
        status="draft",
    )


def test_valid_job_is_created():
    job = create_valid_job()

    assert job.job_id == "job-001"
    assert job.title == "AI Engineer"
    assert len(job.criteria) == 3
    assert job.thresholds.shortlisted == 75.0
    assert job.thresholds.maybe == 50.0
    assert job.status == "draft"


def test_criterion_weights_must_total_100():
    with pytest.raises(ValidationError):
        Job(
            job_id="job-001",
            title="AI Engineer",
            description="AI Engineer position.",
            criteria=[
                create_valid_criterion(
                    name="Python",
                    weight=60.0,
                ),
                create_valid_criterion(
                    name="Machine Learning",
                    weight=30.0,
                ),
            ],
            thresholds=create_valid_thresholds(),
            created_by="recruiter-001",
            created_at="2026-08-17T10:00:00Z",
            updated_at="2026-08-17T10:00:00Z",
        )


def test_criterion_weights_must_be_positive():
    with pytest.raises(ValidationError):
        create_valid_criterion(
            name="Python",
            weight=0.0,
        )


def test_negative_minimum_years_are_rejected():
    with pytest.raises(ValidationError):
        create_valid_criterion(
            name="Python",
            weight=100.0,
            minimum_years=-1.0,
        )


def test_negative_thresholds_are_rejected():
    with pytest.raises(ValidationError):
        JobThresholds(
            shortlisted=-1.0,
            maybe=50.0,
        )


def test_thresholds_above_100_are_rejected():
    with pytest.raises(ValidationError):
        JobThresholds(
            shortlisted=101.0,
            maybe=50.0,
        )


def test_maybe_threshold_cannot_exceed_shortlisted_threshold():
    with pytest.raises(ValidationError):
        JobThresholds(
            shortlisted=60.0,
            maybe=70.0,
        )


def test_job_requires_at_least_one_criterion():
    with pytest.raises(ValidationError):
        Job(
            job_id="job-001",
            title="AI Engineer",
            description="AI Engineer position.",
            criteria=[],
            thresholds=create_valid_thresholds(),
            created_by="recruiter-001",
            created_at="2026-08-17T10:00:00Z",
            updated_at="2026-08-17T10:00:00Z",
        )


def test_job_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        Job(
            job_id="job-001",
            title="AI Engineer",
            description="AI Engineer position.",
            criteria=[
                create_valid_criterion(
                    name="Python",
                    weight=100.0,
                ),
            ],
            thresholds=create_valid_thresholds(),
            created_by="recruiter-001",
            created_at="2026-08-17T10:00:00Z",
            updated_at="2026-08-17T10:00:00Z",
            unexpected_field="not allowed",
        )


def test_criterion_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        JobCriterion(
            name="Python",
            description="Python development experience.",
            required=True,
            weight=100.0,
            minimum_years=2.0,
            unexpected_field="not allowed",
        )


def test_job_status_is_restricted():
    with pytest.raises(ValidationError):
        Job(
            job_id="job-001",
            title="AI Engineer",
            description="AI Engineer position.",
            criteria=[
                create_valid_criterion(
                    name="Python",
                    weight=100.0,
                ),
            ],
            thresholds=create_valid_thresholds(),
            created_by="recruiter-001",
            created_at="2026-08-17T10:00:00Z",
            updated_at="2026-08-17T10:00:00Z",
            status="invalid",
        )


def test_required_and_nice_to_have_criteria_are_supported():
    job = create_valid_job()

    required_criteria = [
        criterion
        for criterion in job.criteria
        if criterion.required
    ]

    nice_to_have_criteria = [
        criterion
        for criterion in job.criteria
        if not criterion.required
    ]

    assert len(required_criteria) == 2
    assert len(nice_to_have_criteria) == 1
    assert nice_to_have_criteria[0].name == "React"


def test_minimum_years_are_preserved():
    job = create_valid_job()

    python_criterion = next(
        criterion
        for criterion in job.criteria
        if criterion.name == "Python Development"
    )

    assert python_criterion.minimum_years == 2.0