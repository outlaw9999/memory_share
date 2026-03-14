from dataclasses import dataclass


@dataclass(frozen=True)
class KitError(Exception):
    message: str


@dataclass(frozen=True)
class KitIndexError(KitError):
    file_path: str | None = None


@dataclass(frozen=True)
class KitQueryError(KitError):
    query_name: str | None = None


@dataclass(frozen=True)
class KitSyncError(KitError):
    project_name: str | None = None


@dataclass(frozen=True)
class KitParseError(KitError):
    node_id: str | None = None


@dataclass(frozen=True)
class KitLockError(KitError):
    resource_id: str | None = None


@dataclass(frozen=True)
class KitGraphError(KitError):
    symbol: str | None = None
