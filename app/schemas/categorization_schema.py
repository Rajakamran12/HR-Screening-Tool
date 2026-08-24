from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


CandidateCategory = Literal[
    "shortlisted",
    "maybe",
    "rejected",
]


class CandidateCategorization(BaseModel):
    """
    Deterministic application-level candidate categorization.

    This model represents the result produced by application logic
    using the AI-generated overall score and the job's configured
    thresholds.

    The LLM must never directly produce this category.
    """

    model_config = ConfigDict(extra="forbid")

    category: CandidateCategory = Field(
        ...,
        description="Deterministic candidate category.",
    )

    score: float = Field(
        ...,
        ge=0,
        le=100,
        description="AI-generated overall candidate score used for categorization.",
    )

    shortlisted_threshold: float = Field(
        ...,
        ge=0,
        le=100,
        description="Job threshold required for the shortlisted category.",
    )

    maybe_threshold: float = Field(
        ...,
        ge=0,
        le=100,
        description="Job threshold required for the maybe category.",
    )