import pytest

from app.core.job_manager import (
    JobManager,
    JobManagerError,
)
from app.schemas.job_schema import (
    JobCriterion,
    JobThresholds,
)


def build_criteria() -> list[JobCriterion]:
    """
    Build valid criteria whose weights total 100%.
    """

    return [
        JobCriterion(
            name="Python",
            description="Practical Python development experience.",
            required=True,
            weight=60.0,
            minimum_years=2.0,
        ),
        JobCriterion(
            name="Machine Learning",
            description="Practical machine learning experience.",
            required=True,
            weight=40.0,
            minimum_years=1.0,
        ),
    ]


def build_thresholds() -> JobThresholds:
    """
    Build valid candidate categorization thresholds.
    """

    return JobThresholds(
        shortlisted=80.0,
        maybe=60.0,
    )


def create_manager_with_job() -> JobManager:
    """
    Create a JobManager containing one valid job.
    """

    manager = JobManager()

    manager.create_job(
        job_id="job-001",
        title="AI Engineer",
        description="AI Engineer position.",
        criteria=build_criteria(),
        thresholds=build_thresholds(),
        created_by="admin",
    )

    return manager


def test_create_job_returns_valid_job():
    """
    Verify that a valid job can be created and registered.
    """

    manager = JobManager()

    job = manager.create_job(
        job_id="job-001",
        title="AI Engineer",
        description="AI Engineer position.",
        criteria=build_criteria(),
        thresholds=build_thresholds(),
        created_by="admin",
    )

    assert job.job_id == "job-001"
    assert job.title == "AI Engineer"
    assert job.description == "AI Engineer position."
    assert job.created_by == "admin"
    assert job.status == "draft"
    assert len(job.criteria) == 2
    assert job.thresholds.shortlisted == 80.0
    assert job.thresholds.maybe == 60.0


def test_created_job_can_be_retrieved():
    """
    Verify that a created job can be retrieved by ID.
    """

    manager = create_manager_with_job()

    job = manager.get_job(
        "job-001"
    )

    assert job.job_id == "job-001"
    assert job.title == "AI Engineer"


def test_get_unknown_job_raises_error():
    """
    Verify that retrieving a non-existent job fails clearly.
    """

    manager = JobManager()

    with pytest.raises(
        JobManagerError,
        match="was not found",
    ):
        manager.get_job(
            "missing-job"
        )


def test_duplicate_job_id_is_rejected():
    """
    Verify that job IDs are unique within the manager.
    """

    manager = create_manager_with_job()

    with pytest.raises(
        JobManagerError,
        match="already exists",
    ):
        manager.create_job(
            job_id="job-001",
            title="Another Job",
            description="Another position.",
            criteria=build_criteria(),
            thresholds=build_thresholds(),
            created_by="admin",
        )


def test_empty_job_id_is_rejected():
    """
    Verify that an empty job ID cannot be created.
    """

    manager = JobManager()

    with pytest.raises(
        JobManagerError,
        match="Job ID must be a non-empty string",
    ):
        manager.create_job(
            job_id="   ",
            title="AI Engineer",
            description="AI Engineer position.",
            criteria=build_criteria(),
            thresholds=build_thresholds(),
            created_by="admin",
        )


def test_empty_criteria_are_rejected():
    """
    Verify that a job cannot be created without criteria.
    """

    manager = JobManager()

    with pytest.raises(
        JobManagerError,
        match="At least one job criterion is required",
    ):
        manager.create_job(
            job_id="job-001",
            title="AI Engineer",
            description="AI Engineer position.",
            criteria=[],
            thresholds=build_thresholds(),
            created_by="admin",
        )


def test_invalid_criterion_type_is_rejected():
    """
    Verify that criteria must be JobCriterion objects.
    """

    manager = JobManager()

    with pytest.raises(
        JobManagerError,
        match="Every job criterion must be a valid JobCriterion",
    ):
        manager.create_job(
            job_id="job-001",
            title="AI Engineer",
            description="AI Engineer position.",
            criteria=[
                {
                    "name": "Python",
                    "description": "Python experience.",
                    "required": True,
                    "weight": 100.0,
                    "minimum_years": 1.0,
                }
            ],
            thresholds=build_thresholds(),
            created_by="admin",
        )


def test_invalid_threshold_type_is_rejected():
    """
    Verify that thresholds must be JobThresholds objects.
    """

    manager = JobManager()

    with pytest.raises(
        JobManagerError,
        match="Thresholds must be a valid JobThresholds object",
    ):
        manager.create_job(
            job_id="job-001",
            title="AI Engineer",
            description="AI Engineer position.",
            criteria=build_criteria(),
            thresholds={
                "shortlisted": 80.0,
                "maybe": 60.0,
            },
            created_by="admin",
        )


def test_job_exists_returns_correct_result():
    """
    Verify job existence checks.
    """

    manager = create_manager_with_job()

    assert manager.job_exists(
        "job-001"
    ) is True

    assert manager.job_exists(
        "missing-job"
    ) is False


def test_get_all_jobs_returns_registered_jobs():
    """
    Verify that all registered jobs can be retrieved.
    """

    manager = create_manager_with_job()

    manager.create_job(
        job_id="job-002",
        title="Backend Engineer",
        description="Backend engineering position.",
        criteria=build_criteria(),
        thresholds=build_thresholds(),
        created_by="admin",
    )

    jobs = manager.get_all_jobs()

    assert len(jobs) == 2
    assert jobs[0].job_id == "job-001"
    assert jobs[1].job_id == "job-002"


