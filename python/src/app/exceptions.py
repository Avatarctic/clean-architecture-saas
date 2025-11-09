class DuplicateError(Exception):
    """Raised when a DB unique constraint is violated (duplicate resource)."""

    pass
