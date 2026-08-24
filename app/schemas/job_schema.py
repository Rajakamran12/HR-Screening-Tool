from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


JobStatus = Literal[
    "draft",
    "active",
    "closed",
]


class JobCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ...,
        min_length=1,
    )

    description: str = Field(
        ...,
        min_length=1,
    )

    required: bool

    weight: float = Field(
        ...,
        gt=0,
        le=100,
    )

    minimum_years: float = Field(
        default=0.0,
        ge=0,
    )


class JobThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shortlisted: float = Field(
        ...,
        ge=0,
        le=100,
    )

    maybe: float = Field(
        ...,
        ge=0,
        le=100,
    )

    @model_validator(mode="after")
    def validate_threshold_order(self) -> "JobThresholds":
        if self.maybe > self.shortlisted:
            raise ValueError(
                "The maybe threshold must be less than or equal to "
                "the shortlisted threshold."
            )

        return self


class Job(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(
        ...,
        min_length=1,
    )

    title: str = Field(
        ...,
        min_length=1,
    )

    description: str = Field(
        ...,
        min_length=1,
    )

    criteria: list[JobCriterion] = Field(
        ...,
        min_length=1,
    )

    thresholds: JobThresholds

    created_by: str = Field(
        ...,
        min_length=1,
    )

    created_at: str = Field(
        ...,
        min_length=1,
    )

    updated_at: str = Field(
        ...,
        min_length=1,
    )

    status: JobStatus = "draft"

    @model_validator(mode="after")
    def validate_criteria_weights(self) -> "Job":
        total_weight = sum(
            criterion.weight
            for criterion in self.criteria
        )

        if abs(total_weight - 100.0) > 0.0001:
            raise ValueError(
                "Criterion weights must total 100.0. "
                f"Current total: {total_weight:.4f}."
            )

        return self