from dataclasses import dataclass


@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str
    file: str
    line: int
