"""Tests for the custom exception hierarchy."""

from trading_advisor.exceptions import (
    APIError,
    ConfigurationError,
    DataValidationError,
    InsufficientHistoryError,
    StorageError,
    WealthOpsError,
)

# ---------------------------------------------------------------------------
# WealthOpsError base class
# ---------------------------------------------------------------------------


def test_wealthops_error_message_preserved() -> None:
    """WealthOpsError can be raised with a message and message is preserved."""
    message = "Something went wrong"
    exc = WealthOpsError(message)
    assert str(exc) == message


# ---------------------------------------------------------------------------
# DataValidationError
# ---------------------------------------------------------------------------


def test_data_validation_error_message_preserved() -> None:
    """DataValidationError message is preserved in str(exc)."""
    message = "Invalid data format"
    exc = DataValidationError(message)
    assert str(exc) == message


def test_data_validation_error_is_subclass_of_wealthops_error() -> None:
    """DataValidationError is a subclass of WealthOpsError."""
    assert issubclass(DataValidationError, WealthOpsError)


def test_data_validation_error_is_subclass_of_exception() -> None:
    """DataValidationError is a subclass of Exception."""
    assert issubclass(DataValidationError, Exception)


# ---------------------------------------------------------------------------
# InsufficientHistoryError
# ---------------------------------------------------------------------------


def test_insufficient_history_error_message_preserved() -> None:
    """InsufficientHistoryError message is preserved in str(exc)."""
    message = "Not enough historical data"
    exc = InsufficientHistoryError(message)
    assert str(exc) == message


def test_insufficient_history_error_is_subclass_of_wealthops_error() -> None:
    """InsufficientHistoryError is a subclass of WealthOpsError."""
    assert issubclass(InsufficientHistoryError, WealthOpsError)


def test_insufficient_history_error_is_subclass_of_exception() -> None:
    """InsufficientHistoryError is a subclass of Exception."""
    assert issubclass(InsufficientHistoryError, Exception)


# ---------------------------------------------------------------------------
# ConfigurationError
# ---------------------------------------------------------------------------


def test_configuration_error_message_preserved() -> None:
    """ConfigurationError message is preserved in str(exc)."""
    message = "Missing required configuration"
    exc = ConfigurationError(message)
    assert str(exc) == message


def test_configuration_error_is_subclass_of_wealthops_error() -> None:
    """ConfigurationError is a subclass of WealthOpsError."""
    assert issubclass(ConfigurationError, WealthOpsError)


def test_configuration_error_is_subclass_of_exception() -> None:
    """ConfigurationError is a subclass of Exception."""
    assert issubclass(ConfigurationError, Exception)


# ---------------------------------------------------------------------------
# StorageError
# ---------------------------------------------------------------------------


def test_storage_error_message_preserved() -> None:
    """StorageError message is preserved in str(exc)."""
    message = "Failed to read from storage"
    exc = StorageError(message)
    assert str(exc) == message


def test_storage_error_is_subclass_of_wealthops_error() -> None:
    """StorageError is a subclass of WealthOpsError."""
    assert issubclass(StorageError, WealthOpsError)


def test_storage_error_is_subclass_of_exception() -> None:
    """StorageError is a subclass of Exception."""
    assert issubclass(StorageError, Exception)


# ---------------------------------------------------------------------------
# APIError
# ---------------------------------------------------------------------------


def test_api_error_message_preserved() -> None:
    """APIError message is preserved in str(exc)."""
    message = "External API request failed"
    exc = APIError(message)
    assert str(exc) == message


def test_api_error_is_subclass_of_wealthops_error() -> None:
    """APIError is a subclass of WealthOpsError."""
    assert issubclass(APIError, WealthOpsError)


def test_api_error_is_subclass_of_exception() -> None:
    """APIError is a subclass of Exception."""
    assert issubclass(APIError, Exception)
