"""Custom exception hierarchy for WealthOps trading advisory system."""


class WealthOpsError(Exception):
    """Base exception for all WealthOps errors."""

    pass


class DataValidationError(WealthOpsError):
    """Raised when data validation fails or invalid data is encountered."""

    pass


class InsufficientHistoryError(WealthOpsError):
    """Raised when there is not enough historical data to perform an operation."""

    pass


class ConfigurationError(WealthOpsError):
    """Raised when configuration is missing or invalid."""

    pass


class StorageError(WealthOpsError):
    """Raised when storage read/write operations fail."""

    pass


class APIError(WealthOpsError):
    """Raised when external API calls fail."""

    pass
