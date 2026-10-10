"""Exception types used across the service layer."""


class LibraryError(Exception):
    """Base class for expected, user-facing errors."""


class ValidationError(LibraryError):
    """Invalid input. ``errors`` maps field names to messages."""

    def __init__(self, errors):
        self.errors = dict(errors)
        super().__init__("; ".join(self.errors.values()))


class NotFoundError(LibraryError):
    """A requested record does not exist."""


class ConflictError(LibraryError):
    """The action breaks a library rule (e.g. no copies available)."""


class StorageError(LibraryError):
    """The data file could not be read or written."""


class BackupError(LibraryError):
    """A backup file failed validation. ``problems`` lists the reasons."""

    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))
