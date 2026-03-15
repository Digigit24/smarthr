"""Custom exceptions for Voice AI Orchestrator integration."""


class VoiceAIError(Exception):
    """Base exception for Voice AI API errors."""
    def __init__(self, message: str, code: str = "VOICE_AI_ERROR", status_code: int = 500, details: dict = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


class VoiceAIAuthError(VoiceAIError):
    """Authentication failed with Voice AI service."""
    def __init__(self, message: str = "Authentication failed with Voice AI service", details: dict = None):
        super().__init__(message, code="PROVIDER_AUTH_ERROR", status_code=401, details=details)


class VoiceAINotFoundError(VoiceAIError):
    """Resource not found in Voice AI service."""
    def __init__(self, message: str = "Resource not found in Voice AI service", details: dict = None):
        super().__init__(message, code="NOT_FOUND", status_code=404, details=details)


class VoiceAIProviderError(VoiceAIError):
    """Voice provider (Omnidim/Bolna) returned an error or is unavailable."""
    def __init__(self, message: str = "Voice provider error or service unavailable", details: dict = None):
        super().__init__(message, code="PROVIDER_ERROR", status_code=502, details=details)


class VoiceAICredentialsMissing(VoiceAIError):
    """No provider credentials configured for this tenant."""
    def __init__(self, message: str = "Voice AI provider credentials are not configured", details: dict = None):
        super().__init__(message, code="CREDENTIALS_MISSING", status_code=400, details=details)


class VoiceAIValidationError(VoiceAIError):
    """Request validation failed."""
    def __init__(self, message: str = "Validation error", details: dict = None):
        super().__init__(message, code="VALIDATION_ERROR", status_code=400, details=details)
