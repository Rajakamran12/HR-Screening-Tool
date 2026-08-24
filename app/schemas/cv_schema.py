from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Common Types
# ---------------------------------------------------------------------------

SourceQuality = Literal[
    "high",
    "medium",
    "low",
]


# ---------------------------------------------------------------------------
# Skill Schema
# ---------------------------------------------------------------------------

class CVSkill(BaseModel):
    """
    A skill identified from the candidate CV.

    A skill mention alone must not be treated as demonstrated expertise.
    Evidence is stored separately so the scoring layer can distinguish
    between listed skills and skills demonstrated through experience.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ...,
        min_length=1,
        description="Name of the identified skill.",
    )

    category: str | None = Field(
        ...,
        description=(
            "Optional category for the skill, such as programming, "
            "machine learning, database, framework, cloud, or tool."
        ),
    )

    evidence: str = Field(
        ...,
        min_length=1,
        description=(
            "Evidence from the CV supporting the identification of "
            "this skill."
        ),
    )


# ---------------------------------------------------------------------------
# Employment Period
# ---------------------------------------------------------------------------

class EmploymentPeriod(BaseModel):
    """
    Employment or experience period extracted from the CV.
    """

    model_config = ConfigDict(extra="forbid")

    start_date: str | None = Field(
        ...,
        description=(
            "Start date or year exactly as supported by the CV."
        ),
    )

    end_date: str | None = Field(
        ...,
        description=(
            "End date or year exactly as supported by the CV."
        ),
    )

    is_current: bool = Field(
        ...,
        description=(
            "Whether the CV explicitly indicates that this experience "
            "is currently ongoing."
        ),
    )


# ---------------------------------------------------------------------------
# Professional Experience
# ---------------------------------------------------------------------------

class CVExperience(BaseModel):
    """
    A professional, freelance, internship, research, or other relevant
    experience entry extracted from the CV.
    """

    model_config = ConfigDict(extra="forbid")

    job_title: str = Field(
        ...,
        min_length=1,
        description="Job title or role as stated in the CV.",
    )

    company: str | None = Field(
        ...,
        description=(
            "Company, organization, client, or employer associated "
            "with the experience."
        ),
    )

    period: EmploymentPeriod = Field(
        ...,
        description="Employment or experience period.",
    )

    location: str | None = Field(
        ...,
        description=(
            "Work location when explicitly provided by the CV."
        ),
    )

    demonstrated_skills: list[str] = Field(
        ...,
        description=(
            "Skills explicitly demonstrated through the responsibilities "
            "or work described in this experience."
        ),
    )

    responsibilities: list[str] = Field(
        ...,
        description=(
            "Responsibilities or activities explicitly described "
            "in the CV."
        ),
    )

    evidence: list[str] = Field(
        ...,
        description=(
            "Source-grounded evidence extracted from this experience."
        ),
    )


# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------

class CVEducation(BaseModel):
    """
    Education entry extracted from the candidate CV.
    """

    model_config = ConfigDict(extra="forbid")

    degree: str = Field(
        ...,
        min_length=1,
        description="Degree or qualification as stated in the CV.",
    )

    field_of_study: str | None = Field(
        ...,
        description=(
            "Field, major, specialization, or program when explicitly "
            "provided by the CV."
        ),
    )

    institution: str | None = Field(
        ...,
        description=(
            "Educational institution when explicitly provided."
        ),
    )

    start_date: str | None = Field(
        ...,
        description=(
            "Education start date or year when available."
        ),
    )

    end_date: str | None = Field(
        ...,
        description=(
            "Education completion date or year when available."
        ),
    )

    evidence: str = Field(
        ...,
        min_length=1,
        description=(
            "Source-grounded evidence supporting this education entry."
        ),
    )


# ---------------------------------------------------------------------------
# Candidate Information
# ---------------------------------------------------------------------------

class CandidateProfile(BaseModel):
    """
    Structured candidate information extracted from a CV.

    Only information explicitly supported by the source CV should be
    represented here.
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(
        ...,
        description=(
            "Candidate's full name when explicitly present in the CV."
        ),
    )

    professional_summary: str | None = Field(
        ...,
        description=(
            "Professional summary or profile statement when present "
            "in the CV."
        ),
    )

    skills: list[CVSkill] = Field(
        ...,
        description=(
            "Skills identified from the CV."
        ),
    )

    experience: list[CVExperience] = Field(
        ...,
        description=(
            "Professional and relevant work experience."
        ),
    )

    education: list[CVEducation] = Field(
        ...,
        description=(
            "Education and academic qualifications."
        ),
    )

    certifications: list[str] = Field(
        ...,
        description=(
            "Certifications explicitly listed in the CV."
        ),
    )

    projects: list[str] = Field(
        ...,
        description=(
            "Projects explicitly described in the CV."
        ),
    )

    languages: list[str] = Field(
        ...,
        description=(
            "Languages explicitly listed in the CV."
        ),
    )


# ---------------------------------------------------------------------------
# Complete CV Extraction Result
# ---------------------------------------------------------------------------

class CVExtraction(BaseModel):
    """
    Complete structured result produced by the CV extraction stage.

    This model is intentionally evidence-oriented. The extraction model
    does not make hiring decisions or candidate classifications.
    """

    model_config = ConfigDict(extra="forbid")

    candidate: CandidateProfile = Field(
        ...,
        description=(
            "Structured candidate information extracted from the CV."
        ),
    )

    source_quality: SourceQuality = Field(
        ...,
        description=(
            "Assessment of the quality and completeness of the extracted "
            "source text."
        ),
    )

    source_quality_reason: str = Field(
        ...,
        min_length=1,
        description=(
            "Explanation of the source quality assessment."
        ),
    )

    missing_information: list[str] = Field(
        ...,
        description=(
            "Important candidate information that is absent, unclear, "
            "or insufficiently supported by the CV."
        ),
    )