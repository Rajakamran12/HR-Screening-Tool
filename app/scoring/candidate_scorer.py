from typing import Any

from pydantic import ValidationError

from app.core.config import LLM_MAX_RETRIES
from app.schemas.cv_schema import CVExtraction
from app.schemas.scoring_schema import CandidateScore
from app.services.groq_service import GroqService


class CandidateScoringError(RuntimeError):
    """
    Raised when candidate scoring cannot be completed successfully.
    """


class CandidateScorer:
    """
    Score a structured CV against a defined set of job criteria.

    This is the scoring stage of the HR screening pipeline.

    Pipeline:

        Parsed CV
            ↓
        Structured CV Extraction
            ↓
        CandidateScorer
            ↓
        CandidateScore

    The LLM evaluates expertise, experience depth, recency,
    seniority, and supporting evidence.

    Threshold/category decisions are deliberately NOT performed
    here. Those decisions belong to deterministic application
    logic in the categorization stage.
    """

    SCHEMA_NAME = "candidate_score"

    MAX_OUTPUT_TOKENS = 1000

    def __init__(
        self,
        llm_service: GroqService | None = None,
    ) -> None:
        """
        Initialize the candidate scorer.

        A Groq service can be injected so the extraction and
        scoring stages can share the same configured service.
        """

        self.llm_service = (
            llm_service
            or GroqService()
        )

    async def score(
        self,
        candidate: CVExtraction,
        criteria: list[dict[str, Any]],
    ) -> CandidateScore:
        """
        Score a structured candidate against the supplied criteria.

        The model must evaluate demonstrated expertise rather than
        simply checking whether a keyword exists in the CV.
        """

        if not isinstance(
            candidate,
            CVExtraction,
        ):
            raise CandidateScoringError(
                "Candidate must be a valid CVExtraction object."
            )

        if not criteria:
            raise CandidateScoringError(
                "At least one scoring criterion is required."
            )

        candidate_data = candidate.model_dump(
            mode="json"
        )

        # Keep identifying profile data out of the model scoring prompt.
        candidate_data["candidate"]["name"] = None

        criteria_data = criteria

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert HR screening analysis "
                    "assistant.\n\n"

                    "Your task is to evaluate a candidate against "
                    "explicitly defined job criteria.\n\n"

                    "IMPORTANT PRINCIPLE:\n"
                    "This system recommends candidates. It does not "
                    "make hiring decisions. Your evaluation must be "
                    "transparent, evidence-grounded, and reviewable "
                    "by a human recruiter.\n\n"

                    "SCORING RULES:\n"
                    "1. Evaluate ONLY the criteria supplied by the "
                    "application.\n"

                    "2. Use ONLY evidence contained in the structured "
                    "CV data.\n"

                    "3. Never invent experience, skills, employers, "
                    "dates, qualifications, responsibilities, "
                    "achievements, or technologies.\n"

                    "4. A skill appearing in a skills list is NOT "
                    "automatically evidence of expertise.\n"

                    "5. Distinguish between a skill being listed and "
                    "a skill being demonstrated through actual work, "
                    "projects, responsibilities, or achievements.\n"

                    "6. When supported by the CV, consider:\n"
                    "   - duration of relevant experience\n"
                    "   - recency of experience\n"
                    "   - role and seniority\n"
                    "   - responsibilities\n"
                    "   - complexity of work\n"
                    "   - depth of practical use\n"
                    "   - repeated or sustained use\n"

                    "7. For minimum-year requirements, do not claim "
                    "that a candidate meets the requirement unless "
                    "the available CV evidence supports the required "
                    "duration.\n"

                    "8. If dates are incomplete or ambiguous, do not "
                    "invent missing dates. Treat the evidence as "
                    "uncertain and explain the limitation.\n"

                    "9. Every criterion assessment must contain "
                    "specific supporting evidence grounded in the "
                    "candidate data.\n"

                    "10. Evidence must explain WHY the candidate "
                    "received the score, not merely repeat the "
                    "criterion name.\n"

                    "11. If evidence is insufficient, explicitly "
                    "state that the evidence is insufficient.\n"

                    "12. Never compensate for missing evidence by "
                    "guessing.\n"

                    "13. Do not use protected characteristics or "
                    "irrelevant personal information in scoring.\n"

                    "14. Do not make a final hiring decision.\n"

                    "15. Return ONLY the requested structured output.\n\n"

                    "STRICT OUTPUT STRUCTURE:\n"

                    "16. criterion_scores MUST be an array.\n"

                    "17. Each item in criterion_scores MUST contain "
                    "an evidence OBJECT.\n"

                    "18. The evidence OBJECT MUST have exactly these "
                    "two collection fields:\n"
                    "   - evidence: an array of strings\n"
                    "   - evidence_location: an array of strings\n"

                    "19. IMPORTANT: criterion_scores[].evidence is "
                    "NOT an array. It MUST be a JSON object.\n"

                    "20. Correct evidence structure example:\n"
                    "{\n"
                    '  "evidence": {\n'
                    '    "evidence": ["Built ML models in Python"],\n'
                    '    "evidence_location": ["Work Experience"]\n'
                    "  }\n"
                    "}\n"

                    "21. Incorrect evidence structure:\n"
                    "{\n"
                    '  "evidence": ["Built ML models in Python"]\n'
                    "}\n"

                    "22. Every field defined as a list MUST ALWAYS "
                    "be returned as a JSON array.\n"

                    "23. NEVER return null for a list field.\n"

                    "24. If there is no evidence, return:\n"
                    "{\n"
                    '  "evidence": {\n'
                    '    "evidence": [],\n'
                    '    "evidence_location": []\n'
                    "  }\n"
                    "}\n"

                    "25. The following fields MUST always be arrays:\n"
                    "   - criterion_scores[].evidence.evidence\n"
                    "   - criterion_scores[].evidence.evidence_location\n"
                    "   - strengths\n"
                    "   - gaps\n"

                    "26. Do not omit required fields.\n"

                    "27. Do not use null where the schema expects a "
                    "list, string, number, or boolean.\n"

                    "28. For review_reason, use null only when "
                    "review_required is false; otherwise provide a "
                    "clear explanation.\n"

                    "29. Return one criterion_scores item for every "
                    "criterion supplied by the application.\n"

                    "30. Do not return a final candidate category such "
                    "as Shortlisted, Maybe, or Rejected.\n"
                ),
            },
            {
                "role": "user",
                "content": (
                    "Evaluate the candidate against the supplied "
                    "job criteria.\n\n"

                    "STRUCTURED CV:\n"
                    "--------------------\n"
                    f"{candidate_data}\n"
                    "--------------------\n\n"

                    "JOB CRITERIA:\n"
                    "--------------------\n"
                    f"{criteria_data}\n"
                    "--------------------\n\n"

                    "For every criterion, evaluate actual "
                    "demonstrated expertise rather than simple "
                    "keyword presence.\n\n"

                    "CRITICAL EVIDENCE FORMAT:\n"
                    "For each criterion, the 'evidence' field MUST "
                    "be an OBJECT containing:\n"
                    "- 'evidence': an array of evidence strings\n"
                    "- 'evidence_location': an array of locations\n\n"

                    "NEVER return criterion_scores[].evidence as a "
                    "direct array.\n\n"

                    "If there is no supporting evidence, use:\n"
                    "{"
                    '"evidence": [], '
                    '"evidence_location": []'
                    "}\n\n"

                    "Remember: if any list has no items, return [] "
                    "and NEVER null."
                ),
            },
        ]

        schema = CandidateScore.model_json_schema()

        last_error: Exception | None = None

        total_attempts = (
            LLM_MAX_RETRIES + 1
        )

        for attempt in range(
            total_attempts
        ):
            attempt_number = attempt + 1

            print(
                f"[Candidate Scorer] Attempt "
                f"{attempt_number}/{total_attempts}"
            )

            try:
                raw_data = (
                    await self.llm_service.generate_structured(
                        messages=messages,
                        schema=schema,
                        schema_name=self.SCHEMA_NAME,
                        max_tokens=self.MAX_OUTPUT_TOKENS,
                    )
                )

                normalized_data = (
                    self._normalize_score_data(
                        raw_data
                    )
                )

                return self._validate_score(
                    normalized_data
                )

            except (
                RuntimeError,
                ValidationError,
                ValueError,
                CandidateScoringError,
            ) as exc:

                last_error = exc

                print(
                    "[Candidate Scorer] Scoring attempt "
                    f"{attempt_number} failed: {exc}"
                )

                if attempt_number < total_attempts:
                    print(
                        "[Candidate Scorer] Retrying "
                        "candidate scoring..."
                    )

        raise CandidateScoringError(
            "Candidate scoring failed after "
            f"{total_attempts} attempts: "
            f"{last_error}"
        )

    @staticmethod
    def _normalize_score_data(
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Normalize safe empty collection values and recover the
        known malformed evidence-list structure sometimes returned
        by the LLM.

        The expected structure is:

            "evidence": {
                "evidence": [...],
                "evidence_location": [...]
            }

        Some LLM responses may incorrectly return:

            "evidence": [
                "some evidence"
            ]

        When that occurs, the evidence is preserved and wrapped
        inside the required CriterionEvidence object.

        No evidence text or scoring value is invented or changed.
        The evidence location remains empty because the model did
        not provide one.
        """

        if not isinstance(
            data,
            dict,
        ):
            raise CandidateScoringError(
                "Groq scoring response must be a JSON object."
            )

        normalized = dict(
            data
        )

        # --------------------------------------------------------------
        # Top-level collection fields
        # --------------------------------------------------------------

        list_fields = (
            "strengths",
            "gaps",
        )

        for field_name in list_fields:

            if normalized.get(
                field_name
            ) is None:

                normalized[
                    field_name
                ] = []

        # --------------------------------------------------------------
        # Criterion scores
        # --------------------------------------------------------------

        criterion_scores = normalized.get(
            "criterion_scores"
        )

        if criterion_scores is None:
            raise CandidateScoringError(
                "Groq scoring response is missing "
                "criterion_scores."
            )

        if not isinstance(
            criterion_scores,
            list,
        ):
            raise CandidateScoringError(
                "Groq scoring response contains an invalid "
                "criterion_scores value."
            )

        normalized_criteria = []

        for index, criterion_score in enumerate(
            criterion_scores,
            start=1,
        ):

            if not isinstance(
                criterion_score,
                dict,
            ):
                normalized_criteria.append(
                    criterion_score
                )
                continue

            normalized_criterion = dict(
                criterion_score
            )

            evidence = normalized_criterion.get(
                "evidence"
            )

            # ----------------------------------------------------------
            # Correct structure:
            #
            # "evidence": {
            #     "evidence": [...],
            #     "evidence_location": [...]
            # }
            # ----------------------------------------------------------

            if isinstance(
                evidence,
                dict,
            ):

                normalized_evidence = dict(
                    evidence
                )

                if normalized_evidence.get(
                    "evidence"
                ) is None:

                    normalized_evidence[
                        "evidence"
                    ] = []

                if normalized_evidence.get(
                    "evidence_location"
                ) is None:

                    normalized_evidence[
                        "evidence_location"
                    ] = []

                normalized_criterion[
                    "evidence"
                ] = normalized_evidence

            # ----------------------------------------------------------
            # Malformed but recoverable structure:
            #
            # "evidence": [
            #     "some evidence"
            # ]
            #
            # Preserve the evidence and wrap it in the schema-required
            # CriterionEvidence object.
            # ----------------------------------------------------------

            elif isinstance(
                evidence,
                list,
            ):

                normalized_criterion[
                    "evidence"
                ] = {
                    "evidence": evidence,
                    "evidence_location": [],
                }

            # ----------------------------------------------------------
            # Missing evidence object
            # ----------------------------------------------------------

            elif evidence is None:

                raise CandidateScoringError(
                    "Criterion score at index "
                    f"{index} is missing the required "
                    "evidence object."
                )

            # ----------------------------------------------------------
            # Any other evidence type is invalid.
            # ----------------------------------------------------------

            else:

                raise CandidateScoringError(
                    "Criterion score at index "
                    f"{index} contains an invalid "
                    "evidence value. Expected an object "
                    "or an evidence list."
                )

            normalized_criteria.append(
                normalized_criterion
            )

        normalized[
            "criterion_scores"
        ] = normalized_criteria

        return normalized

    @staticmethod
    def _validate_score(
        data: dict[str, Any],
    ) -> CandidateScore:
        """
        Validate the model-generated score against the
        application's Pydantic scoring schema.

        This validation is performed even though Groq has already
        been requested to produce strict JSON Schema output.
        """

        if not isinstance(
            data,
            dict,
        ):
            raise CandidateScoringError(
                "Groq scoring response must be a JSON object."
            )

        try:

            return CandidateScore.model_validate(
                data
            )

        except ValidationError as exc:

            raise CandidateScoringError(
                "Groq returned structured scoring data "
                "that does not satisfy the CandidateScore "
                f"schema: {exc}"
            ) from exc