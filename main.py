
import asyncio
import sys
from pathlib import Path

from app.core.config import initialize_directories
from app.pipeline.screening_pipeline import (
    ScreeningPipeline,
    ScreeningPipelineError,
)
from app.schemas.job_schema import JobThresholds
from app.schemas.scoring_schema import ScreeningCriterion


# ---------------------------------------------------------------------------
# Step 0 Screening Criteria
# ---------------------------------------------------------------------------

STEP0_CRITERIA = [
    ScreeningCriterion(
        name="Python Development",
        description=(
            "Professional experience developing software using Python, "
            "with evidence of practical implementation rather than only "
            "listing Python as a skill."
        ),
        required=True,
        weight=0.40,
        minimum_years=2.0,
    ),
    ScreeningCriterion(
        name="Machine Learning",
        description=(
            "Practical experience applying machine learning techniques "
            "in professional, academic, research, or project work, "
            "with evidence of actual implementation."
        ),
        required=True,
        weight=0.35,
        minimum_years=1.0,
    ),
    ScreeningCriterion(
        name="SQL and Database Experience",
        description=(
            "Practical experience working with SQL or relational "
            "databases, including evidence of actual database usage."
        ),
        required=False,
        weight=0.25,
        minimum_years=1.0,
    ),
]


# ---------------------------------------------------------------------------
# Step 0 Thresholds
# ---------------------------------------------------------------------------

STEP0_THRESHOLDS = JobThresholds(
    shortlisted=80.0,
    maybe=60.0,
)


# ---------------------------------------------------------------------------
# Console Output Helpers
# ---------------------------------------------------------------------------

