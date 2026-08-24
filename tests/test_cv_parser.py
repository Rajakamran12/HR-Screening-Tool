from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.parsing.cv_parser import (
    CVParser,
    CVParsingError,
    ParsedCV,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def create_parser() -> CVParser:
    """
    Create a CVParser instance for testing.
    """

    return CVParser()


def create_mock_pdf_reader(
    page_texts: list[str],
) -> MagicMock:
    """
    Create a mocked PdfReader with the supplied page texts.
    """

    reader = MagicMock()

    pages = []

    for text in page_texts:
        page = MagicMock()
        page.extract_text.return_value = text
        pages.append(page)

    reader.pages = pages

    return reader


# ---------------------------------------------------------------------------
# ParsedCV Tests
# ---------------------------------------------------------------------------


def test_parsed_cv_stores_supplied_values():
    """
    Verify that ParsedCV preserves the supplied source-level values.
    """

    file_path = Path("sample.pdf")
    text = "John Doe\nPython Developer"
    page_count = 2

    parsed_cv = ParsedCV(
        file_path=file_path,
        text=text,
        page_count=page_count,
    )

    assert parsed_cv.file_path == file_path
    assert parsed_cv.text == text
    assert parsed_cv.page_count == page_count


# ---------------------------------------------------------------------------
# Supported Format Tests
# ---------------------------------------------------------------------------


def test_pdf_is_supported():
    """
    Verify that PDF files are supported.
    """

    parser = create_parser()

    assert ".pdf" in parser.SUPPORTED_EXTENSIONS


def test_pdf_extension_is_case_insensitive(tmp_path):
    """
    Verify that uppercase PDF extensions are accepted.
    """

    pdf_path = tmp_path / "resume.PDF"
    pdf_path.touch()

    parser = create_parser()

    with patch(
        "app.parsing.cv_parser.PdfReader"
    ) as mock_reader:

        mock_reader.return_value = create_mock_pdf_reader(
            ["John Doe\nPython Developer"]
        )

        result = parser.parse(pdf_path)

    assert isinstance(result, ParsedCV)
    assert result.file_path == pdf_path
    assert result.page_count == 1


def test_unsupported_file_extension_is_rejected(tmp_path):
    """
    Verify that unsupported CV formats are rejected.
    """

    docx_path = tmp_path / "resume.docx"
    docx_path.write_text(
        "John Doe",
        encoding="utf-8",
    )

    parser = create_parser()

    with pytest.raises(
        CVParsingError,
        match="Unsupported CV format",
    ):
        parser.parse(docx_path)


# ---------------------------------------------------------------------------
# File Validation Tests
# ---------------------------------------------------------------------------


def test_missing_file_is_rejected(tmp_path):
    """
    Verify that a nonexistent CV path is rejected.
    """

    pdf_path = tmp_path / "missing.pdf"

    parser = create_parser()

    with pytest.raises(
        CVParsingError,
        match="CV file does not exist",
    ):
        parser.parse(pdf_path)


def test_directory_is_rejected(tmp_path):
    """
    Verify that a directory cannot be used as a CV file.
    """

    pdf_directory = tmp_path / "resume.pdf"
    pdf_directory.mkdir()

    parser = create_parser()

    with pytest.raises(
        CVParsingError,
        match="CV path is not a file",
    ):
        parser.parse(pdf_directory)


def test_unsupported_extension_is_rejected_by_validation(
    tmp_path,
):
    """
    Verify that _validate_file rejects unsupported extensions.
    """

    txt_path = tmp_path / "resume.txt"
    txt_path.write_text(
        "John Doe",
        encoding="utf-8",
    )

    parser = create_parser()

    with pytest.raises(
        CVParsingError,
        match="Unsupported CV format",
    ):
        parser._validate_file(txt_path)


# ---------------------------------------------------------------------------
# PDF Parsing Tests
# ---------------------------------------------------------------------------


def test_parse_pdf_returns_parsed_cv(tmp_path):
    """
    Verify that a valid text-based PDF produces a ParsedCV.
    """

    pdf_path = tmp_path / "resume.pdf"
    pdf_path.touch()

    parser = create_parser()

    with patch(
        "app.parsing.cv_parser.PdfReader"
    ) as mock_reader:

        mock_reader.return_value = create_mock_pdf_reader(
            [
                "John Doe\nPython Developer",
                "Experience\nMachine Learning",
            ]
        )

        result = parser.parse(pdf_path)

    assert isinstance(result, ParsedCV)
    assert result.file_path == pdf_path
    assert result.page_count == 2

    assert "John Doe" in result.text
    assert "Python Developer" in result.text
    assert "Experience" in result.text
    assert "Machine Learning" in result.text


def test_parse_pdf_preserves_page_count(tmp_path):
    """
    Verify that the parser reports the correct PDF page count.
    """

    pdf_path = tmp_path / "resume.pdf"
    pdf_path.touch()

    parser = create_parser()

    with patch(
        "app.parsing.cv_parser.PdfReader"
    ) as mock_reader:

        mock_reader.return_value = create_mock_pdf_reader(
            [
                "Page One",
                "Page Two",
                "Page Three",
            ]
        )

        result = parser.parse(pdf_path)

    assert result.page_count == 3


def test_parse_pdf_extracts_text_from_all_pages(tmp_path):
    """
    Verify that text from every PDF page is included.
    """

    pdf_path = tmp_path / "resume.pdf"
    pdf_path.touch()

    parser = create_parser()

    page_texts = [
        "Candidate Name",
        "Professional Experience",
        "Education",
        "Skills",
    ]

    with patch(
        "app.parsing.cv_parser.PdfReader"
    ) as mock_reader:

        mock_reader.return_value = create_mock_pdf_reader(
            page_texts
        )

        result = parser.parse(pdf_path)

    for page_text in page_texts:
        assert page_text in result.text


def test_parse_pdf_skips_empty_pages(tmp_path):
    """
    Verify that empty PDF pages do not cause parsing to fail when
    other pages contain usable text.
    """

    pdf_path = tmp_path / "resume.pdf"
    pdf_path.touch()

    parser = create_parser()

    with patch(
        "app.parsing.cv_parser.PdfReader"
    ) as mock_reader:

        mock_reader.return_value = create_mock_pdf_reader(
            [
                "",
                "John Doe",
                "",
                "Python Developer",
            ]
        )

        result = parser.parse(pdf_path)

    assert result.page_count == 4
    assert "John Doe" in result.text
    assert "Python Developer" in result.text


def test_parse_pdf_rejects_pdf_with_no_pages(tmp_path):
    """
    Verify that a PDF containing no pages is rejected.
    """

    pdf_path = tmp_path / "empty.pdf"
    pdf_path.touch()

    parser = create_parser()

    reader = MagicMock()
    reader.pages = []

    with patch(
        "app.parsing.cv_parser.PdfReader",
        return_value=reader,
    ):
        with pytest.raises(
            CVParsingError,
            match="PDF CV contains no pages",
        ):
            parser.parse(pdf_path)


def test_parse_pdf_rejects_pdf_with_no_extractable_text(
    tmp_path,
):
    """
    Verify that an image-only/scanned PDF with no extractable text
    is rejected.
    """

    pdf_path = tmp_path / "scanned.pdf"
    pdf_path.touch()

    parser = create_parser()

    with patch(
        "app.parsing.cv_parser.PdfReader"
    ) as mock_reader:

        mock_reader.return_value = create_mock_pdf_reader(
            [
                "",
                "   ",
                "\n\n",
            ]
        )

        with pytest.raises(
            CVParsingError,
            match="No text could be extracted",
        ):
            parser.parse(pdf_path)


def test_parse_pdf_handles_pdf_open_error(tmp_path):
    """
    Verify that errors opening a PDF are converted into CVParsingError.
    """

    pdf_path = tmp_path / "broken.pdf"
    pdf_path.touch()

    parser = create_parser()

    with patch(
        "app.parsing.cv_parser.PdfReader",
        side_effect=Exception("Invalid PDF"),
    ):
        with pytest.raises(
            CVParsingError,
            match="Unable to open PDF CV",
        ):
            parser.parse(pdf_path)


def test_parse_pdf_handles_page_extraction_error(tmp_path):
    """
    Verify that page extraction errors are converted into
    CVParsingError.
    """

    pdf_path = tmp_path / "resume.pdf"
    pdf_path.touch()

    parser = create_parser()

    reader = MagicMock()

    first_page = MagicMock()
    first_page.extract_text.return_value = "John Doe"

    second_page = MagicMock()
    second_page.extract_text.side_effect = Exception(
        "Page extraction failed"
    )

    reader.pages = [
        first_page,
        second_page,
    ]

    with patch(
        "app.parsing.cv_parser.PdfReader",
        return_value=reader,
    ):
        with pytest.raises(
            CVParsingError,
            match="Unable to extract text from PDF page 2",
        ):
            parser.parse(pdf_path)


# ---------------------------------------------------------------------------
# Text Cleaning Tests
# ---------------------------------------------------------------------------


def test_clean_extracted_text_normalizes_whitespace():
    """
    Verify that excessive whitespace inside lines is normalized.
    """

    text = (
        "John    Doe\n"
        "   Python     Developer   \n"
        "\n"
        "Machine\tLearning"
    )

    cleaned = CVParser._clean_extracted_text(
        text
    )

    assert cleaned == (
        "John Doe\n"
        "Python Developer\n"
        "Machine Learning"
    )


def test_clean_extracted_text_removes_empty_lines():
    """
    Verify that empty lines are removed.
    """

    text = (
        "John Doe\n"
        "\n"
        "\n"
        "Python Developer\n"
        "   \n"
        "Machine Learning"
    )

    cleaned = CVParser._clean_extracted_text(
        text
    )

    assert cleaned == (
        "John Doe\n"
        "Python Developer\n"
        "Machine Learning"
    )


def test_clean_extracted_text_preserves_line_structure():
    """
    Verify that separate meaningful lines remain separate.
    """

    text = (
        "John Doe\n"
        "Python Developer\n"
        "Experience\n"
        "Education"
    )

    cleaned = CVParser._clean_extracted_text(
        text
    )

    assert cleaned.splitlines() == [
        "John Doe",
        "Python Developer",
        "Experience",
        "Education",
    ]


# ---------------------------------------------------------------------------
# Parser Integration Behaviour
# ---------------------------------------------------------------------------


def test_parse_rejects_non_pdf_before_calling_pdf_reader(
    tmp_path,
):
    """
    Verify that unsupported files are rejected before PdfReader
    is invoked.
    """

    txt_path = tmp_path / "resume.txt"
    txt_path.write_text(
        "John Doe",
        encoding="utf-8",
    )

    parser = create_parser()

    with patch(
        "app.parsing.cv_parser.PdfReader"
    ) as mock_reader:

        with pytest.raises(
            CVParsingError,
            match="Unsupported CV format",
        ):
            parser.parse(txt_path)

        mock_reader.assert_not_called()


def test_parse_uses_pdf_reader_for_pdf_files(tmp_path):
    """
    Verify that PDF files are passed to PdfReader.
    """

    pdf_path = tmp_path / "resume.pdf"
    pdf_path.touch()

    parser = create_parser()

    with patch(
        "app.parsing.cv_parser.PdfReader"
    ) as mock_reader:

        mock_reader.return_value = create_mock_pdf_reader(
            ["John Doe"]
        )

        result = parser.parse(pdf_path)

    mock_reader.assert_called_once_with(
        str(pdf_path)
    )

    assert result.text == "John Doe"


def test_parser_returns_cleaned_source_text(tmp_path):
    """
    Verify that the parser returns normalized source text rather
    than the raw uncleaned page output.
    """

    pdf_path = tmp_path / "resume.pdf"
    pdf_path.touch()

    parser = create_parser()

    with patch(
        "app.parsing.cv_parser.PdfReader"
    ) as mock_reader:

        mock_reader.return_value = create_mock_pdf_reader(
            [
                "John    Doe\n\n"
                "Python     Developer\n"
                "   Machine Learning   "
            ]
        )

        result = parser.parse(pdf_path)

    assert result.text == (
        "John Doe\n"
        "Python Developer\n"
        "Machine Learning"
    )