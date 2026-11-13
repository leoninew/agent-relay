class RoomNotFoundError(LookupError):
    def __init__(self, message: str, *, code: str = "not_found") -> None:
        super().__init__(message)
        self.code = code


class RoomInputError(ValueError):
    def __init__(self, message: str, *, code: str = "unprocessable_entity") -> None:
        super().__init__(message)
        self.code = code


class RoomConflictError(ValueError):
    def __init__(self, message: str, *, code: str = "conflict") -> None:
        super().__init__(message)
        self.code = code
