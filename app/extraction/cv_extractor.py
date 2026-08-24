
from typing import Any

from pydantic import ValidationError

from app.core.config import LLM_MAX_RETRIES
from app.schemas.cv_schema import CVExtraction
from app.services.groq_service import GroqService


class CVExtractionError(RuntimeError):
    """
    Raised when structured CV extraction cannot be completed
    successfully.
    """


class CVExtractor:
    """
    Extract structured information from parsed CV text.

    This class is responsible only for the extraction stage.

    Pipeline:

        CV Parser
            ↓
        CVExtractor
            ↓
        CVExtraction
            ↓
        Candidate Scorer

    The extractor does not score candidates and does not make
    hiring decisions.
    """

    SCHEMA_NAME = "cv_extraction"

    # Keep the output compact because extraction is performed before
    # the scoring stage and the Groq TPM limit is relatively small.
    MAX_OUTPUT_TOKENS = 1400

    def __init__(
        self,
        groq_service: GroqService | None = None,
    ) -> None:
        """
        Initialize the CV extractor.

        A Groq service can be injected for testing and for sharing
        one configured LLM client across pipeline stages.
        """

        self.groq_service = (
            groq_service
            or GroqService()
        )

    async def extract(
        self,
        cv_text: str,
    ) -> CVExtraction:
        """
        Extract structured CV information.

        The model is explicitly instructed to use only information
        contained in the supplied CV text.

        Groq's strict structured-output request is attempted first.

        If Groq rejects the generated JSON because the model omitted
        required fields, GroqService may perform one JSON-object
        recovery request.

        The recovered response is then conservatively normalized
        for structural omissions that have an unambiguous empty
        representation.

        No candidate information is invented.
        """

        if not isinstance(
            cv_text,
            str,
        ):
            raise CVExtractionError(
                "CV text must be a string."
            )

        if not cv_text.strip():
            raise CVExtractionError(
                "Cannot extract information from empty CV text."
            )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a professional CV information "
                    "extraction system.\n\n"

                    "Your task is to extract structured information "
                    "from the supplied CV text.\n\n"

                    "IMPORTANT:\n"
                    "The extracted information will later be used "
                    "by an HR screening system. Accuracy and "
                    "grounding are more important than completeness.\n\n"

                    "STRICT RULES:\n"

                    "1. Use ONLY information explicitly present in "
                    "the supplied CV text.\n"

                    "2. Never invent skills, experience, dates, "
                    "education, employers, roles, qualifications, "
                    "certifications, or achievements.\n"

                    "3. Never assume that a person has experience "
                    "merely because a technology appears in a skills "
                    "section.\n"

                    "4. Keep demonstrated skills and merely listed "
                    "skills distinguishable whenever the schema "
                    "allows it.\n"

                    "5. Preserve job titles, company names, dates, "
                    "and education details as accurately as possible.\n"

                    "6. Do not calculate unsupported years of "
                    "experience.\n"

                    "7. Do not infer seniority unless it is supported "
                    "by the CV.\n"

                    "8. Every evidence field must be grounded in "
                    "the supplied CV text.\n"

                    "9. If information is unavailable, use the "
                    "schema's empty representation.\n"

                    "10. Do not use outside knowledge.\n"

                    "11. Do not make hiring recommendations.\n"

                    "12. Return only data matching the requested "
                    "structured schema.\n\n"

                    "EXACT STRUCTURE RULES:\n"

                    "13. The top-level JSON object MUST contain "
                    "EXACTLY these four properties:\n"
                    "- candidate\n"
                    "- source_quality\n"
                    "- source_quality_reason\n"
                    "- missing_information\n\n"

                    "14. The candidate object MUST contain EXACTLY "
                    "these properties:\n"
                    "- name\n"
                    "- professional_summary\n"
                    "- skills\n"
                    "- experience\n"
                    "- education\n"
                    "- certifications\n"
                    "- projects\n"
                    "- languages\n\n"

                    "15. Each object inside candidate.experience MUST "
                    "contain EXACTLY these properties:\n"
                    "- job_title\n"
                    "- company\n"
                    "- period\n"
                    "- location\n"
                    "- demonstrated_skills\n"
                    "- responsibilities\n"
                    "- evidence\n\n"

                    "16. The period object inside an experience "
                    "entry MUST contain EXACTLY these properties:\n"
                    "- start_date\n"
                    "- end_date\n"
                    "- is_current\n\n"

                    "17. NEVER put job_title, company, or period "
                    "directly inside candidate. They belong ONLY "
                    "inside an object in candidate.experience.\n\n"

                    "18. NEVER flatten an experience entry into the "
                    "candidate object.\n\n"

                    "19. If there is no experience information, "
                    "candidate.experience MUST be [].\n\n"

                    "20. If an experience entry exists but a particular "
                    "field is not supported by the CV:\n"
                    "- location MUST be null\n"
                    "- demonstrated_skills MUST be []\n"
                    "- responsibilities MUST be []\n"
                    "- evidence MUST be []\n\n"

                    "21. If an experience period is not available, "
                    "period must still be present with:\n"
                    "- start_date: null\n"
                    "- end_date: null\n"
                    "- is_current: false\n\n"

                    "22. Every list field must be returned as an "
                    "array, even when empty.\n\n"

                    "23. source_quality MUST be exactly one of: "
                    "high, medium, low.\n"

                    "24. source_quality_reason MUST always be a "
                    "non-empty string.\n"

                    "25. missing_information MUST always be an array. "
                    "Use [] when nothing important is missing.\n\n"

                    "26. Complete the entire top-level JSON object "
                    "before finishing the response.\n\n"

                    "27. NEVER return only the candidate object.\n\n"

                    "28. NEVER create a second representation of the "
                    "same experience outside candidate.experience."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Extract the candidate information from the "
                    "following CV text.\n\n"

                    "CV TEXT:\n"
                    "--------------------\n"
                    f"{cv_text}\n"
                    "--------------------\n\n"

                    "FINAL OUTPUT REQUIREMENT:\n"
                    "Return ONE complete JSON object containing "
                    "ALL FOUR top-level properties:\n"
                    "candidate, source_quality, "
                    "source_quality_reason, missing_information.\n\n"

                    "The candidate object must contain exactly:\n"
                    "name, professional_summary, skills, experience, "
                    "education, certifications, projects, languages.\n\n"

                    "Every experience object must contain exactly:\n"
                    "job_title, company, period, location, "
                    "demonstrated_skills, responsibilities, evidence.\n\n"

                    "Every period object must contain exactly:\n"
                    "start_date, end_date, is_current.\n\n"

                    "For unavailable list fields, return [].\n"
                    "For unavailable optional scalar fields, return null.\n"
                    "Do not omit required fields.\n"
                    "Do not flatten experience fields into candidate.\n"
                    "Do not return candidate by itself."
                ),
            },
        ]

        schema = CVExtraction.model_json_schema()

        total_attempts = (
            LLM_MAX_RETRIES + 1
        )

        last_error: Exception | None = None

        for attempt in range(
            total_attempts
        ):

            attempt_number = (
                attempt + 1
            )

            print(
                f"[CV Extractor] Attempt "
                f"{attempt_number}/{total_attempts}"
            )

            try:

                raw_data = (
                    await self.groq_service.generate_structured(
                        messages=messages,
                        schema=schema,
                        schema_name=self.SCHEMA_NAME,
                        max_tokens=self.MAX_OUTPUT_TOKENS,
                    )
                )

                extraction = (
                    self._validate_extraction(
                        raw_data
                    )
                )

                print(
                    "[CV Extractor] Structured CV "
                    "validation completed."
                )

                return extraction

            except (
                RuntimeError,
                ValidationError,
                ValueError,
            ) as exc:

                last_error = exc

                print(
                    "[CV Extractor] Extraction attempt "
                    f"{attempt_number} failed: {exc}"
                )

                if attempt_number < total_attempts:

                    print(
                        "[CV Extractor] Retrying "
                        "structured extraction..."
                    )

        raise CVExtractionError(
            "CV extraction failed after "
            f"{total_attempts} attempts: "
            f"{last_error}"
        )

    @classmethod
    def _validate_extraction(
        cls,
        data: dict[str, Any],
    ) -> CVExtraction:
        """
        Validate the model response against the application's
        Pydantic CV extraction schema.

        Before validation, a narrowly-scoped structural repair is
        performed for fields that have an unambiguous empty
        representation.

        This repair NEVER creates candidate facts.

        Examples:

            missing experience → []
            missing education → []
            missing certifications → []
            missing projects → []
            missing languages → []

        Additionally, if Groq's recovery response incorrectly places
        one complete experience record directly inside the candidate
        object using the unambiguous keys job_title/company/period,
        that record is moved into candidate.experience.

        Missing non-factual experience fields are then represented
        conservatively as:

            location → None
            demonstrated_skills → []
            responsibilities → []
            evidence → []

        Pydantic validation remains the final authority.
        """

        if not isinstance(
            data,
            dict,
        ):
            raise CVExtractionError(
                "Groq structured extraction response "
                "must be a JSON object."
            )

        normalized = cls._repair_extraction_structure(
            data
        )

        try:

            return CVExtraction.model_validate(
                normalized
            )

        except ValidationError as exc:

            raise CVExtractionError(
                "Groq returned structured data that "
                "does not satisfy the CVExtraction schema: "
                f"{exc}"
            ) from exc

    @classmethod
    def _repair_extraction_structure(
        cls,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Perform conservative structural normalization.

        The purpose of this method is NOT to guess missing CV data.

        It only converts structural omissions into representations that
        explicitly mean "no information extracted".

        It also repairs one specific malformed structure observed in
        Groq JSON-object recovery:

            candidate:
                job_title: ...
                company: ...
                period: ...

        When those three fields are present directly inside candidate
        and candidate.experience is absent or empty, they unambiguously
        represent one experience entry. They are therefore moved into
        candidate.experience.

        No new factual candidate information is generated here.
        """

        normalized = dict(
            data
        )

        candidate = normalized.get(
            "candidate"
        )

        # --------------------------------------------------------------
        # Candidate envelope
        # --------------------------------------------------------------

        if not isinstance(
            candidate,
            dict,
        ):
            raise CVExtractionError(
                "Groq structured extraction response "
                "must contain a candidate JSON object."
            )

        candidate = dict(
            candidate
        )

        # --------------------------------------------------------------
        # Repair flattened experience structure
        # --------------------------------------------------------------
        #
        # This directly addresses the structure observed in the
        # failed Maya Rao extraction:
        #
        # candidate:
        #     job_title: "Machine Learning Engineer"
        #     company: "Northgate Analytics"
        #     period: {...}
        #
        # These fields belong inside candidate.experience[0].
        #
        # We only perform this repair when the three identifying
        # experience fields are present together. This prevents
        # accidentally moving unrelated candidate information.
        # --------------------------------------------------------------

        flattened_experience_keys = {
            "job_title",
            "company",
            "period",
        }

        if (
            flattened_experience_keys.issubset(
                candidate.keys()
            )
            and not candidate.get(
                "experience"
            )
        ):

            experience_entry = {
                "job_title": candidate.pop(
                    "job_title"
                ),
                "company": candidate.pop(
                    "company"
                ),
                "period": candidate.pop(
                    "period"
                ),
                "location": None,
                "demonstrated_skills": [],
                "responsibilities": [],
                "evidence": [],
            }

            candidate[
                "experience"
            ] = [
                experience_entry
            ]

            print(
                "[CV Extractor] Repaired flattened "
                "experience object returned by Groq."
            )

        # --------------------------------------------------------------
        # Repair experience entries
        # --------------------------------------------------------------
        #
        # Groq may correctly create experience[0] but omit fields that
        # contain no information. These fields have safe empty values.
        #
        # We NEVER fill job_title/company/period because those are
        # factual experience fields and cannot safely be invented.
        # --------------------------------------------------------------

        experience = candidate.get(
            "experience"
        )

        if isinstance(
            experience,
            list,
        ):

            repaired_experience: list[Any] = []

            for index, entry in enumerate(
                experience
            ):

                if not isinstance(
                    entry,
                    dict,
                ):

                    repaired_experience.append(
                        entry
                    )

                    continue

                repaired_entry = dict(
                    entry
                )

                if "location" not in repaired_entry:

                    repaired_entry[
                        "location"
                    ] = None

                if (
                    "demonstrated_skills"
                    not in repaired_entry
                ):

                    repaired_entry[
                        "demonstrated_skills"
                    ] = []

                if (
                    "responsibilities"
                    not in repaired_entry
                ):

                    repaired_entry[
                        "responsibilities"
                    ] = []

                if "evidence" not in repaired_entry:

                    repaired_entry[
                        "evidence"
                    ] = []

                # --------------------------------------------------
                # Employment period repair
                # --------------------------------------------------

                period = repaired_entry.get(
                    "period"
                )

                if isinstance(
                    period,
                    dict,
                ):

                    repaired_period = dict(
                        period
                    )

                    if (
                        "start_date"
                        not in repaired_period
                    ):

                        repaired_period[
                            "start_date"
                        ] = None

                    if (
                        "end_date"
                        not in repaired_period
                    ):

                        repaired_period[
                            "end_date"
                        ] = None

                    if (
                        "is_current"
                        not in repaired_period
                    ):

                        repaired_period[
                            "is_current"
                        ] = False

                    repaired_entry[
                        "period"
                    ] = repaired_period

                repaired_experience.append(
                    repaired_entry
                )

            candidate[
                "experience"
            ] = repaired_experience

        # --------------------------------------------------------------
        # Safe empty candidate list fields
        # --------------------------------------------------------------
        #
        # These fields represent collections. If the CV contains no
        # information for them, [] is the only safe non-invented value.
        #
        # Do NOT add scalar fields here because an empty scalar may
        # incorrectly imply information that was not extracted.
        # --------------------------------------------------------------

        safe_empty_list_fields = (
            "skills",
            "experience",
            "education",
            "certifications",
            "projects",
            "languages",
        )

        repaired_fields: list[str] = []

        for field_name in safe_empty_list_fields:

            if field_name not in candidate:

                candidate[
                    field_name
                ] = []

                repaired_fields.append(
                    field_name
                )

        normalized[
            "candidate"
        ] = candidate

        # --------------------------------------------------------------
        # Extraction metadata
        # --------------------------------------------------------------
        #
        # If the model omitted the metadata envelope during JSON
        # recovery, we do not invent a positive source-quality result.
        #
        # "low" explicitly communicates that the model did not return
        # the complete requested extraction structure and therefore
        # human review is appropriate.
        # --------------------------------------------------------------

        missing_metadata: list[str] = []

        if not normalized.get(
            "source_quality"
        ):

            normalized[
                "source_quality"
            ] = "low"

            missing_metadata.append(
                "source_quality"
            )

        if not isinstance(
            normalized.get(
                "source_quality_reason"
            ),
            str,
        ) or not normalized[
            "source_quality_reason"
        ].strip():

            normalized[
                "source_quality_reason"
            ] = (
                "The CV information was extracted, but the model "
                "did not return the complete requested extraction "
                "metadata. The result should be reviewed by a human."
            )

            if (
                "source_quality_reason"
                not in missing_metadata
            ):

                missing_metadata.append(
                    "source_quality_reason"
                )

        if not isinstance(
            normalized.get(
                "missing_information"
            ),
            list,
        ):

            normalized[
                "missing_information"
            ] = []

            missing_metadata.append(
                "missing_information"
            )

        # --------------------------------------------------------------
        # Record structural omissions as missing information
        # --------------------------------------------------------------
        #
        # This does not invent CV facts. It explicitly tells downstream
        # consumers that the model failed to return some expected
        # extraction structure.
        # --------------------------------------------------------------

        missing_information = list(
            normalized[
                "missing_information"
            ]
        )

        for field_name in repaired_fields:

            message = (
                f"{field_name} was not returned by the "
                "structured extraction model."
            )

            if message not in missing_information:

                missing_information.append(
                    message
                )

        for field_name in missing_metadata:

            message = (
                f"{field_name} was not returned by the "
                "structured extraction model."
            )

            if message not in missing_information:

                missing_information.append(
                    message
                )

        normalized[
            "missing_information"
        ] = missing_information

        return normalized