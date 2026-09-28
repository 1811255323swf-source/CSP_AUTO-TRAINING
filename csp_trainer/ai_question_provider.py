from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from csp_trainer.config import AISection, ConfigurationError
from csp_trainer.models import Question, Sample

DEFAULT_BASE_URL = "https://api.deepseek.com"
# deepseek-chat / deepseek-reasoner were retired on 2026-07-24.
DEFAULT_MODEL = "deepseek-flash"
# 3 full CSP statements in one JSON payload need room; truncation breaks parsing.
DEFAULT_MAX_TOKENS = 8192

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_SECTION_RE = re.compile(r"^\s*【\s*([^】]+?)\s*】\s*[:：]?\s*(.*)$")

# Keeps the output schema close to the one used in data/questions.json so that
# the PDF renderer does not need to know where the questions came from.
_JSON_SCHEMA_HINT = """{
  "questions": [
    {
      "slot": 1,
      "title": "题目标题",
      "difficulty": "CSP 第 1 题难度",
      "tags": ["知识点1", "知识点2"],
      "time_limit": "1s",
      "memory_limit": "256MB",
      "statement": "完整的题目描述，包含背景、约束与数据范围",
      "input_format": "输入格式说明",
      "output_format": "输出格式说明",
      "samples": [
        {
          "input": "输入样例内容，保留换行",
          "output": "输出样例内容，保留换行",
          "explanation": "样例说明"
        }
      ],
      "hints": ["提示1", "提示2"]
    }
  ]
}"""


def _prompt_for(training_date: date) -> str:
    return f"""你是一名 CCF CSP 认证考试的资深出题老师。

请为一名计算机科学专业本科生生成 {training_date.isoformat()} 当天的 3 道 CSP 训练题（C++ 作答）。

学生情况：
- 掌握 C++ 基础语法、STL 常用容器
- 掌握基础数据结构与回溯算法、基础图算法
- 正在冲 CSP 100 分

难度分配（必须严格执行）：
- 第 1 题（slot=1）：对标 CSP 第一题，签到题，考察基础模拟/枚举
- 第 2 题（slot=2）：对标 CSP 第二题，需要一个明确的数据结构或经典算法
- 第 3 题（slot=3）：稍有挑战，对标 CSP 第三题，可能需要综合建模

硬性要求：
1. 只做原创题，不要照搬 CSP 历年真题原题。
2. 每道题必须给出完整、可判定的题目描述，包含清晰的数据范围。
3. 每道题至少 1 组输入/输出样例，样例必须自洽（输出确实由输入推得）。
4. 不要输出代码、不要输出题解和答案，hints 只能给思路方向的提示。
5. 所有文本使用简体中文；样例中的数字与字符串保持 ASCII。
6. 只输出一个 JSON 对象，不要任何解释性文字或 markdown 代码块标记。

输出 JSON 结构（严格遵循，questions 数组长度必须为 3）：
{_JSON_SCHEMA_HINT}
"""


def _extract_json_candidate(text: str) -> str:
    """Strip markdown fences / stray prose and return the JSON payload."""
    stripped = text.strip()

    fence = _JSON_FENCE_RE.search(stripped)
    if fence:
        return fence.group(1).strip()

    # Fall back to the outermost brace pair when the model wraps JSON in prose.
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1]

    return stripped


def _as_text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    if isinstance(value, str):
        text = value.strip()
        return text or fallback
    if isinstance(value, list):
        return "\n".join(_as_text(item) for item in value).strip() or fallback
    return str(value).strip() or fallback


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, (list, tuple)):
        items = list(value)
    else:
        items = [value]
    return tuple(text for text in (_as_text(item) for item in items) if text)