def print_section(
    title: str,
) -> None:
    """
    Print a clearly separated console section.
    """

    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def print_screening_result(
    result,
) -> None:
    """
    Display the complete screening result.
    """

    # -----------------------------------------------------------------------
    # Structured CV
    # -----------------------------------------------------------------------

    print_section(
        "STRUCTURED CV EXTRACTION"
    )

    extraction = result.extraction
    candidate = extraction.candidate

    print(
        f"Source Quality: "
        f"{extraction.source_quality}"
    )

    print(
        f"Source Quality Reason: "
        f"{extraction.source_quality_reason}"
    )

    print()

    print(
        f"Candidate Name: "
        f"{candidate.name or 'Not provided'}"
    )

    print()

    # -----------------------------------------------------------------------
    # Skills
    # -----------------------------------------------------------------------

    print("Skills:")

    if candidate.skills:
        for skill in candidate.skills:
            print(
                f"  - {skill.name}"
                f" | Category: "
                f"{skill.category or 'N/A'}"
            )

            print(
                f"    Evidence: "
                f"{skill.evidence}"
            )

    else:
        print("  - None identified")

    print()

    # -----------------------------------------------------------------------
    # Experience
    # -----------------------------------------------------------------------

    print("Experience:")

    if candidate.experience:
        for experience in candidate.experience:

            start_date = (
                experience.period.start_date
                or "Unknown"
            )

            end_date = (
                "Current"
                if experience.period.is_current
                else (
                    experience.period.end_date
                    or "Unknown"
                )
            )

            print(
                f"  - {experience.job_title}"
                f" | {experience.company or 'Unknown'}"
            )

            print(
                f"    Period: "
                f"{start_date} -> {end_date}"
            )

            if experience.location:
                print(
                    f"    Location: "
                    f"{experience.location}"
                )

            if experience.demonstrated_skills:
                print(
                    "    Demonstrated Skills: "
                    + ", ".join(
                        experience.demonstrated_skills
                    )
                )

            if experience.responsibilities:
                print(
                    "    Responsibilities:"
                )

                for responsibility in (
                    experience.responsibilities
                ):
                    print(
                        f"      - {responsibility}"
                    )

            if experience.evidence:
                print(
                    "    Evidence:"
                )

                for evidence in experience.evidence:
                    print(
                        f"      - {evidence}"
                    )

    else:
        print("  - None identified")

    print()

    # -----------------------------------------------------------------------
    # Education
    # -----------------------------------------------------------------------

    print("Education:")

    if candidate.education:
        for education in candidate.education:

            print(
                f"  - {education.degree}"
                f" | "
                f"{education.field_of_study or 'N/A'}"
            )

            print(
                f"    Institution: "
                f"{education.institution or 'N/A'}"
            )

            if education.start_date:
                print(
                    f"    Start Date: "
                    f"{education.start_date}"
                )

            if education.end_date:
                print(
                    f"    End Date: "
                    f"{education.end_date}"
                )

            print(
                f"    Evidence: "
                f"{education.evidence}"
            )

    else:
        print("  - None identified")

    print()

    # -----------------------------------------------------------------------
    # Certifications
    # -----------------------------------------------------------------------

    print("Certifications:")

    if candidate.certifications:
        for certification in candidate.certifications:
            print(
                f"  - {certification}"
            )

    else:
        print("  - None identified")

    print()

    # -----------------------------------------------------------------------
    # Projects
    # -----------------------------------------------------------------------

    print("Projects:")

    if candidate.projects:
        for project in candidate.projects:
            print(
                f"  - {project}"
            )

    else:
        print("  - None identified")

    print()

    # -----------------------------------------------------------------------
    # Languages
    # -----------------------------------------------------------------------

    print("Languages:")

    if candidate.languages:
        for language in candidate.languages:
            print(
                f"  - {language}"
            )

    else:
        print("  - None identified")

    print()

    # -----------------------------------------------------------------------
    # Missing Information
    # -----------------------------------------------------------------------

    print("Missing Information:")

    if extraction.missing_information:
        for item in extraction.missing_information:
            print(
                f"  - {item}"
            )

    else:
        print("  - None identified")

    # -----------------------------------------------------------------------
    # Candidate Score
    # -----------------------------------------------------------------------

    print_section(
        "CANDIDATE SCORING"
    )

    scoring = result.candidate_score

    print(
        f"Overall Score: "
        f"{scoring.overall_score:.2f}/100"
    )

    print(
        f"Review Required: "
        f"{scoring.review_required}"
    )

    if scoring.review_reason:
        print(
            f"Review Reason: "
            f"{scoring.review_reason}"
        )

    print()

    # -----------------------------------------------------------------------
    # Criterion Scores
    # -----------------------------------------------------------------------

    print(
        "Criterion Assessments:"
    )

    if scoring.criterion_scores:

        for criterion in scoring.criterion_scores:

            print()

            print(
                f"  {criterion.criterion_name}"
            )

            print(
                f"    Score: "
                f"{criterion.score:.2f}/100"
            )

            print(
                f"    Expertise: "
                f"{criterion.expertise_level}"
            )

            print(
                f"    Relevant Years: "
                f"{criterion.relevant_years:.2f}"
            )

            print(
                f"    Meets Requirement: "
                f"{criterion.meets_requirement}"
            )

            print(
                f"    Confidence: "
                f"{criterion.confidence:.2f}"
            )

            print(
                f"    Recency: "
                f"{criterion.recency_assessment}"
            )

            print(
                f"    Seniority: "
                f"{criterion.seniority_assessment}"
            )

            print(
                f"    Depth: "
                f"{criterion.depth_assessment}"
            )

            print(
                "    Evidence:"
            )

            if criterion.evidence.evidence:

                for evidence in (
                    criterion.evidence.evidence
                ):
                    print(
                        f"      - {evidence}"
                    )

            else:
                print(
                    "      - No supporting evidence provided"
                )

            if criterion.evidence.evidence_location:

                print(
                    "    Evidence Location:"
                )

                for location in (
                    criterion.evidence.evidence_location
                ):
                    print(
                        f"      - {location}"
                    )

            print(
                f"    Reasoning: "
                f"{criterion.reasoning}"
            )

    else:
        print(
            "  - No criterion scores returned"
        )

    print()

    # -----------------------------------------------------------------------
    # Strengths
    # -----------------------------------------------------------------------

    print("Strengths:")

    if scoring.strengths:

        for strength in scoring.strengths:
            print(
                f"  - {strength}"
            )

    else:
        print("  - None identified")

    print()

    # -----------------------------------------------------------------------
    # Gaps
    # -----------------------------------------------------------------------

    print("Gaps:")

    if scoring.gaps:

        for gap in scoring.gaps:
            print(
                f"  - {gap}"
            )

    else:
        print("  - None identified")

    print()

    print(
        f"Overall Reasoning: "
        f"{scoring.overall_reasoning}"
    )

    # -----------------------------------------------------------------------
    # Deterministic Categorization
    # -----------------------------------------------------------------------

    print_section(
        "CANDIDATE CATEGORIZATION"
    )

    categorization = result.categorization

    print(
        f"Category: "
        f"{categorization.category.upper()}"
    )

    print(
        f"Score: "
        f"{categorization.score:.2f}/100"
    )

    print(
        f"Shortlisted Threshold: "
        f"{categorization.shortlisted_threshold:.2f}"
    )

    print(
        f"Maybe Threshold: "
        f"{categorization.maybe_threshold:.2f}"
    )

    print()

    print(
        "Categorization was performed deterministically "
        "using application thresholds."
    )


