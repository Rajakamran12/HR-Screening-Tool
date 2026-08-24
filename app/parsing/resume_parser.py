from dataclasses import dataclass
from pathlib import Path

from app.parsing.cv_parser import (
    CVParser,
    CVParsingError,
    ParsedCV,
)


class ResumeParsingError(RuntimeError):
    """
    Raised when a resume cannot be parsed successfully.
    """


@dataclass(frozen=True)
class ParsedResume:
    """
    Represents the normalized parsing result of a resume.

    This object contains only source-level information. Structured
    candidate extraction remains the responsibility of
    app.extraction.cv_extractor.CVExtractor.
    """

    file_path: Path
    text: str
    page_count: int


class ResumeParser:
    """
    High-level resume parsing service.

    Responsibilities:
        - Accept a resume file path.
        - Delegate raw document parsing to CVParser.
        - Normalize the parsed result into ParsedResume.
        - Convert lower-level parsing failures into
          ResumeParsingError.

    This class does NOT:
        - Call an LLM.
        - Extract structured candidate information.
        - Score candidates.
        - Categorize candidates.
        - Make hiring decisions.
    """

    def __init__(
        self,
        cv_parser: CVParser | None = None,
    ) -> None:
        """
        Initialize the resume parser.

        A CVParser can be injected for testing or for sharing an
        existing parser instance.
        """

        self.cv_parser = (
            cv_parser
            or CVParser(
                allow_document_formats=True,
            )
        )

    def parse(
        self,
        file_path: str | Path,
    ) -> ParsedResume:
        """
        Parse a resume file.

        Args:
            file_path:
                Path to the resume file.

        Returns:
            ParsedResume containing cleaned source text and metadata.

        Raises:
            ResumeParsingError:
                If the supplied path is invalid or the underlying
                CV parser cannot parse the document.
        """

        if not isinstance(
            file_path,
            (str, Path),
        ):
            raise ResumeParsingError(
                "Resume file path must be a string or Path."
            )

        try:
            parsed_cv = self.cv_parser.parse(
                file_path
            )

        except CVParsingError as exc:
            raise ResumeParsingError(
                f"Unable to parse resume: {exc}"
            ) from exc

        except Exception as exc:
            raise ResumeParsingError(
                f"Unexpected resume parsing error: {exc}"
            ) from exc

        return self._convert_parsed_cv(
            parsed_cv
        )

    @staticmethod
    def _convert_parsed_cv(
        parsed_cv: ParsedCV,
    ) -> ParsedResume:
        """
        Convert a ParsedCV object into ParsedResume.

        The conversion is intentionally lossless with respect to the
        source-level information produced by CVParser.
        """

        if not isinstance(
            parsed_cv,
            ParsedCV,
        ):
            raise ResumeParsingError(
                "CV parser returned an invalid ParsedCV object."
            )

        if not isinstance(
            parsed_cv.file_path,
            Path,
        ):
            raise ResumeParsingError(
                "Parsed CV file path must be a Path object."
            )

        if not isinstance(
            parsed_cv.text,
            str,
        ):
            raise ResumeParsingError(
                "Parsed CV text must be a string."
            )

        if not isinstance(
            parsed_cv.page_count,
            int,
        ):
            raise ResumeParsingError(
                "Parsed CV page count must be an integer."
            )

        if parsed_cv.page_count < 1:
            raise ResumeParsingError(
                "Parsed CV page count must be at least 1."
            )

        if not parsed_cv.text.strip():
            raise ResumeParsingError(
                "Parsed CV contains no usable text."
            )

        return ParsedResume(
            file_path=parsed_cv.file_path,
            text=parsed_cv.text,
            page_count=parsed_cv.page_count,
        )