def _parse_samples(raw: Any) -> tuple[Sample, ...]:
    if not isinstance(raw, list) or not raw:
        return ()

    samples: list[Sample] = []
    for item in raw:
        if isinstance(item, dict):
            input_text = _as_text(item.get("input"))
            output_text = _as_text(item.get("output"))
            if not input_text and not output_text:
                continue
            samples.append(
                Sample(
                    input=input_text,
                    output=output_text,
                    explanation=_as_text(item.get("explanation")),
                )
            )
        else:
            text = _as_text(item)
            if text:
                samples.append(Sample(input=text, output=""))
    return tuple(samples)


def _question_from_dict(item: dict, index: int) -> Question:
    statement = _as_text(item.get("statement") or item.get("description"))
    if not statement:
        raise ValueError(f"Question #{index + 1} is missing a statement.")

    input_format = _as_text(item.get("input_format"))
    output_format = _as_text(item.get("output_format"))
    if not input_format:
        raise ValueError(f"Question #{index + 1} is missing input_format.")
    if not output_format:
        raise ValueError(f"Question #{index + 1} is missing output_format.")

    samples = _parse_samples(item.get("samples"))
    if not samples:
        raise ValueError(f"Question #{index + 1} has no usable samples.")

    try:
        slot = int(item.get("slot", index + 1))
    except (TypeError, ValueError):
        slot = index + 1
    if slot not in (1, 2, 3):
        slot = index + 1

    return Question(
        slot=slot,
        title=_as_text(item.get("title"), f"训练题 {index + 1}"),
        difficulty=_as_text(item.get("difficulty"), "未标注"),
        tags=_as_tuple(item.get("tags")),
        time_limit=_as_text(item.get("time_limit"), "1s"),
        memory_limit=_as_text(item.get("memory_limit"), "256MB"),
        statement=statement,
        input_format=input_format,
        output_format=output_format,
        samples=samples,
        hints=_as_tuple(item.get("hints")),
    )


def _parse_markdown_fallback(text: str) -> list[Question]:
    """Last-resort parser for models that answer with 【...】 sections."""
    blocks: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    current_key: str | None = None

    for line in text.splitlines():
        match = _SECTION_RE.match(line)
        if match:
            key = match.group(1).replace(" ", "")
            value = match.group(2).strip()
            if key == "题目名称":
                current = {}
                blocks.append(current)
            if current is None:
                continue
            current_key = key
            current[key] = value
            continue

        if current is not None and current_key and line.strip():
            current[current_key] = (current[current_key] + "\n" + line.strip()).strip()

    questions: list[Question] = []
    for index, block in enumerate(blocks[:3]):
        questions.append(
            Question(
                slot=index + 1,
                title=_as_text(block.get("题目名称"), f"训练题 {index + 1}"),
                difficulty=_as_text(block.get("难度"), "未标注"),
                tags=_as_tuple(
                    [tag for tag in re.split(r"[、,，/]", block.get("考察知识点", "")) if tag]
                ),
                time_limit="1s",
                memory_limit="256MB",
                statement=_as_text(block.get("题目描述")),
                input_format=_as_text(block.get("输入格式")),
                output_format=_as_text(block.get("输出格式")),
                samples=(
                    Sample(
                        input=_as_text(block.get("输入样例")),
                        output=_as_text(block.get("输出样例")),
                    ),
                ),
                hints=(),
            )
        )

    return [q for q in questions if q.statement]


def parse_ai_payload(text: str) -> list[Question]:
    """Turn raw model output into three Question objects."""
    if not text or not text.strip():
        raise ValueError("The AI provider returned an empty response.")

    candidate = _extract_json_candidate(text)
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        questions = _parse_markdown_fallback(text)
        if len(questions) == 3:
            return questions
        raise ValueError(
            "Could not parse the AI response as JSON or as structured markdown."
        ) from None

    if isinstance(payload, list):
        raw_items = payload
    elif isinstance(payload, dict):
        raw_items = payload.get("questions")
        if raw_items is None:
            for value in payload.values():
                if isinstance(value, list):
                    raw_items = value
                    break
    else:
        raw_items = None

    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("AI response does not contain a 'questions' list.")

    items = [item for item in raw_items if isinstance(item, dict)]
    if len(items) != 3:
        raise ValueError(
            f"AI returned {len(items)} usable question(s); exactly 3 are required."
        )

    return [_question_from_dict(item, index) for index, item in enumerate(items)]


