from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Sample:
    input: str
    output: str
    explanation: str = ""


@dataclass(frozen=True)
class Question:
    slot: int
    title: str
    difficulty: str
    tags: tuple[str, ...]
    time_limit: str
    memory_limit: str
    statement: str
    input_format: str
    output_format: str
    samples: tuple[Sample, ...]
    hints: tuple[str, ...] = field(default_factory=tuple)

