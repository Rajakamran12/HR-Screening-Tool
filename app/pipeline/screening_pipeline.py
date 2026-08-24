
from pathlib import Path
from typing import Any

from app.extraction.cv_extractor import (
    CVExtractionError,
    CVExtractor,
)
from app.parsing.cv_parser import (
    CVParser,
    CVParsingError,
    ParsedCV,
)
from app.schemas.categorization_schema import (
    CandidateCategorization,
)
from app.schemas.cv_schema import (
    CVExtraction,
)
from app.schemas.job_schema import (
    JobCriterion,
    JobThresholds,
)
from app.schemas.scoring_schema import (
    CandidateScore,
    ScreeningCriterion,
)
from app.scoring.candidate_categorizer import (
    CandidateCategorizer,
)
from app.scoring.candidate_scorer import (
    CandidateScorer,
    CandidateScoringError,
)


class ScreeningPipelineError(RuntimeError):
    """
    Raised when the HR screening pipeline cannot complete
    successfully.
    """


class ScreeningResult:
    """
    Complete result produced by the HR screening pipeline.

    The pipeline combines:

        ParsedCV
            ↓
        CVExtraction
            ↓
        CandidateScore
            ↓
        CandidateCategorization

    Candidate categorization remains deterministic and is performed
    separately from the LLM scoring stage.
    """

    def __init__(
        self,
        parsed_cv: ParsedCV,
        candidate: CVExtraction,
        candidate_score: CandidateScore,
        categorization: CandidateCategorization,
    ) -> None:
        self.parsed_cv = parsed_cv
        self.candidate = candidate
        self.candidate_score = candidate_score
        self.categorization = categorization

    def model_dump(self) -> dict[str, Any]:
        """
        Return the screening result as a serializable dictionary.
        """

        return {
            "parsed_cv": {
                "file_path": str(
                    self.parsed_cv.file_path
                ),
                "page_count": self.parsed_cv.page_count,
                "text": self.parsed_cv.text,
            },
            "candidate": self.candidate.model_dump(
                mode="json"
            ),
            "candidate_score": self.candidate_score.model_dump(
                mode="json"
            ),
            "categorization": self.categorization.model_dump(
                mode="json"
            ),
        }


