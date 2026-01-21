"""Custom exceptions."""


class YangonError(Exception):
    """Base exception for yangon."""

    pass


class ConfigError(YangonError):
    """Configuration error."""

    pass


class ScanError(YangonError):
    """Error during library scanning."""

    pass


class ConversionError(YangonError):
    """Error during audio conversion."""

    pass


class XLSXError(YangonError):
    """Error with XLSX operations."""

    pass
