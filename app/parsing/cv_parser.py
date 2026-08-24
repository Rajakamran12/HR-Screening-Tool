from pathlib import Path

from pypdf import PdfReader

from app.core.config import OCR_ENABLED, OCR_LANGUAGE

try:
    from docx import Document
except ImportError:
    Document = None


class CVParsingError(Exception):
    """
    Raised when a CV cannot be parsed successfully.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)


class ParsedCV:
    """
    Represents the raw parsing result of a CV.

    This object intentionally contains only source-level information.
    Structured candidate extraction belongs to the extraction module.
    """

    def __init__(
        self,
        file_path: Path,
        text: str,
        page_count: int,
    ) -> None:
        self.file_path = file_path
        self.text = text
        self.page_count = page_count


class CVParser:
    """
    Extracts raw text from CV files.

    Responsibilities:
        - Validate the CV file.
        - Identify the supported file format.
        - Extract raw text.
        - Report parsing failures.

    This module does NOT:
        - Extract candidate information.
        - Call an LLM.
        - Score candidates.
        - Categorize candidates.
    """

    SUPPORTED_EXTENSIONS = {
        ".pdf",
    }

    DOCUMENT_EXTENSIONS = {
        ".docx",
        ".txt",
    }

    def __init__(self, allow_document_formats: bool = False) -> None:
        self.allow_document_formats = allow_document_formats

    def parse(self, file_path: str | Path) -> ParsedCV:
        """
        Parse a CV and return its raw text.

        Args:
            file_path:
                Path to the CV file.

        Returns:
            ParsedCV containing the extracted source text.

        Raises:
            CVParsingError:
                If the file does not exist, is unsupported, or
                cannot be parsed.
        """

        path = Path(file_path)

        self._validate_file(path)

        extension = path.suffix.lower()

        if extension == ".pdf":
            return self._parse_pdf(path)

        if extension == ".docx" and self.allow_document_formats:
            return self._parse_docx(path)

        if extension == ".txt" and self.allow_document_formats:
            return self._parse_txt(path)

        raise CVParsingError(
            f"Unsupported CV format: {extension}"
        )

    def _validate_file(self, file_path: Path) -> None:
        """
        Validate that the supplied CV exists and is a regular file.
        """

        if not file_path.exists():
            raise CVParsingError(
                f"CV file does not exist: {file_path}"
            )

        if not file_path.is_file():
            raise CVParsingError(
                f"CV path is not a file: {file_path}"
            )

        supported_extensions = self.SUPPORTED_EXTENSIONS
        if self.allow_document_formats:
            supported_extensions = supported_extensions | self.DOCUMENT_EXTENSIONS

        if file_path.suffix.lower() not in supported_extensions:
            raise CVParsingError(
                f"Unsupported CV format: {file_path.suffix}"
            )

    def _parse_pdf(self, file_path: Path) -> ParsedCV:
        """
        Extract text from a PDF CV.

        This first implementation handles text-based PDFs such as
        ATS-friendly CVs and digitally generated CVs.

        Image-only/scanned PDFs will be detected when they produce
        insufficient text. OCR will be added as a separate parsing
        capability later without mixing OCR logic into extraction
        or scoring.
        """

        try:
            reader = PdfReader(str(file_path))
        except Exception as exc:
            raise CVParsingError(
                f"Unable to open PDF CV: {exc}"
            ) from exc

        if not reader.pages:
            raise CVParsingError(
                "The PDF CV contains no pages."
            )

        extracted_pages: list[str] = []

        for page_number, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except Exception as exc:
                raise CVParsingError(
                    f"Unable to extract text from PDF page "
                    f"{page_number}: {exc}"
                ) from exc

            extracted_pages.append(page_text)

        text = self._clean_extracted_text(
            "\n".join(extracted_pages)
        )

        if not text and OCR_ENABLED:
            text = self._extract_ocr_text(file_path)

        if not text:
            raise CVParsingError(
                "No text could be extracted from the PDF CV. "
                "The document may be scanned or image-based and "
                "requires OCR."
            )

        return ParsedCV(
            file_path=file_path,
            text=text,
            page_count=len(reader.pages),
        )

    @staticmethod
    def _extract_ocr_text(file_path: Path) -> str:
        """Attempt OCR without making OCR a dependency of extraction."""

        try:
            from pdf2image import convert_from_path
            import pytesseract

            images = convert_from_path(str(file_path), dpi=200)
            text = "\n".join(
                pytesseract.image_to_string(
                    image,
                    lang=OCR_LANGUAGE,
                )
                for image in images
            )
            return CVParser._clean_extracted_text(text)
        except Exception:
            return ""

    def _parse_docx(self, file_path: Path) -> ParsedCV:
        if Document is None:
            raise CVParsingError(
                "DOCX parsing is unavailable. Install python-docx."
            )

        try:
            document = Document(str(file_path))
            paragraphs = [paragraph.text for paragraph in document.paragraphs]
            for table in document.tables:
                for row in table.rows:
                    paragraphs.append(" | ".join(cell.text for cell in row.cells))
        except Exception as exc:
            raise CVParsingError(
                f"Unable to parse DOCX CV: {exc}"
            ) from exc

        text = self._clean_extracted_text("\n".join(paragraphs))
        if not text:
            raise CVParsingError("No text could be extracted from the DOCX CV.")

        return ParsedCV(file_path=file_path, text=text, page_count=1)

    def _parse_txt(self, file_path: Path) -> ParsedCV:
        try:
            text = file_path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            try:
                text = file_path.read_text(encoding="cp1252")
            except Exception as exc:
                raise CVParsingError(
                    f"Unable to decode TXT CV: {exc}"
                ) from exc
        except Exception as exc:
            raise CVParsingError(
                f"Unable to read TXT CV: {exc}"
            ) from exc

        text = self._clean_extracted_text(text)
        if not text:
            raise CVParsingError("No text could be extracted from the TXT CV.")

        return ParsedCV(file_path=file_path, text=text, page_count=1)

    @staticmethod
    def _clean_extracted_text(text: str) -> str:
        """
        Normalize extracted text while preserving the source content.
        """

        lines = text.splitlines()

        cleaned_lines: list[str] = []

        for line in lines:
            normalized_line = " ".join(line.split())

            if normalized_line:
                cleaned_lines.append(normalized_line)

        return "\n".join(cleaned_lines)