# backend/app/exceptions.py

"""
Centralized exception hierarchy for NovaMind.
Every raised application error should be one of these types (or a subclass),
never a bare Exception/ValueError, so api/deps.py and main.py's global
exception handler can map them to consistent HTTP responses.
"""

from typing import Any


class NovaMindError(Exception):
    """
    Base class for all application-raised errors.

    status_code: the HTTP status this error should map to.
    error_code: a stable machine-readable string for API consumers.
    """

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
        }


# ── Auth errors ───────────────────────────────────────────────────────────

class AuthError(NovaMindError):
    status_code = 401
    error_code = "auth_error"


class InvalidCredentialsError(AuthError):
    error_code = "invalid_credentials"

    def __init__(self) -> None:
        super().__init__("Incorrect email or password.")


class TokenExpiredError(AuthError):
    error_code = "token_expired"

    def __init__(self, token_type: str = "access") -> None:
        super().__init__(f"The {token_type} token has expired.", details={"token_type": token_type})


class TokenInvalidError(AuthError):
    error_code = "token_invalid"

    def __init__(self, reason: str = "Token could not be verified.") -> None:
        super().__init__(reason)


class TokenRevokedError(AuthError):
    error_code = "token_revoked"

    def __init__(self) -> None:
        super().__init__("This token has been revoked.")


class EmailNotVerifiedError(AuthError):
    status_code = 403
    error_code = "email_not_verified"

    def __init__(self) -> None:
        super().__init__("Please verify your email address before continuing.")


class UserAlreadyExistsError(NovaMindError):
    status_code = 409
    error_code = "user_already_exists"

    def __init__(self, email: str) -> None:
        super().__init__(f"An account with email '{email}' already exists.", details={"email": email})


class UserNotFoundError(NovaMindError):
    status_code = 404
    error_code = "user_not_found"

    def __init__(self) -> None:
        super().__init__("User not found.")


class InsufficientPermissionsError(NovaMindError):
    status_code = 403
    error_code = "insufficient_permissions"

    def __init__(self, action: str = "perform this action") -> None:
        super().__init__(f"You do not have permission to {action}.")


# ── Validation errors ─────────────────────────────────────────────────────

class ValidationError(NovaMindError):
    status_code = 422
    error_code = "validation_error"


class WeakPasswordError(ValidationError):
    error_code = "weak_password"

    def __init__(self, reason: str) -> None:
        super().__init__(f"Password does not meet requirements: {reason}")


# ── Search pipeline errors ───────────────────────────────────────────────

class SearchError(NovaMindError):
    status_code = 502
    error_code = "search_error"


class SearchProviderError(SearchError):
    error_code = "search_provider_error"

    def __init__(self, provider: str, reason: str) -> None:
        super().__init__(
            f"Search provider '{provider}' failed: {reason}",
            details={"provider": provider},
        )


class AllSearchProvidersFailedError(SearchError):
    error_code = "all_search_providers_failed"

    def __init__(self, attempted_providers: list[str]) -> None:
        super().__init__(
            "All configured search providers failed to return results.",
            details={"attempted_providers": attempted_providers},
        )


class NoSearchResultsError(SearchError):
    status_code = 200
    error_code = "no_search_results"

    def __init__(self, query: str) -> None:
        super().__init__(
            f"No search results were found for the given query.",
            details={"query": query},
        )


# ── LLM / inference errors ───────────────────────────────────────────────

class LLMError(NovaMindError):
    status_code = 502
    error_code = "llm_error"


class LLMProviderRateLimitedError(LLMError):
    status_code = 429
    error_code = "llm_rate_limited"

    def __init__(self, provider: str, key_slot: str) -> None:
        super().__init__(
            f"LLM provider '{provider}' rate-limited the '{key_slot}' API key.",
            details={"provider": provider, "key_slot": key_slot},
        )


class AllLLMKeysExhaustedError(LLMError):
    error_code = "all_llm_keys_exhausted"

    def __init__(self, provider: str) -> None:
        super().__init__(
            f"All available API keys for '{provider}' are rate-limited or invalid.",
            details={"provider": provider},
        )


class LLMResponseParsingError(LLMError):
    error_code = "llm_response_parsing_error"

    def __init__(self, reason: str) -> None:
        super().__init__(f"Could not parse the LLM response: {reason}")


# ── RAG / document errors ────────────────────────────────────────────────

class DocumentError(NovaMindError):
    status_code = 422
    error_code = "document_error"


class UnsupportedDocumentTypeError(DocumentError):
    error_code = "unsupported_document_type"

    def __init__(self, file_type: str) -> None:
        super().__init__(
            f"Document type '{file_type}' is not supported.",
            details={"file_type": file_type},
        )


class DocumentTooLargeError(DocumentError):
    error_code = "document_too_large"

    def __init__(self, size_mb: float, max_mb: float) -> None:
        super().__init__(
            f"Document is {size_mb:.1f}MB, which exceeds the {max_mb:.1f}MB limit.",
            details={"size_mb": size_mb, "max_mb": max_mb},
        )


class DocumentProcessingError(DocumentError):
    status_code = 500
    error_code = "document_processing_error"

    def __init__(self, document_id: str, reason: str) -> None:
        super().__init__(
            f"Failed to process document: {reason}",
            details={"document_id": document_id},
        )


class DocumentNotFoundError(NovaMindError):
    status_code = 404
    error_code = "document_not_found"

    def __init__(self) -> None:
        super().__init__("Document not found.")


# ── Conversation / resource errors ───────────────────────────────────────

class ConversationNotFoundError(NovaMindError):
    status_code = 404
    error_code = "conversation_not_found"

    def __init__(self) -> None:
        super().__init__("Conversation not found.")


class ResourceNotFoundError(NovaMindError):
    status_code = 404
    error_code = "resource_not_found"

    def __init__(self, resource_type: str) -> None:
        super().__init__(f"{resource_type} not found.", details={"resource_type": resource_type})


# ── Rate limiting / quota errors ─────────────────────────────────────────

class RateLimitExceededError(NovaMindError):
    status_code = 429
    error_code = "rate_limit_exceeded"

    def __init__(self, retry_after_seconds: int | None = None) -> None:
        details = {"retry_after_seconds": retry_after_seconds} if retry_after_seconds else {}
        super().__init__("Rate limit exceeded. Please try again later.", details=details)


# ── Configuration errors (fail fast at startup) ──────────────────────────

class ConfigurationError(NovaMindError):
    status_code = 500
    error_code = "configuration_error"

    def __init__(self, missing_var: str) -> None:
        super().__init__(
            f"Required configuration '{missing_var}' is missing or invalid.",
            details={"missing_var": missing_var},
        )