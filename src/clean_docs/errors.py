class CleanDocsError(Exception):
    """Base error with a stable process exit code."""

    exit_code = 3


class ConfigurationError(CleanDocsError):
    exit_code = 2


class ExtractionError(CleanDocsError):
    exit_code = 3


class RegionError(CleanDocsError):
    exit_code = 3


class PolicyError(CleanDocsError):
    exit_code = 1
