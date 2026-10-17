class FilesError(Exception):
    pass


class FileMissingError(FilesError):
    pass


class StorageError(FilesError):
    pass