class AIQuestionProvider:
    """Generate daily CSP questions through an OpenAI-compatible chat API."""

    def __init__(
        self,
        config: AISection | None = None,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: float = 60.0,
        max_retries: int = 2,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = 1.0,
        thinking: bool = False,
    ) -> None:
        if config is not None:
            resolved_key = api_key or config.api_key
            base_url = base_url or config.base_url
            model = config.model or model
            timeout = config.timeout
            max_retries = config.max_retries
            max_tokens = config.max_tokens
            temperature = config.temperature
            thinking = config.thinking
        else:
            resolved_key = api_key

        if not resolved_key:
            env_name = config.api_key_env if config else "DEEPSEEK_API_KEY"
            raise ConfigurationError(
                f"AI provider is enabled but {env_name} is not set. "
                "Export the key or switch app.provider to static."
            )

        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - depends on env
            raise ConfigurationError(
                "AI provider requires the 'openai' package. Run: pip install -r requirements.txt"
            ) from exc

        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.max_retries = max_retries
        self.max_tokens = max_tokens
        self.thinking = thinking
        self.client = OpenAI(
            api_key=resolved_key,
            base_url=base_url or DEFAULT_BASE_URL,
            timeout=timeout,
            max_retries=0,  # Retries are handled here so failures can be reported.
        )

    def get_daily_questions(self, training_date: date) -> list[Question]:
        return self.generate(training_date)

    def generate(self, training_date: date) -> list[Question]:
        prompt = _prompt_for(training_date)
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                content = self._chat(prompt, attempt)
                return parse_ai_payload(content)
            except Exception as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break

        raise RuntimeError(
            f"AI question generation failed after {self.max_retries + 1} attempt(s): {last_error}"
        ) from last_error

    @staticmethod
    def _is_param_error(exc: Exception) -> bool:
        """True when the endpoint rejected an optional/extended parameter."""
        if getattr(exc, "status_code", None) == 400:
            return True
        text = str(exc).lower()
        return any(
            key in text
            for key in (
                "response_format",
                "reasoning_effort",
                "extra_body",
                "thinking",
                "max_tokens",
                "unexpected keyword",
                "unknown parameter",
                "unsupported",
            )
        )

    def _chat(self, prompt: str, attempt: int) -> str:
        messages: list[dict[str, str]] = [{"role": "user", "content": prompt}]
        temperature = self.temperature
        if attempt > 0:
            # Nudge towards strict JSON after a parse failure.
            messages.append(
                {
                    "role": "assistant",
                    "content": "I will answer with a single valid JSON object only.",
                }
            )
            temperature = min(self.temperature, 0.3)

        # Plain parameters every OpenAI-compatible endpoint understands.
        base: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "timeout": self.timeout,
        }
        if not self.thinking:
            # temperature has no effect in thinking mode, so only send it otherwise.
            base["temperature"] = temperature

        # DeepSeek extensions: JSON output, an explicit output budget, and an
        # explicit thinking-mode switch (the server defaults to enabled).
        extended: dict[str, Any] = {
            **base,
            "response_format": {"type": "json_object"},
            "max_tokens": self.max_tokens,
            "extra_body": {"thinking": {"type": "enabled" if self.thinking else "disabled"}},
        }
        if self.thinking:
            extended["reasoning_effort"] = "high"

        last_error: Exception | None = None
        for kwargs in (extended, base):
            try:
                response = self.client.chat.completions.create(**kwargs)
            except Exception as exc:
                last_error = exc
                if kwargs is base or not self._is_param_error(exc):
                    raise
                continue

            content = response.choices[0].message.content
            if not content:
                raise ValueError("The AI provider returned an empty message.")
            return content

        raise last_error if last_error else RuntimeError("Chat request failed.")
