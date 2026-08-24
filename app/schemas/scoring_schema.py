from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Expertise Level
# ---------------------------------------------------------------------------

ExpertiseLevel = Literal[
    "none",
    "basic",
    "intermediate",
    "advanced",
    "expert",
]


# ---------------------------------------------------------------------------
# Screening Criterion
# ---------------------------------------------------------------------------

class ScreeningCriterion(BaseModel):
    """
    A single hardcoded or job-defined screening criterion.

    The scoring system evaluates candidates against explicit criteria
    rather than allowing the LLM to invent its own requirements.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    name: str = Field(
        ...,
        min_length=1,
        description="Name of the screening criterion.",
    )

    description: str = Field(
        ...,
        min_length=1,
        description="What the criterion requires.",
    )

    required: bool = Field(
        ...,
        description="Whether the criterion is mandatory.",
    )

    weight: float = Field(
        ...,
        ge=0,
        le=1,
        description="Relative importance of the criterion.",
    )

    minimum_years: float | None = Field(
        default=None,
        ge=0,
        description=(
            "Minimum relevant years of experience when the "
            "criterion is experience-based."
        ),
    )


# ---------------------------------------------------------------------------
# Criterion Evidence
# ---------------------------------------------------------------------------

class CriterionEvidence(BaseModel):
    """
    Evidence supporting a candidate's evaluation for one criterion.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    evidence: list[str] = Field(
        default_factory=list,
        description=(
            "Specific evidence quoted or closely paraphrased "
            "from the candidate CV supporting the evaluation."
        ),
    )

    evidence_location: list[str] = Field(
        default_factory=list,
        description=(
            "Description of where the evidence appears in the CV, "
            "such as a job title, employment section, project, "
            "or education section."
        ),
    )


# ---------------------------------------------------------------------------
# Criterion Score
# ---------------------------------------------------------------------------

class CriterionScore(BaseModel):
    """
    Evaluation of one candidate against one screening criterion.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    criterion_name: str = Field(
        ...,
        min_length=1,
        description="Name of the evaluated criterion.",
    )

    score: float = Field(
        ...,
        ge=0,
        le=100,
        description=(
            "Criterion score from 0 to 100 based on "
            "demonstrated qualification."
        ),
    )

    expertise_level: ExpertiseLevel = Field(
        ...,
        description=(
            "Estimated expertise level based on demonstrated "
            "use, depth, recency, role, and seniority."
        ),
    )

    relevant_years: float = Field(
        ...,
        ge=0,
        description=(
            "Estimated years of directly relevant experience "
            "supported by the CV."
        ),
    )

    recency_assessment: str = Field(
        ...,
        min_length=1,
        description=(
            "Assessment of how recent the relevant experience "
            "is, grounded in the CV."
        ),
    )

    seniority_assessment: str = Field(
        ...,
        min_length=1,
        description=(
            "Assessment of the seniority and responsibility "
            "level at which the relevant skill or experience "
            "was demonstrated."
        ),
    )

    depth_assessment: str = Field(
        ...,
        min_length=1,
        description=(
            "Assessment of the depth of demonstrated experience "
            "rather than simple skill-list presence."
        ),
    )

    evidence: CriterionEvidence = Field(
        ...,
        description="Source-grounded evidence for the evaluation.",
    )

    reasoning: str = Field(
        ...,
        min_length=1,
        description=(
            "Concise explanation of how the evidence supports "
            "the score."
        ),
    )

    meets_requirement: bool = Field(
        ...,
        description=(
            "Whether the candidate appears to meet the criterion's "
            "defined requirement based on the evidence."
        ),
    )

    confidence: float = Field(
        ...,
        ge=0,
        le=1,
        description=(
            "Confidence in this criterion evaluation based on "
            "the quality and completeness of available CV evidence."
        ),
    )


# ---------------------------------------------------------------------------
# Candidate Score
# ---------------------------------------------------------------------------

class CandidateScore(BaseModel):
    """
    Complete AI-generated screening assessment.

    This model contains recommendations and evidence only.

    Final candidate categorization is deliberately excluded and
    will be performed deterministically by application code.
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    overall_score: float = Field(
        ...,
        ge=0,
        le=100,
        description=(
            "Weighted overall candidate score from 0 to 100."
        ),
    )

    criterion_scores: list[CriterionScore] = Field(
        ...,
        min_length=1,
        description=(
            "Evaluation for every screening criterion supplied "
            "to the model."
        ),
    )

    strengths: list[str] = Field(
        default_factory=list,
        description=(
            "Important job-relevant strengths supported by "
            "the CV evidence."
        ),
    )

    gaps: list[str] = Field(
        default_factory=list,
        description=(
            "Important job-relevant gaps or weaknesses supported "
            "by the CV."
        ),
    )

    overall_reasoning: str = Field(
        ...,
        min_length=1,
        description=(
            "Overall explanation of the assessment based on "
            "criterion-level evidence."
        ),
    )

    review_required: bool = Field(
        ...,
        description=(
            "Whether the result should receive human review because "
            "the available evidence is insufficient, ambiguous, "
            "or low-confidence."
        ),
    )

    review_reason: str | None = Field(
        default=None,
        description=(
            "Reason human review is required, when applicable."
        ),
    )


# ---------------------------------------------------------------------------
# Backward-Compatible Alias
# ---------------------------------------------------------------------------

CandidateScoringResult = CandidateScore