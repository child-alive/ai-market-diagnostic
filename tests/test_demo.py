"""双受众演示的固定 Prompt Set、流协议与服务端防护测试。"""
from __future__ import annotations

import io
import json
import asyncio

import httpx

from src.config import Settings
from src.demo_api import SlidingWindowLimiter, create_app
from src.demo_worker import run_worker, select_live_questions
from src.providers.mock import MockProvider


def test_live_prompt_set_is_fixed_high_value_unbranded() -> None:
    questions = select_live_questions(3)

    assert len(questions) == 3
    assert all(question.query_scope.value == "unbranded" for question in questions)
    assert all(question.value_score >= 4 for question in questions)
    assert not any(
        term.casefold() in f"{question.text_local} {question.text_zh}".casefold()
        for question in questions
        for term in ["Deli", "得力", "DeliWorld"]
    )


def test_demo_worker_emits_json_lines_without_real_api() -> None:
    stream = io.StringIO()

    code = run_worker(
        Settings(force_mock=True),
        question_limit=3,
        provider=MockProvider(),
        stream=stream,
    )
    events = [json.loads(line) for line in stream.getvalue().splitlines()]

    assert code == 0
    assert events[0]["type"] == "started"
    assert sum(event["type"] == "question" for event in events) == 3
    assert sum(event["type"] == "result" for event in events) == 3
    assert events[-1]["type"] == "completed"
    assert events[-1]["completed"] == 3


def test_live_endpoint_fails_closed_without_server_key() -> None:
    async def request() -> tuple[httpx.Response, httpx.Response]:
        transport = httpx.ASGITransport(
            app=create_app(live_enabled=False, mount_static=False)
        )
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return (
                await client.get("/api/health"),
                await client.post(
                    "/api/live-diagnose/stream", json={"question_limit": 3}
                ),
            )

    health, response = asyncio.run(request())

    assert health.status_code == 200
    assert health.json()["live_available"] is False
    assert response.status_code == 503
    assert "回放模式" in response.json()["detail"]
    assert "key" not in response.text.lower()


def test_live_request_rejects_more_than_five_questions() -> None:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(
            app=create_app(live_enabled=True, mount_static=False)
        )
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.post(
                "/api/live-diagnose/stream", json={"question_limit": 6}
            )

    response = asyncio.run(request())

    assert response.status_code == 422


def test_sliding_window_limiter_allows_two_runs_per_hour() -> None:
    async def scenario() -> tuple[bool, bool, bool, bool]:
        limiter = SlidingWindowLimiter(limit=2, window_seconds=3600)
        return (
            await limiter.allow("ip", now=0),
            await limiter.allow("ip", now=1),
            await limiter.allow("ip", now=2),
            await limiter.allow("ip", now=3601),
        )

    assert asyncio.run(scenario()) == (True, True, False, True)
