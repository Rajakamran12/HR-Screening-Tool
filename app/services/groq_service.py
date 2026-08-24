
import asyncio
import json
from copy import deepcopy
from typing import Any

import httpx

from app.core.config import (
    GROQ_API_KEY,
    GROQ_BASE_URL,
    GROQ_MODEL,
    LLM_REQUEST_TIMEOUT_SECONDS,
)


class GroqService:
    """
    LLM service used by the HR screening pipeline.

    This service communicates with Groq's OpenAI-compatible API.

    Primary mode:
        Strict JSON Schema structured output.

    Recovery mode:
        If Groq accepts the request but the model-generated JSON does
        not satisfy the strict schema, the service performs ONE recovery
        request using Groq's JSON object mode.

    The recovery request is intentionally different from the original
    request so that the application does not repeatedly send the same
    failing strict request.

    Responsibilities:
        - Communicate with Groq.
        - Convert Pydantic JSON Schema into Groq-compatible strict schema.
        - Handle HTTP/network errors.
        - Handle transient rate limits.
        - Recover from model-generated schema mismatches.
        - Parse returned JSON.

    Pydantic validation remains the responsibility of the extraction
    and scoring layers.
    """

    CHAT_COMPLETIONS_ENDPOINT = (
        f"{GROQ_BASE_URL}/chat/completions"
    )

    # Maximum number of times we retry a rate-limited request.
    #
    # This is deliberately small because a retry itself consumes TPM
    # capacity and can make a rate-limit situation worse.
    MAX_RATE_LIMIT_RETRIES = 2

    # Maximum number of JSON-object recovery requests.
    #
    # We never repeatedly retry the same failed strict-schema request.
    MAX_SCHEMA_RECOVERY_ATTEMPTS = 1

    RATE_LIMIT_BASE_DELAY_SECONDS = 12.0

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ) -> None:

        self.api_key = (
            api_key
            or GROQ_API_KEY
        )

        self.model = (
            model
            or GROQ_MODEL
        )

        self.timeout = (
            timeout
            if timeout is not None
            else LLM_REQUEST_TIMEOUT_SECONDS
        )

        if not self.api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not configured. "
                "Add GROQ_API_KEY to the project's .env file."
            )

    # ------------------------------------------------------------------
    # Headers
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        """
        Build the HTTP headers required by Groq.
        """

        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Main structured generation method
    # ------------------------------------------------------------------

    async def generate_structured(
        self,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        schema_name: str,
        max_tokens: int = 3000,
    ) -> dict[str, Any]:
        """
        Generate structured JSON using Groq.

        Strategy:

            1. Try strict JSON Schema mode.
            2. If Groq reports that the model-generated JSON does not
               satisfy the schema, do NOT repeat the same request.
            3. Perform one JSON-object recovery request.
            4. Return the recovered JSON.
            5. Pydantic validation happens in the caller.

        HTTP 429 responses are handled separately with a small number
        of controlled retries.
        """

        groq_schema = self._prepare_strict_schema(
            schema
        )

        strict_payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "reasoning_effort": "low",
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": groq_schema,
                },
            },
        }

        print(
            f"[Groq] Requesting structured output "
            f"from {self.model}..."
        )

        print(
            f"[Groq] Maximum output tokens: "
            f"{max_tokens}"
        )

        print(
            "[Groq] Reasoning effort: low"
        )

        print(
            "[Groq] Strict JSON Schema: enabled"
        )

        print(
            f"[Groq] Timeout: "
            f"{self.timeout}s"
        )

        # --------------------------------------------------------------
        # First request: strict schema
        # --------------------------------------------------------------

        try:
            return await self._send_with_rate_limit_retries(
                strict_payload
            )

        except _GroqSchemaMismatchError as exc:

            print(
                "[Groq] Strict structured output was rejected "
                "because the generated JSON did not satisfy "
                "the schema."
            )

            print(
                "[Groq] The strict request will NOT be repeated "
                "unchanged."
            )

            print(
                "[Groq] Starting one JSON-object recovery request..."
            )

            # ----------------------------------------------------------
            # Recovery request
            # ----------------------------------------------------------

            recovery_payload = self._build_json_object_recovery_payload(
                messages=messages,
                schema=schema,
                schema_name=schema_name,
                max_tokens=max_tokens,
            )

            try:

                recovered_data = (
                    await self._send_with_rate_limit_retries(
                        recovery_payload
                    )
                )

                print(
                    "[Groq] JSON-object recovery request "
                    "completed successfully."
                )

                return recovered_data

            except RuntimeError as recovery_error:

                raise RuntimeError(
                    "Groq strict structured output failed and "
                    "the JSON-object recovery request also failed. "
                    f"Strict error: {exc}. "
                    f"Recovery error: {recovery_error}"
                ) from recovery_error

    # ------------------------------------------------------------------
    # Recovery payload
    # ------------------------------------------------------------------

    @classmethod
    def _build_json_object_recovery_payload(
        cls,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        schema_name: str,
        max_tokens: int,
    ) -> dict[str, Any]:
        """
        Build a different request for recovery after strict schema
        generation fails.

        JSON mode is used here deliberately.

        The model is explicitly reminded that ALL top-level fields
        must be present.

        The complete Pydantic schema is included as compact JSON text
        inside the recovery instruction so the model still has a
        concrete representation of the expected structure.
        """

        compact_schema = json.dumps(
            schema,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        recovery_instruction = {
            "role": "user",
            "content": (
                "RECOVERY INSTRUCTION\n\n"
                "Your previous response did not satisfy the requested "
                "structured schema.\n\n"
                "Return ONE complete JSON object now.\n\n"
                "IMPORTANT:\n"
                "The JSON object MUST contain ALL required top-level "
                "properties. Do not stop after generating the candidate "
                "object.\n\n"
                "The required top-level properties are exactly:\n"
                "1. candidate\n"
                "2. source_quality\n"
                "3. source_quality_reason\n"
                "4. missing_information\n\n"
                "The top-level object MUST contain all four properties "
                "even when some information is unavailable.\n\n"
                "Rules:\n"
                "- candidate must contain the candidate information.\n"
                "- source_quality must be exactly one of: high, medium, low.\n"
                "- source_quality_reason must be a non-empty string.\n"
                "- missing_information must always be an array.\n"
                "- Use an empty array when there is no missing information.\n"
                "- Use null only where the schema explicitly permits null.\n"
                "- Use empty arrays for unavailable list fields.\n"
                "- Do not invent information.\n"
                "- Use only the supplied CV text.\n"
                "- Return JSON only.\n\n"
                f"Expected schema reference:\n"
                f"{compact_schema}\n"
            ),
        }

        return {
            "model": cls._get_model_from_messages_or_default(
                messages=messages,
            ),
            "messages": [
                *messages,
                recovery_instruction,
            ],
            "max_tokens": max_tokens,
            "reasoning_effort": "low",
            "temperature": 0,
            "response_format": {
                "type": "json_object",
            },
        }

    @staticmethod
    def _get_model_from_messages_or_default(
        messages: list[dict[str, str]],
    ) -> str:
        """
        Placeholder helper retained to keep recovery payload construction
        explicit.

        The actual model is inserted by generate_structured() immediately
        after this method.
        """

        # This value is replaced by generate_structured() below.
        #
        # Keeping this helper avoids extracting model information from
        # unrelated message content.
        return ""

    # ------------------------------------------------------------------
    # Rate-limit wrapper
    # ------------------------------------------------------------------

    async def _send_with_rate_limit_retries(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Send a request while handling HTTP 429 responses.

        Schema mismatch is deliberately NOT retried here because it
        indicates a model-generation/schema compatibility problem,
        not a transient network problem.
        """

        # Ensure recovery payloads always use the configured model.
        payload = deepcopy(payload)

        payload["model"] = self.model

        last_error: RuntimeError | None = None

        for attempt in range(
            self.MAX_RATE_LIMIT_RETRIES + 1
        ):

            try:

                return await self._send_request(
                    payload
                )

            except _GroqRateLimitError as exc:

                last_error = RuntimeError(
                    str(exc)
                )

                if attempt >= self.MAX_RATE_LIMIT_RETRIES:

                    raise RuntimeError(
                        "Groq rate limit persisted after "
                        f"{self.MAX_RATE_LIMIT_RETRIES + 1} attempts. "
                        f"{exc}"
                    ) from exc

                delay = (
                    exc.retry_after
                    if exc.retry_after is not None
                    else (
                        self.RATE_LIMIT_BASE_DELAY_SECONDS
                        * (attempt + 1)
                    )
                )

                print(
                    "[Groq] Rate limit reached."
                )

                print(
                    f"[Groq] Waiting "
                    f"{delay:.2f}s before retry "
                    f"{attempt + 1}/"
                    f"{self.MAX_RATE_LIMIT_RETRIES}..."
                )

                await asyncio.sleep(
                    delay
                )

            except _GroqSchemaMismatchError:
                raise

        raise last_error or RuntimeError(
            "Groq request failed."
        )

    # ------------------------------------------------------------------
    # HTTP request
    # ------------------------------------------------------------------

    async def _send_request(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Send one HTTP request to Groq and parse the returned JSON.
        """

        try:

            async with httpx.AsyncClient(
                timeout=self.timeout
            ) as client:

                response = await client.post(
                    self.CHAT_COMPLETIONS_ENDPOINT,
                    headers=self._headers(),
                    json=payload,
                )

        except httpx.TimeoutException as exc:

            raise RuntimeError(
                "Groq request timed out."
            ) from exc

        except httpx.RequestError as exc:

            raise RuntimeError(
                f"Groq network request failed: {exc}"
            ) from exc

        # --------------------------------------------------------------
        # Rate limit
        # --------------------------------------------------------------

        if response.status_code == 429:

            retry_after = (
                self._get_retry_after(
                    response
                )
            )

            try:
                error_data = response.json()

            except ValueError:
                error_data = {
                    "error": response.text,
                }

            error_message = (
                self._extract_error_message(
                    error_data
                )
            )

            self._print_rate_limit_details(
                response=response,
                error_message=error_message,
                retry_after=retry_after,
            )

            raise _GroqRateLimitError(
                message=(
                    "Groq returned HTTP 429. "
                    f"Message: {error_message}"
                ),
                retry_after=retry_after,
            )

        # --------------------------------------------------------------
        # Other HTTP errors
        # --------------------------------------------------------------

        if response.status_code != 200:

            try:
                error_data = response.json()

            except ValueError:
                error_data = {
                    "error": response.text,
                }

            error_message = (
                self._extract_error_message(
                    error_data
                )
            )

            # Groq returns HTTP 400 when the generated output cannot
            # satisfy the requested JSON schema.
            if (
                response.status_code == 400
                and self._is_schema_rejection_message(
                    error_message
                )
            ):

                raise _GroqSchemaMismatchError(
                    "Groq returned HTTP 400 because the generated "
                    "JSON did not satisfy the requested schema. "
                    f"Message: {error_message}"
                )

            raise RuntimeError(
                "Groq returned an error. "
                f"HTTP status: {response.status_code}. "
                f"Message: {error_message}"
            )

        # --------------------------------------------------------------
        # Parse HTTP response
        # --------------------------------------------------------------

        try:

            response_data = response.json()

        except ValueError as exc:

            raise RuntimeError(
                "Groq returned a response that "
                "is not valid JSON."
            ) from exc

        content = self._extract_content(
            response_data
        )

        if not content:

            raise RuntimeError(
                "Groq returned empty model content."
            )

        try:

            structured_data = json.loads(
                content
            )

        except json.JSONDecodeError as exc:

            raise RuntimeError(
                "Groq returned content that is not "
                "valid JSON."
            ) from exc

        if not isinstance(
            structured_data,
            dict,
        ):

            raise RuntimeError(
                "Groq structured output must be "
                "a JSON object."
            )

        return structured_data

    # ------------------------------------------------------------------
    # Schema rejection detection
    # ------------------------------------------------------------------

    @staticmethod
    def _is_schema_rejection_message(
        message: str,
    ) -> bool:
        """
        Detect Groq errors caused by generated JSON failing
        the requested schema.
        """

        normalized = message.lower()

        indicators = (
            "does not match the expected schema",
            "does not validate with",
            "generated json does not match",
            "missing properties",
            "jsonschema:",
            "failed_generation",
        )

        return any(
            indicator in normalized
            for indicator in indicators
        )

    # ------------------------------------------------------------------
    # Rate-limit diagnostics
    # ------------------------------------------------------------------

    @staticmethod
    def _print_rate_limit_details(
        response: httpx.Response,
        error_message: str,
        retry_after: float | None,
    ) -> None:
        """
        Print useful Groq TPM diagnostics when available.
        """

        print(
            "[Groq] 429 rate-limit details:"
        )

        tpm_limit = response.headers.get(
            "x-ratelimit-limit-tokens"
        )

        tpm_remaining = response.headers.get(
            "x-ratelimit-remaining-tokens"
        )

        reset_tokens = response.headers.get(
            "x-ratelimit-reset-tokens"
        )

        if tpm_limit:
            print(
                f"[Groq] TPM limit: {tpm_limit}"
            )

        if tpm_remaining:
            print(
                f"[Groq] Remaining TPM: {tpm_remaining}"
            )

        if reset_tokens:
            print(
                f"[Groq] Token reset: {reset_tokens}"
            )

        if retry_after is not None:
            print(
                f"[Groq] Retry-After: "
                f"{retry_after:.2f}s"
            )

        # Keep the API message visible because Groq sometimes exposes
        # additional useful rate-limit information there.
        if error_message:
            print(
                f"[Groq] Rate-limit message: "
                f"{error_message}"
            )

    # ------------------------------------------------------------------
    # Pydantic → Groq strict schema normalization
    # ------------------------------------------------------------------

    @classmethod
    def _prepare_strict_schema(
        cls,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Convert a Pydantic JSON Schema into the subset required
        by Groq strict Structured Outputs.

        Every object property is made required.

        Originally optional properties are converted to nullable
        properties so that the model must still return the property.
        """

        normalized_schema = deepcopy(
            schema
        )

        definitions = normalized_schema.get(
            "$defs"
        )

        if isinstance(
            definitions,
            dict,
        ):

            for definition_name, definition in definitions.items():

                if isinstance(
                    definition,
                    dict,
                ):

                    definitions[
                        definition_name
                    ] = cls._normalize_schema_node(
                        definition
                    )

        return cls._normalize_schema_node(
            normalized_schema
        )

    @classmethod
    def _normalize_schema_node(
        cls,
        node: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Recursively normalize one JSON Schema node.
        """

        if not isinstance(
            node,
            dict,
        ):
            return node

        # --------------------------------------------------------------
        # Object
        # --------------------------------------------------------------

        if node.get("type") == "object":

            properties = node.get(
                "properties"
            )

            if isinstance(
                properties,
                dict,
            ):

                original_required = set(
                    node.get(
                        "required",
                        []
                    )
                )

                required_fields: list[str] = []

                for property_name, property_schema in properties.items():

                    if isinstance(
                        property_schema,
                        dict,
                    ):

                        normalized_property = (
                            cls._normalize_schema_node(
                                property_schema
                            )
                        )

                        if property_name not in original_required:

                            normalized_property = (
                                cls._make_nullable(
                                    normalized_property
                                )
                            )

                        properties[
                            property_name
                        ] = normalized_property

                    required_fields.append(
                        property_name
                    )

                node["required"] = (
                    required_fields
                )

            else:

                node["required"] = (
                    node.get(
                        "required",
                        []
                    )
                )

            node[
                "additionalProperties"
            ] = False

        # --------------------------------------------------------------
        # Array
        # --------------------------------------------------------------

        if node.get("type") == "array":

            items = node.get(
                "items"
            )

            if isinstance(
                items,
                dict,
            ):

                node["items"] = (
                    cls._normalize_schema_node(
                        items
                    )
                )

        # --------------------------------------------------------------
        # anyOf
        # --------------------------------------------------------------

        any_of = node.get(
            "anyOf"
        )

        if isinstance(
            any_of,
            list,
        ):

            normalized_any_of = []

            for item in any_of:

                if isinstance(
                    item,
                    dict,
                ):

                    normalized_any_of.append(
                        cls._normalize_schema_node(
                            item
                        )
                    )

                else:

                    normalized_any_of.append(
                        item
                    )

            node["anyOf"] = (
                normalized_any_of
            )

        # --------------------------------------------------------------
        # oneOf
        # --------------------------------------------------------------

        one_of = node.get(
            "oneOf"
        )

        if isinstance(
            one_of,
            list,
        ):

            normalized_one_of = []

            for item in one_of:

                if isinstance(
                    item,
                    dict,
                ):

                    normalized_one_of.append(
                        cls._normalize_schema_node(
                            item
                        )
                    )

                else:

                    normalized_one_of.append(
                        item
                    )

            node["oneOf"] = (
                normalized_one_of
            )

        # --------------------------------------------------------------
        # allOf
        # --------------------------------------------------------------

        all_of = node.get(
            "allOf"
        )

        if isinstance(
            all_of,
            list,
        ):

            normalized_all_of = []

            for item in all_of:

                if isinstance(
                    item,
                    dict,
                ):

                    normalized_all_of.append(
                        cls._normalize_schema_node(
                            item
                        )
                    )

                else:

                    normalized_all_of.append(
                        item
                    )

            node["allOf"] = (
                normalized_all_of
            )

        return node

    # ------------------------------------------------------------------
    # Nullable conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _make_nullable(
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Convert a schema into a nullable schema.
        """

        schema = deepcopy(
            schema
        )

        if GroqService._is_nullable(
            schema
        ):

            return schema

        return {
            "anyOf": [
                schema,
                {
                    "type": "null"
                },
            ],
        }

    @staticmethod
    def _is_nullable(
        schema: dict[str, Any],
    ) -> bool:
        """
        Determine whether a JSON Schema node already allows null.
        """

        schema_type = schema.get(
            "type"
        )

        if (
            isinstance(
                schema_type,
                list,
            )
            and "null" in schema_type
        ):

            return True

        any_of = schema.get(
            "anyOf"
        )

        if isinstance(
            any_of,
            list,
        ):

            for option in any_of:

                if (
                    isinstance(
                        option,
                        dict,
                    )
                    and option.get(
                        "type"
                    ) == "null"
                ):

                    return True

        return False

    # ------------------------------------------------------------------
    # Retry-After
    # ------------------------------------------------------------------

    @staticmethod
    def _get_retry_after(
        response: httpx.Response,
    ) -> float | None:
        """
        Read Groq's Retry-After header when available.
        """

        value = response.headers.get(
            "retry-after"
        )

        if value is None:
            return None

        try:

            return max(
                0.0,
                float(value)
            )

        except ValueError:

            return None

    # ------------------------------------------------------------------
    # Response content
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_content(
        response_data: dict[str, Any],
    ) -> str:
        """
        Extract assistant content from a Groq chat-completion response.
        """

        try:

            content = (
                response_data["choices"][0]
                ["message"]["content"]
            )

        except (
            KeyError,
            IndexError,
            TypeError,
        ) as exc:

            raise RuntimeError(
                "Groq response did not contain "
                "the expected chat completion "
                "content."
            ) from exc

        if not isinstance(
            content,
            str,
        ):

            raise RuntimeError(
                "Groq returned model content "
                "in an unexpected format."
            )

        return content

    # ------------------------------------------------------------------
    # Error message extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_error_message(
        error_data: Any,
    ) -> str:
        """
        Extract a useful error message from Groq's API error response.
        """

        if isinstance(
            error_data,
            dict,
        ):

            error = error_data.get(
                "error"
            )

            if isinstance(
                error,
                dict,
            ):

                message = error.get(
                    "message"
                )

                if message:
                    return str(
                        message
                    )

            if isinstance(
                error,
                str,
            ):

                return error

            message = error_data.get(
                "message"
            )

            if message:
                return str(
                    message
                )

        return "Unknown Groq API error."


# ----------------------------------------------------------------------
# Internal exceptions
# ----------------------------------------------------------------------

class _GroqRateLimitError(RuntimeError):
    """
    Internal exception used to distinguish HTTP 429 responses
    from other failures.
    """

    def __init__(
        self,
        message: str,
        retry_after: float | None = None,
    ) -> None:

        super().__init__(
            message
        )

        self.retry_after = retry_after


class _GroqSchemaMismatchError(RuntimeError):
    """
    Internal exception used when Groq successfully receives the
    request but the model-generated JSON does not satisfy the
    requested strict schema.
    """