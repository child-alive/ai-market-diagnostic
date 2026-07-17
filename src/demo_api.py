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
from contextlib import suppress
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


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class LiveLease:
    """全局并发 1 的实况租约（替代 asyncio.Semaphore）。

    获取/释放均为同步操作（单事件循环内原子），从根上消除
    `wait_for(semaphore.acquire())` 在客户端断开瞬间的取消竞态
    （Python 3.10 wait_for 可能丢失已获取的信号量，导致永久泄漏）。

    reconcile() 是看门狗对账：租约声称忙碌，但对应 worker 进程不存在、
    从未挂载、或超过最大生命周期时，强制释放并返回原因供调用方记录日志。
    它挂在健康接口与实况入口上——任何一次访问都会触发对账，
    因此即使出现未知的断开姿势，系统也会在有限时间内自愈，不会永久卡死。
    """

    def __init__(self, max_lifetime_seconds: float, orphan_grace_seconds: float = 15.0):
        self.max_lifetime_seconds = max_lifetime_seconds
        self.orphan_grace_seconds = orphan_grace_seconds
        self._held = False
        self._token = 0
        self._acquired_at = 0.0
        self._worker_pid: int | None = None

    def locked(self) -> bool:
        return self._held

    def try_acquire(self) -> int | None:
        """空闲时占用租约并返回持有 token；忙碌时返回 None。"""
        if self._held:
            return None
        self._token += 1
        self._held = True
        self._acquired_at = time.monotonic()
        self._worker_pid = None
        return self._token

    def attach_worker(self, token: int, pid: int) -> None:
        if self._held and token == self._token:
            self._worker_pid = pid

    def release(self, token: int) -> None:
        if self._held and token == self._token:
            self._held = False
            self._worker_pid = None

    def reconcile(self, now: float | None = None) -> str | None:
        """看门狗对账；强制释放时返回原因，无需处理时返回 None。"""
        if not self._held:
            return None
        age = (time.monotonic() if now is None else now) - self._acquired_at
        reason: str | None = None
        if age > self.max_lifetime_seconds:
            reason = (
                f"租约超过最大生命周期 {self.max_lifetime_seconds:.0f}s"
                f"（已持有 {age:.0f}s）"
            )
        elif age > self.orphan_grace_seconds and self._worker_pid is None:
            reason = f"租约持有 {age:.0f}s 仍未挂载 worker 进程"
        elif (
            age > self.orphan_grace_seconds
            and self._worker_pid is not None
            and not _pid_alive(self._worker_pid)
        ):
            reason = f"worker 进程 {self._worker_pid} 已不存在（租约已持有 {age:.0f}s）"
        if reason is None:
            return None
        self._held = False
        self._worker_pid = None
        return reason


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


async def _readline_until_disconnect(
    stream: asyncio.StreamReader,
    request: Request,
    deadline: float,
    *,
    poll_seconds: float = 0.5,
) -> bytes:
    """等待子进程输出时同时监测浏览器断开，避免停止后长时间占用全局锁。"""
    read_task = asyncio.create_task(stream.readline())
    try:
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise asyncio.TimeoutError
            done, _ = await asyncio.wait(
                {read_task}, timeout=min(poll_seconds, remaining)
            )
            if read_task in done:
                return read_task.result()
            if await request.is_disconnected():
                raise asyncio.CancelledError
    finally:
        if not read_task.done():
            read_task.cancel()
            with suppress(asyncio.CancelledError):
                await read_task


def create_app(*, live_enabled: bool | None = None, mount_static: bool = True) -> FastAPI:
    app = FastAPI(
        title="AI Market Diagnostic Demo",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
    )
    limiter = SlidingWindowLimiter(_positive_int("DEMO_RATE_LIMIT_PER_HOUR", 2))
    timeout_seconds = _positive_int("DEMO_LIVE_TIMEOUT_SECONDS", 180)
    lease = LiveLease(
        max_lifetime_seconds=timeout_seconds
        + _positive_int("DEMO_LEASE_EXTRA_LIFETIME_SECONDS", 30),
        orphan_grace_seconds=float(_positive_int("DEMO_LEASE_ORPHAN_GRACE_SECONDS", 15)),
    )
    app.state.live_lease = lease
    app.state.live_semaphore = lease  # 向后兼容旧测试/调用方的 .locked() 探测

    def _reconcile_lease() -> None:
        reason = lease.reconcile()
        if reason:
            print(f"[watchdog] 强制释放实况租约: {reason}", flush=True)

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
        _reconcile_lease()
        return {
            "status": "ok",
            "replay_available": (WEB_DIST_DIR / "demo-report.json").exists(),
            "live_available": is_live_enabled(),
            "live_busy": lease.locked(),
            "live_question_range": [3, 5],
        }

    @app.post("/api/live-diagnose/stream")
    async def live_diagnose(payload: LiveRequest, request: Request) -> StreamingResponse:
        if not is_live_enabled():
            raise HTTPException(
                status_code=503,
                detail="实况服务未配置 DeepSeek Web Search；请使用不耗额度的回放模式",
            )

        # 这里只做无状态的快速判断；真正占用租约必须在
        # event_stream 内完成，否则客户端在流开始前断开会泄漏锁。
        # 判断前先对账：幽灵租约（无 worker/超时）在此被强制回收。
        _reconcile_lease()
        if lease.locked():
            raise HTTPException(
                status_code=409,
                detail="已有一项实况诊断正在运行，请稍后重试或使用回放模式",
            )

        ip = _client_ip(request)
        if not await limiter.allow(ip):
            raise HTTPException(
                status_code=429,
                detail="本 IP 本小时的 2 次实况额度已用完；回放模式仍可完整使用",
            )

        async def event_stream():  # type: ignore[no-untyped-def]
            process: asyncio.subprocess.Process | None = None
            terminal_event_seen = False
            deadline = asyncio.get_running_loop().time() + timeout_seconds
            # 同步获取租约：单事件循环内原子完成，不经过任何 await，
            # 客户端在任意瞬间断开都不可能让"已获取"状态丢失。
            token = lease.try_acquire()
            if token is None:
                yield _sse({
                    "type": "error",
                    "message": "已有一项实况诊断正在运行，请稍后重试",
                })
                return
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
                lease.attach_worker(token, process.pid)
                assert process.stdout is not None
                while True:
                    remaining = deadline - asyncio.get_running_loop().time()
                    if remaining <= 0:
                        raise asyncio.TimeoutError
                    line = await _readline_until_disconnect(
                        process.stdout, request, deadline
                    )
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
                lease.release(token)

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
