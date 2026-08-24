from pathlib import Path

import pytest

from app.parsing.cv_parser import (
    CVParser,
    CVParsingError,
    ParsedCV,
)
from app.parsing.resume_parser import (
    ParsedResume,
    ResumeParser,
    ResumeParsingError,
)


class FakeCVParser:
    """
    Test double for CVParser.
    """

    def __init__(
        self,
        parsed_cv: ParsedCV | None = None,
        error: Exception | None = None,
    ) -> None:
        self.parsed_cv = parsed_cv
        self.error = error
        self.received_file_path = None
        self.call_count = 0

    def parse(
        self,
        file_path,
    ) -> ParsedCV:

        self.call_count += 1
        self.received_file_path = file_path

        if self.error is not None:
            raise self.error

        return self.parsed_cv


def build_parsed_cv(
    *,
    file_path: Path | None = None,
    text: str = "John Doe\nPython Developer",
    page_count: int = 2,
) -> ParsedCV:
    """
    Build a valid ParsedCV test object.
    """

    return ParsedCV(
        file_path=file_path or Path("resume.pdf"),
        text=text,
        page_count=page_count,
    )


def test_resume_parser_returns_parsed_resume():
    """
    Verify that ResumeParser converts ParsedCV into ParsedResume.
    """

    parsed_cv = build_parsed_cv()

    parser = ResumeParser(
        cv_parser=FakeCVParser(
            parsed_cv=parsed_cv
        )
    )

    result = parser.parse(
        "resume.pdf"
    )

    assert isinstance(
        result,
        ParsedResume,
    )

    assert result.file_path == parsed_cv.file_path
    assert result.text == parsed_cv.text
    assert result.page_count == parsed_cv.page_count


def test_resume_parser_delegates_to_cv_parser():
    """
    Verify that raw document parsing is delegated to CVParser.
    """

    parsed_cv = build_parsed_cv()

    fake_parser = FakeCVParser(
        parsed_cv=parsed_cv
    )

    parser = ResumeParser(
        cv_parser=fake_parser
    )

    parser.parse(
        "candidate.pdf"
    )

    assert fake_parser.call_count == 1
    assert fake_parser.received_file_path == "candidate.pdf"


def test_resume_parser_accepts_path_object():
    """
    Verify that Path objects are accepted.
    """

    file_path = Path("candidate.pdf")

    parsed_cv = build_parsed_cv(
        file_path=file_path
    )

    fake_parser = FakeCVParser(
        parsed_cv=parsed_cv
    )

    parser = ResumeParser(
        cv_parser=fake_parser
    )

    result = parser.parse(
        file_path
    )

    assert result.file_path == file_path


def test_resume_parser_rejects_invalid_path_type():
    """
    Verify that unsupported path types are rejected.
    """

    parser = ResumeParser(
        cv_parser=FakeCVParser()
    )

    with pytest.raises(
        ResumeParsingError,
        match="Resume file path must be a string or Path",
    ):
        parser.parse(
            123
        )


def test_resume_parser_converts_cv_parsing_error():
    """
    Verify that CVParsingError is translated into ResumeParsingError.
    """

    fake_parser = FakeCVParser(
        error=CVParsingError(
            "PDF could not be opened."
        )
    )

    parser = ResumeParser(
        cv_parser=fake_parser
    )

    with pytest.raises(
        ResumeParsingError,
        match="Unable to parse resume",
    ):
        parser.parse(
            "resume.pdf"
        )


def test_resume_parser_preserves_original_parsing_error():
    """
    Verify that the original CVParsingError remains available as
    the exception cause.
    """

    original_error = CVParsingError(
        "Invalid PDF."
    )

    fake_parser = FakeCVParser(
        error=original_error
    )

    parser = ResumeParser(
        cv_parser=fake_parser
    )

    with pytest.raises(
        ResumeParsingError,
    ) as exc_info:

        parser.parse(
            "resume.pdf"
        )

    assert exc_info.value.__cause__ is original_error


def test_resume_parser_converts_unexpected_parser_error():
    """
    Verify that unexpected parser failures are converted into the
    public ResumeParsingError.
    """

    fake_parser = FakeCVParser(
        error=RuntimeError(
            "Unexpected failure."
        )
    )

    parser = ResumeParser(
        cv_parser=fake_parser
    )

    with pytest.raises(
        ResumeParsingError,
        match="Unexpected resume parsing error",
    ):
        parser.parse(
            "resume.pdf"
        )