def test_get_jobs_by_status_returns_matching_jobs():
    """
    Verify filtering jobs by status.
    """

    manager = create_manager_with_job()

    manager.create_job(
        job_id="job-002",
        title="Backend Engineer",
        description="Backend engineering position.",
        criteria=build_criteria(),
        thresholds=build_thresholds(),
        created_by="admin",
        status="active",
    )

    manager.create_job(
        job_id="job-003",
        title="Data Scientist",
        description="Data science position.",
        criteria=build_criteria(),
        thresholds=build_thresholds(),
        created_by="admin",
        status="closed",
    )

    draft_jobs = manager.get_jobs_by_status(
        "draft"
    )

    active_jobs = manager.get_jobs_by_status(
        "active"
    )

    closed_jobs = manager.get_jobs_by_status(
        "closed"
    )

    assert len(draft_jobs) == 1
    assert draft_jobs[0].job_id == "job-001"

    assert len(active_jobs) == 1
    assert active_jobs[0].job_id == "job-002"

    assert len(closed_jobs) == 1
    assert closed_jobs[0].job_id == "job-003"


def test_update_job_changes_supplied_fields():
    """
    Verify that supplied job fields are updated.
    """

    manager = create_manager_with_job()

    original = manager.get_job(
        "job-001"
    )

    updated = manager.update_job(
        "job-001",
        title="Senior AI Engineer",
        description="Updated AI Engineer position.",
    )

    assert updated.job_id == "job-001"
    assert updated.title == "Senior AI Engineer"
    assert updated.description == "Updated AI Engineer position."

    assert updated.created_at == original.created_at
    assert updated.created_by == original.created_by

    assert updated.updated_at >= original.updated_at


def test_update_job_preserves_unsupplied_fields():
    """
    Verify that fields not supplied to update_job remain unchanged.
    """

    manager = create_manager_with_job()

    original = manager.get_job(
        "job-001"
    )

    updated = manager.update_job(
        "job-001",
        title="Updated AI Engineer",
    )

    assert updated.title == "Updated AI Engineer"
    assert updated.description == original.description
    assert updated.criteria == original.criteria
    assert updated.thresholds == original.thresholds
    assert updated.status == original.status
    assert updated.created_by == original.created_by
    assert updated.created_at == original.created_at


def test_update_job_revalidates_criteria():
    """
    Verify that replacement criteria are validated.
    """

    manager = create_manager_with_job()

    invalid_criteria = [
        JobCriterion(
            name="Python",
            description="Python experience.",
            required=True,
            weight=100.0,
            minimum_years=2.0,
        ),
        JobCriterion(
            name="ML",
            description="Machine learning experience.",
            required=True,
            weight=50.0,
            minimum_years=1.0,
        ),
    ]

    with pytest.raises(
        JobManagerError,
        match="Invalid updated job configuration",
    ):
        manager.update_job(
            "job-001",
            criteria=invalid_criteria,
        )


def test_set_status_changes_job_status():
    """
    Verify deterministic job status changes.
    """

    manager = create_manager_with_job()

    updated = manager.set_status(
        "job-001",
        "active",
    )

    assert updated.status == "active"
    assert manager.get_job(
        "job-001"
    ).status == "active"


def test_set_status_rejects_invalid_status():
    """
    Verify invalid status values are rejected.
    """

    manager = create_manager_with_job()

    with pytest.raises(
        JobManagerError,
        match="Invalid job status",
    ):
        manager.set_status(
            "job-001",
            "invalid",
        )


def test_delete_job_removes_job():
    """
    Verify that an existing job can be deleted.
    """

    manager = create_manager_with_job()

    assert manager.job_exists(
        "job-001"
    ) is True

    manager.delete_job(
        "job-001"
    )

    assert manager.job_exists(
        "job-001"
    ) is False

    with pytest.raises(
        JobManagerError,
        match="was not found",
    ):
        manager.get_job(
            "job-001"
        )


def test_delete_unknown_job_raises_error():
    """
    Verify that deleting a non-existent job fails clearly.
    """

    manager = JobManager()

    with pytest.raises(
        JobManagerError,
        match="was not found",
    ):
        manager.delete_job(
            "missing-job"
        )


def test_job_manager_accepts_initial_jobs():
    """
    Verify that an existing jobs dictionary can initialize the manager.
    """

    manager = JobManager()

    job = manager.create_job(
        job_id="job-001",
        title="AI Engineer",
        description="AI Engineer position.",
        criteria=build_criteria(),
        thresholds=build_thresholds(),
        created_by="admin",
    )

    initial_jobs = {
        "job-001": job,
    }

    restored_manager = JobManager(
        jobs=initial_jobs
    )

    assert restored_manager.job_exists(
        "job-001"
    )

    assert restored_manager.get_job(
        "job-001"
    ).title == "AI Engineer"


def test_initial_jobs_dictionary_is_copied():
    """
    Verify that JobManager does not directly mutate the caller's
    initial dictionary.
    """

    manager = JobManager()

    job = manager.create_job(
        job_id="job-001",
        title="AI Engineer",
        description="AI Engineer position.",
        criteria=build_criteria(),
        thresholds=build_thresholds(),
        created_by="admin",
    )

    initial_jobs = {
        "job-001": job,
    }

    restored_manager = JobManager(
        jobs=initial_jobs
    )

    restored_manager.delete_job(
        "job-001"
    )

    assert "job-001" in initial_jobs
    assert not restored_manager.job_exists(
        "job-001"
    )