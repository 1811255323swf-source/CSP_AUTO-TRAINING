"""Offline checks for the AI question provider.

Runs without pytest and without any API key:
    python tests/test_ai_provider.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from csp_trainer.ai_question_provider import (  # noqa: E402
    AIQuestionProvider,
    parse_ai_payload,
)
from csp_trainer.models import Question  # noqa: E402


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _BadRequest(Exception):
    """Stands in for openai.BadRequestError."""

    status_code = 400


class _FakeCompletions:
    def __init__(self, script: list[str], reject: tuple[str, ...] = ()) -> None:
        self.script = list(script)
        self.calls = 0
        self.kwargs_seen: list[dict] = []
        self.reject = reject

    def create(self, **kwargs):
        self.calls += 1
        self.kwargs_seen.append(kwargs)
        for key in self.reject:
            if key in kwargs:
                raise _BadRequest(f"Unsupported parameter: {key}")
        return _FakeResponse(self.script.pop(0))


class _FakeClient:
    def __init__(self, script: list[str], reject: tuple[str, ...] = ()) -> None:
        self.chat = self
        self.completions = _FakeCompletions(script, reject)


def _valid_payload() -> str:
    return json.dumps(
        {
            "questions": [
                {
                    "slot": 1,
                    "title": "签到统计",
                    "difficulty": "CSP 第 1 题",
                    "tags": ["模拟", "字符串"],
                    "time_limit": "1s",
                    "memory_limit": "256MB",
                    "statement": "给定 n 天的签到记录，统计连续签到天数。",
                    "input_format": "第一行一个整数 n，第二行一个长度为 n 的字符串。",
                    "output_format": "输出一个整数。",
                    "samples": [{"input": "5\nYYNYY", "output": "2", "explanation": "最长连续 2 天。"}],
                    "hints": ["一次遍历维护计数"],
                },
                {
                    "slot": 2,
                    "title": "区间合并",
                    "difficulty": "CSP 第 2 题",
                    "tags": ["排序", "贪心"],
                    "statement": "合并所有重叠区间。",
                    "input_format": "第一行 n，随后 n 行两个整数。",
                    "output_format": "每行输出一个合并后的区间。",
                    "samples": [{"input": "3\n1 3\n2 6\n8 10", "output": "1 6\n8 10"}],
                    "hints": ["先按左端点排序"],
                },
                {
                    "slot": 3,
                    "title": "树形路径计数",
                    "difficulty": "CSP 第 3 题",
                    "tags": ["树", "DP"],
                    "statement": "统计树上满足条件的路径条数。",
                    "input_format": "第一行 n，随后 n-1 条边。",
                    "output_format": "输出路径条数。",
                    "samples": [{"input": "3\n1 2\n2 3", "output": "6"}],
                    "hints": ["树上 DP"],
                },
            ]
        },
        ensure_ascii=False,
    )


def _check_parse_plain_json() -> None:
    questions = parse_ai_payload(_valid_payload())
    assert len(questions) == 3, questions
    assert all(isinstance(q, Question) for q in questions)
    assert [q.slot for q in questions] == [1, 2, 3]
    assert questions[0].samples[0].input == "5\nYYNYY"
    assert questions[1].tags == ("排序", "贪心")
    print("ok  parse_ai_payload: plain JSON")


def _check_parse_fenced_json() -> None:
    payload = "```json\n" + _valid_payload() + "\n```"
    questions = parse_ai_payload(payload)
    assert len(questions) == 3
    print("ok  parse_ai_payload: ```json fence")


def _check_parse_json_with_prose() -> None:
    payload = "好的，这是今天的题目：\n" + _valid_payload() + "\n希望对你有帮助。"
    questions = parse_ai_payload(payload)
    assert len(questions) == 3
    print("ok  parse_ai_payload: JSON wrapped in prose")


def _check_markdown_fallback() -> None:
    text = "\n".join(
        [
            "【题目名称】数字统计",
            "【题目描述】统计区间内数字 d 的出现次数。",
            "【输入格式】两个整数 l, r 和一个数字 d。",
            "【输出格式】输出出现次数。",
            "【输入样例】1 13 1",
            "【输出样例】6",
            "【考察知识点】枚举、数位",
        ]
        * 3
    )
    questions = parse_ai_payload(text)
    assert len(questions) == 3, len(questions)
    assert questions[0].title == "数字统计"
    assert questions[0].samples[0].output == "6"
    print("ok  parse_ai_payload: markdown 【】 fallback")


def _check_bad_payload_raises() -> None:
    for bad in ("", "抱歉，我无法完成。", json.dumps({"questions": []})):
        try:
            parse_ai_payload(bad)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for payload: {bad!r}")
    print("ok  parse_ai_payload: rejects empty / unusable payloads")


def _check_two_questions_rejected() -> None:
    payload = json.loads(_valid_payload())
    payload["questions"] = payload["questions"][:2]
    try:
        parse_ai_payload(json.dumps(payload))
    except ValueError as exc:
        assert "exactly 3" in str(exc)
        print("ok  parse_ai_payload: rejects 2-question payloads")
        return
    raise AssertionError("expected rejection of 2-question payload")


def _check_provider_retry_then_success() -> None:
    provider = AIQuestionProvider(api_key="test-key")
    provider.client = _FakeClient(["这不是 JSON", _valid_payload()])
    questions = provider.get_daily_questions(date(2026, 9, 28))
    assert len(questions) == 3
    assert provider.client.completions.calls == 2
    print("ok  AIQuestionProvider: retries after a bad response and recovers")


def _check_provider_exhausts_retries() -> None:
    provider = AIQuestionProvider(api_key="test-key", max_retries=1)
    provider.client = _FakeClient(["nope", "still nope"])
    try:
        provider.get_daily_questions(date(2026, 9, 28))
    except RuntimeError as exc:
        assert "failed after 2 attempt(s)" in str(exc)
        assert provider.client.completions.calls == 2
        print("ok  AIQuestionProvider: raises RuntimeError after retries are exhausted")
        return
    raise AssertionError("expected RuntimeError")


def _check_request_parameters() -> None:
    """Non-thinking mode must send max_tokens, JSON output and thinking=disabled."""
    provider = AIQuestionProvider(api_key="test-key", max_tokens=8192, thinking=False)
    provider.client = _FakeClient([_valid_payload()])
    provider.get_daily_questions(date(2026, 9, 28))

    sent = provider.client.completions.kwargs_seen[0]
    assert sent["max_tokens"] == 8192, sent
    assert sent["response_format"] == {"type": "json_object"}, sent
    assert sent["extra_body"] == {"thinking": {"type": "disabled"}}, sent
    assert sent["model"] == "deepseek-flash", sent
    assert "temperature" in sent, "temperature must be sent in non-thinking mode"
    assert "reasoning_effort" not in sent, sent
    print("ok  request: non-thinking mode sends max_tokens + json_object + thinking=disabled")


def _check_thinking_mode_parameters() -> None:
    """Thinking mode must not send temperature (server ignores it) but set effort."""
    provider = AIQuestionProvider(api_key="test-key", thinking=True)
    provider.client = _FakeClient([_valid_payload()])
    provider.get_daily_questions(date(2026, 9, 28))

    sent = provider.client.completions.kwargs_seen[0]
    assert sent["extra_body"] == {"thinking": {"type": "enabled"}}, sent
    assert sent["reasoning_effort"] == "high", sent
    assert "temperature" not in sent, "temperature is ignored in thinking mode"
    print("ok  request: thinking mode sets effort and omits temperature")


def _check_param_downgrade() -> None:
    """An endpoint rejecting response_format/extra_body must be retried without them."""
    provider = AIQuestionProvider(api_key="test-key")
    provider.client = _FakeClient(
        [_valid_payload()], reject=("response_format", "extra_body", "max_tokens")
    )
    questions = provider.get_daily_questions(date(2026, 9, 28))

    assert len(questions) == 3
    assert provider.client.completions.calls == 2, provider.client.completions.calls
    fallback_kwargs = provider.client.completions.kwargs_seen[1]
    assert "response_format" not in fallback_kwargs
    assert "extra_body" not in fallback_kwargs
    assert "max_tokens" not in fallback_kwargs
    print("ok  request: downgrades to plain parameters when the endpoint rejects extensions")


def _check_missing_api_key() -> None:
    from csp_trainer.config import AISection, ConfigurationError

    section = AISection(
        api_key_env="CSP_TEST_MISSING_KEY",
        base_url="https://api.deepseek.com",
        model="deepseek-flash",
        timeout=60.0,
        max_retries=2,
        max_tokens=8192,
        temperature=1.0,
        thinking=False,
        fallback_to_static=False,
    )
    try:
        AIQuestionProvider(config=section)
    except ConfigurationError as exc:
        assert "CSP_TEST_MISSING_KEY" in str(exc)
        print("ok  AIQuestionProvider: missing API key raises ConfigurationError")
        return
    raise AssertionError("expected ConfigurationError")


def main() -> int:
    _check_parse_plain_json()
    _check_parse_fenced_json()
    _check_parse_json_with_prose()
    _check_markdown_fallback()
    _check_bad_payload_raises()
    _check_two_questions_rejected()
    _check_provider_retry_then_success()
    _check_provider_exhausts_retries()
    _check_request_parameters()
    _check_thinking_mode_parameters()
    _check_param_downgrade()
    _check_missing_api_key()
    print("\nAll AI provider checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
