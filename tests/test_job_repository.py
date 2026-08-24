import pytest

from app.core.job_repository import (
    JobRepository,
    JobRepositoryError,
)
from app.schemas.job_schema import (
    Job,
    JobCriterion,
    JobThresholds,
)


def create_job(
    job_id: str = "job-001",
    title: str = "Python Developer",
    status: str = "draft",
) -> Job:
    """
    Create a valid Job fixture for repository tests.
    """

    criterion = JobCriterion(
        name="Python",
        description="Strong Python programming skills.",
        weight=60,
        required=True,
        minimum_years=2,
    )

    second_criterion = JobCriterion(
        name="FastAPI",
        description="Experience building APIs with FastAPI.",
        weight=40,
        required=False,
        minimum_years=1,
    )

    thresholds = JobThresholds(
        shortlisted=70,
        maybe=50,
    )

    return Job(
        job_id=job_id,
        title=title,
        description="Python backend developer position.",
        criteria=[
            criterion,
            second_criterion,
        ],
        thresholds=thresholds,
        created_by="test-user",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        status=status,
    )


def test_repository_starts_empty() -> None:
    repository = JobRepository()

    assert repository.count() == 0
    assert repository.get_all() == []


def test_save_stores_job() -> None:
    repository = JobRepository()
    job = create_job()

    result = repository.save(job)

    assert result is job
    assert repository.count() == 1
    assert repository.get("job-001") is job


def test_save_replaces_existing_job_with_same_id() -> None:
    repository = JobRepository()

    original_job = create_job(
        title="Original Title",
    )

    replacement_job = create_job(
        title="Replacement Title",
    )

    repository.save(original_job)
    repository.save(replacement_job)

    assert repository.count() == 1
    assert repository.get("job-001") is replacement_job
    assert repository.get("job-001").title == "Replacement Title"


def test_save_rejects_invalid_job() -> None:
    repository = JobRepository()

    with pytest.raises(
        JobRepositoryError,
        match="Only valid Job objects can be stored",
    ):
        repository.save("not-a-job")  # type: ignore[arg-type]


def test_get_existing_job_returns_job() -> None:
    repository = JobRepository()
    job = create_job()

    repository.save(job)

    result = repository.get("job-001")

    assert result is job


def test_get_unknown_job_raises_error() -> None:
    repository = JobRepository()

    with pytest.raises(
        JobRepositoryError,
        match="Job with ID 'missing' was not found",
    ):
        repository.get("missing")


def test_get_rejects_empty_job_id() -> None:
    repository = JobRepository()

    with pytest.raises(
        JobRepositoryError,
        match="Job ID must be a non-empty string",
    ):
        repository.get("   ")


def test_get_rejects_non_string_job_id() -> None:
    repository = JobRepository()

    with pytest.raises(
        JobRepositoryError,
        match="Job ID must be a string",
    ):
        repository.get(123)  # type: ignore[arg-type]


def test_exists_returns_true_for_existing_job() -> None:
    repository = JobRepository()
    job = create_job()

    repository.save(job)

    assert repository.exists("job-001") is True


def test_exists_returns_false_for_unknown_job() -> None:
    repository = JobRepository()

    assert repository.exists("missing") is False


def test_get_all_returns_all_jobs_in_insertion_order() -> None:
    repository = JobRepository()

    first_job = create_job(
        job_id="job-001",
        title="First Job",
    )

    second_job = create_job(
        job_id="job-002",
        title="Second Job",
    )

    third_job = create_job(
        job_id="job-003",
        title="Third Job",
    )

    repository.save(first_job)
    repository.save(second_job)
    repository.save(third_job)

    result = repository.get_all()

    assert result == [
        first_job,
        second_job,
        third_job,
    ]


def test_update_replaces_existing_job() -> None:
    repository = JobRepository()

    original_job = create_job(
        title="Original Title",
    )

    updated_job = create_job(
        title="Updated Title",
    )

    repository.save(original_job)

    result = repository.update(updated_job)

    assert result is updated_job
    assert repository.count() == 1
    assert repository.get("job-001") is updated_job
    assert repository.get("job-001").title == "Updated Title"


def test_update_unknown_job_raises_error() -> None:
    repository = JobRepository()

    job = create_job(
        job_id="missing",
    )

    with pytest.raises(
        JobRepositoryError,
        match="Job with ID 'missing' was not found",
    ):
        repository.update(job)


def test_update_rejects_invalid_job() -> None:
    repository = JobRepository()

    with pytest.raises(
        JobRepositoryError,
        match="Only valid Job objects can be stored",
    ):
        repository.update("not-a-job")  # type: ignore[arg-type]


def test_delete_removes_existing_job() -> None:
    repository = JobRepository()
    job = create_job()

    repository.save(job)

    repository.delete("job-001")

    assert repository.count() == 0
    assert repository.exists("job-001") is False
    assert repository.get_all() == []


