"""双受众演示页的极简 FastAPI 服务。

静态回放永远可用；实况端点固定 3~5 个无品牌词、每 IP 限流、全局并发 1，
并通过可终止子进程实现总超时。API key 只从服务端环境读取。
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import PROJECT_ROOT, Settings

WEB_DIST_DIR = PROJECT_ROOT / "web" / "dist"


def _positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


class LiveRequest(BaseModel):
    question_limit: int = Field(default=3, ge=3, le=5)


class SlidingWindowLimiter:
    """单进程滑动窗口；部署手册固定 Uvicorn 单 worker。"""

    def __init__(self, limit: int, window_seconds: int = 3600):
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, key: str, now: float | None = None) -> bool:
        timestamp = time.monotonic() if now is None else now
        async with self._lock:
            bucket = self._events[key]
            cutoff = timestamp - self.window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.limit:
                return False
            bucket.append(timestamp)
            return True


def _client_ip(request: Request) -> str:
    trust_proxy = os.getenv("DEMO_TRUST_PROXY", "false").lower() in {
        "1", "true", "yes", "on"
    }
    if trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if forwarded:
            return forwarded
    return request.client.host if request.client else "unknown"


async def _terminate(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=3)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()


def _sse(event: dict) -> bytes:
    payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    return f"data: {payload}\n\n".encode()


def create_app(*, live_enabled: bool | None = None, mount_static: bool = True) -> FastAPI:
    app = FastAPI(
        title="AI Market Diagnostic Demo",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
    )
    limiter = SlidingWindowLimiter(_positive_int("DEMO_RATE_LIMIT_PER_HOUR", 2))
    semaphore = asyncio.Semaphore(1)
    timeout_seconds = _positive_int("DEMO_LIVE_TIMEOUT_SECONDS", 180)

    def is_live_enabled() -> bool:
        if live_enabled is not None:
            return live_enabled
        settings = Settings()
        return bool(settings.deepseek_api_key and settings.deepseek_web_search)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.get("/api/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "replay_available": (WEB_DIST_DIR / "demo-report.json").exists(),
            "live_available": is_live_enabled(),
            "live_question_range": [3, 5],
        }

    @app.post("/api/live-diagnose/stream")
    async def live_diagnose(payload: LiveRequest, request: Request) -> StreamingResponse:
        if not is_live_enabled():
            raise HTTPException(
                status_code=503,
                detail="实况服务未配置 DeepSeek Web Search；请使用不耗额度的回放模式",
            )

        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=0.05)
        except asyncio.TimeoutError as exc:
            raise HTTPException(
                status_code=409,
                detail="已有一项实况诊断正在运行，请稍后重试或使用回放模式",
            ) from exc

        ip = _client_ip(request)
        if not await limiter.allow(ip):
            semaphore.release()
            raise HTTPException(
                status_code=429,
                detail="本 IP 本小时的 2 次实况额度已用完；回放模式仍可完整使用",
            )

        async def event_stream():  # type: ignore[no-untyped-def]
            process: asyncio.subprocess.Process | None = None
            terminal_event_seen = False
            deadline = asyncio.get_running_loop().time() + timeout_seconds
            try:
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-m",
                    "src.demo_worker",
                    "--question-limit",
                    str(payload.question_limit),
                    cwd=PROJECT_ROOT,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                assert process.stdout is not None
                while True:
                    remaining = deadline - asyncio.get_running_loop().time()
                    if remaining <= 0:
                        raise asyncio.TimeoutError
                    line = await asyncio.wait_for(process.stdout.readline(), timeout=remaining)
                    if not line:
                        break
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    terminal_event_seen = terminal_event_seen or event.get("type") in {
                        "completed", "error"
                    }
                    yield _sse(event)

                return_code = await asyncio.wait_for(
                    process.wait(),
                    timeout=max(0.01, deadline - asyncio.get_running_loop().time()),
                )
                if return_code != 0 and not terminal_event_seen:
                    yield _sse({
                        "type": "error",
                        "message": "实况子进程未完成，请返回回放模式",
                    })
            except asyncio.TimeoutError:
                if process is not None:
                    await _terminate(process)
                yield _sse({
                    "type": "error",
                    "message": f"实况诊断超过 {timeout_seconds} 秒，已安全终止",
                })
            except asyncio.CancelledError:
                if process is not None:
                    await _terminate(process)
                raise
            finally:
                if process is not None:
                    await _terminate(process)
                semaphore.release()

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-store",
                "X-Accel-Buffering": "no",
            },
        )

    if mount_static and WEB_DIST_DIR.is_dir():
        app.mount("/", StaticFiles(directory=WEB_DIST_DIR, html=True), name="demo")
    return app


app = create_app()