class ScreeningPipeline:
    """
    Orchestrates the complete HR screening workflow.

    Pipeline:

        CV file
            ↓
        CVParser
            ↓
        ParsedCV
            ↓
        CVExtractor
            ↓
        CVExtraction
            ↓
        CandidateScorer
            ↓
        CandidateScore
            ↓
        CandidateCategorizer
            ↓
        CandidateCategorization
            ↓
        ScreeningResult

    The pipeline supports both:

        - JobCriterion
        - ScreeningCriterion

    ScreeningCriterion uses weights on a 0-1 scale while
    JobCriterion uses weights on a 0-100 scale.

    The pipeline normalizes both representations internally before
    passing criteria to the candidate scorer.
    """

    def __init__(
        self,
        parser: CVParser | None = None,
        extractor: CVExtractor | None = None,
        scorer: CandidateScorer | None = None,
        categorizer: CandidateCategorizer | None = None,
    ) -> None:
        """
        Initialize the screening pipeline.

        Dependencies can be injected for testing and for sharing
        configured service instances.
        """

        self.parser = (
            parser
            or CVParser(
                allow_document_formats=True,
            )
        )

        self.extractor = (
            extractor
            or CVExtractor()
        )

        self.scorer = (
            scorer
            or CandidateScorer()
        )

        self.categorizer = (
            categorizer
            or CandidateCategorizer()
        )

    async def screen(
        self,
        cv_file: str | Path,
        criteria: (
            list[dict[str, Any]]
            | list[JobCriterion]
            | list[ScreeningCriterion]
        ),
        thresholds: JobThresholds,
    ) -> ScreeningResult:
        """
        Execute the complete screening pipeline.

        Args:
            cv_file:
                Path to the candidate CV.

            criteria:
                Job scoring criteria.

                Supported forms:

                    - dictionaries
                    - JobCriterion
                    - ScreeningCriterion

            thresholds:
                Deterministic candidate categorization thresholds.

        Returns:
            ScreeningResult containing the parsed CV, structured
            candidate extraction, AI-generated score, and deterministic
            categorization.

        Raises:
            ScreeningPipelineError:
                If validation or any pipeline stage fails.
        """

        self._validate_criteria(
            criteria
        )

        self._validate_thresholds(
            thresholds
        )

        parsed_cv = self._parse_cv(
            cv_file
        )

        candidate = await self._extract_candidate(
            parsed_cv
        )

        candidate_score = await self._score_candidate(
            candidate,
            criteria,
        )

        categorization = self._categorize_candidate(
            candidate_score,
            thresholds,
        )

        return ScreeningResult(
            parsed_cv=parsed_cv,
            candidate=candidate,
            candidate_score=candidate_score,
            categorization=categorization,
        )

    @staticmethod
    def _validate_criteria(
        criteria: Any,
    ) -> None:
        """
        Validate that at least one valid job scoring criterion
        has been supplied.

        Supported criterion types:

            - JobCriterion
            - ScreeningCriterion
            - dictionary representing either schema
        """

        if not isinstance(
            criteria,
            list,
        ):
            raise ScreeningPipelineError(
                "Job scoring criteria must be provided as a list."
            )

        if not criteria:
            raise ScreeningPipelineError(
                "At least one job scoring criterion is required."
            )

        for index, criterion in enumerate(
            criteria,
            start=1,
        ):

            if isinstance(
                criterion,
                (
                    JobCriterion,
                    ScreeningCriterion,
                ),
            ):
                continue

            if not isinstance(
                criterion,
                dict,
            ):
                raise ScreeningPipelineError(
                    "Each job scoring criterion must be a "
                    "JobCriterion, ScreeningCriterion, or dictionary. "
                    f"Invalid criterion at index {index}."
                )

            # ---------------------------------------------------------------
            # Try the application JobCriterion schema first.
            # ---------------------------------------------------------------

            try:
                JobCriterion.model_validate(
                    criterion
                )

                continue

            except Exception:
                pass

            # ---------------------------------------------------------------
            # Then allow the Step 0 ScreeningCriterion schema.
            # ---------------------------------------------------------------

            try:
                ScreeningCriterion.model_validate(
                    criterion
                )

            except Exception as exc:
                raise ScreeningPipelineError(
                    "Invalid job scoring criterion at "
                    f"index {index}: {exc}"
                ) from exc

    @staticmethod
    def _validate_thresholds(
        thresholds: Any,
    ) -> None:
        """
        Validate that deterministic categorization thresholds are
        represented by JobThresholds.
        """

        if not isinstance(
            thresholds,
            JobThresholds,
        ):
            raise ScreeningPipelineError(
                "Thresholds must be a valid JobThresholds object."
            )

    def _parse_cv(
        self,
        cv_file: str | Path,
    ) -> ParsedCV:
        """
        Parse the candidate CV.
        """

        print(
            "[Screening Pipeline] Parsing CV..."
        )

        try:
            parsed_cv = self.parser.parse(
                cv_file
            )

        except CVParsingError as exc:
            raise ScreeningPipelineError(
                f"CV parsing failed: {exc}"
            ) from exc

        except Exception as exc:
            raise ScreeningPipelineError(
                f"Unexpected CV parsing failure: {exc}"
            ) from exc

        if not isinstance(
            parsed_cv,
            ParsedCV,
        ):
            raise ScreeningPipelineError(
                "CV parser returned an invalid ParsedCV object."
            )

        print(
            "[Screening Pipeline] CV parsing completed."
        )

        return parsed_cv

    async def _extract_candidate(
        self,
        parsed_cv: ParsedCV,
    ) -> CVExtraction:
        """
        Extract structured candidate information from the parsed
        CV text.
        """

        print(
            "[Screening Pipeline] Extracting structured candidate data..."
        )

        try:
            candidate = await self.extractor.extract(
                parsed_cv.text
            )

        except CVExtractionError as exc:
            raise ScreeningPipelineError(
                f"CV extraction failed: {exc}"
            ) from exc

        except Exception as exc:
            raise ScreeningPipelineError(
                f"Unexpected CV extraction failure: {exc}"
            ) from exc

        if not isinstance(
            candidate,
            CVExtraction,
        ):
            raise ScreeningPipelineError(
                "CV extractor returned an invalid CVExtraction object."
            )

        print(
            "[Screening Pipeline] Candidate extraction completed."
        )

        return candidate

    @staticmethod
    def _normalize_criteria(
        criteria: (
            list[dict[str, Any]]
            | list[JobCriterion]
            | list[ScreeningCriterion]
        ),
    ) -> list[dict[str, Any]]:
        """
        Normalize all supported criterion representations into the
        dictionary representation expected by CandidateScorer.

        JobCriterion weights:
            0-100

        ScreeningCriterion weights:
            0-1

        ScreeningCriterion weights are converted to percentages.
        """

        normalized_criteria: list[dict[str, Any]] = []

        for criterion in criteria:

            # ----------------------------------------------------------------
            # Existing application JobCriterion
            # ----------------------------------------------------------------

            if isinstance(
                criterion,
                JobCriterion,
            ):
                normalized_criteria.append(
                    criterion.model_dump(
                        mode="json"
                    )
                )

                continue

            # ----------------------------------------------------------------
            # Step 0 ScreeningCriterion
            # ----------------------------------------------------------------

            if isinstance(
                criterion,
                ScreeningCriterion,
            ):
                normalized_criteria.append(
                    {
                        "name": criterion.name,
                        "description": criterion.description,
                        "required": criterion.required,
                        "weight": criterion.weight * 100.0,
                        "minimum_years": (
                            criterion.minimum_years
                            if criterion.minimum_years is not None
                            else 0.0
                        ),
                    }
                )

                continue

            # ----------------------------------------------------------------
            # Dictionary representation
            # ----------------------------------------------------------------

            if isinstance(
                criterion,
                dict,
            ):

                # Try JobCriterion first.
                try:
                    job_criterion = (
                        JobCriterion.model_validate(
                            criterion
                        )
                    )

                    normalized_criteria.append(
                        job_criterion.model_dump(
                            mode="json"
                        )
                    )

                    continue

                except Exception:
                    pass

                # Try ScreeningCriterion.
                try:
                    screening_criterion = (
                        ScreeningCriterion.model_validate(
                            criterion
                        )
                    )

                    normalized_criteria.append(
                        {
                            "name": screening_criterion.name,
                            "description": screening_criterion.description,
                            "required": screening_criterion.required,
                            "weight": (
                                screening_criterion.weight
                                * 100.0
                            ),
                            "minimum_years": (
                                screening_criterion.minimum_years
                                if (
                                    screening_criterion.minimum_years
                                    is not None
                                )
                                else 0.0
                            ),
                        }
                    )

                    continue

                except Exception as exc:
                    raise ScreeningPipelineError(
                        "Unable to normalize job scoring criterion: "
                        f"{exc}"
                    ) from exc

            raise ScreeningPipelineError(
                "Unable to normalize unsupported job scoring criterion."
            )

        # --------------------------------------------------------------------
        # Validate normalized criteria as JobCriterion objects.
        # --------------------------------------------------------------------

        validated_criteria: list[dict[str, Any]] = []

        for index, criterion in enumerate(
            normalized_criteria,
            start=1,
        ):
            try:
                validated = JobCriterion.model_validate(
                    criterion
                )

            except Exception as exc:
                raise ScreeningPipelineError(
                    "Normalized job scoring criterion is invalid "
                    f"at index {index}: {exc}"
                ) from exc

            validated_criteria.append(
                validated.model_dump(
                    mode="json"
                )
            )

        # --------------------------------------------------------------------
        # Validate total weight.
        # --------------------------------------------------------------------

        total_weight = sum(
            criterion["weight"]
            for criterion in validated_criteria
        )

        if abs(
            total_weight - 100.0
        ) > 0.0001:

            raise ScreeningPipelineError(
                "Criterion weights must total 100.0 after normalization. "
                f"Current total: {total_weight:.4f}."
            )

        return validated_criteria

    async def _score_candidate(
        self,
        candidate: CVExtraction,
        criteria: (
            list[dict[str, Any]]
            | list[JobCriterion]
            | list[ScreeningCriterion]
        ),
    ) -> CandidateScore:
        """
        Score the structured candidate against the supplied
        job criteria.

        Criteria are normalized before being passed to the scorer.
        """

        print(
            "[Screening Pipeline] Scoring candidate..."
        )

        normalized_criteria = (
            self._normalize_criteria(
                criteria
            )
        )

        try:
            candidate_score = await self.scorer.score(
                candidate=candidate,
                criteria=normalized_criteria,
            )

        except CandidateScoringError as exc:
            raise ScreeningPipelineError(
                f"Candidate scoring failed: {exc}"
            ) from exc

        except Exception as exc:
            raise ScreeningPipelineError(
                f"Unexpected candidate scoring failure: {exc}"
            ) from exc

        if not isinstance(
            candidate_score,
            CandidateScore,
        ):
            raise ScreeningPipelineError(
                "Candidate scorer returned an invalid "
                "CandidateScore object."
            )

        print(
            "[Screening Pipeline] Candidate scoring completed."
        )

        return candidate_score

    def _categorize_candidate(
        self,
        candidate_score: CandidateScore,
        thresholds: JobThresholds,
    ) -> CandidateCategorization:
        """
        Categorize the candidate deterministically.

        No LLM is called in this stage.
        """

        print(
            "[Screening Pipeline] Categorizing candidate "
            "using deterministic thresholds..."
        )

        try:
            categorization = self.categorizer.categorize(
                candidate_score=candidate_score,
                thresholds=thresholds,
            )

        except Exception as exc:
            raise ScreeningPipelineError(
                f"Candidate categorization failed: {exc}"
            ) from exc

        if not isinstance(
            categorization,
            CandidateCategorization,
        ):
            raise ScreeningPipelineError(
                "Candidate categorizer returned an invalid "
                "CandidateCategorization object."
            )

        print(
            "[Screening Pipeline] Categorization completed: "
            f"{categorization.category}"
        )

        return categorization