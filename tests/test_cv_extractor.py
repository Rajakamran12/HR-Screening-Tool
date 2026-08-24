import pytest

from app.extraction.cv_extractor import (
    CVExtractionError,
    CVExtractor,
)
from app.schemas.cv_schema import CVExtraction


class MockGroqService:
    """
    Simple mock Groq service used to test CVExtractor behavior.
    """

    def __init__(
        self,
        response=None,
        errors=None,
    ) -> None:
        self.response = response
        self.errors = list(
            errors or []
        )

        self.calls = []

    async def generate_structured(
        self,
        *,
        messages,
        schema,
        schema_name,
        max_tokens,
    ):
        self.calls.append(
            {
                "messages": messages,
                "schema": schema,
                "schema_name": schema_name,
                "max_tokens": max_tokens,
            }
        )

        if self.errors:
            error = self.errors.pop(0)
            raise error

        return self.response


def build_valid_extraction_data() -> dict:
    """
    Build a valid CVExtraction-compatible response.
    """

    return {
        "candidate": {
            "name": "John Doe",
            "professional_summary": (
                "AI Engineer with practical Python experience."
            ),
            "skills": [
                {
                    "name": "Python",
                    "category": "programming",
                    "evidence": (
                        "Developed Python applications in previous roles."
                    ),
                }
            ],
            "experience": [
                {
                    "job_title": "AI Engineer",
                    "company": "Example Technologies",
                    "period": {
                        "start_date": "2023",
                        "end_date": "2025",
                        "is_current": False,
                    },
                    "location": "Islamabad",
                    "demonstrated_skills": [
                        "Python",
                    ],
                    "responsibilities": [
                        "Developed Python applications."
                    ],
                    "evidence": [
                        "Developed Python applications during employment."
                    ],
                }
            ],
            "education": [
                {
                    "degree": "BS Artificial Intelligence",
                    "field_of_study": "Artificial Intelligence",
                    "institution": "Example University",
                    "start_date": "2021",
                    "end_date": "2025",
                    "evidence": (
                        "BS Artificial Intelligence, Example University."
                    ),
                }
            ],
            "certifications": [
                "Example AI Certification",
            ],
            "projects": [
                "AI Screening System",
            ],
            "languages": [
                "English",
            ],
        },
        "source_quality": "high",
        "source_quality_reason": (
            "The CV contains clear professional, educational, "
            "and skills information."
        ),
        "missing_information": [],
    }


def build_valid_extraction() -> CVExtraction:
    """
    Build a valid CVExtraction Pydantic object.
    """

    return CVExtraction.model_validate(
        build_valid_extraction_data()
    )


@pytest.mark.anyio
async def test_cv_extractor_returns_valid_extraction():
    """
    Verify that valid structured LLM output is converted into
    a CVExtraction object.
    """

    mock_service = MockGroqService(
        response=build_valid_extraction_data()
    )

    extractor = CVExtractor(
        groq_service=mock_service
    )

    result = await extractor.extract(
        "John Doe is an AI Engineer with Python experience."
    )

    assert isinstance(
        result,
        CVExtraction,
    )

    assert result.candidate.name == "John Doe"
    assert result.source_quality == "high"


@pytest.mark.anyio
async def test_cv_extractor_rejects_non_string_cv_text():
    """
    Verify that CV text must be a string.
    """

    mock_service = MockGroqService()

    extractor = CVExtractor(
        groq_service=mock_service
    )

    with pytest.raises(
        CVExtractionError,
        match="CV text must be a string",
    ):
        await extractor.extract(
            123
        )


@pytest.mark.anyio
async def test_cv_extractor_rejects_empty_cv_text():
    """
    Verify that empty CV text is rejected before calling the LLM.
    """

    mock_service = MockGroqService()

    extractor = CVExtractor(
        groq_service=mock_service
    )

    with pytest.raises(
        CVExtractionError,
        match="Cannot extract information from empty CV text",
    ):
        await extractor.extract(
            "   "
        )

    assert mock_service.calls == []


@pytest.mark.anyio
async def test_cv_extractor_calls_llm_service():
    """
    Verify that the extractor delegates structured extraction
    to the Groq service.
    """

    mock_service = MockGroqService(
        response=build_valid_extraction_data()
    )

    extractor = CVExtractor(
        groq_service=mock_service
    )

    cv_text = (
        "John Doe is an AI Engineer with Python experience."
    )

    await extractor.extract(
        cv_text
    )

    assert len(
        mock_service.calls
    ) == 1


@pytest.mark.anyio
async def test_cv_extractor_uses_correct_schema_name():
    """
    Verify that the expected structured-output schema name is used.
    """

    mock_service = MockGroqService(
        response=build_valid_extraction_data()
    )

    extractor = CVExtractor(
        groq_service=mock_service
    )

    await extractor.extract(
        "John Doe is an AI Engineer."
    )

    assert (
        mock_service.calls[0]["schema_name"]
        == "cv_extraction"
    )


@pytest.mark.anyio
async def test_cv_extractor_uses_cv_extraction_schema():
    """
    Verify that the extractor sends the application's
    CVExtraction JSON schema to the Groq service.
    """

    mock_service = MockGroqService(
        response=build_valid_extraction_data()
    )

    extractor = CVExtractor(
        groq_service=mock_service
    )

    await extractor.extract(
        "John Doe is an AI Engineer."
    )

    supplied_schema = mock_service.calls[0]["schema"]

    expected_schema = CVExtraction.model_json_schema()

    assert supplied_schema == expected_schema


