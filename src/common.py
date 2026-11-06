class FileLevelError(Exception):
    """Raised when a file cannot be read, has an unsupported format, or lacks required columns."""
    pass

class ConflictingKeyError(Exception):
    """Raised when records have matching (country, year) keys but conflicting measurement values."""
    pass