def test_resume_parser_uses_default_cv_parser():
    """
    Verify that ResumeParser creates a CVParser when one is not
    injected.
    """

    parser = ResumeParser()

    assert isinstance(
        parser.cv_parser,
        CVParser,
    )


def test_convert_parsed_cv_returns_valid_result():
    """
    Verify direct ParsedCV-to-ParsedResume conversion.
    """

    parsed_cv = build_parsed_cv()

    result = ResumeParser._convert_parsed_cv(
        parsed_cv
    )

    assert isinstance(
        result,
        ParsedResume,
    )

    assert result.file_path == parsed_cv.file_path
    assert result.text == parsed_cv.text
    assert result.page_count == parsed_cv.page_count


def test_convert_parsed_cv_rejects_invalid_object():
    """
    Verify that conversion rejects objects that are not ParsedCV.
    """

    with pytest.raises(
        ResumeParsingError,
        match="invalid ParsedCV object",
    ):
        ResumeParser._convert_parsed_cv(
            "invalid"
        )


def test_convert_parsed_cv_rejects_invalid_file_path():
    """
    Verify that ParsedCV with an invalid file path is rejected.
    """

    parsed_cv = build_parsed_cv()

    parsed_cv.file_path = "resume.pdf"

    with pytest.raises(
        ResumeParsingError,
        match="file path must be a Path object",
    ):
        ResumeParser._convert_parsed_cv(
            parsed_cv
        )


def test_convert_parsed_cv_rejects_invalid_text():
    """
    Verify that ParsedCV with non-string text is rejected.
    """

    parsed_cv = build_parsed_cv()

    parsed_cv.text = 123

    with pytest.raises(
        ResumeParsingError,
        match="text must be a string",
    ):
        ResumeParser._convert_parsed_cv(
            parsed_cv
        )


def test_convert_parsed_cv_rejects_invalid_page_count_type():
    """
    Verify that page_count must be an integer.
    """

    parsed_cv = build_parsed_cv()

    parsed_cv.page_count = "2"

    with pytest.raises(
        ResumeParsingError,
        match="page count must be an integer",
    ):
        ResumeParser._convert_parsed_cv(
            parsed_cv
        )


def test_convert_parsed_cv_rejects_zero_page_count():
    """
    Verify that page_count must be positive.
    """

    parsed_cv = build_parsed_cv(
        page_count=0
    )

    with pytest.raises(
        ResumeParsingError,
        match="page count must be at least 1",
    ):
        ResumeParser._convert_parsed_cv(
            parsed_cv
        )


def test_convert_parsed_cv_rejects_negative_page_count():
    """
    Verify that negative page counts are rejected.
    """

    parsed_cv = build_parsed_cv(
        page_count=-1
    )

    with pytest.raises(
        ResumeParsingError,
        match="page count must be at least 1",
    ):
        ResumeParser._convert_parsed_cv(
            parsed_cv
        )


def test_convert_parsed_cv_rejects_empty_text():
    """
    Verify that empty parsed text is rejected.
    """

    parsed_cv = build_parsed_cv(
        text=""
    )

    with pytest.raises(
        ResumeParsingError,
        match="contains no usable text",
    ):
        ResumeParser._convert_parsed_cv(
            parsed_cv
        )


def test_convert_parsed_cv_rejects_whitespace_only_text():
    """
    Verify that whitespace-only parsed text is rejected.
    """

    parsed_cv = build_parsed_cv(
        text="   \n   "
    )

    with pytest.raises(
        ResumeParsingError,
        match="contains no usable text",
    ):
        ResumeParser._convert_parsed_cv(
            parsed_cv
        )


def test_resume_parser_preserves_source_text_exactly():
    """
    Verify that ResumeParser does not modify source text.
    """

    source_text = (
        "John Doe\n"
        "Python Developer\n\n"
        "Machine Learning Engineer"
    )

    parsed_cv = build_parsed_cv(
        text=source_text
    )

    parser = ResumeParser(
        cv_parser=FakeCVParser(
            parsed_cv=parsed_cv
        )
    )

    result = parser.parse(
        "resume.pdf"
    )

    assert result.text == source_text


def test_resume_parser_preserves_page_count():
    """
    Verify that page count is preserved.
    """

    parsed_cv = build_parsed_cv(
        page_count=5
    )

    parser = ResumeParser(
        cv_parser=FakeCVParser(
            parsed_cv=parsed_cv
        )
    )

    result = parser.parse(
        "resume.pdf"
    )

    assert result.page_count == 5