@pytest.mark.anyio
async def test_cv_extractor_sends_cv_text_to_llm():
    """
    Verify that the supplied CV text is included in the
    LLM messages.
    """

    mock_service = MockGroqService(
        response=build_valid_extraction_data()
    )

    extractor = CVExtractor(
        groq_service=mock_service
    )

    cv_text = (
        "John Doe worked as an AI Engineer at Example Technologies."
    )

    await extractor.extract(
        cv_text
    )

    messages = mock_service.calls[0]["messages"]

    combined_content = "\n".join(
        message["content"]
        for message in messages
    )

    assert cv_text in combined_content


@pytest.mark.anyio
async def test_cv_extractor_uses_expected_max_output_tokens():
    """
    Verify that the extractor uses its configured output token limit.
    """

    mock_service = MockGroqService(
        response=build_valid_extraction_data()
    )

    extractor = CVExtractor(
        groq_service=mock_service
    )

    await extractor.extract(
        "John Doe is an AI Engineer."
    )

    assert (
        mock_service.calls[0]["max_tokens"]
        == CVExtractor.MAX_OUTPUT_TOKENS
    )


def test_validate_extraction_accepts_valid_data():
    """
    Verify that valid structured extraction data passes
    Pydantic validation.
    """

    data = build_valid_extraction_data()

    result = CVExtractor._validate_extraction(
        data
    )

    assert isinstance(
        result,
        CVExtraction,
    )

    assert result.candidate.name == "John Doe"


def test_validate_extraction_rejects_non_dictionary():
    """
    Verify that structured extraction output must be a dictionary.
    """

    with pytest.raises(
        CVExtractionError,
        match="must be a JSON object",
    ):
        CVExtractor._validate_extraction(
            ["invalid"]
        )


def test_validate_extraction_rejects_invalid_schema():
    """
    Verify that invalid structured extraction data is rejected.
    """

    invalid_data = build_valid_extraction_data()

    del invalid_data["candidate"]

    with pytest.raises(
        CVExtractionError,
        match="does not satisfy the CVExtraction schema",
    ):
        CVExtractor._validate_extraction(
            invalid_data
        )


@pytest.mark.anyio
async def test_cv_extractor_retries_after_runtime_error():
    """
    Verify that a RuntimeError from the Groq service causes
    another extraction attempt.
    """

    mock_service = MockGroqService(
        response=build_valid_extraction_data(),
        errors=[
            RuntimeError("Temporary Groq failure"),
        ],
    )

    extractor = CVExtractor(
        groq_service=mock_service
    )

    result = await extractor.extract(
        "John Doe is an AI Engineer."
    )

    assert isinstance(
        result,
        CVExtraction,
    )

    assert len(
        mock_service.calls
    ) == 2


@pytest.mark.anyio
async def test_cv_extractor_retries_after_validation_error():
    """
    Verify that invalid structured output causes another
    extraction attempt.
    """

    invalid_data = build_valid_extraction_data()

    del invalid_data["candidate"]

    mock_service = MockGroqService(
        response=build_valid_extraction_data(),
        errors=[],
    )

    original_response = mock_service.response

    responses = [
        invalid_data,
        original_response,
    ]

    async def generate_structured(
        *,
        messages,
        schema,
        schema_name,
        max_tokens,
    ):
        mock_service.calls.append(
            {
                "messages": messages,
                "schema": schema,
                "schema_name": schema_name,
                "max_tokens": max_tokens,
            }
        )

        return responses.pop(0)

    mock_service.generate_structured = (
        generate_structured
    )

    extractor = CVExtractor(
        groq_service=mock_service
    )

    result = await extractor.extract(
        "John Doe is an AI Engineer."
    )

    assert isinstance(
        result,
        CVExtraction,
    )

    assert len(
        mock_service.calls
    ) == 2


@pytest.mark.anyio
async def test_cv_extractor_raises_error_after_retries():
    """
    Verify that extraction ultimately fails after all
    configured attempts fail.
    """

    mock_service = MockGroqService(
        errors=[
            RuntimeError("Failure 1"),
            RuntimeError("Failure 2"),
            RuntimeError("Failure 3"),
            RuntimeError("Failure 4"),
            RuntimeError("Failure 5"),
        ]
    )

    extractor = CVExtractor(
        groq_service=mock_service
    )

    with pytest.raises(
        CVExtractionError,
        match="CV extraction failed after",
    ):
        await extractor.extract(
            "John Doe is an AI Engineer."
        )

    assert len(
        mock_service.calls
    ) >= 1


@pytest.mark.anyio
async def test_cv_extractor_does_not_call_llm_for_invalid_input():
    """
    Verify that invalid CV input is rejected before any LLM call.
    """

    mock_service = MockGroqService(
        response=build_valid_extraction_data()
    )

    extractor = CVExtractor(
        groq_service=mock_service
    )

    with pytest.raises(
        CVExtractionError
    ):
        await extractor.extract(
            ""
        )

    assert mock_service.calls == []


def test_build_valid_extraction_data_matches_schema():
    """
    Sanity-check the test fixture itself so future schema changes
    immediately expose an incompatible test fixture.
    """

    extraction = CVExtraction.model_validate(
        build_valid_extraction_data()
    )

    assert extraction.candidate.name == "John Doe"
    assert extraction.candidate.skills[0].name == "Python"
    assert (
        extraction.candidate.experience[0].job_title
        == "AI Engineer"
    )