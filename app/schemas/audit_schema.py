from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AuditAction(str, Enum):
    """
    Supported candidate audit actions.
    """

    CATEGORIZATION_OVERRIDE = "categorization_override"
    CANDIDATE_UPDATE = "candidate_update"


class CandidateCategory(str, Enum):
    """
    Allowed recruiter-facing candidate categories.

    These values intentionally match the deterministic
    categorization values used by the screening system.
    """

    SHORTLISTED = "Shortlisted"
    MAYBE = "Maybe"
    REJECTED = "Rejected"


class CandidateOverrideRequest(BaseModel):
    """
    Request used by a recruiter to manually override
    an automatically generated candidate category.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    category: CandidateCategory

    reason: str = Field(
        min_length=1,
        max_length=2000,
    )


class CandidateAuditRecord(BaseModel):
    """
    Immutable audit record describing a human action taken
    against a candidate.

    Every manual categorization override must create one of
    these records.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    audit_id: str = Field(
        min_length=1
    )

    candidate_id: str = Field(
        min_length=1
    )

    job_id: str = Field(
        min_length=1
    )

    action: AuditAction

    previous_category: CandidateCategory | None = None

    new_category: CandidateCategory | None = None

    reason: str = Field(
        min_length=1,
        max_length=2000,
    )

    performed_by: str = Field(
        min_length=1
    )

    created_at: datetime | None = None