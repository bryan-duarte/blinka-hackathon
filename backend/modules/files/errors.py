class FilesError(Exception):
    pass


class FileMissingError(FilesError):
    pass


class StorageError(FilesError):
    pass


class UnsupportedFileError(FilesError):
    pass


class FileQuarantinedError(FilesError):
    pass


class UnsafeArchiveError(FilesError):
    pass


class UnsafePrefixError(FilesError, ValueError):
    pass
