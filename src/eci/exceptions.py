"""Project-specific exception hierarchy.

Using named exceptions makes failures easier to classify, log, test, and present
safely to a user without leaking credentials or internal details.
"""


class ECIError(Exception):
    """Base class for expected application errors."""


class ConfigurationError(ECIError):
    """Raised when required configuration is missing or unsafe."""


class DataContractError(ECIError):
    """Raised when an input file does not satisfy the expected column contract."""


class DatabaseOperationError(ECIError):
    """Raised when a database transaction cannot be completed."""


class VectorStoreError(ECIError):
    """Raised when the vector index cannot be read or updated."""


class ExternalServiceError(ECIError):
    """Raised when OpenAI or another external service fails safely."""


class QueryValidationError(ECIError):
    """Raised when a user query is empty, too long, or otherwise invalid."""
