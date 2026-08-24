from app.schemas.categorization_schema import CandidateCategorization
from app.schemas.job_schema import JobThresholds
from app.schemas.scoring_schema import CandidateScore


class CandidateCategorizer:
    """
    Performs deterministic candidate categorization.

    This class does not use an LLM.

    The candidate score is produced by the AI scoring stage, while
    the final category is determined entirely by application logic
    and the thresholds configured for the job.
    """

    def categorize(
        self,
        candidate_score: CandidateScore,
        thresholds: JobThresholds,
    ) -> CandidateCategorization:
        """
        Categorize a candidate using the AI-generated overall score
        and the job's deterministic thresholds.

        Rules:

            score >= shortlisted threshold
                -> shortlisted

            score >= maybe threshold
                -> maybe

            otherwise
                -> rejected
        """

        score = candidate_score.overall_score

        if score >= thresholds.shortlisted:
            category = "shortlisted"

        elif score >= thresholds.maybe:
            category = "maybe"

        else:
            category = "rejected"

        return CandidateCategorization(
            category=category,
            score=score,
            shortlisted_threshold=thresholds.shortlisted,
            maybe_threshold=thresholds.maybe,
        )


def categorize_candidate(
    candidate_score: CandidateScore,
    thresholds: JobThresholds,
) -> CandidateCategorization:
    """
    Convenience function for deterministic candidate categorization.
    """

    categorizer = CandidateCategorizer()

    return categorizer.categorize(
        candidate_score=candidate_score,
        thresholds=thresholds,
    )