from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Protocol

from csp_trainer.models import Question, Sample


class QuestionProvider(Protocol):
    def get_daily_questions(self, training_date: date) -> list[Question]:
        """Return exactly three questions for the requested date."""


class StaticQuestionProvider:
    """Load local JSON questions and rotate them deterministically by date."""

    def __init__(self, questions_file: Path) -> None:
        self.questions_file = questions_file

    def get_daily_questions(self, training_date: date) -> list[Question]:
        questions = self._load_questions()
        by_slot: dict[int, list[Question]] = defaultdict(list)
        for question in questions:
            by_slot[question.slot].append(question)

        selected: list[Question] = []
        day_index = training_date.toordinal()
        for slot in (1, 2, 3):
            slot_questions = by_slot.get(slot, [])
            if not slot_questions:
                raise ValueError(f"No questions configured for slot {slot}.")
            selected.append(slot_questions[day_index % len(slot_questions)])
        return selected

    def _load_questions(self) -> list[Question]:
        if not self.questions_file.exists():
            raise FileNotFoundError(f"Question file not found: {self.questions_file}")

        raw = json.loads(self.questions_file.read_text(encoding="utf-8"))
        items = raw.get("questions", [])
        if not isinstance(items, list) or not items:
            raise ValueError("questions.json must contain a non-empty 'questions' list.")

        return [self._parse_question(item) for item in items]

    @staticmethod
    def _parse_question(item: dict) -> Question:
        samples = tuple(
            Sample(
                input=str(sample.get("input", "")),
                output=str(sample.get("output", "")),
                explanation=str(sample.get("explanation", "")),
            )
            for sample in item.get("samples", [])
        )
        if not samples:
            raise ValueError(f"Question '{item.get('title', '<untitled>')}' needs samples.")

        return Question(
            slot=int(item["slot"]),
            title=str(item["title"]),
            difficulty=str(item.get("difficulty", "")),
            tags=tuple(str(tag) for tag in item.get("tags", [])),
            time_limit=str(item.get("time_limit", "1s")),
            memory_limit=str(item.get("memory_limit", "256MB")),
            statement=str(item["statement"]),
            input_format=str(item["input_format"]),
            output_format=str(item["output_format"]),
            samples=samples,
            hints=tuple(str(hint) for hint in item.get("hints", [])),
        )


class ApiQuestionProvider:
    """Placeholder for future ChatGPT/OpenAI API generated questions."""

    def get_daily_questions(self, training_date: date) -> list[Question]:
        raise NotImplementedError(
            "ApiQuestionProvider is reserved for the next version. "
            "Implement it so it returns list[Question], then switch provider wiring in main.py."
        )

