class SourceboundError(Exception):
    """Base error with a stable process exit code."""

    exit_code = 3


class ConfigurationError(SourceboundError):
    exit_code = 2


class ExtractionError(SourceboundError):
    exit_code = 3


class RegionError(SourceboundError):
    exit_code = 3


class PolicyError(SourceboundError):
    exit_code = 1
