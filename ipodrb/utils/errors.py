"""Custom exceptions."""


class IpodrbError(Exception):
    """Base exception for ipodrb."""

    pass


class ConfigError(IpodrbError):
    """Configuration error."""

    pass


class ScanError(IpodrbError):
    """Error during library scanning."""

    pass


class ConversionError(IpodrbError):
    """Error during audio conversion."""

    pass


class XLSXError(IpodrbError):
    """Error with XLSX operations."""

    pass
