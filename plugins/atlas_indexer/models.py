from dataclasses import dataclass


@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str
    file: str
    line: int


@dataclass(frozen=True)
class CallSite:
    caller: str
    callee: str
    file: str
    line: int