# ---------------------------------------------------------------------------
# CV Path
# ---------------------------------------------------------------------------

def get_cv_path() -> Path:
    """
    Obtain the CV path from the command line.
    """

    if len(sys.argv) != 2:
        raise ValueError(
            "Usage: python main.py <path-to-cv.pdf>"
        )

    cv_path = (
        Path(sys.argv[1])
        .expanduser()
        .resolve()
    )

    return cv_path


# ---------------------------------------------------------------------------
# Step 0 Pipeline
# ---------------------------------------------------------------------------

async def run_step0(
    cv_path: Path,
) -> None:
    """
    Execute the complete Step 0 screening pipeline.

    Pipeline:

        CV file
            |
        CV Parser
            |
        CV Extraction
            |
        Candidate Scoring
            |
        Deterministic Categorization
            |
        ScreeningResult
    """

    print_section(
        "HR SCREENING TOOL - STEP 0"
    )

    print(
        f"CV: {cv_path}"
    )

    print(
        "Mode: Core AI screening pipeline validation"
    )

    print(
        "Firebase/UI/Upload: Not used in Step 0"
    )

    print(
        "LLM Provider: Groq"
    )

    print(
        "Categorization: Deterministic application logic"
    )

    # -----------------------------------------------------------------------
    # Initialization
    # -----------------------------------------------------------------------

    initialize_directories()

    # -----------------------------------------------------------------------
    # Pipeline Initialization
    # -----------------------------------------------------------------------

    pipeline = ScreeningPipeline()

    # -----------------------------------------------------------------------
    # Execute Complete Pipeline
    # -----------------------------------------------------------------------

    print_section(
        "RUNNING SCREENING PIPELINE"
    )

    print(
        "Stage 1 -> CV text parsing"
    )

    print(
        "Stage 2 -> Structured CV extraction"
    )

    print(
        "Stage 3 -> Candidate scoring"
    )

    print(
        "Stage 4 -> Deterministic categorization"
    )

    print()

    try:
        result = await pipeline.screen(
            cv_file=cv_path,
            criteria=STEP0_CRITERIA,
            thresholds=STEP0_THRESHOLDS,
        )

    except ScreeningPipelineError as exc:
        print(
            f"Screening pipeline failed: {exc}"
        )

        raise

    # -----------------------------------------------------------------------
    # Display Complete Result
    # -----------------------------------------------------------------------

    print_screening_result(
        result
    )

    # -----------------------------------------------------------------------
    # Completion
    # -----------------------------------------------------------------------

    print_section(
        "STEP 0 COMPLETED"
    )

    print(
        "The CV successfully passed through:"
    )

    print(
        "  1. Raw CV text parsing"
    )

    print(
        "  2. Structured CV extraction"
    )

    print(
        "  3. Pydantic validation"
    )

    print(
        "  4. Evidence-grounded criterion scoring"
    )

    print(
        "  5. Deterministic candidate categorization"
    )

    print()

    print(
        f"Final Category: "
        f"{result.categorization.category.upper()}"
    )

    print(
        f"Final Score: "
        f"{result.categorization.score:.2f}/100"
    )


# ---------------------------------------------------------------------------
# Application Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    """
    Application entry point.
    """

    try:
        cv_path = get_cv_path()

        asyncio.run(
            run_step0(
                cv_path
            )
        )

    except (
        ValueError,
        ScreeningPipelineError,
    ) as exc:

        print()
        print("=" * 80)
        print("APPLICATION FAILED")
        print("=" * 80)

        print(
            str(exc)
        )

        sys.exit(1)

    except KeyboardInterrupt:

        print()

        print(
            "Application interrupted by user."
        )

        sys.exit(130)


if __name__ == "__main__":
    main()