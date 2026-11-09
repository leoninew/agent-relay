class RoomNotFoundError(LookupError):
    pass


class RoomInputError(ValueError):
    pass


class RoomConflictError(ValueError):
    pass