def test_delete_unknown_job_raises_error() -> None:
    repository = JobRepository()

    with pytest.raises(
        JobRepositoryError,
        match="Job with ID 'missing' was not found",
    ):
        repository.delete("missing")


def test_find_by_status_returns_matching_jobs() -> None:
    repository = JobRepository()

    draft_job = create_job(
        job_id="job-001",
        status="draft",
    )

    active_job = create_job(
        job_id="job-002",
        status="active",
    )

    closed_job = create_job(
        job_id="job-003",
        status="closed",
    )

    repository.save(draft_job)
    repository.save(active_job)
    repository.save(closed_job)

    result = repository.find_by_status("active")

    assert result == [
        active_job,
    ]


def test_find_by_status_returns_empty_list_when_no_jobs_match() -> None:
    repository = JobRepository()

    repository.save(
        create_job(
            status="draft",
        )
    )

    result = repository.find_by_status("closed")

    assert result == []


def test_save_all_stores_multiple_jobs() -> None:
    repository = JobRepository()

    jobs = [
        create_job(
            job_id="job-001",
        ),
        create_job(
            job_id="job-002",
        ),
        create_job(
            job_id="job-003",
        ),
    ]

    result = repository.save_all(jobs)

    assert result == jobs
    assert repository.count() == 3
    assert repository.get_all() == jobs


def test_save_all_replaces_existing_jobs() -> None:
    repository = JobRepository()

    original_job = create_job(
        job_id="job-001",
        title="Original",
    )

    replacement_job = create_job(
        job_id="job-001",
        title="Replacement",
    )

    repository.save(original_job)

    result = repository.save_all(
        [
            replacement_job,
        ]
    )

    assert result == [
        replacement_job,
    ]
    assert repository.count() == 1
    assert repository.get("job-001") is replacement_job
    assert repository.get("job-001").title == "Replacement"


def test_save_all_rejects_string_input() -> None:
    repository = JobRepository()

    with pytest.raises(
        JobRepositoryError,
        match="Jobs must be an iterable of Job objects",
    ):
        repository.save_all("not-an-iterable-of-jobs")  # type: ignore[arg-type]


def test_save_all_rejects_non_iterable_input() -> None:
    repository = JobRepository()

    with pytest.raises(
        JobRepositoryError,
        match="Jobs must be an iterable of Job objects",
    ):
        repository.save_all(123)  # type: ignore[arg-type]


def test_save_all_rejects_invalid_job_inside_iterable() -> None:
    repository = JobRepository()

    valid_job = create_job()

    with pytest.raises(
        JobRepositoryError,
        match="Only valid Job objects can be stored",
    ):
        repository.save_all(
            [
                valid_job,
                "invalid-job",  # type: ignore[list-item]
            ]
        )

    assert repository.get("job-001") is valid_job


def test_count_returns_number_of_jobs() -> None:
    repository = JobRepository()

    assert repository.count() == 0

    repository.save(
        create_job(
            job_id="job-001",
        )
    )

    assert repository.count() == 1

    repository.save(
        create_job(
            job_id="job-002",
        )
    )

    assert repository.count() == 2


def test_clear_removes_all_jobs() -> None:
    repository = JobRepository()

    repository.save(
        create_job(
            job_id="job-001",
        )
    )

    repository.save(
        create_job(
            job_id="job-002",
        )
    )

    assert repository.count() == 2

    repository.clear()

    assert repository.count() == 0
    assert repository.get_all() == []


def test_repository_accepts_initial_jobs() -> None:
    first_job = create_job(
        job_id="job-001",
    )

    second_job = create_job(
        job_id="job-002",
    )

    initial_jobs = {
        "job-001": first_job,
        "job-002": second_job,
    }

    repository = JobRepository(
        initial_jobs
    )

    assert repository.count() == 2
    assert repository.get_all() == [
        first_job,
        second_job,
    ]


def test_initial_jobs_dictionary_is_copied() -> None:
    first_job = create_job(
        job_id="job-001",
    )

    initial_jobs = {
        "job-001": first_job,
    }

    repository = JobRepository(
        initial_jobs
    )

    initial_jobs.clear()

    assert repository.count() == 1
    assert repository.get("job-001") is first_job


def test_repository_get_accepts_surrounding_whitespace_in_job_id() -> None:
    repository = JobRepository()

    job = create_job(
        job_id="job-001",
    )

    repository.save(job)

    result = repository.get(
        "  job-001  "
    )

    assert result is job


def test_repository_exists_accepts_surrounding_whitespace_in_job_id() -> None:
    repository = JobRepository()

    repository.save(
        create_job(
            job_id="job-001",
        )
    )

    assert repository.exists(
        "  job-001  "
    ) is True


def test_repository_delete_accepts_surrounding_whitespace_in_job_id() -> None:
    repository = JobRepository()

    repository.save(
        create_job(
            job_id="job-001",
        )
    )

    repository.delete(
        "  job-001  "
    )

    assert repository.count() == 0