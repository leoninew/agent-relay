from contextlib import AbstractContextManager
from typing import Protocol, TypeVar

RepositoryT_co = TypeVar("RepositoryT_co", covariant=True)


class RepositoryScope(Protocol[RepositoryT_co]):
    def read(self) -> AbstractContextManager[RepositoryT_co]: ...
    def write(self) -> AbstractContextManager[RepositoryT_co]: ...
